from datetime import datetime
import json
import logging
import sys
from time import sleep
import uuid

import numpy as np
#import pnpkg_resources

from distutils.version import LooseVersion
from pandas import compat
from pandas.core.api import DataFrame
from pandas.tools.merge import concat
from pandas.core.common import PandasError

from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError

from oauth2client.client import AccessTokenRefreshError

import httplib2

# P.Chr added libs
from hurry.filesize import size, si
import time

logger = logging.getLogger('pandas.io.gbq')
logger.setLevel(logging.ERROR)

class InvalidPageToken(PandasError, IOError):
    """
    Raised when Google BigQuery fails to return,
    or returns a duplicate page token.
    """
    pass

class AccessDeniedException(PandasError, IOError):
    """
    Raised when invalid credentials are provided, or tokens have expired.
    """
    pass

class NotFoundException(PandasError, IOError):
    """
    Raised when the project_id/table provided in the query could not be found.
    """
    pass

class TermsOfServiceNotAcceptedException(PandasError, IOError):
    """
    Raised when the terms of service were not accepted or have been unaccepted.
    """
    pass

class UnknownGBQException(PandasError, IOError):
    """
    Raised when an unrecognized Google API Error occurs.
    """
    pass


class InvalidColumnOrder(PandasError, IOError):
    """
    Raised when the provided column order for output
    results DataFrame does not match the schema
    returned by BigQuery.
    """
    pass

class GbqConnector:
    def __init__(self, project_id, reauth=False):
        self.project_id     = project_id
        self.reauth         = reauth
        self.scope          = 'https://www.googleapis.com/auth/bigquery'
        self.json_key_path = '{}/.google_api_oauth2_credentials/service_accounts/{}.json'.format(os.environ['HOME'], project_id)
        self.service        = self.get_service()

    def _get_credentials(self):
        from oauth2client.client import SignedJwtAssertionCredentials

        with open(self.json_key_path) as f:
            json_key = json.load(f)

        return SignedJwtAssertionCredentials(
            json_key['client_email'],
            bytes(json_key['private_key'], 'UTF-8'),
            self.scope,
        )

    def get_service(self):
        try:
            credentials = self._get_credentials()
            http = httplib2.Http()
            http = credentials.authorize(http)
            bigquery_service = build('bigquery', 'v2', http=http)

            return bigquery_service
        except (FileNotFoundError, ValueError, KeyError, NotImplementedError):
            raise NotFoundException("There's problem with service account credentials for project: {}. Please "
                  "provide valid JSON key file to {}\n".format(self.project_id, self.json_key_path))

    def _start_timer(self):
        self.start = time.monotonic()

    def get_elapsed_seconds(self):
        return round(time.monotonic() - self.start, 2)

    def print_elapsed_seconds(self, prefix='Elapsed', postfix='s.', overlong=7):
        sec = self.get_elapsed_seconds()
        if sec > overlong:
            print('{} {} {}'.format(prefix, sec, postfix))
            sys.stdout.flush()

    def run_query(self, query):
        job_collection = self.service.jobs()
        job_data = {
            'configuration': {
                'query': {
                    'query': query
                    #'allowLargeResults', 'createDisposition', 'preserveNulls', destinationTable, useQueryCache
                }
            }
        }

        self._start_timer()
        try:
            query_reply = job_collection.insert(projectId=self.project_id,
                                           body=job_data).execute()
            status = query_reply['status']
            print('Query requested...')
            sys.stdout.flush()
        except AccessTokenRefreshError:
            raise AccessDeniedException("The credentials have been revoked or expired, please re-run"
                "the application to re-authorize")
        except HttpError as ex:
            status = json.loads(ex.content)['error']


        errors = status.get('errors', None)

        if errors:
            reasons = [error['reason'] for error in errors]
            messages = [error['message'] for error in errors]
            if 'accessDenied' in reasons:
                raise AccessDeniedException(messages)
            if 'notFound' in reasons:
                raise NotFoundException(messages)
            if 'termsOfServiceNotAccepted' in reasons:
                raise TermsOfServiceNotAcceptedException(messages)
            else:
                raise UnknownGBQException(status)

        job_reference = query_reply['jobReference']

        while(not query_reply.get('jobComplete', False)):
            self.print_elapsed_seconds('  Elapsed', 's. Waiting...')
            query_reply = job_collection.getQueryResults(
                            projectId=job_reference['projectId'],
                            jobId=job_reference['jobId'],
                        ).execute()


        bytes_processed = int(query_reply.get('totalBytesProcessed', '0'))
        if query_reply['cacheHit']:
            print('Query done.\nCached result.\nPrice: 0 $.\n')
        else:
            # Charges are rounded to the nearest MB, with a minimum 10 MB data processed per table referenced by the query.
            mbytes = max( round( bytes_processed / 1e6 ), 10) # minimal charge is 10MB
            price = round(mbytes * 5 / 1e6, 4) # 5$ per TB
            print('Query done.\nProcessed: {}.\nPrice: {} $.\n'.format(size(bytes_processed, system=si), price))

        print('Retrieving results...')

        total_rows = int(query_reply['totalRows'])
        result_pages = list()
        seen_page_tokens = list()
        current_row = 0
        #Only read schema on first page
        schema = query_reply['schema']

        # Loop through each page of data
        while('rows' in query_reply and current_row < total_rows):
            page = query_reply['rows']
            result_pages.append(page)
            current_row += len(page)

            self.print_elapsed_seconds('  Got page: {}; {}% done. Elapsed'.format(
                len(result_pages) ,
                round(100.0 * current_row / total_rows) ,
            ))

            if current_row == total_rows:
                break

            page_token = query_reply.get('pageToken', None)

            if not page_token:
                raise InvalidPageToken("Required pageToken was missing. Recieved {0} of {1} rows"
                                       .format(current_row, total_rows))
            elif page_token in seen_page_tokens:
                raise InvalidPageToken("A duplicate pageToken was returned")

            seen_page_tokens.append(page_token)

            query_reply = job_collection.getQueryResults(
                            projectId = job_reference['projectId'],
                            jobId = job_reference['jobId'],
                            pageToken = page_token,
                        ).execute()

        if (current_row < total_rows):
            raise InvalidPageToken()

        # print basic query stats
        print('Got all {} rows.'.format(total_rows))
        self.print_elapsed_seconds('Query + retrieving time taken' , 's.\n\nConstructing DataFrame...')

        return schema, result_pages

    def load_data(self, dataframe, dataset_id, table_id, chunksize, verbose):
        job_id = uuid.uuid4().hex
        rows = []
        remaining_rows = len(dataframe)

        if verbose:
            total_rows = remaining_rows
            sys.stdout.write("\n\n")
            sys.stdout.flush()

        for index, row in dataframe.reset_index(drop=True).iterrows():
            row_dict = dict()
            row_dict['json'] = json.loads(row.to_json(force_ascii = False,
                                                      date_unit = 's',
                                                      date_format = 'iso',
                                ))
            row_dict['insertId'] = job_id + str(index)
            rows.append(row_dict)
            remaining_rows -= 1

            if (len(rows) % chunksize == 0) or (remaining_rows == 0):
                if verbose:
                    sys.stdout.write("\rStreaming Insert is {0}% Complete".format(((total_rows - remaining_rows) * 100) / total_rows))
                    sys.stdout.flush()

                body = {'rows': rows}
                response = self.service.tabledata().insertAll(
                                                        projectId = self.project_id,
                                                        datasetId = dataset_id,
                                                        tableId = table_id,
                                                        body = body,
                            ).execute()
                if 'insertErrors' in response:
                    raise UnknownGBQException(response)

                sleep(1) # Maintains the inserts "per second" rate per API
                rows = []

        if verbose:
            sys.stdout.write("\n")
            sys.stdout.flush()

def _parse_data(schema, rows):
    # see: http://pandas.pydata.org/pandas-docs/dev/missing_data.html#missing-data-casting-rules-and-indexing
    dtype_map = {
                 'INTEGER': np.dtype(int),
                 'FLOAT': np.dtype(float),
                 'TIMESTAMP': 'M8[ns]', # This seems to be buggy without nanosecond indicator
                }

    fields = schema['fields']
    col_types = [field['type'] for field in fields]
    col_names = [field['name'] for field in fields]
    col_dtypes = [dtype_map.get(field['type'], object) for field in fields]
    page_array = np.zeros( shape = len(rows), dtype = list(zip(col_names, col_dtypes)) )

    for row_num, raw_row in enumerate(rows):
        entries = raw_row.get('f', [])
        for col_num, field_type in enumerate(col_types):
            field_value = _parse_entry(entries[col_num].get('v', ''), field_type)
            page_array[row_num][col_num] = field_value

    return DataFrame(page_array)

def _parse_entry(field_value, field_type):
    if field_value is None or field_value == 'null':
        return None
    if field_type == 'INTEGER':
        return int(field_value)
    elif field_type == 'FLOAT':
        return float(field_value)
    elif field_type == 'TIMESTAMP':
        timestamp = datetime.utcfromtimestamp(float(field_value))
        return np.datetime64(timestamp)
    #    return int(timestamp)
    elif field_type == 'BOOLEAN':
        return field_value == 'true'
    return field_value

def read_gbq(query, project_id = None, index_col=None, col_order=None, reauth=False):
    """Load data from Google BigQuery.

    Adapted to Python3 and upgraded by P.Chromiec for model team @ RTBHouse

    THIS IS AN EXPERIMENTAL LIBRARY

    The main method a user calls to execute a Query in Google BigQuery and read results
    into a pandas DataFrame using the v2 Google API client for Python.  Documentation for
    the API is available at https://developers.google.com/api-client-library/python/.
    Authentication to the Google BigQuery service is via OAuth 2.0 using the product name
    'pandas GBQ'.

    Parameters
    ----------
    query : str
        SQL-Like Query to return data values
    project_id : str
        Google BigQuery Account project ID.
    index_col : str (optional)
        Name of result column to use for index in results DataFrame
    col_order : list(str) (optional)
        List of BigQuery column names in the desired order for results
        DataFrame
    reauth : boolean (default False)
        Force Google BigQuery to reauthenticate the user. This is useful
        if multiple accounts are used.

    Returns
    -------
    df: DataFrame
        DataFrame representing results of query

    """

    # TODO: first check index_col and col_order with dry_run mode

    if not project_id:
        raise TypeError("Missing required parameter: project_id")

    connector = GbqConnector(project_id, reauth = reauth)
    schema, pages = connector.run_query(query)

    if not pages:
        return DataFrame()

    dataframe_list = []
    while len(pages) > 0:
        page = pages.pop()
        dataframe_list.append(_parse_data(schema, page))

    final_df = concat(dataframe_list, ignore_index = True)

    # Reindex the DataFrame on the provided column
    if index_col is not None:
        if index_col in final_df.columns:
            final_df.set_index(index_col, inplace = True)
        else:
            raise InvalidColumnOrder(
                'Index column "{0}" does not exist in DataFrame.'
                .format(index_col)
            )

    # Change the order of columns in the DataFrame based on provided list
    if col_order is not None:
        if sorted(col_order) == sorted(final_df.columns):
            final_df = final_df[col_order]
        else:
            raise InvalidColumnOrder(
                'Column order does not match this DataFrame.'
            )

    # Downcast floats to integers and objects to booleans
    # if there are no NaN's. This is presently due to a
    # limitation of numpy in handling missing data.
    final_df._data = final_df._data.downcast(dtypes='infer')

    connector.print_elapsed_seconds('Total time taken', 's.', 0)
    print( datetime.now().strftime("Finished at %Y-%m-%d %H:%M:%S.") );

    return final_df

def to_gbq(dataframe, destination_table, project_id=None, chunksize=10000,
           verbose=True, reauth=False):
    """Write a DataFrame to a Google BigQuery table.

    THIS IS AN EXPERIMENTAL LIBRARY

    If the table exists, the dataframe will be written to the table using
    the defined table schema and column types. For simplicity, this method
    uses the Google BigQuery streaming API. The to_gbq method chunks data
    into a default chunk size of 10,000. Failures return the complete error
    response which can be quite long depending on the size of the insert.
    There are several important limitations of the Google streaming API
    which are detailed at:
    https://developers.google.com/bigquery/streaming-data-into-bigquery.

    Parameters
    ----------
    dataframe : DataFrame
        DataFrame to be written
    destination_table : string
        Name of table to be written, in the form 'dataset.tablename'
    project_id : str
        Google BigQuery Account project ID.
    chunksize : int (default 10000)
        Number of rows to be inserted in each chunk from the dataframe.
    verbose : boolean (default True)
        Show percentage complete
    reauth : boolean (default False)
        Force Google BigQuery to reauthenticate the user. This is useful
        if multiple accounts are used.

    """

    if not project_id:
        raise TypeError("Missing required parameter: project_id")

    if not '.' in destination_table:
        raise NotFoundException("Invalid Table Name. Should be of the form 'datasetId.tableId' ")

    connector = GbqConnector(project_id, reauth = reauth)
    dataset_id, table_id = destination_table.rsplit('.',1)

    connector.load_data(dataframe, dataset_id, table_id, chunksize, verbose)

def generate_bq_schema(df, default_type='STRING'):
    """ Given a passed df, generate the associated big query schema.

    Parameters
    ----------
    df : DataFrame
    default_type : string
        The default big query type in case the type of the column
        does not exist in the schema.
    """

    type_mapping = {
        'i': 'INTEGER',
        'b': 'BOOLEAN',
        'f': 'FLOAT',
        'O': 'STRING',
        'S': 'STRING',
        'U': 'STRING',
        'M': 'TIMESTAMP'
    }

    fields = []
    for column_name, dtype in df.dtypes.iteritems():
        fields.append({'name': column_name,
                       'type': type_mapping.get(dtype.kind, default_type)})

    return {'fields': fields}

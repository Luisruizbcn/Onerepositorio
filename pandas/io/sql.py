"""
Collection of query wrappers / abstractions to both facilitate data
retrieval and to reduce dependency on DB-specific API.
"""
from __future__ import print_function
from datetime import datetime, date
import warnings
from pandas.compat import range, lzip, map, zip, raise_with_traceback
import pandas.compat as compat
import numpy as np


from pandas.core.api import DataFrame
from pandas.core.base import PandasObject
from pandas.tseries.tools import to_datetime


class SQLAlchemyRequired(ImportError):
    pass


class DatabaseError(IOError):
    pass


#------------------------------------------------------------------------------
# Helper execution functions

def _convert_params(sql, params):
    """convert sql and params args to DBAPI2.0 compliant format"""
    args = [sql]
    if params is not None:
        args += list(params)
    return args


def execute(sql, con, cur=None, params=None, flavor='sqlite'):
    """
    Execute the given SQL query using the provided connection object.

    Parameters
    ----------
    sql: string
        Query to be executed
    con: SQLAlchemy engine or DBAPI2 connection (legacy mode)
        Using SQLAlchemy makes it possible to use any DB supported by that
        library.
        If a DBAPI2 object is given, a supported SQL flavor must also be provided
    cur: depreciated, cursor is obtained from connection
    params: list or tuple, optional
        List of parameters to pass to execute method.
    flavor : string "sqlite", "mysql"
        Specifies the flavor of SQL to use.
        Ignored when using SQLAlchemy engine. Required when using DBAPI2 connection.
    Returns
    -------
    Results Iterable
    """
    pandas_sql = pandasSQL_builder(con, flavor=flavor)
    args = _convert_params(sql, params)
    return pandas_sql.execute(*args)


def tquery(sql, con, cur=None, params=None, flavor='sqlite'):
    """
    Returns list of tuples corresponding to each row in given sql
    query.

    If only one column selected, then plain list is returned.

    Parameters
    ----------
    sql: string
        SQL query to be executed
    con: SQLAlchemy engine or DBAPI2 connection (legacy mode)
        Using SQLAlchemy makes it possible to use any DB supported by that
        library.
        If a DBAPI2 object is given, a supported SQL flavor must also be provided
    cur: depreciated, cursor is obtained from connection
    params: list or tuple, optional
        List of parameters to pass to execute method.
    flavor : string "sqlite", "mysql"
        Specifies the flavor of SQL to use.
        Ignored when using SQLAlchemy engine. Required when using DBAPI2
        connection.
    Returns
    -------
    Results Iterable
    """
    warnings.warn(
        "tquery is depreciated, and will be removed in future versions",
        DeprecationWarning)

    pandas_sql = pandasSQL_builder(con, flavor=flavor)
    args = _convert_params(sql, params)
    return pandas_sql.tquery(*args)


def uquery(sql, con, cur=None, params=None, engine=None, flavor='sqlite'):
    """
    Does the same thing as tquery, but instead of returning results, it
    returns the number of rows affected.  Good for update queries.

    Parameters
    ----------
    sql: string
        SQL query to be executed
    con: SQLAlchemy engine or DBAPI2 connection (legacy mode)
        Using SQLAlchemy makes it possible to use any DB supported by that
        library.
        If a DBAPI2 object is given, a supported SQL flavor must also be provided
    cur: depreciated, cursor is obtained from connection
    params: list or tuple, optional
        List of parameters to pass to execute method.
    flavor : string "sqlite", "mysql"
        Specifies the flavor of SQL to use.
        Ignored when using SQLAlchemy engine. Required when using DBAPI2
        connection.
    Returns
    -------
    Number of affected rows
    """
    warnings.warn(
        "uquery is depreciated, and will be removed in future versions",
        DeprecationWarning)
    pandas_sql = pandasSQL_builder(con, flavor=flavor)
    args = _convert_params(sql, params)
    return pandas_sql.uquery(*args)


#------------------------------------------------------------------------------
# Read and write to DataFrames


def read_sql(sql, con, index_col=None, flavor='sqlite', coerce_float=True,
             params=None, parse_dates=None):
    """
    Returns a DataFrame corresponding to the result set of the query
    string.

    Optionally provide an index_col parameter to use one of the
    columns as the index, otherwise default integer index will be used

    Parameters
    ----------
    sql: string
        SQL query to be executed
    con: SQLAlchemy engine or DBAPI2 connection (legacy mode)
        Using SQLAlchemy makes it possible to use any DB supported by that
        library.
        If a DBAPI2 object is given, a supported SQL flavor must also be provided
    index_col: string, optional
        column name to use for the returned DataFrame object.
    flavor : string specifying the flavor of SQL to use. Ignored when using
        SQLAlchemy engine. Required when using DBAPI2 connection.
    coerce_float : boolean, default True
        Attempt to convert values to non-string, non-numeric objects (like
        decimal.Decimal) to floating point, useful for SQL result sets
    cur: depreciated, cursor is obtained from connection
    params: list or tuple, optional
        List of parameters to pass to execute method.
    parse_dates: list or dict
        List of column names to parse as dates
        Or
        Dict of {column_name: format string} where format string is
        strftime compatible in case of parsing string times or is one of
        (D, s, ns, ms, us) in case of parsing integer timestamps
        Or
        Dict of {column_name: arg dict}, where the arg dict corresponds
        to the keyword arguments of :func:`pandas.tseries.tools.to_datetime`
        Especially useful with databases without native Datetime support,
        such as SQLite
    Returns
    -------
    DataFrame
    """
    pandas_sql = pandasSQL_builder(con, flavor=flavor)
    return pandas_sql.read_sql(sql,
                               index_col=index_col,
                               params=params,
                               coerce_float=coerce_float,
                               parse_dates=parse_dates)


def to_sql(frame, name, con, flavor='sqlite', if_exists='fail'):
    """
    Write records stored in a DataFrame to a SQL database.

    Parameters
    ----------
    frame: DataFrame
    name: name of SQL table
    con: SQLAlchemy engine or DBAPI2 connection (legacy mode)
        Using SQLAlchemy makes it possible to use any DB supported by that
        library.
        If a DBAPI2 object is given, a supported SQL flavor must also be provided
    flavor: {'sqlite', 'mysql', 'postgres'}, default 'sqlite', ignored when using engine
    if_exists: {'fail', 'replace', 'append'}, default 'fail'
        fail: If table exists, do nothing.
        replace: If table exists, drop it, recreate it, and insert data.
        append: If table exists, insert data. Create if does not exist.
    """
    pandas_sql = pandasSQL_builder(con, flavor=flavor)
    pandas_sql.to_sql(frame, name, if_exists=if_exists)


def has_table(table_name, con, meta=None, flavor='sqlite'):
    """
    Check if DB has named table

    Parameters
    ----------
    frame: DataFrame
    name: name of SQL table
    con: SQLAlchemy engine or DBAPI2 connection (legacy mode)
        Using SQLAlchemy makes it possible to use any DB supported by that
        library.
        If a DBAPI2 object is given, a supported SQL flavor name must also be provided
    flavor: {'sqlite', 'mysql'}, default 'sqlite', ignored when using engine
    Returns
    -------
    boolean
    """
    pandas_sql = pandasSQL_builder(con, flavor=flavor)
    return pandas_sql.has_table(table_name)


def read_table(table_name, con, meta=None, index_col=None, coerce_float=True,
               parse_dates=None, columns=None):
    """Given a table name and SQLAlchemy engine, return a DataFrame.
    Type convertions will be done automatically

    Parameters
    ----------
    table_name: name of SQL table in database
    con: SQLAlchemy engine. Legacy mode not supported
    meta: SQLAlchemy meta, optional. If omitted MetaData is reflected from engine
    index_col: column to set as index, optional
    coerce_float : boolean, default True
        Attempt to convert values to non-string, non-numeric objects (like
        decimal.Decimal) to floating point. Can result in loss of Precision.
    parse_dates: list or dict
        List of column names to parse as dates
        Or
        Dict of {column_name: format string} where format string is
        strftime compatible in case of parsing string times or is one of
        (D, s, ns, ms, us) in case of parsing integer timestamps
        Or
        Dict of {column_name: arg dict}, where the arg dict corresponds
        to the keyword arguments of :func:`pandas.tseries.tools.to_datetime`
        Especially useful with databases without native Datetime support,
        such as SQLite
    columns: list
        List of column names to select from sql table
    Returns
    -------
    DataFrame
    """
    pandas_sql = PandasSQLAlchemy(con, meta=meta)
    table = pandas_sql.read_table(table_name,
                                  index_col=index_col,
                                  coerce_float=coerce_float,
                                  parse_dates=parse_dates)

    if table is not None:
        return table
    else:
        raise ValueError("Table %s not found" % table_name, con)


def pandasSQL_builder(con, flavor=None, meta=None):
    """
    Convenience function to return the correct PandasSQL subclass based on the
    provided parameters
    """
    try:
        import sqlalchemy

        if isinstance(con, sqlalchemy.engine.Engine):
            return PandasSQLAlchemy(con, meta=meta)
        else:
            warnings.warn(
                "Not an SQLAlchemy engine, attempting to use as legacy DBAPI connection")
            if flavor is None:
                raise ValueError("""PandasSQL must be created with an SQLAlchemy engine
                    or a DBAPI2 connection and SQL flavour""")
            else:
                return PandasSQLLegacy(con, flavor)

    except ImportError:
        warnings.warn("SQLAlchemy not installed, using legacy mode")
        if flavor is None:
            raise SQLAlchemyRequired
        else:
            return PandasSQLLegacy(con, flavor)


class PandasSQL(PandasObject):

    """
    Subclasses Should define read_sql and to_sql
    """

    def read_sql(self, *args, **kwargs):
        raise ValueError(
            "PandasSQL must be created with an SQLAlchemy engine or connection+sql flavor")

    def to_sql(self, *args, **kwargs):
        raise ValueError(
            "PandasSQL must be created with an SQLAlchemy engine or connection+sql flavor")

    def _create_sql_schema(self, frame, name, keys):
        raise ValueError(
            "PandasSQL must be created with an SQLAlchemy engine or connection+sql flavor")

    def _frame_from_data_and_columns(self, data, columns, index_col=None,
                                     coerce_float=True):
        df = DataFrame.from_records(
            data, columns=columns, coerce_float=coerce_float)
        if index_col is not None:
            df.set_index(index_col, inplace=True)
        return df

    def _safe_col_names(self, col_names):
        # may not be safe enough...
        return [s.replace(' ', '_').strip() for s in col_names]

    def _parse_date_columns(self, data_frame, parse_dates):
        """ Force non-datetime columns to be read as such.
            Supports both string formatted and integer timestamp columns
        """
        # handle non-list entries for parse_dates gracefully
        if parse_dates is True or parse_dates is None or parse_dates is False:
            parse_dates = []

        if not hasattr(parse_dates, '__iter__'):
            parse_dates = [parse_dates]

        for col_name in parse_dates:
            df_col = data_frame[col_name]
            try:
                fmt = parse_dates[col_name]
            except TypeError:
                fmt = None
            data_frame[col_name] = self._parse_date_col(df_col, format=fmt)

        return data_frame

    def _parse_date_col(self, col, col_type=None, format=None):
            if isinstance(format, dict):
                return to_datetime(col, **format)
            else:
                if format in ['D', 's', 'ms', 'us', 'ns']:
                    return to_datetime(col, coerce=True, unit=format)
                elif issubclass(col.dtype.type, np.floating) or issubclass(col.dtype.type, np.integer):
                    # parse dates as timestamp
                    format = 's' if format is None else format
                    return to_datetime(col, coerce=True, unit=format)
                else:
                    return to_datetime(col, coerce=True, format=format)


class PandasSQLAlchemy(PandasSQL):

    """
    This class enables convertion between DataFrame and SQL databases
    using SQLAlchemy to handle DataBase abstraction
    """

    def __init__(self, engine, meta=None):
        self.engine = engine
        if not meta:
            from sqlalchemy.schema import MetaData
            meta = MetaData(self.engine)
            meta.reflect(self.engine)

        self.meta = meta

    def execute(self, *args, **kwargs):
        """Simple passthrough to SQLAlchemy engine"""
        return self.engine.execute(*args, **kwargs)

    def tquery(self, *args, **kwargs):
        """Accepts same args as execute"""
        result = self.execute(*args, **kwargs)
        return result.fetchall()

    def uquery(self, *args, **kwargs):
        """Accepts same args as execute"""
        result = self.execute(*args, **kwargs)
        return result.rowcount

    def read_sql(self, sql, index_col=None, coerce_float=True, parse_dates=None, params=None):
        args = _convert_params(sql, params)
        result = self.execute(*args)
        data = result.fetchall()
        columns = result.keys()

        data_frame = self._frame_from_data_and_columns(data, columns,
                                                       index_col=index_col,
                                                       coerce_float=coerce_float)

        return self._parse_date_columns(data_frame, parse_dates)

    def to_sql(self, frame, name, if_exists='fail'):
        if self.engine.has_table(name):
            if if_exists == 'fail':
                raise ValueError("Table '%s' already exists." % name)
            elif if_exists == 'replace':
                # TODO: this triggers a full refresh of metadata, could
                # probably avoid this.
                self._drop_table(name)
                self._create_table(frame, name)
            elif if_exists == 'append':
                pass  # table exists and will automatically be appended to
        else:
            self._create_table(frame, name)
        self._write(frame, name)

    def _write(self, frame, table_name):
        table = self.get_table(table_name)
        ins = table.insert()

        def maybe_asscalar(i):
            try:
                return np.asscalar(i)
            except AttributeError:
                return i

        for t in frame.iterrows():
            self.engine.execute(ins, **dict((k, maybe_asscalar(v))
                                            for k, v in t[1].iteritems()))

    def has_table(self, name):
        return self.engine.has_table(name)

    def get_table(self, table_name):
        if self.engine.has_table(table_name):
            return self.meta.tables[table_name]
        else:
            return None

    def read_table(self, table_name, index_col=None, coerce_float=True,
                   parse_dates=None, columns=None):
        table = self.get_table(table_name)

        if table is not None:

            if columns is not None and len(columns) > 0:
                from sqlalchemy import select
                sql_select = select([table.c[n] for n in columns])
            else:
                sql_select = table.select()

            result = self.execute(sql_select)
            data = result.fetchall()
            columns = result.keys()

            data_frame = self._frame_from_data_and_columns(data, columns,
                                                           index_col=index_col,
                                                           coerce_float=coerce_float)

            data_frame = self._harmonize_columns(
                data_frame, table, parse_dates)
            return data_frame
        else:
            return None

    def _drop_table(self, table_name):
        if self.engine.has_table(table_name):
            self.get_table(table_name).drop()
            self.meta.clear()
            self.meta.reflect()

    def _create_table(self, frame, table_name, keys=None):
        table = self._create_sqlalchemy_table(frame, table_name, keys)
        table.create()

    def _create_sql_schema(self, frame, table_name, keys=None):
        table = self._create_sqlalchemy_table(frame, table_name, keys)
        return str(table.compile())

    def _create_sqlalchemy_table(self, frame, table_name, keys=None):
        from sqlalchemy import Table, Column
        if keys is None:
            keys = []

        safe_columns = self._safe_col_names(frame.dtypes.index)
        column_types = map(self._lookup_sql_type, frame.dtypes)

        columns = [(col_name, col_sqltype, col_name in keys)
                   for col_name, col_sqltype in zip(safe_columns, column_types)]

        columns = [Column(name, typ, primary_key=pk)
                   for name, typ, pk in columns]

        return Table(table_name, self.meta, *columns)

    def _lookup_sql_type(self, dtype):
        from sqlalchemy.types import Integer, Float, Text, Boolean, DateTime, Date

        pytype = dtype.type

        if pytype is date:
            return Date
        if issubclass(pytype, np.datetime64) or pytype is datetime:
            # Caution: np.datetime64 is also a subclass of np.number.
            return DateTime
        if issubclass(pytype, np.floating):
            return Float
        if issubclass(pytype, np.integer):
            # TODO: Refine integer size.
            return Integer
        if issubclass(pytype, np.bool_):
            return Boolean
        return Text

    def _lookup_np_type(self, sqltype):
        from sqlalchemy.types import Integer, Float, Boolean, DateTime, Date

        if isinstance(sqltype, Float):
            return float
        if isinstance(sqltype, Integer):
            # TODO: Refine integer size.
            return int
        if isinstance(sqltype, DateTime):
            # Caution: np.datetime64 is also a subclass of np.number.
            return datetime
        if isinstance(sqltype, Date):
            return date
        if isinstance(sqltype, Boolean):
            return bool
        return object

    def _harmonize_columns(self, data_frame, sql_table, parse_dates=None):
        """ Make a data_frame's column type align with an sql_table column types
            Need to work around limited NA value support.
            Floats are always fine, ints must always
            be floats if there are Null values.
            Booleans are hard because converting bool column with None replaces
            all Nones with false. Therefore only convert bool if there are no NA
            values.
            Datetimes should already be converted
            to np.datetime if supported, but here we also force conversion
            if required
        """
        for sql_col in sql_table.columns:
            col_name = sql_col.name
            try:
                df_col = data_frame[col_name]
                # the type the dataframe column should have
                col_type = self._lookup_np_type(sql_col.type)

                if col_type is datetime or col_type is date:
                    if not issubclass(df_col.dtype.type, np.datetime64):
                        data_frame[col_name] = self._parse_date_col(
                            df_col, col_type)

                elif col_type is float:
                    # floats support NA, can always convert!
                    data_frame[col_name].astype(col_type, copy=False)

                elif len(df_col) == df_col.count():
                    # No NA values, can convert ints and bools
                    if col_type is int or col_type is bool:
                        data_frame[col_name].astype(col_type, copy=False)
            except KeyError:
                pass  # this column not in results

        data_frame = self._parse_date_columns(data_frame, parse_dates)

        return data_frame


# ---- SQL without SQLAlchemy ---
# Flavour specific sql strings and handler class for access to DBs without
# SQLAlchemy installed
# SQL type convertions for each DB
_SQL_TYPES = {
    'text': {
        'mysql': 'VARCHAR (63)',
        'sqlite': 'TEXT',
    },
    'float': {
        'mysql': 'FLOAT',
        'sqlite': 'REAL',
    },
    'int': {
        'mysql': 'BIGINT',
        'sqlite': 'INTEGER',
    },
    'datetime': {
        'mysql': 'DATETIME',
        'sqlite': 'TIMESTAMP',
    },
    'date': {
        'mysql': 'DATE',
        'sqlite': 'TIMESTAMP',
    },
    'bool': {
        'mysql': 'BOOLEAN',
        'sqlite': 'INTEGER',
    }
}

# SQL enquote and wildcard symbols
_SQL_SYMB = {
    'mysql': {
        'br_l': '`',
        'br_r': '`',
        'wld': '%s'
    },
    'sqlite': {
        'br_l': '[',
        'br_r': ']',
        'wld': '?'
    }
}


class PandasSQLLegacy(PandasSQL):

    def __init__(self, con, flavor):
        self.con = con
        if flavor not in ['sqlite', 'mysql']:
            raise NotImplementedError
        else:
            self.flavor = flavor

    def execute(self, *args, **kwargs):
        try:
            cur = self.con.cursor()
            if kwargs:
                cur.execute(*args, **kwargs)
            else:
                cur.execute(*args)
            return cur
        except Exception as e:
            try:
                self.con.rollback()
            except Exception:  # pragma: no cover
                ex = DatabaseError(
                    "Execution failed on sql: %s\n%s\nunable to rollback" % (args[0], e))
                raise_with_traceback(ex)

            ex = DatabaseError("Execution failed on sql: %s" % args[0])
            raise_with_traceback(ex)

    def tquery(self, *args):
        cur = self.execute(*args)
        result = self._fetchall_as_list(cur)

        # This makes into tuples
        if result and len(result[0]) == 1:
            # python 3 compat
            result = list(lzip(*result)[0])
        elif result is None:  # pragma: no cover
            result = []
        return result

    def uquery(self, *args):
        """
        Does the same thing as tquery, but instead of returning results, it
        returns the number of rows affected.  Good for update queries.
        """
        cur = self.execute(*args)
        return cur.rowcount

    def read_sql(self, sql, index_col=None, coerce_float=True, params=None,
                 parse_dates=None):
        args = _convert_params(sql, params)
        cursor = self.execute(*args)
        columns = [col_desc[0] for col_desc in cursor.description]
        data = self._fetchall_as_list(cursor)
        cursor.close()

        data_frame = self._frame_from_data_and_columns(data, columns,
                                                       index_col=index_col,
                                                       coerce_float=coerce_float)
        return self._parse_date_columns(data_frame, parse_dates=parse_dates)

    def to_sql(self, frame, name, if_exists='fail'):
        """
        Write records stored in a DataFrame to a SQL database.

        Parameters
        ----------
        frame: DataFrame
        name: name of SQL table
        flavor: {'sqlite', 'mysql', 'postgres'}, default 'sqlite'
        if_exists: {'fail', 'replace', 'append'}, default 'fail'
            fail: If table exists, do nothing.
            replace: If table exists, drop it, recreate it, and insert data.
            append: If table exists, insert data. Create if does not exist.
        """
        if self.has_table(name):
            if if_exists == 'fail':
                raise ValueError("Table '%s' already exists." % name)
            elif if_exists == 'replace':
                self._drop_table(name)
                self._create_table(frame, name)
            elif if_exists == "append":
                pass  # should just add...
        else:
            self._create_table(frame, name)

        self._write(frame, name)

    def _fetchall_as_list(self, cur):
        '''ensures result of fetchall is a list'''
        result = cur.fetchall()
        if not isinstance(result, list):
            result = list(result)
        return result

    def _write(self, frame, table_name):
        # Replace spaces in DataFrame column names with _.
        safe_names = self._safe_col_names(frame.columns)

        br_l = _SQL_SYMB[self.flavor]['br_l']  # left val quote char
        br_r = _SQL_SYMB[self.flavor]['br_r']  # right val quote char
        wld = _SQL_SYMB[self.flavor]['wld']  # wildcard char

        bracketed_names = [br_l + column + br_r for column in safe_names]
        col_names = ','.join(bracketed_names)
        wildcards = ','.join([wld] * len(safe_names))
        insert_query = 'INSERT INTO %s (%s) VALUES (%s)' % (
            table_name, col_names, wildcards)

        # pandas types are badly handled if there is only 1 col (Issue #3628)
        if len(frame.columns) != 1:
            data = [tuple(x) for x in frame.values]
        else:
            data = [tuple(x) for x in frame.values.tolist()]

        cur = self.con.cursor()
        cur.executemany(insert_query, data)
        cur.close()

    def _create_table(self, frame, name, keys=None):
        create_sql = self._create_sql_schema(frame, name, keys)
        self.execute(create_sql)

    def has_table(self, name):
        flavor_map = {
            'sqlite': ("SELECT name FROM sqlite_master "
                       "WHERE type='table' AND name='%s';") % name,
            'mysql': "SHOW TABLES LIKE '%s'" % name}
        query = flavor_map.get(self.flavor)
        if query is None:
            raise NotImplementedError
        return len(self.tquery(query)) > 0

    def _drop_table(self, name):
        # Previously this worried about connection tp cursor then closing...
        drop_sql = "DROP TABLE %s" % name
        self.execute(drop_sql)

    def _create_sql_schema(self, frame, table_name, keys=None):
        "Return a CREATE TABLE statement to suit the contents of a DataFrame."

        lookup_type = lambda dtype: self._get_sqltype(dtype.type)
        # Replace spaces in DataFrame column names with _.
        safe_columns = self._safe_col_names(frame.dtypes.index)

        column_types = lzip(safe_columns, map(lookup_type, frame.dtypes))

        br_l = _SQL_SYMB[self.flavor]['br_l']  # left val quote char
        br_r = _SQL_SYMB[self.flavor]['br_r']  # right val quote char
        col_template = br_l + '%s' + br_r + ' %s'
        columns = ',\n  '.join(col_template % x for x in column_types)

        keystr = ''
        if keys is not None:
            if isinstance(keys, compat.string_types):
                keys = (keys,)
            keystr = ', PRIMARY KEY (%s)' % ','.join(keys)
        template = """CREATE TABLE %(name)s (
                      %(columns)s
                      %(keystr)s
                      );"""
        create_statement = template % {'name': table_name, 'columns': columns,
                                       'keystr': keystr}
        return create_statement

    def _get_sqltype(self, pytype):
        pytype_name = "text"
        if issubclass(pytype, np.floating):
            pytype_name = "float"
        elif issubclass(pytype, np.integer):
            pytype_name = "int"
        elif issubclass(pytype, np.datetime64) or pytype is datetime:
            # Caution: np.datetime64 is also a subclass of np.number.
            pytype_name = "datetime"
        elif pytype is datetime.date:
            pytype_name = "date"
        elif issubclass(pytype, np.bool_):
            pytype_name = "bool"

        return _SQL_TYPES[pytype_name][self.flavor]


# legacy names, with depreciation warnings and copied docs
def get_schema(frame, name, con, flavor='sqlite'):
    """
    Get the SQL db table schema for the given frame

    Parameters
    ----------
    frame: DataFrame
    name: name of SQL table
    con: an open SQL database connection object
    engine: an SQLAlchemy engine - replaces connection and flavor
    flavor: {'sqlite', 'mysql', 'postgres'}, default 'sqlite'

    """
    warnings.warn(
        "get_schema is depreciated", DeprecationWarning)
    pandas_sql = pandasSQL_builder(con=con, flavor=flavor)
    return pandas_sql._create_sql_schema(frame, name)


def read_frame(*args, **kwargs):
    """DEPRECIATED - use read_sql
    """
    warnings.warn(
        "read_frame is depreciated, use read_sql", DeprecationWarning)
    return read_sql(*args, **kwargs)


def write_frame(*args, **kwargs):
    """DEPRECIATED - use to_sql
    """
    warnings.warn("write_frame is depreciated, use to_sql", DeprecationWarning)
    return to_sql(*args, **kwargs)


# Append wrapped function docstrings
read_frame.__doc__ += read_sql.__doc__
write_frame.__doc__ += to_sql.__doc__

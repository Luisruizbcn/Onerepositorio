from functools import partial
from importlib import reload
from io import BytesIO, StringIO
import os
import re
import threading

import numpy as np
from numpy.random import rand
import pytest

from pandas.compat import is_platform_windows
from pandas.errors import ParserError
import pandas.util._test_decorators as td

from pandas import (
    DataFrame, Index, MultiIndex, Series, Timestamp, date_range, read_csv)
import pandas.util.testing as tm
from pandas.util.testing import makeCustomDataframe as mkdf, network

from pandas.io.common import URLError, file_path_to_url
import pandas.io.html
from pandas.io.html import read_html

HERE = os.path.dirname(__file__)


@pytest.fixture(params=[
    'chinese_utf-16.html',
    'chinese_utf-32.html',
    'chinese_utf-8.html',
    'letz_latin1.html',
])
def html_encoding_file(request, datapath):
    """Parametrized fixture for HTML encoding test filenames."""
    return datapath('io', 'data', 'html_encoding', request.param)


def assert_framelist_equal(list1, list2, *args, **kwargs):
    assert len(list1) == len(list2), ('lists are not of equal size '
                                      'len(list1) == {0}, '
                                      'len(list2) == {1}'.format(len(list1),
                                                                 len(list2)))
    msg = 'not all list elements are DataFrames'
    both_frames = all(map(lambda x, y: isinstance(x, DataFrame) and
                          isinstance(y, DataFrame), list1, list2))
    assert both_frames, msg
    for frame_i, frame_j in zip(list1, list2):
        tm.assert_frame_equal(frame_i, frame_j, *args, **kwargs)
        assert not frame_i.empty, 'frames are both empty'


@td.skip_if_no('bs4')
def test_bs4_version_fails(monkeypatch, datapath):
    import bs4
    monkeypatch.setattr(bs4, '__version__', '4.2')
    with pytest.raises(ValueError, match="minimum version"):
        read_html(datapath("io", "data", "spam.html"), flavor='bs4')


def test_invalid_flavor():
    url = "google.com"
    flavor = "invalid flavor"
    msg = r"\{" + flavor + r"\} is not a valid set of flavors"

    with pytest.raises(ValueError, match=msg):
        read_html(url, "google", flavor=flavor)


@td.skip_if_no('bs4')
@td.skip_if_no('lxml')
def test_same_ordering(datapath):
    filename = datapath('io', 'data', 'valid_markup.html')
    dfs_lxml = read_html(filename, index_col=0, flavor=['lxml'])
    dfs_bs4 = read_html(filename, index_col=0, flavor=['bs4'])
    assert_framelist_equal(dfs_lxml, dfs_bs4)


@pytest.mark.parametrize("flavor", [
    pytest.param('bs4', marks=pytest.mark.skipif(
        not td.safe_import('lxml'), reason='No bs4')),
    pytest.param('lxml', marks=pytest.mark.skipif(
        not td.safe_import('lxml'), reason='No lxml'))], scope="class")
class TestReadHtml:

    @pytest.fixture(autouse=True)
    def set_files(self, datapath):
        self.spam_data = datapath('io', 'data', 'spam.html')
        self.spam_data_kwargs = {}
        self.spam_data_kwargs['encoding'] = 'UTF-8'
        self.banklist_data = datapath("io", "data", "banklist.html")

    @pytest.fixture(autouse=True, scope="function")
    def set_defaults(self, flavor, request):
        self.read_html = partial(read_html, flavor=flavor)
        yield

    def test_to_html_compat(self):
        df = mkdf(4, 3, data_gen_f=lambda *args: rand(), c_idx_names=False,
                  r_idx_names=False).applymap('{0:.3f}'.format).astype(float)
        out = df.to_html()
        res = self.read_html(out, attrs={'class': 'dataframe'}, index_col=0)[0]
        tm.assert_frame_equal(res, df)

    @network
    def test_banklist_url(self):
        url = 'http://www.fdic.gov/bank/individual/failed/banklist.html'
        df1 = self.read_html(url, 'First Federal Bank of Florida',
                             attrs={"id": 'table'})
        df2 = self.read_html(url, 'Metcalf Bank', attrs={'id': 'table'})

        assert_framelist_equal(df1, df2)

    @network
    def test_spam_url(self):
        url = ('http://ndb.nal.usda.gov/ndb/foods/show/300772?fg=&man=&'
               'lfacet=&format=&count=&max=25&offset=&sort=&qlookup=spam')
        df1 = self.read_html(url, '.*Water.*')
        df2 = self.read_html(url, 'Unit')

        assert_framelist_equal(df1, df2)

    @pytest.mark.slow
    def test_banklist(self):
        df1 = self.read_html(self.banklist_data, '.*Florida.*',
                             attrs={'id': 'table'})
        df2 = self.read_html(self.banklist_data, 'Metcalf Bank',
                             attrs={'id': 'table'})

        assert_framelist_equal(df1, df2)

    def test_spam(self):
        df1 = self.read_html(self.spam_data, '.*Water.*')
        df2 = self.read_html(self.spam_data, 'Unit')
        assert_framelist_equal(df1, df2)

        assert df1[0].iloc[0, 0] == 'Proximates'
        assert df1[0].columns[0] == 'Nutrient'

    def test_spam_no_match(self):
        dfs = self.read_html(self.spam_data)
        for df in dfs:
            assert isinstance(df, DataFrame)

    def test_banklist_no_match(self):
        dfs = self.read_html(self.banklist_data, attrs={'id': 'table'})
        for df in dfs:
            assert isinstance(df, DataFrame)

    def test_spam_header(self):
        df = self.read_html(self.spam_data, '.*Water.*', header=2)[0]
        assert df.columns[0] == 'Proximates'
        assert not df.empty

    def test_skiprows_int(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', skiprows=1)
        df2 = self.read_html(self.spam_data, 'Unit', skiprows=1)

        assert_framelist_equal(df1, df2)

    def test_skiprows_xrange(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', skiprows=range(2))[0]
        df2 = self.read_html(self.spam_data, 'Unit', skiprows=range(2))[0]
        tm.assert_frame_equal(df1, df2)

    def test_skiprows_list(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', skiprows=[1, 2])
        df2 = self.read_html(self.spam_data, 'Unit', skiprows=[2, 1])

        assert_framelist_equal(df1, df2)

    def test_skiprows_set(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', skiprows={1, 2})
        df2 = self.read_html(self.spam_data, 'Unit', skiprows={2, 1})

        assert_framelist_equal(df1, df2)

    def test_skiprows_slice(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', skiprows=1)
        df2 = self.read_html(self.spam_data, 'Unit', skiprows=1)

        assert_framelist_equal(df1, df2)

    def test_skiprows_slice_short(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', skiprows=slice(2))
        df2 = self.read_html(self.spam_data, 'Unit', skiprows=slice(2))

        assert_framelist_equal(df1, df2)

    def test_skiprows_slice_long(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', skiprows=slice(2, 5))
        df2 = self.read_html(self.spam_data, 'Unit', skiprows=slice(4, 1, -1))

        assert_framelist_equal(df1, df2)

    def test_skiprows_ndarray(self):
        df1 = self.read_html(self.spam_data, '.*Water.*',
                             skiprows=np.arange(2))
        df2 = self.read_html(self.spam_data, 'Unit', skiprows=np.arange(2))

        assert_framelist_equal(df1, df2)

    def test_skiprows_invalid(self):
        with pytest.raises(TypeError, match=('is not a valid type '
                                             'for skipping rows')):
            self.read_html(self.spam_data, '.*Water.*', skiprows='asdf')

    def test_index(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', index_col=0)
        df2 = self.read_html(self.spam_data, 'Unit', index_col=0)
        assert_framelist_equal(df1, df2)

    def test_header_and_index_no_types(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', header=1,
                             index_col=0)
        df2 = self.read_html(self.spam_data, 'Unit', header=1, index_col=0)
        assert_framelist_equal(df1, df2)

    def test_header_and_index_with_types(self):
        df1 = self.read_html(self.spam_data, '.*Water.*', header=1,
                             index_col=0)
        df2 = self.read_html(self.spam_data, 'Unit', header=1, index_col=0)
        assert_framelist_equal(df1, df2)

    def test_infer_types(self):

        # 10892 infer_types removed
        df1 = self.read_html(self.spam_data, '.*Water.*', index_col=0)
        df2 = self.read_html(self.spam_data, 'Unit', index_col=0)
        assert_framelist_equal(df1, df2)

    def test_string_io(self):
        with open(self.spam_data, **self.spam_data_kwargs) as f:
            data1 = StringIO(f.read())

        with open(self.spam_data, **self.spam_data_kwargs) as f:
            data2 = StringIO(f.read())

        df1 = self.read_html(data1, '.*Water.*')
        df2 = self.read_html(data2, 'Unit')
        assert_framelist_equal(df1, df2)

    def test_string(self):
        with open(self.spam_data, **self.spam_data_kwargs) as f:
            data = f.read()

        df1 = self.read_html(data, '.*Water.*')
        df2 = self.read_html(data, 'Unit')

        assert_framelist_equal(df1, df2)

    def test_file_like(self):
        with open(self.spam_data, **self.spam_data_kwargs) as f:
            df1 = self.read_html(f, '.*Water.*')

        with open(self.spam_data, **self.spam_data_kwargs) as f:
            df2 = self.read_html(f, 'Unit')

        assert_framelist_equal(df1, df2)

    @network
    def test_bad_url_protocol(self):
        with pytest.raises(URLError):
            self.read_html('git://github.com', match='.*Water.*')

    @network
    def test_invalid_url(self):
        try:
            with pytest.raises(URLError):
                self.read_html('http://www.a23950sdfa908sd.com',
                               match='.*Water.*')
        except ValueError as e:
            assert 'No tables found' in str(e)

    @pytest.mark.slow
    def test_file_url(self):
        url = self.banklist_data
        dfs = self.read_html(file_path_to_url(os.path.abspath(url)),
                             'First',
                             attrs={'id': 'table'})
        assert isinstance(dfs, list)
        for df in dfs:
            assert isinstance(df, DataFrame)

    @pytest.mark.slow
    def test_invalid_table_attrs(self):
        url = self.banklist_data
        with pytest.raises(ValueError, match='No tables found'):
            self.read_html(url, 'First Federal Bank of Florida',
                           attrs={'id': 'tasdfable'})

    def _bank_data(self, *args, **kwargs):
        return self.read_html(self.banklist_data, 'Metcalf',
                              attrs={'id': 'table'}, *args, **kwargs)

    @pytest.mark.slow
    def test_multiindex_header(self):
        df = self._bank_data(header=[0, 1])[0]
        assert isinstance(df.columns, MultiIndex)

    @pytest.mark.slow
    def test_multiindex_index(self):
        df = self._bank_data(index_col=[0, 1])[0]
        assert isinstance(df.index, MultiIndex)

    @pytest.mark.slow
    def test_multiindex_header_index(self):
        df = self._bank_data(header=[0, 1], index_col=[0, 1])[0]
        assert isinstance(df.columns, MultiIndex)
        assert isinstance(df.index, MultiIndex)

    @pytest.mark.slow
    def test_multiindex_header_skiprows_tuples(self):
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            df = self._bank_data(header=[0, 1], skiprows=1,
                                 tupleize_cols=True)[0]
            assert isinstance(df.columns, Index)

    @pytest.mark.slow
    def test_multiindex_header_skiprows(self):
        df = self._bank_data(header=[0, 1], skiprows=1)[0]
        assert isinstance(df.columns, MultiIndex)

    @pytest.mark.slow
    def test_multiindex_header_index_skiprows(self):
        df = self._bank_data(header=[0, 1], index_col=[0, 1], skiprows=1)[0]
        assert isinstance(df.index, MultiIndex)
        assert isinstance(df.columns, MultiIndex)

    @pytest.mark.slow
    def test_regex_idempotency(self):
        url = self.banklist_data
        dfs = self.read_html(file_path_to_url(os.path.abspath(url)),
                             match=re.compile(re.compile('Florida')),
                             attrs={'id': 'table'})
        assert isinstance(dfs, list)
        for df in dfs:
            assert isinstance(df, DataFrame)

    def test_negative_skiprows(self):
        msg = r'\(you passed a negative value\)'
        with pytest.raises(ValueError, match=msg):
            self.read_html(self.spam_data, 'Water', skiprows=-1)

    @network
    def test_multiple_matches(self):
        url = 'https://docs.python.org/2/'
        dfs = self.read_html(url, match='Python')
        assert len(dfs) > 1

    @network
    def test_python_docs_table(self):
        url = 'https://docs.python.org/2/'
        dfs = self.read_html(url, match='Python')
        zz = [df.iloc[0, 0][0:4] for df in dfs]
        assert sorted(zz) == sorted(['Repo', 'What'])

    @pytest.mark.slow
    def test_thousands_macau_stats(self, datapath):
        all_non_nan_table_index = -2
        macau_data = datapath("io", "data", "macau.html")
        dfs = self.read_html(macau_data, index_col=0,
                             attrs={'class': 'style1'})
        df = dfs[all_non_nan_table_index]

        assert not any(s.isna().any() for _, s in df.iteritems())

    @pytest.mark.slow
    def test_thousands_macau_index_col(self, datapath):
        all_non_nan_table_index = -2
        macau_data = datapath('io', 'data', 'macau.html')
        dfs = self.read_html(macau_data, index_col=0, header=0)
        df = dfs[all_non_nan_table_index]

        assert not any(s.isna().any() for _, s in df.iteritems())

    def test_empty_tables(self):
        """
        Make sure that read_html ignores empty tables.
        """
        result = self.read_html('''
            <table>
                <thead>
                    <tr>
                        <th>A</th>
                        <th>B</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>1</td>
                        <td>2</td>
                    </tr>
                </tbody>
            </table>
            <table>
                <tbody>
                </tbody>
            </table>
        ''')

        assert len(result) == 1

    def test_multiple_tbody(self):
        # GH-20690
        # Read all tbody tags within a single table.
        result = self.read_html('''<table>
            <thead>
                <tr>
                    <th>A</th>
                    <th>B</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>1</td>
                    <td>2</td>
                </tr>
            </tbody>
            <tbody>
                <tr>
                    <td>3</td>
                    <td>4</td>
                </tr>
            </tbody>
        </table>''')[0]

        expected = DataFrame(data=[[1, 2], [3, 4]], columns=['A', 'B'])

        tm.assert_frame_equal(result, expected)

    def test_header_and_one_column(self):
        """
        Don't fail with bs4 when there is a header and only one column
        as described in issue #9178
        """
        result = self.read_html('''<table>
                <thead>
                    <tr>
                        <th>Header</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>first</td>
                    </tr>
                </tbody>
            </table>''')[0]

        expected = DataFrame(data={'Header': 'first'}, index=[0])

        tm.assert_frame_equal(result, expected)

    def test_thead_without_tr(self):
        """
        Ensure parser adds <tr> within <thead> on malformed HTML.
        """
        result = self.read_html('''<table>
            <thead>
                <tr>
                    <th>Country</th>
                    <th>Municipality</th>
                    <th>Year</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Ukraine</td>
                    <th>Odessa</th>
                    <td>1944</td>
                </tr>
            </tbody>
        </table>''')[0]

        expected = DataFrame(data=[['Ukraine', 'Odessa', 1944]],
                             columns=['Country', 'Municipality', 'Year'])

        tm.assert_frame_equal(result, expected)

    def test_tfoot_read(self):
        """
        Make sure that read_html reads tfoot, containing td or th.
        Ignores empty tfoot
        """
        data_template = '''<table>
            <thead>
                <tr>
                    <th>A</th>
                    <th>B</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>bodyA</td>
                    <td>bodyB</td>
                </tr>
            </tbody>
            <tfoot>
                {footer}
            </tfoot>
        </table>'''

        expected1 = DataFrame(data=[['bodyA', 'bodyB']], columns=['A', 'B'])

        expected2 = DataFrame(data=[['bodyA', 'bodyB'], ['footA', 'footB']],
                              columns=['A', 'B'])

        data1 = data_template.format(footer="")
        data2 = data_template.format(
            footer="<tr><td>footA</td><th>footB</th></tr>")

        result1 = self.read_html(data1)[0]
        result2 = self.read_html(data2)[0]

        tm.assert_frame_equal(result1, expected1)
        tm.assert_frame_equal(result2, expected2)

    def test_parse_header_of_non_string_column(self):
        # GH5048: if header is specified explicitly, an int column should be
        # parsed as int while its header is parsed as str
        result = self.read_html('''
            <table>
                <tr>
                    <td>S</td>
                    <td>I</td>
                </tr>
                <tr>
                    <td>text</td>
                    <td>1944</td>
                </tr>
            </table>
        ''', header=0)[0]

        expected = DataFrame([['text', 1944]], columns=('S', 'I'))

        tm.assert_frame_equal(result, expected)

    def test_nyse_wsj_commas_table(self, datapath):
        data = datapath('io', 'data', 'nyse_wsj.html')
        df = self.read_html(data, index_col=0, header=0,
                            attrs={'class': 'mdcTable'})[0]

        expected = Index(['Issue(Roll over for charts and headlines)',
                          'Volume', 'Price', 'Chg', '% Chg'])
        nrows = 100
        assert df.shape[0] == nrows
        tm.assert_index_equal(df.columns, expected)

    @pytest.mark.slow
    def test_banklist_header(self, datapath):
        from pandas.io.html import _remove_whitespace

        def try_remove_ws(x):
            try:
                return _remove_whitespace(x)
            except AttributeError:
                return x

        df = self.read_html(self.banklist_data, 'Metcalf',
                            attrs={'id': 'table'})[0]
        ground_truth = read_csv(datapath('io', 'data', 'banklist.csv'),
                                converters={'Updated Date': Timestamp,
                                            'Closing Date': Timestamp})
        assert df.shape == ground_truth.shape
        old = ['First Vietnamese American BankIn Vietnamese',
               'Westernbank Puerto RicoEn Espanol',
               'R-G Premier Bank of Puerto RicoEn Espanol',
               'EurobankEn Espanol', 'Sanderson State BankEn Espanol',
               'Washington Mutual Bank(Including its subsidiary Washington '
               'Mutual Bank FSB)',
               'Silver State BankEn Espanol',
               'AmTrade International BankEn Espanol',
               'Hamilton Bank, NAEn Espanol',
               'The Citizens Savings BankPioneer Community Bank, Inc.']
        new = ['First Vietnamese American Bank', 'Westernbank Puerto Rico',
               'R-G Premier Bank of Puerto Rico', 'Eurobank',
               'Sanderson State Bank', 'Washington Mutual Bank',
               'Silver State Bank', 'AmTrade International Bank',
               'Hamilton Bank, NA', 'The Citizens Savings Bank']
        dfnew = df.applymap(try_remove_ws).replace(old, new)
        gtnew = ground_truth.applymap(try_remove_ws)
        converted = dfnew._convert(datetime=True, numeric=True)
        date_cols = ['Closing Date', 'Updated Date']
        converted[date_cols] = converted[date_cols]._convert(datetime=True,
                                                             coerce=True)
        tm.assert_frame_equal(converted, gtnew)

    @pytest.mark.slow
    def test_gold_canyon(self):
        gc = 'Gold Canyon'
        with open(self.banklist_data, 'r') as f:
            raw_text = f.read()

        assert gc in raw_text
        df = self.read_html(self.banklist_data, 'Gold Canyon',
                            attrs={'id': 'table'})[0]
        assert gc in df.to_string()

    def test_different_number_of_cols(self):
        expected = self.read_html("""<table>
                        <thead>
                            <tr style="text-align: right;">
                            <th></th>
                            <th>C_l0_g0</th>
                            <th>C_l0_g1</th>
                            <th>C_l0_g2</th>
                            <th>C_l0_g3</th>
                            <th>C_l0_g4</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                            <th>R_l0_g0</th>
                            <td> 0.763</td>
                            <td> 0.233</td>
                            <td> nan</td>
                            <td> nan</td>
                            <td> nan</td>
                            </tr>
                            <tr>
                            <th>R_l0_g1</th>
                            <td> 0.244</td>
                            <td> 0.285</td>
                            <td> 0.392</td>
                            <td> 0.137</td>
                            <td> 0.222</td>
                            </tr>
                        </tbody>
                    </table>""", index_col=0)[0]

        result = self.read_html("""<table>
                    <thead>
                        <tr style="text-align: right;">
                        <th></th>
                        <th>C_l0_g0</th>
                        <th>C_l0_g1</th>
                        <th>C_l0_g2</th>
                        <th>C_l0_g3</th>
                        <th>C_l0_g4</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                        <th>R_l0_g0</th>
                        <td> 0.763</td>
                        <td> 0.233</td>
                        </tr>
                        <tr>
                        <th>R_l0_g1</th>
                        <td> 0.244</td>
                        <td> 0.285</td>
                        <td> 0.392</td>
                        <td> 0.137</td>
                        <td> 0.222</td>
                        </tr>
                    </tbody>
                 </table>""", index_col=0)[0]

        tm.assert_frame_equal(result, expected)

    def test_colspan_rowspan_1(self):
        # GH17054
        result = self.read_html("""
            <table>
                <tr>
                    <th>A</th>
                    <th colspan="1">B</th>
                    <th rowspan="1">C</th>
                </tr>
                <tr>
                    <td>a</td>
                    <td>b</td>
                    <td>c</td>
                </tr>
            </table>
        """)[0]

        expected = DataFrame([['a', 'b', 'c']], columns=['A', 'B', 'C'])

        tm.assert_frame_equal(result, expected)

    def test_colspan_rowspan_copy_values(self):
        # GH17054

        # In ASCII, with lowercase letters being copies:
        #
        # X x Y Z W
        # A B b z C

        result = self.read_html("""
            <table>
                <tr>
                    <td colspan="2">X</td>
                    <td>Y</td>
                    <td rowspan="2">Z</td>
                    <td>W</td>
                </tr>
                <tr>
                    <td>A</td>
                    <td colspan="2">B</td>
                    <td>C</td>
                </tr>
            </table>
        """, header=0)[0]

        expected = DataFrame(data=[['A', 'B', 'B', 'Z', 'C']],
                             columns=['X', 'X.1', 'Y', 'Z', 'W'])

        tm.assert_frame_equal(result, expected)

    def test_colspan_rowspan_both_not_1(self):
        # GH17054

        # In ASCII, with lowercase letters being copies:
        #
        # A B b b C
        # a b b b D

        result = self.read_html("""
            <table>
                <tr>
                    <td rowspan="2">A</td>
                    <td rowspan="2" colspan="3">B</td>
                    <td>C</td>
                </tr>
                <tr>
                    <td>D</td>
                </tr>
            </table>
        """, header=0)[0]

        expected = DataFrame(data=[['A', 'B', 'B', 'B', 'D']],
                             columns=['A', 'B', 'B.1', 'B.2', 'C'])

        tm.assert_frame_equal(result, expected)

    def test_rowspan_at_end_of_row(self):
        # GH17054

        # In ASCII, with lowercase letters being copies:
        #
        # A B
        # C b

        result = self.read_html("""
            <table>
                <tr>
                    <td>A</td>
                    <td rowspan="2">B</td>
                </tr>
                <tr>
                    <td>C</td>
                </tr>
            </table>
        """, header=0)[0]

        expected = DataFrame(data=[['C', 'B']], columns=['A', 'B'])

        tm.assert_frame_equal(result, expected)

    def test_rowspan_only_rows(self):
        # GH17054

        result = self.read_html("""
            <table>
                <tr>
                    <td rowspan="3">A</td>
                    <td rowspan="3">B</td>
                </tr>
            </table>
        """, header=0)[0]

        expected = DataFrame(data=[['A', 'B'], ['A', 'B']],
                             columns=['A', 'B'])

        tm.assert_frame_equal(result, expected)

    def test_header_inferred_from_rows_with_only_th(self):
        # GH17054
        result = self.read_html("""
            <table>
                <tr>
                    <th>A</th>
                    <th>B</th>
                </tr>
                <tr>
                    <th>a</th>
                    <th>b</th>
                </tr>
                <tr>
                    <td>1</td>
                    <td>2</td>
                </tr>
            </table>
        """)[0]

        columns = MultiIndex(levels=[['A', 'B'], ['a', 'b']],
                             codes=[[0, 1], [0, 1]])
        expected = DataFrame(data=[[1, 2]], columns=columns)

        tm.assert_frame_equal(result, expected)

    def test_parse_dates_list(self):
        df = DataFrame({'date': date_range('1/1/2001', periods=10)})
        expected = df.to_html()
        res = self.read_html(expected, parse_dates=[1], index_col=0)
        tm.assert_frame_equal(df, res[0])
        res = self.read_html(expected, parse_dates=['date'], index_col=0)
        tm.assert_frame_equal(df, res[0])

    def test_parse_dates_combine(self):
        raw_dates = Series(date_range('1/1/2001', periods=10))
        df = DataFrame({'date': raw_dates.map(lambda x: str(x.date())),
                        'time': raw_dates.map(lambda x: str(x.time()))})
        res = self.read_html(df.to_html(), parse_dates={'datetime': [1, 2]},
                             index_col=1)
        newdf = DataFrame({'datetime': raw_dates})
        tm.assert_frame_equal(newdf, res[0])

    def test_computer_sales_page(self, datapath):
        data = datapath('io', 'data', 'computer_sales_page.html')
        msg = (r"Passed header=\[0,1\] are too many "
               r"rows for this multi_index of columns")
        with pytest.raises(ParserError, match=msg):
            self.read_html(data, header=[0, 1])

        data = datapath('io', 'data', 'computer_sales_page.html')
        assert self.read_html(data, header=[1, 2])

    def test_wikipedia_states_table(self, datapath):
        data = datapath('io', 'data', 'wikipedia_states.html')
        assert os.path.isfile(data), '%r is not a file' % data
        assert os.path.getsize(data), '%r is an empty file' % data
        result = self.read_html(data, 'Arizona', header=1)[0]
        assert result['sq mi'].dtype == np.dtype('float64')

    def test_parser_error_on_empty_header_row(self):
        msg = (r"Passed header=\[0,1\] are too many "
               r"rows for this multi_index of columns")
        with pytest.raises(ParserError, match=msg):
            self.read_html("""
                <table>
                    <thead>
                        <tr><th></th><th></tr>
                        <tr><th>A</th><th>B</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>a</td><td>b</td></tr>
                    </tbody>
                </table>
            """, header=[0, 1])

    def test_decimal_rows(self):
        # GH 12907
        result = self.read_html('''<html>
            <body>
             <table>
                <thead>
                    <tr>
                        <th>Header</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>1100#101</td>
                    </tr>
                </tbody>
            </table>
            </body>
        </html>''', decimal='#')[0]

        expected = DataFrame(data={'Header': 1100.101}, index=[0])

        assert result['Header'].dtype == np.dtype('float64')
        tm.assert_frame_equal(result, expected)

    def test_bool_header_arg(self):
        # GH 6114
        for arg in [True, False]:
            with pytest.raises(TypeError):
                self.read_html(self.spam_data, header=arg)

    def test_converters(self):
        # GH 13461
        result = self.read_html(
            """<table>
                 <thead>
                   <tr>
                     <th>a</th>
                    </tr>
                 </thead>
                 <tbody>
                   <tr>
                     <td> 0.763</td>
                   </tr>
                   <tr>
                     <td> 0.244</td>
                   </tr>
                 </tbody>
               </table>""",
            converters={'a': str}
        )[0]

        expected = DataFrame({'a': ['0.763', '0.244']})

        tm.assert_frame_equal(result, expected)

    def test_na_values(self):
        # GH 13461
        result = self.read_html(
            """<table>
                 <thead>
                   <tr>
                     <th>a</th>
                   </tr>
                 </thead>
                 <tbody>
                   <tr>
                     <td> 0.763</td>
                   </tr>
                   <tr>
                     <td> 0.244</td>
                   </tr>
                 </tbody>
               </table>""",
            na_values=[0.244])[0]

        expected = DataFrame({'a': [0.763, np.nan]})

        tm.assert_frame_equal(result, expected)

    def test_keep_default_na(self):
        html_data = """<table>
                        <thead>
                            <tr>
                            <th>a</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                            <td> N/A</td>
                            </tr>
                            <tr>
                            <td> NA</td>
                            </tr>
                        </tbody>
                    </table>"""

        expected_df = DataFrame({'a': ['N/A', 'NA']})
        html_df = self.read_html(html_data, keep_default_na=False)[0]
        tm.assert_frame_equal(expected_df, html_df)

        expected_df = DataFrame({'a': [np.nan, np.nan]})
        html_df = self.read_html(html_data, keep_default_na=True)[0]
        tm.assert_frame_equal(expected_df, html_df)

    def test_preserve_empty_rows(self):
        result = self.read_html("""
            <table>
                <tr>
                    <th>A</th>
                    <th>B</th>
                </tr>
                <tr>
                    <td>a</td>
                    <td>b</td>
                </tr>
                <tr>
                    <td></td>
                    <td></td>
                </tr>
            </table>
        """)[0]

        expected = DataFrame(data=[['a', 'b'], [np.nan, np.nan]],
                             columns=['A', 'B'])

        tm.assert_frame_equal(result, expected)

    def test_ignore_empty_rows_when_inferring_header(self):
        result = self.read_html("""
            <table>
                <thead>
                    <tr><th></th><th></tr>
                    <tr><th>A</th><th>B</th></tr>
                    <tr><th>a</th><th>b</th></tr>
                </thead>
                <tbody>
                    <tr><td>1</td><td>2</td></tr>
                </tbody>
            </table>
        """)[0]

        columns = MultiIndex(levels=[['A', 'B'], ['a', 'b']],
                             codes=[[0, 1], [0, 1]])
        expected = DataFrame(data=[[1, 2]], columns=columns)

        tm.assert_frame_equal(result, expected)

    def test_multiple_header_rows(self):
        # Issue #13434
        expected_df = DataFrame(data=[("Hillary", 68, "D"),
                                      ("Bernie", 74, "D"),
                                      ("Donald", 69, "R")])
        expected_df.columns = [["Unnamed: 0_level_0", "Age", "Party"],
                               ["Name", "Unnamed: 1_level_1",
                                "Unnamed: 2_level_1"]]
        html = expected_df.to_html(index=False)
        html_df = self.read_html(html, )[0]
        tm.assert_frame_equal(expected_df, html_df)

    def test_works_on_valid_markup(self, datapath):
        filename = datapath('io', 'data', 'valid_markup.html')
        dfs = self.read_html(filename, index_col=0)
        assert isinstance(dfs, list)
        assert isinstance(dfs[0], DataFrame)

    @pytest.mark.slow
    def test_fallback_success(self, datapath):
        banklist_data = datapath('io', 'data', 'banklist.html')
        self.read_html(banklist_data, '.*Water.*', flavor=['lxml', 'html5lib'])

    def test_to_html_timestamp(self):
        rng = date_range('2000-01-01', periods=10)
        df = DataFrame(np.random.randn(10, 4), index=rng)

        result = df.to_html()
        assert '2000-01-01' in result

    @pytest.mark.parametrize("displayed_only,exp0,exp1", [
        (True, DataFrame(["foo"]), None),
        (False, DataFrame(["foo  bar  baz  qux"]), DataFrame(["foo"]))])
    def test_displayed_only(self, displayed_only, exp0, exp1):
        # GH 20027
        data = StringIO("""<html>
          <body>
            <table>
              <tr>
                <td>
                  foo
                  <span style="display:none;text-align:center">bar</span>
                  <span style="display:none">baz</span>
                  <span style="display: none">qux</span>
                </td>
              </tr>
            </table>
            <table style="display: none">
              <tr>
                <td>foo</td>
              </tr>
            </table>
          </body>
        </html>""")

        dfs = self.read_html(data, displayed_only=displayed_only)
        tm.assert_frame_equal(dfs[0], exp0)

        if exp1 is not None:
            tm.assert_frame_equal(dfs[1], exp1)
        else:
            assert len(dfs) == 1  # Should not parse hidden table

    def test_encode(self, html_encoding_file):
        _, encoding = os.path.splitext(
            os.path.basename(html_encoding_file)
        )[0].split('_')

        try:
            with open(html_encoding_file, 'rb') as fobj:
                from_string = self.read_html(fobj.read(), encoding=encoding,
                                             index_col=0).pop()

            with open(html_encoding_file, 'rb') as fobj:
                from_file_like = self.read_html(BytesIO(fobj.read()),
                                                encoding=encoding,
                                                index_col=0).pop()

            from_filename = self.read_html(html_encoding_file,
                                           encoding=encoding,
                                           index_col=0).pop()
            tm.assert_frame_equal(from_string, from_file_like)
            tm.assert_frame_equal(from_string, from_filename)
        except Exception:
            # seems utf-16/32 fail on windows
            if is_platform_windows():
                if '16' in encoding or '32' in encoding:
                    pytest.skip()
                raise

    def test_parse_failure_unseekable(self):
        # Issue #17975

        if self.read_html.keywords.get('flavor') == 'lxml':
            pytest.skip("Not applicable for lxml")

        class UnseekableStringIO(StringIO):
            def seekable(self):
                return False

        bad = UnseekableStringIO('''
            <table><tr><td>spam<foobr />eggs</td></tr></table>''')

        assert self.read_html(bad)

        with pytest.raises(ValueError,
                           match='passed a non-rewindable file object'):
            self.read_html(bad)

    def test_parse_failure_rewinds(self):
        # Issue #17975

        class MockFile:
            def __init__(self, data):
                self.data = data
                self.at_end = False

            def read(self, size=None):
                data = '' if self.at_end else self.data
                self.at_end = True
                return data

            def seek(self, offset):
                self.at_end = False

            def seekable(self):
                return True

        good = MockFile('<table><tr><td>spam<br />eggs</td></tr></table>')
        bad = MockFile('<table><tr><td>spam<foobr />eggs</td></tr></table>')

        assert self.read_html(good)
        assert self.read_html(bad)

    @pytest.mark.slow
    def test_importcheck_thread_safety(self, datapath):
        # see gh-16928

        class ErrorThread(threading.Thread):
            def run(self):
                try:
                    super().run()
                except Exception as e:
                    self.err = e
                else:
                    self.err = None

        # force import check by reinitalising global vars in html.py
        reload(pandas.io.html)

        filename = datapath('io', 'data', 'valid_markup.html')
        helper_thread1 = ErrorThread(target=self.read_html, args=(filename,))
        helper_thread2 = ErrorThread(target=self.read_html, args=(filename,))

        helper_thread1.start()
        helper_thread2.start()

        while helper_thread1.is_alive() or helper_thread2.is_alive():
            pass
        assert None is helper_thread1.err is helper_thread2.err

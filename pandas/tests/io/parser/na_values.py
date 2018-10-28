# -*- coding: utf-8 -*-

"""
Tests that NA values are properly handled during
parsing for all of the parsers defined in parsers.py
"""

import numpy as np
import pytest
from numpy import nan

import pandas.io.common as com
import pandas.util.testing as tm
from pandas import DataFrame, Index, MultiIndex
from pandas.compat import StringIO, range


class NAvaluesTests(object):

    def test_string_nas(self):
        data = """A,B,C
a,b,c
d,,f
,g,h
"""
        result = self.read_csv(StringIO(data))
        expected = DataFrame([['a', 'b', 'c'],
                              ['d', np.nan, 'f'],
                              [np.nan, 'g', 'h']],
                             columns=['A', 'B', 'C'])

        tm.assert_frame_equal(result, expected)

    def test_detect_string_na(self):
        data = """A,B
foo,bar
NA,baz
NaN,nan
"""
        expected = np.array([['foo', 'bar'], [nan, 'baz'], [nan, nan]],
                            dtype=np.object_)
        df = self.read_csv(StringIO(data))
        tm.assert_numpy_array_equal(df.values, expected)

    def test_non_string_na_values(self):
        # see gh-3611: with an odd float format, we can't match
        # the string '999.0' exactly but still need float matching
        nice = """A,B
-999,1.2
2,-999
3,4.5
"""
        ugly = """A,B
-999,1.200
2,-999.000
3,4.500
"""
        na_values_param = [['-999.0', '-999'],
                           [-999, -999.0],
                           [-999.0, -999],
                           ['-999.0'], ['-999'],
                           [-999.0], [-999]]
        expected = DataFrame([[np.nan, 1.2], [2.0, np.nan],
                              [3.0, 4.5]], columns=['A', 'B'])

        for data in (nice, ugly):
            for na_values in na_values_param:
                out = self.read_csv(StringIO(data), na_values=na_values)
                tm.assert_frame_equal(out, expected)

    def test_default_na_values(self):
        _NA_VALUES = {'-1.#IND', '1.#QNAN', '1.#IND', '-1.#QNAN', '#N/A',
                      'N/A', 'n/a', 'NA', '#NA', 'NULL', 'null', 'NaN', 'nan',
                      '-NaN', '-nan', '#N/A N/A', ''}
        assert _NA_VALUES == com._NA_VALUES
        nv = len(_NA_VALUES)

        def f(i, v):
            if i == 0:
                buf = ''
            elif i > 0:
                buf = ''.join([','] * i)

            buf = "{0}{1}".format(buf, v)

            if i < nv - 1:
                buf = "{0}{1}".format(buf, ''.join([','] * (nv - i - 1)))

            return buf

        data = StringIO('\n'.join(f(i, v) for i, v in enumerate(_NA_VALUES)))
        expected = DataFrame(np.nan, columns=range(nv), index=range(nv))
        df = self.read_csv(data, header=None)
        tm.assert_frame_equal(df, expected)

    def test_custom_na_values(self):
        data = """A,B,C
ignore,this,row
1,NA,3
-1.#IND,5,baz
7,8,NaN
"""
        expected = np.array([[1., nan, 3],
                             [nan, 5, nan],
                             [7, 8, nan]])

        df = self.read_csv(StringIO(data), na_values=['baz'], skiprows=[1])
        tm.assert_numpy_array_equal(df.values, expected)

        df2 = self.read_table(StringIO(data), sep=',', na_values=['baz'],
                              skiprows=[1])
        tm.assert_numpy_array_equal(df2.values, expected)

        df3 = self.read_table(StringIO(data), sep=',', na_values='baz',
                              skiprows=[1])
        tm.assert_numpy_array_equal(df3.values, expected)

    def test_bool_na_values(self):
        data = """A,B,C
True,False,True
NA,True,False
False,NA,True"""

        result = self.read_csv(StringIO(data))
        expected = DataFrame({'A': np.array([True, nan, False], dtype=object),
                              'B': np.array([False, True, nan], dtype=object),
                              'C': [True, False, True]})

        tm.assert_frame_equal(result, expected)

    def test_na_value_dict(self):
        data = """A,B,C
foo,bar,NA
bar,foo,foo
foo,bar,NA
bar,foo,foo"""

        df = self.read_csv(StringIO(data),
                           na_values={'A': ['foo'], 'B': ['bar']})
        expected = DataFrame({'A': [np.nan, 'bar', np.nan, 'bar'],
                              'B': [np.nan, 'foo', np.nan, 'foo'],
                              'C': [np.nan, 'foo', np.nan, 'foo']})
        tm.assert_frame_equal(df, expected)

        data = """\
a,b,c,d
0,NA,1,5
"""
        xp = DataFrame({'b': [np.nan], 'c': [1], 'd': [5]}, index=[0])
        xp.index.name = 'a'
        df = self.read_csv(StringIO(data), na_values={}, index_col=0)
        tm.assert_frame_equal(df, xp)

        xp = DataFrame({'b': [np.nan], 'd': [5]},
                       MultiIndex.from_tuples([(0, 1)]))
        xp.index.names = ['a', 'c']
        df = self.read_csv(StringIO(data), na_values={}, index_col=[0, 2])
        tm.assert_frame_equal(df, xp)

        xp = DataFrame({'b': [np.nan], 'd': [5]},
                       MultiIndex.from_tuples([(0, 1)]))
        xp.index.names = ['a', 'c']
        df = self.read_csv(StringIO(data), na_values={}, index_col=['a', 'c'])
        tm.assert_frame_equal(df, xp)

    def test_na_values_keep_default(self):
        data = """\
One,Two,Three
a,1,one
b,2,two
,3,three
d,4,nan
e,5,five
nan,6,
g,7,seven
"""
        df = self.read_csv(StringIO(data))
        xp = DataFrame({'One': ['a', 'b', np.nan, 'd', 'e', np.nan, 'g'],
                        'Two': [1, 2, 3, 4, 5, 6, 7],
                        'Three': ['one', 'two', 'three', np.nan, 'five',
                                  np.nan, 'seven']})
        tm.assert_frame_equal(xp.reindex(columns=df.columns), df)

        df = self.read_csv(StringIO(data), na_values={'One': [], 'Three': []},
                           keep_default_na=False)
        xp = DataFrame({'One': ['a', 'b', '', 'd', 'e', 'nan', 'g'],
                        'Two': [1, 2, 3, 4, 5, 6, 7],
                        'Three': ['one', 'two', 'three', 'nan', 'five',
                                  '', 'seven']})
        tm.assert_frame_equal(xp.reindex(columns=df.columns), df)

        df = self.read_csv(
            StringIO(data), na_values=['a'], keep_default_na=False)
        xp = DataFrame({'One': [np.nan, 'b', '', 'd', 'e', 'nan', 'g'],
                        'Two': [1, 2, 3, 4, 5, 6, 7],
                        'Three': ['one', 'two', 'three', 'nan', 'five', '',
                                  'seven']})
        tm.assert_frame_equal(xp.reindex(columns=df.columns), df)

        df = self.read_csv(StringIO(data), na_values={'One': [], 'Three': []})
        xp = DataFrame({'One': ['a', 'b', np.nan, 'd', 'e', np.nan, 'g'],
                        'Two': [1, 2, 3, 4, 5, 6, 7],
                        'Three': ['one', 'two', 'three', np.nan, 'five',
                                  np.nan, 'seven']})
        tm.assert_frame_equal(xp.reindex(columns=df.columns), df)

        # see gh-4318: passing na_values=None and
        # keep_default_na=False yields 'None' as a na_value
        data = """\
One,Two,Three
a,1,None
b,2,two
,3,None
d,4,nan
e,5,five
nan,6,
g,7,seven
"""
        df = self.read_csv(
            StringIO(data), keep_default_na=False)
        xp = DataFrame({'One': ['a', 'b', '', 'd', 'e', 'nan', 'g'],
                        'Two': [1, 2, 3, 4, 5, 6, 7],
                        'Three': ['None', 'two', 'None', 'nan', 'five', '',
                                  'seven']})
        tm.assert_frame_equal(xp.reindex(columns=df.columns), df)

    def test_no_keep_default_na_dict_na_values(self):
        # see gh-19227
        data = "a,b\n,2"

        df = self.read_csv(StringIO(data), na_values={"b": ["2"]},
                           keep_default_na=False)
        expected = DataFrame({"a": [""], "b": [np.nan]})
        tm.assert_frame_equal(df, expected)

        # Scalar values shouldn't cause the parsing to crash or fail.
        data = "a,b\n1,2"

        df = self.read_csv(StringIO(data), na_values={"b": 2},
                           keep_default_na=False)
        expected = DataFrame({"a": [1], "b": [np.nan]})
        tm.assert_frame_equal(df, expected)

        data = """\
113125,"blah","/blaha",kjsdkj,412.166,225.874,214.008
729639,"qwer","",asdfkj,466.681,,252.373
"""
        expected = DataFrame({0: [np.nan, 729639.0],
                              1: [np.nan, "qwer"],
                              2: ["/blaha", np.nan],
                              3: ["kjsdkj", "asdfkj"],
                              4: [412.166, 466.681],
                              5: ["225.874", ""],
                              6: [np.nan, 252.373]})

        df = self.read_csv(StringIO(data), header=None, keep_default_na=False,
                           na_values={2: "", 6: "214.008",
                                      1: "blah", 0: 113125})
        tm.assert_frame_equal(df, expected)

        df = self.read_csv(StringIO(data), header=None, keep_default_na=False,
                           na_values={2: "", 6: "214.008",
                                      1: "blah", 0: "113125"})
        tm.assert_frame_equal(df, expected)

    def test_na_values_na_filter_override(self):
        data = """\
A,B
1,A
nan,B
3,C
"""

        expected = DataFrame([[1, 'A'], [np.nan, np.nan], [3, 'C']],
                             columns=['A', 'B'])
        out = self.read_csv(StringIO(data), na_values=['B'], na_filter=True)
        tm.assert_frame_equal(out, expected)

        expected = DataFrame([['1', 'A'], ['nan', 'B'], ['3', 'C']],
                             columns=['A', 'B'])
        out = self.read_csv(StringIO(data), na_values=['B'], na_filter=False)
        tm.assert_frame_equal(out, expected)

    def test_na_trailing_columns(self):
        data = """Date,Currenncy,Symbol,Type,Units,UnitPrice,Cost,Tax
2012-03-14,USD,AAPL,BUY,1000
2012-05-12,USD,SBUX,SELL,500"""

        result = self.read_csv(StringIO(data))
        assert result['Date'][1] == '2012-05-12'
        assert result['UnitPrice'].isna().all()

    def test_na_values_scalar(self):
        # see gh-12224
        names = ['a', 'b']
        data = '1,2\n2,1'

        expected = DataFrame([[np.nan, 2.0], [2.0, np.nan]],
                             columns=names)
        out = self.read_csv(StringIO(data), names=names, na_values=1)
        tm.assert_frame_equal(out, expected)

        expected = DataFrame([[1.0, 2.0], [np.nan, np.nan]],
                             columns=names)
        out = self.read_csv(StringIO(data), names=names,
                            na_values={'a': 2, 'b': 1})
        tm.assert_frame_equal(out, expected)

    def test_na_values_dict_aliasing(self):
        na_values = {'a': 2, 'b': 1}
        na_values_copy = na_values.copy()

        names = ['a', 'b']
        data = '1,2\n2,1'

        expected = DataFrame([[1.0, 2.0], [np.nan, np.nan]], columns=names)
        out = self.read_csv(StringIO(data), names=names, na_values=na_values)

        tm.assert_frame_equal(out, expected)
        tm.assert_dict_equal(na_values, na_values_copy)

    def test_na_values_dict_col_index(self):
        # see gh-14203

        data = 'a\nfoo\n1'
        na_values = {0: 'foo'}

        out = self.read_csv(StringIO(data), na_values=na_values)
        expected = DataFrame({'a': [np.nan, 1]})
        tm.assert_frame_equal(out, expected)

    def test_na_values_uint64(self):
        # see gh-14983

        na_values = [2**63]
        data = str(2**63) + '\n' + str(2**63 + 1)
        expected = DataFrame([str(2**63), str(2**63 + 1)])
        out = self.read_csv(StringIO(data), header=None, na_values=na_values)
        tm.assert_frame_equal(out, expected)

        data = str(2**63) + ',1' + '\n,2'
        expected = DataFrame([[str(2**63), 1], ['', 2]])
        out = self.read_csv(StringIO(data), header=None)
        tm.assert_frame_equal(out, expected)

    def test_empty_na_values_no_default_with_index(self):
        # see gh-15835
        data = "a,1\nb,2"

        expected = DataFrame({'1': [2]}, index=Index(["b"], name="a"))
        out = self.read_csv(StringIO(data), keep_default_na=False, index_col=0)

        tm.assert_frame_equal(out, expected)

    def test_no_na_filter_on_index(self):
        # see gh-5239
        data = "a,b,c\n1,,3\n4,5,6"

        # Don't parse NA-values in index when na_filter=False.
        out = self.read_csv(StringIO(data), index_col=[1], na_filter=False)

        expected = DataFrame({"a": [1, 4], "c": [3, 6]},
                             index=Index(["", "5"], name="b"))
        tm.assert_frame_equal(out, expected)

        # Parse NA-values in index when na_filter=True.
        out = self.read_csv(StringIO(data), index_col=[1], na_filter=True)

        expected = DataFrame({"a": [1, 4], "c": [3, 6]},
                             index=Index([np.nan, 5.0], name="b"))
        tm.assert_frame_equal(out, expected)

    def test_inf_na_values_with_int_index(self):
        # see gh-17128
        data = "idx,col1,col2\n1,3,4\n2,inf,-inf"

        # Don't fail with OverflowError with infs and integer index column
        out = self.read_csv(StringIO(data), index_col=[0],
                            na_values=['inf', '-inf'])
        expected = DataFrame({"col1": [3, np.nan], "col2": [4, np.nan]},
                             index=Index([1, 2], name="idx"))
        tm.assert_frame_equal(out, expected)

    @pytest.mark.parametrize("na_filter", [True, False])
    def test_na_values_with_dtype_str_and_na_filter(self, na_filter):
        # see gh-20377
        data = "a,b,c\n1,,3\n4,5,6"

        # na_filter=True --> missing value becomes NaN.
        # na_filter=False --> missing value remains empty string.
        empty = np.nan if na_filter else ""
        expected = DataFrame({"a": ["1", "4"],
                              "b": [empty, "5"],
                              "c": ["3", "6"]})

        result = self.read_csv(StringIO(data), na_filter=na_filter, dtype=str)
        tm.assert_frame_equal(result, expected)

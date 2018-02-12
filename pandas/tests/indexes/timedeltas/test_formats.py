# -*- coding: utf-8 -*-

import pandas as pd
from pandas import TimedeltaIndex


class TestTimedeltaIndexRendering(object):
    def test_representation(self):
        idx1 = TimedeltaIndex([], freq='D')
        idx2 = TimedeltaIndex(['1 days'], freq='D')
        idx3 = TimedeltaIndex(['1 days', '2 days'], freq='D')
        idx4 = TimedeltaIndex(['1 days', '2 days', '3 days'], freq='D')
        idx5 = TimedeltaIndex(['1 days 00:00:01', '2 days', '3 days'])

        exp1 = """TimedeltaIndex([], dtype='timedelta64[ns]', freq='D')"""

        exp2 = ("TimedeltaIndex(['1 days'], dtype='timedelta64[ns]', "
                "freq='D')")

        exp3 = ("TimedeltaIndex(['1 days', '2 days'], "
                "dtype='timedelta64[ns]', freq='D')")

        exp4 = ("TimedeltaIndex(['1 days', '2 days', '3 days'], "
                "dtype='timedelta64[ns]', freq='D')")

        exp5 = ("TimedeltaIndex(['1 days 00:00:01', '2 days 00:00:00', "
                "'3 days 00:00:00'], dtype='timedelta64[ns]', freq=None)")

        with pd.option_context('display.width', 300):
            for idx, expected in zip([idx1, idx2, idx3, idx4, idx5],
                                     [exp1, exp2, exp3, exp4, exp5]):
                for func in ['__repr__', '__unicode__', '__str__']:
                    result = getattr(idx, func)()
                    assert result == expected

    def test_representation_to_series(self):
        idx1 = TimedeltaIndex([], freq='D')
        idx2 = TimedeltaIndex(['1 days'], freq='D')
        idx3 = TimedeltaIndex(['1 days', '2 days'], freq='D')
        idx4 = TimedeltaIndex(['1 days', '2 days', '3 days'], freq='D')
        idx5 = TimedeltaIndex(['1 days 00:00:01', '2 days', '3 days'])

        exp1 = """Series([], dtype: timedelta64[ns])"""

        exp2 = """0   1 days
dtype: timedelta64[ns]"""

        exp3 = """0   1 days
1   2 days
dtype: timedelta64[ns]"""

        exp4 = """0   1 days
1   2 days
2   3 days
dtype: timedelta64[ns]"""

        exp5 = """0   1 days 00:00:01
1   2 days 00:00:00
2   3 days 00:00:00
dtype: timedelta64[ns]"""

        with pd.option_context('display.width', 300):
            for idx, expected in zip([idx1, idx2, idx3, idx4, idx5],
                                     [exp1, exp2, exp3, exp4, exp5]):
                result = repr(pd.Series(idx))
                assert result == expected

    def test_summary(self):
        # GH#9116
        idx1 = TimedeltaIndex([], freq='D')
        idx2 = TimedeltaIndex(['1 days'], freq='D')
        idx3 = TimedeltaIndex(['1 days', '2 days'], freq='D')
        idx4 = TimedeltaIndex(['1 days', '2 days', '3 days'], freq='D')
        idx5 = TimedeltaIndex(['1 days 00:00:01', '2 days', '3 days'])

        exp1 = ("TimedeltaIndex: 0 entries\n"
                "Freq: D")

        exp2 = ("TimedeltaIndex: 1 entries, 1 days to 1 days\n"
                "Freq: D")

        exp3 = ("TimedeltaIndex: 2 entries, 1 days to 2 days\n"
                "Freq: D")

        exp4 = ("TimedeltaIndex: 3 entries, 1 days to 3 days\n"
                "Freq: D")

        exp5 = ("TimedeltaIndex: 3 entries, 1 days 00:00:01 to 3 days "
                "00:00:00")

        for idx, expected in zip([idx1, idx2, idx3, idx4, idx5],
                                 [exp1, exp2, exp3, exp4, exp5]):
            result = idx.summary()
            assert result == expected

from datetime import (
    datetime,
    time,
)

import numpy as np
import pytest

from pandas._libs.tslibs import timezones
import pandas.util._test_decorators as td

from pandas import (
    DataFrame,
    Series,
    date_range,
)
import pandas._testing as tm


class TestBetweenTime:
    @td.skip_if_has_locale
    def test_between_time_formats(self, frame_or_series):
        # GH#11818
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        ts = DataFrame(np.random.randn(len(rng), 2), index=rng)
        if frame_or_series is Series:
            ts = ts[0]

        strings = [
            ("2:00", "2:30"),
            ("0200", "0230"),
            ("2:00am", "2:30am"),
            ("0200am", "0230am"),
            ("2:00:00", "2:30:00"),
            ("020000", "023000"),
            ("2:00:00am", "2:30:00am"),
            ("020000am", "023000am"),
        ]
        expected_length = 28

        for time_string in strings:
            assert len(ts.between_time(*time_string)) == expected_length

    @pytest.mark.parametrize("tzstr", ["US/Eastern", "dateutil/US/Eastern"])
    def test_localized_between_time(self, tzstr, frame_or_series):
        tz = timezones.maybe_get_tz(tzstr)

        rng = date_range("4/16/2012", "5/1/2012", freq="H")
        ts = Series(np.random.randn(len(rng)), index=rng)
        if frame_or_series is DataFrame:
            ts = ts.to_frame()

        ts_local = ts.tz_localize(tzstr)

        t1, t2 = time(10, 0), time(11, 0)
        result = ts_local.between_time(t1, t2)
        expected = ts.between_time(t1, t2).tz_localize(tzstr)
        tm.assert_equal(result, expected)
        assert timezones.tz_compare(result.index.tz, tz)

    def test_between_time_types(self, frame_or_series):
        # GH11818
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        obj = DataFrame({"A": 0}, index=rng)
        if frame_or_series is Series:
            obj = obj["A"]

        msg = r"Cannot convert arg \[datetime\.datetime\(2010, 1, 2, 1, 0\)\] to a time"
        with pytest.raises(ValueError, match=msg):
            obj.between_time(datetime(2010, 1, 2, 1), datetime(2010, 1, 2, 5))

    @pytest.mark.parametrize("inclusive", ["both", "neither", "left", "right"])
    def test_between_time(self, inclusive, frame_or_series):
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        ts = DataFrame(np.random.randn(len(rng), 2), index=rng)
        if frame_or_series is not DataFrame:
            ts = ts[0]

        stime = time(0, 0)
        etime = time(1, 0)

        filtered = ts.between_time(stime, etime, inclusive=inclusive)
        exp_len = 13 * 4 + 1

        if inclusive in ["right", "neither"]:
            exp_len -= 5
        if inclusive in ["left", "neither"]:
            exp_len -= 4

        assert len(filtered) == exp_len
        for rs in filtered.index:
            t = rs.time()
            if inclusive in ["left", "both"]:
                assert t >= stime
            else:
                assert t > stime

            if inclusive in ["right", "both"]:
                assert t <= etime
            else:
                assert t < etime

        result = ts.between_time("00:00", "01:00")
        expected = ts.between_time(stime, etime)
        tm.assert_equal(result, expected)

        # across midnight
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        ts = DataFrame(np.random.randn(len(rng), 2), index=rng)
        if frame_or_series is not DataFrame:
            ts = ts[0]
        stime = time(22, 0)
        etime = time(9, 0)

        filtered = ts.between_time(stime, etime, inclusive=inclusive)
        exp_len = (12 * 11 + 1) * 4 + 1
        if inclusive in ["right", "neither"]:
            exp_len -= 4
        if inclusive in ["left", "neither"]:
            exp_len -= 4

        assert len(filtered) == exp_len
        for rs in filtered.index:
            t = rs.time()
            if inclusive in ["left", "both"]:
                assert (t >= stime) or (t <= etime)
            else:
                assert (t > stime) or (t <= etime)

            if inclusive in ["right", "both"]:
                assert (t <= etime) or (t >= stime)
            else:
                assert (t < etime) or (t >= stime)

    def test_between_time_raises(self, frame_or_series):
        # GH#20725
        obj = DataFrame([[1, 2, 3], [4, 5, 6]])
        if frame_or_series is not DataFrame:
            obj = obj[0]

        msg = "Index must be DatetimeIndex"
        with pytest.raises(TypeError, match=msg):  # index is not a DatetimeIndex
            obj.between_time(start_time="00:00", end_time="12:00")

    def test_between_time_axis(self, frame_or_series):
        # GH#8839
        rng = date_range("1/1/2000", periods=100, freq="10min")
        ts = Series(np.random.randn(len(rng)), index=rng)
        if frame_or_series is DataFrame:
            ts = ts.to_frame()

        stime, etime = ("08:00:00", "09:00:00")
        expected_length = 7

        assert len(ts.between_time(stime, etime)) == expected_length
        assert len(ts.between_time(stime, etime, axis=0)) == expected_length
        msg = f"No axis named {ts.ndim} for object type {type(ts).__name__}"
        with pytest.raises(ValueError, match=msg):
            ts.between_time(stime, etime, axis=ts.ndim)

    def test_between_time_axis_aliases(self, axis):
        # GH#8839
        rng = date_range("1/1/2000", periods=100, freq="10min")
        ts = DataFrame(np.random.randn(len(rng), len(rng)))
        stime, etime = ("08:00:00", "09:00:00")
        exp_len = 7

        if axis in ["index", 0]:
            ts.index = rng
            assert len(ts.between_time(stime, etime)) == exp_len
            assert len(ts.between_time(stime, etime, axis=0)) == exp_len

        if axis in ["columns", 1]:
            ts.columns = rng
            selected = ts.between_time(stime, etime, axis=1).columns
            assert len(selected) == exp_len

    def test_between_time_axis_raises(self, axis):
        # issue 8839
        rng = date_range("1/1/2000", periods=100, freq="10min")
        mask = np.arange(0, len(rng))
        rand_data = np.random.randn(len(rng), len(rng))
        ts = DataFrame(rand_data, index=rng, columns=rng)
        stime, etime = ("08:00:00", "09:00:00")

        msg = "Index must be DatetimeIndex"
        if axis in ["columns", 1]:
            ts.index = mask
            with pytest.raises(TypeError, match=msg):
                ts.between_time(stime, etime)
            with pytest.raises(TypeError, match=msg):
                ts.between_time(stime, etime, axis=0)

        if axis in ["index", 0]:
            ts.columns = mask
            with pytest.raises(TypeError, match=msg):
                ts.between_time(stime, etime, axis=1)

    def test_between_time_datetimeindex(self):
        index = date_range("2012-01-01", "2012-01-05", freq="30min")
        df = DataFrame(np.random.randn(len(index), 5), index=index)
        bkey = slice(time(13, 0, 0), time(14, 0, 0))
        binds = [26, 27, 28, 74, 75, 76, 122, 123, 124, 170, 171, 172]

        result = df.between_time(bkey.start, bkey.stop)
        expected = df.loc[bkey]
        expected2 = df.iloc[binds]
        tm.assert_frame_equal(result, expected)
        tm.assert_frame_equal(result, expected2)
        assert len(result) == 12

    # GH40245
    @pytest.mark.parametrize("inc_start", (True, False))
    @pytest.mark.parametrize("inc_end", (True, False))
    def test_between_time_warn(self, inc_start, inc_end, frame_or_series):
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        ts = DataFrame(np.random.randn(len(rng), 2), index=rng)
        if frame_or_series is not DataFrame:
            ts = ts[0]

        stime = time(0, 0)
        etime = time(1, 0)

        match = (
            "`include_start` and `include_end` "
            "are deprecated in favour of `inclusive`."
        )
        with tm.assert_produces_warning(FutureWarning, match=match):
            _ = ts.between_time(stime, etime, inc_start, inc_end)

    # GH40245
    def test_between_time_incorr_arg_inclusive(self):
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        ts = DataFrame(np.random.randn(len(rng), 2), index=rng)

        stime = time(0, 0)
        etime = time(1, 0)
        inclusive = "bad_string"
        msg = (
            "Inclusive has to be either string of 'both','left', 'right', "
            "or 'neither'. Got bad_string."
        )
        with pytest.raises(ValueError, match=msg):
            ts.between_time(stime, etime, inclusive=inclusive)

    # GH40245
    @pytest.mark.parametrize(
        "include_start, include_end", [(True, None), (True, True), (None, True)]
    )
    def test_between_time_incompatiable_args_given(self, include_start, include_end):
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        ts = DataFrame(np.random.randn(len(rng), 2), index=rng)

        stime = time(0, 0)
        etime = time(1, 0)
        msg = (
            "Deprecated arguments `include_start` and `include_end` cannot be "
            "passed if `inclusive` has been given."
        )
        with pytest.raises(ValueError, match=msg):
            ts.between_time(stime, etime, include_start, include_end, inclusive="left")

    # GH40245
    def test_between_time_same_functionality_old_and_new_args(self):
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        ts = DataFrame(np.random.randn(len(rng), 2), index=rng)
        stime = time(0, 0)
        etime = time(1, 0)
        match = (
            "`include_start` and `include_end` "
            "are deprecated in favour of `inclusive`."
        )

        x1 = ts.between_time(stime, etime)
        y1 = ts.between_time(stime, etime, inclusive="both")
        assert x1.equals(y1)

        with tm.assert_produces_warning(FutureWarning, match=match):
            x2 = ts.between_time(stime, etime, include_start=False)
        y2 = ts.between_time(stime, etime, inclusive="right")
        assert x2.equals(y2)

        with tm.assert_produces_warning(FutureWarning, match=match):
            x3 = ts.between_time(stime, etime, include_end=False)
        y3 = ts.between_time(stime, etime, inclusive="left")
        assert x3.equals(y3)

        with tm.assert_produces_warning(FutureWarning, match=match):
            x4 = ts.between_time(stime, etime, include_start=False, include_end=False)
        y4 = ts.between_time(stime, etime, inclusive="neither")
        assert x4.equals(y4)

        with tm.assert_produces_warning(FutureWarning, match=match):
            x5 = ts.between_time(stime, etime, include_start=True, include_end=True)
        y5 = ts.between_time(stime, etime, inclusive="both")
        assert x5.equals(y5)

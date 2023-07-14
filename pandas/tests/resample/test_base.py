from datetime import datetime

import numpy as np
import pytest

from pandas import (
    DataFrame,
    MultiIndex,
    NaT,
    PeriodIndex,
    Series,
    TimedeltaIndex,
)
import pandas._testing as tm
from pandas.core.groupby.groupby import DataError
from pandas.core.groupby.grouper import Grouper
from pandas.core.indexes.datetimes import date_range
from pandas.core.indexes.period import period_range
from pandas.core.indexes.timedeltas import timedelta_range
from pandas.core.resample import _asfreq_compat

# a fixture value can be overridden by the test parameter value. Note that the
# value of the fixture can be overridden this way even if the test doesn't use
# it directly (doesn't mention it in the function prototype).
# see https://docs.pytest.org/en/latest/fixture.html#override-a-fixture-with-direct-test-parametrization  # noqa: E501
# in this module we override the fixture values defined in conftest.py
# tuples of '_index_factory,_series_name,_index_start,_index_end'
DATE_RANGE = (date_range, "dti", datetime(2005, 1, 1), datetime(2005, 1, 10))
PERIOD_RANGE = (period_range, "pi", datetime(2005, 1, 1), datetime(2005, 1, 10))
TIMEDELTA_RANGE = (timedelta_range, "tdi", "1 day", "10 day")

all_ts = pytest.mark.parametrize(
    "_index_factory,_series_name,_index_start,_index_end",
    [DATE_RANGE, PERIOD_RANGE, TIMEDELTA_RANGE],
)


@pytest.fixture
def create_index(_index_factory):
    def _create_index(*args, **kwargs):
        """return the _index_factory created using the args, kwargs"""
        return _index_factory(*args, **kwargs)

    return _create_index


@pytest.mark.parametrize("freq", ["2D", "1H"])
@pytest.mark.parametrize(
    "_index_factory,_series_name,_index_start,_index_end", [DATE_RANGE, TIMEDELTA_RANGE]
)
def test_asfreq(series_and_frame, freq, create_index):
    obj = series_and_frame

    result = obj.resample(freq).asfreq()
    new_index = create_index(obj.index[0], obj.index[-1], freq=freq)
    expected = obj.reindex(new_index)
    tm.assert_almost_equal(result, expected)


@pytest.mark.parametrize(
    "_index_factory,_series_name,_index_start,_index_end", [DATE_RANGE, TIMEDELTA_RANGE]
)
def test_asfreq_fill_value(series, create_index):
    # test for fill value during resampling, issue 3715

    ser = series

    result = ser.resample("1H").asfreq()
    new_index = create_index(ser.index[0], ser.index[-1], freq="1H")
    expected = ser.reindex(new_index)
    tm.assert_series_equal(result, expected)

    # Explicit cast to float to avoid implicit cast when setting None
    frame = ser.astype("float").to_frame("value")
    frame.iloc[1] = None
    result = frame.resample("1H").asfreq(fill_value=4.0)
    new_index = create_index(frame.index[0], frame.index[-1], freq="1H")
    expected = frame.reindex(new_index, fill_value=4.0)
    tm.assert_frame_equal(result, expected)


@all_ts
def test_resample_interpolate(frame):
    # GH#12925
    df = frame
    result = df.resample("1T").asfreq().interpolate()
    expected = df.resample("1T").interpolate()
    tm.assert_frame_equal(result, expected)


def test_raises_on_non_datetimelike_index():
    # this is a non datetimelike index
    xp = DataFrame()
    msg = (
        "Only valid with DatetimeIndex, TimedeltaIndex or PeriodIndex, "
        "but got an instance of 'RangeIndex'"
    )
    with pytest.raises(TypeError, match=msg):
        xp.resample("A")


@all_ts
@pytest.mark.parametrize("freq", ["M", "D", "H"])
def test_resample_empty_series(freq, empty_series_dti, resample_method):
    # GH12771 & GH12868

    ser = empty_series_dti
    if freq == "M" and isinstance(ser.index, TimedeltaIndex):
        msg = (
            "Resampling on a TimedeltaIndex requires fixed-duration `freq`, "
            "e.g. '24H' or '3D', not <MonthEnd>"
        )
        with pytest.raises(ValueError, match=msg):
            ser.resample(freq)
        return

    rs = ser.resample(freq)
    result = getattr(rs, resample_method)()

    if resample_method == "ohlc":
        expected = DataFrame(
            [], index=ser.index[:0].copy(), columns=["open", "high", "low", "close"]
        )
        expected.index = _asfreq_compat(ser.index, freq)
        tm.assert_frame_equal(result, expected, check_dtype=False)
    else:
        expected = ser.copy()
        expected.index = _asfreq_compat(ser.index, freq)
        tm.assert_series_equal(result, expected, check_dtype=False)

    tm.assert_index_equal(result.index, expected.index)
    assert result.index.freq == expected.index.freq


@all_ts
@pytest.mark.parametrize(
    "freq",
    [
        pytest.param("M", marks=pytest.mark.xfail(reason="Don't know why this fails")),
        "D",
        "H",
    ],
)
def test_resample_nat_index_series(freq, series, resample_method):
    # GH39227

    ser = series.copy()
    ser.index = PeriodIndex([NaT] * len(ser), freq=freq)
    rs = ser.resample(freq)
    result = getattr(rs, resample_method)()

    if resample_method == "ohlc":
        expected = DataFrame(
            [], index=ser.index[:0].copy(), columns=["open", "high", "low", "close"]
        )
        tm.assert_frame_equal(result, expected, check_dtype=False)
    else:
        expected = ser[:0].copy()
        tm.assert_series_equal(result, expected, check_dtype=False)
    tm.assert_index_equal(result.index, expected.index)
    assert result.index.freq == expected.index.freq


@all_ts
@pytest.mark.parametrize("freq", ["M", "D", "H"])
@pytest.mark.parametrize("resample_method", ["count", "size"])
def test_resample_count_empty_series(freq, empty_series_dti, resample_method):
    # GH28427
    ser = empty_series_dti
    if freq == "M" and isinstance(ser.index, TimedeltaIndex):
        msg = (
            "Resampling on a TimedeltaIndex requires fixed-duration `freq`, "
            "e.g. '24H' or '3D', not <MonthEnd>"
        )
        with pytest.raises(ValueError, match=msg):
            ser.resample(freq)
        return

    rs = ser.resample(freq)

    result = getattr(rs, resample_method)()

    index = _asfreq_compat(ser.index, freq)

    expected = Series([], dtype="int64", index=index, name=ser.name)

    tm.assert_series_equal(result, expected)


@all_ts
@pytest.mark.parametrize("freq", ["M", "D", "H"])
def test_resample_empty_dataframe(empty_frame_dti, freq, resample_method):
    # GH13212
    df = empty_frame_dti
    # count retains dimensions too
    if freq == "M" and isinstance(df.index, TimedeltaIndex):
        msg = (
            "Resampling on a TimedeltaIndex requires fixed-duration `freq`, "
            "e.g. '24H' or '3D', not <MonthEnd>"
        )
        with pytest.raises(ValueError, match=msg):
            df.resample(freq, group_keys=False)
        return

    rs = df.resample(freq, group_keys=False)
    result = getattr(rs, resample_method)()
    if resample_method == "ohlc":
        # TODO: no tests with len(df.columns) > 0
        mi = MultiIndex.from_product([df.columns, ["open", "high", "low", "close"]])
        expected = DataFrame(
            [], index=df.index[:0].copy(), columns=mi, dtype=np.float64
        )
        expected.index = _asfreq_compat(df.index, freq)

    elif resample_method != "size":
        expected = df.copy()
    else:
        # GH14962
        expected = Series([], dtype=np.int64)

    expected.index = _asfreq_compat(df.index, freq)

    tm.assert_index_equal(result.index, expected.index)
    assert result.index.freq == expected.index.freq
    tm.assert_almost_equal(result, expected)

    # test size for GH13212 (currently stays as df)


@all_ts
@pytest.mark.parametrize("freq", ["M", "D", "H"])
def test_resample_count_empty_dataframe(freq, empty_frame_dti):
    # GH28427

    empty_frame_dti["a"] = []

    if freq == "M" and isinstance(empty_frame_dti.index, TimedeltaIndex):
        msg = (
            "Resampling on a TimedeltaIndex requires fixed-duration `freq`, "
            "e.g. '24H' or '3D', not <MonthEnd>"
        )
        with pytest.raises(ValueError, match=msg):
            empty_frame_dti.resample(freq)
        return

    result = empty_frame_dti.resample(freq).count()

    index = _asfreq_compat(empty_frame_dti.index, freq)

    expected = DataFrame({"a": []}, dtype="int64", index=index)

    tm.assert_frame_equal(result, expected)


@all_ts
@pytest.mark.parametrize("freq", ["M", "D", "H"])
def test_resample_size_empty_dataframe(freq, empty_frame_dti):
    # GH28427

    empty_frame_dti["a"] = []

    if freq == "M" and isinstance(empty_frame_dti.index, TimedeltaIndex):
        msg = (
            "Resampling on a TimedeltaIndex requires fixed-duration `freq`, "
            "e.g. '24H' or '3D', not <MonthEnd>"
        )
        with pytest.raises(ValueError, match=msg):
            empty_frame_dti.resample(freq)
        return

    result = empty_frame_dti.resample(freq).size()

    index = _asfreq_compat(empty_frame_dti.index, freq)

    expected = Series([], dtype="int64", index=index)

    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("index", tm.all_timeseries_index_generator(0))
@pytest.mark.parametrize("dtype", [float, int, object, "datetime64[ns]"])
def test_resample_empty_dtypes(index, dtype, resample_method):
    # Empty series were sometimes causing a segfault (for the functions
    # with Cython bounds-checking disabled) or an IndexError.  We just run
    # them to ensure they no longer do.  (GH #10228)
    empty_series_dti = Series([], index, dtype)
    try:
        getattr(empty_series_dti.resample("d", group_keys=False), resample_method)()
    except DataError:
        # Ignore these since some combinations are invalid
        # (ex: doing mean with dtype of np.object_)
        pass


@all_ts
@pytest.mark.parametrize("freq", ["M", "D", "H"])
def test_apply_to_empty_series(empty_series_dti, freq):
    # GH 14313
    ser = empty_series_dti

    if freq == "M" and isinstance(empty_series_dti.index, TimedeltaIndex):
        msg = (
            "Resampling on a TimedeltaIndex requires fixed-duration `freq`, "
            "e.g. '24H' or '3D', not <MonthEnd>"
        )
        with pytest.raises(ValueError, match=msg):
            empty_series_dti.resample(freq)
        return

    result = ser.resample(freq, group_keys=False).apply(lambda x: 1)
    expected = ser.resample(freq).apply("sum")

    tm.assert_series_equal(result, expected, check_dtype=False)


@all_ts
def test_resampler_is_iterable(series):
    # GH 15314
    freq = "H"
    tg = Grouper(freq=freq, convention="start")
    grouped = series.groupby(tg)
    resampled = series.resample(freq)
    for (rk, rv), (gk, gv) in zip(resampled, grouped):
        assert rk == gk
        tm.assert_series_equal(rv, gv)


@all_ts
def test_resample_quantile(series):
    # GH 15023
    ser = series
    q = 0.75
    freq = "H"
    result = ser.resample(freq).quantile(q)
    expected = ser.resample(freq).agg(lambda x: x.quantile(q)).rename(ser.name)
    tm.assert_series_equal(result, expected)

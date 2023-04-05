import math

import numpy as np
import pytest

import pandas as pd
from pandas import (
    DataFrame,
    Index,
    Series,
    concat,
    timedelta_range,
)
import pandas._testing as tm
from pandas.tests.apply.common import series_transform_kernels


def test_series_map_box_timedelta():
    # GH#11349
    ser = Series(timedelta_range("1 day 1 s", periods=3, freq="h"))

    def f(x):
        return x.total_seconds()

    result = ser.apply(f)

    tm.assert_series_equal(result, ser.map(f))

    expected = Series([86401.0, 90001.0, 93601.0])
    tm.assert_series_equal(result, expected)


def test_apply(datetime_series):
    with np.errstate(all="ignore"):
        tm.assert_series_equal(datetime_series.apply(np.sqrt), np.sqrt(datetime_series))

    # element-wise apply
    tm.assert_series_equal(datetime_series.apply(math.exp), np.exp(datetime_series))

    # empty series
    s = Series(dtype=object, name="foo", index=Index([], name="bar"))
    rs = s.apply(lambda x: x)
    tm.assert_series_equal(s, rs)

    # check all metadata (GH 9322)
    assert s is not rs
    assert s.index is rs.index
    assert s.dtype == rs.dtype
    assert s.name == rs.name

    # index but no data
    s = Series(index=[1, 2, 3], dtype=np.float64)
    rs = s.apply(lambda x: x)
    tm.assert_series_equal(s, rs)


def test_apply_map_same_length_inference_bug():
    s = Series([1, 2])

    def f(x):
        return (x, x + 1)

    result = s.apply(f)
    expected = s.map(f)
    tm.assert_series_equal(result, expected)

    s = Series([1, 2, 3])
    result = s.apply(f)
    expected = s.map(f)
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("convert_dtype", [True, False])
def test_apply_convert_dtype_deprecated(convert_dtype):
    ser = Series(np.random.randn(10))

    def func(x):
        return x if x > 0 else np.nan

    with tm.assert_produces_warning(FutureWarning):
        ser.apply(func, convert_dtype=convert_dtype)


def test_apply_args():
    s = Series(["foo,bar"])

    result = s.apply(str.split, args=(",",))
    assert result[0] == ["foo", "bar"]
    assert isinstance(result[0], list)


@pytest.mark.parametrize(
    "args, kwargs, increment",
    [((), {}, 0), ((), {"a": 1}, 1), ((2, 3), {}, 32), ((1,), {"c": 2}, 201)],
)
def test_agg_args(args, kwargs, increment):
    # GH 43357
    def f(x, a=0, b=0, c=0):
        return x + a + 10 * b + 100 * c

    s = Series([1, 2])
    result = s.agg(f, 0, *args, **kwargs)
    expected = s + increment
    tm.assert_series_equal(result, expected)


def test_agg_list_like_func_with_args():
    # GH 50624

    s = Series([1, 2, 3])

    def foo1(x, a=1, c=0):
        return x + a + c

    def foo2(x, b=2, c=0):
        return x + b + c

    msg = r"foo1\(\) got an unexpected keyword argument 'b'"
    with pytest.raises(TypeError, match=msg):
        s.agg([foo1, foo2], 0, 3, b=3, c=4)

    result = s.agg([foo1, foo2], 0, 3, c=4)
    expected = DataFrame({"foo1": [8, 9, 10], "foo2": [8, 9, 10]})
    tm.assert_frame_equal(result, expected)


def test_series_apply_map_box_timestamps():
    # GH#2689, GH#2627
    ser = Series(pd.date_range("1/1/2000", periods=10))

    def func(x):
        return (x.hour, x.day, x.month)

    result = ser.apply(func)
    expected = ser.map(func)
    tm.assert_series_equal(result, expected)


def test_apply_box():
    # ufunc will not be boxed. Same test cases as the test_map_box
    vals = [pd.Timestamp("2011-01-01"), pd.Timestamp("2011-01-02")]
    s = Series(vals)
    assert s.dtype == "datetime64[ns]"
    # boxed value must be Timestamp instance
    res = s.apply(lambda x: f"{type(x).__name__}_{x.day}_{x.tz}")
    exp = Series(["Timestamp_1_None", "Timestamp_2_None"])
    tm.assert_series_equal(res, exp)

    vals = [
        pd.Timestamp("2011-01-01", tz="US/Eastern"),
        pd.Timestamp("2011-01-02", tz="US/Eastern"),
    ]
    s = Series(vals)
    assert s.dtype == "datetime64[ns, US/Eastern]"
    res = s.apply(lambda x: f"{type(x).__name__}_{x.day}_{x.tz}")
    exp = Series(["Timestamp_1_US/Eastern", "Timestamp_2_US/Eastern"])
    tm.assert_series_equal(res, exp)

    # timedelta
    vals = [pd.Timedelta("1 days"), pd.Timedelta("2 days")]
    s = Series(vals)
    assert s.dtype == "timedelta64[ns]"
    res = s.apply(lambda x: f"{type(x).__name__}_{x.days}")
    exp = Series(["Timedelta_1", "Timedelta_2"])
    tm.assert_series_equal(res, exp)

    # period
    vals = [pd.Period("2011-01-01", freq="ME"), pd.Period("2011-01-02", freq="ME")]
    s = Series(vals)
    assert s.dtype == "period[ME]"
    res = s.apply(lambda x: f"{type(x).__name__}_{x.freqstr}")
    exp = Series(["Period_ME", "Period_ME"])
    tm.assert_series_equal(res, exp)


def test_apply_datetimetz():
    values = pd.date_range("2011-01-01", "2011-01-02", freq="H").tz_localize(
        "Asia/Tokyo"
    )
    s = Series(values, name="XX")

    result = s.apply(lambda x: x + pd.offsets.Day())
    exp_values = pd.date_range("2011-01-02", "2011-01-03", freq="H").tz_localize(
        "Asia/Tokyo"
    )
    exp = Series(exp_values, name="XX")
    tm.assert_series_equal(result, exp)

    result = s.apply(lambda x: x.hour)
    exp = Series(list(range(24)) + [0], name="XX", dtype=np.int64)
    tm.assert_series_equal(result, exp)

    # not vectorized
    def f(x):
        return str(x.tz)

    result = s.apply(f)
    exp = Series(["Asia/Tokyo"] * 25, name="XX")
    tm.assert_series_equal(result, exp)


def test_apply_categorical():
    values = pd.Categorical(list("ABBABCD"), categories=list("DCBA"), ordered=True)
    ser = Series(values, name="XX", index=list("abcdefg"))
    result = ser.apply(lambda x: x.lower())

    # should be categorical dtype when the number of categories are
    # the same
    values = pd.Categorical(list("abbabcd"), categories=list("dcba"), ordered=True)
    exp = Series(values, name="XX", index=list("abcdefg"))
    tm.assert_series_equal(result, exp)
    tm.assert_categorical_equal(result.values, exp.values)

    result = ser.apply(lambda x: "A")
    exp = Series(["A"] * 7, name="XX", index=list("abcdefg"))
    tm.assert_series_equal(result, exp)
    assert result.dtype == object


@pytest.mark.parametrize("series", [["1-1", "1-1", np.NaN], ["1-1", "1-2", np.NaN]])
def test_apply_categorical_with_nan_values(series):
    # GH 20714 bug fixed in: GH 24275
    s = Series(series, dtype="category")
    result = s.apply(lambda x: x.split("-")[0])
    result = result.astype(object)
    expected = Series(["1", "1", np.NaN], dtype="category")
    expected = expected.astype(object)
    tm.assert_series_equal(result, expected)


def test_apply_empty_integer_series_with_datetime_index():
    # GH 21245
    s = Series([], index=pd.date_range(start="2018-01-01", periods=0), dtype=int)
    result = s.apply(lambda x: x)
    tm.assert_series_equal(result, s)


def test_transform(string_series):
    # transforming functions

    with np.errstate(all="ignore"):
        f_sqrt = np.sqrt(string_series)
        f_abs = np.abs(string_series)

        # ufunc
        result = string_series.apply(np.sqrt)
        expected = f_sqrt.copy()
        tm.assert_series_equal(result, expected)

        # list-like
        result = string_series.apply([np.sqrt])
        expected = f_sqrt.to_frame().copy()
        expected.columns = ["sqrt"]
        tm.assert_frame_equal(result, expected)

        result = string_series.apply(["sqrt"])
        tm.assert_frame_equal(result, expected)

        # multiple items in list
        # these are in the order as if we are applying both functions per
        # series and then concatting
        expected = concat([f_sqrt, f_abs], axis=1)
        expected.columns = ["sqrt", "absolute"]
        result = string_series.apply([np.sqrt, np.abs])
        tm.assert_frame_equal(result, expected)

        # dict, provide renaming
        expected = concat([f_sqrt, f_abs], axis=1)
        expected.columns = ["foo", "bar"]
        expected = expected.unstack().rename("series")

        result = string_series.apply({"foo": np.sqrt, "bar": np.abs})
        tm.assert_series_equal(result.reindex_like(expected), expected)


@pytest.mark.parametrize("op", series_transform_kernels)
def test_transform_partial_failure(op, request):
    # GH 35964
    if op in ("ffill", "bfill", "pad", "backfill", "shift"):
        request.node.add_marker(
            pytest.mark.xfail(reason=f"{op} is successful on any dtype")
        )

    # Using object makes most transform kernels fail
    ser = Series(3 * [object])

    if op in ("fillna", "ngroup"):
        error = ValueError
        msg = "Transform function failed"
    else:
        error = TypeError
        msg = "|".join(
            [
                "not supported between instances of 'type' and 'type'",
                "unsupported operand type",
            ]
        )

    with pytest.raises(error, match=msg):
        ser.transform([op, "shift"])

    with pytest.raises(error, match=msg):
        ser.transform({"A": op, "B": "shift"})

    with pytest.raises(error, match=msg):
        ser.transform({"A": [op], "B": ["shift"]})

    with pytest.raises(error, match=msg):
        ser.transform({"A": [op, "shift"], "B": [op]})


def test_transform_partial_failure_valueerror():
    # GH 40211
    def noop(x):
        return x

    def raising_op(_):
        raise ValueError

    ser = Series(3 * [object])
    msg = "Transform function failed"

    with pytest.raises(ValueError, match=msg):
        ser.transform([noop, raising_op])

    with pytest.raises(ValueError, match=msg):
        ser.transform({"A": raising_op, "B": noop})

    with pytest.raises(ValueError, match=msg):
        ser.transform({"A": [raising_op], "B": [noop]})

    with pytest.raises(ValueError, match=msg):
        ser.transform({"A": [noop, raising_op], "B": [noop]})


def test_demo():
    # demonstration tests
    s = Series(range(6), dtype="int64", name="series")

    result = s.agg(["min", "max"])
    expected = Series([0, 5], index=["min", "max"], name="series")
    tm.assert_series_equal(result, expected)

    result = s.agg({"foo": "min"})
    expected = Series([0], index=["foo"], name="series")
    tm.assert_series_equal(result, expected)


def test_agg_apply_evaluate_lambdas_the_same(string_series):
    # test that we are evaluating row-by-row first
    # before vectorized evaluation
    result = string_series.apply(lambda x: str(x))
    expected = string_series.agg(lambda x: str(x))
    tm.assert_series_equal(result, expected)

    result = string_series.apply(str)
    expected = string_series.agg(str)
    tm.assert_series_equal(result, expected)


def test_with_nested_series(datetime_series):
    # GH 2316
    # .agg with a reducer and a transform, what to do
    result = datetime_series.apply(lambda x: Series([x, x**2], index=["x", "x^2"]))
    expected = DataFrame({"x": datetime_series, "x^2": datetime_series**2})
    tm.assert_frame_equal(result, expected)

    result = datetime_series.agg(lambda x: Series([x, x**2], index=["x", "x^2"]))
    tm.assert_frame_equal(result, expected)


def test_replicate_describe(string_series):
    # this also tests a result set that is all scalars
    expected = string_series.describe()
    result = string_series.apply(
        {
            "count": "count",
            "mean": "mean",
            "std": "std",
            "min": "min",
            "25%": lambda x: x.quantile(0.25),
            "50%": "median",
            "75%": lambda x: x.quantile(0.75),
            "max": "max",
        }
    )
    tm.assert_series_equal(result, expected)


def test_reduce(string_series):
    # reductions with named functions
    result = string_series.agg(["sum", "mean"])
    expected = Series(
        [string_series.sum(), string_series.mean()],
        ["sum", "mean"],
        name=string_series.name,
    )
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("how", ["agg", "apply"])
def test_non_callable_aggregates(how):
    # test agg using non-callable series attributes
    # GH 39116 - expand to apply
    s = Series([1, 2, None])

    # Calling agg w/ just a string arg same as calling s.arg
    result = getattr(s, how)("size")
    expected = s.size
    assert result == expected

    # test when mixed w/ callable reducers
    result = getattr(s, how)(["size", "count", "mean"])
    expected = Series({"size": 3.0, "count": 2.0, "mean": 1.5})
    tm.assert_series_equal(result, expected)


def test_series_apply_no_suffix_index():
    # GH36189
    s = Series([4] * 3)
    result = s.apply(["sum", lambda x: x.sum(), lambda x: x.sum()])
    expected = Series([12, 12, 12], index=["sum", "<lambda>", "<lambda>"])

    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    "dti,exp",
    [
        (
            Series([1, 2], index=pd.DatetimeIndex([0, 31536000000])),
            DataFrame(np.repeat([[1, 2]], 2, axis=0), dtype="int64"),
        ),
        (
            tm.makeTimeSeries(nper=30),
            DataFrame(np.repeat([[1, 2]], 30, axis=0), dtype="int64"),
        ),
    ],
)
@pytest.mark.parametrize("aware", [True, False])
def test_apply_series_on_date_time_index_aware_series(dti, exp, aware):
    # GH 25959
    # Calling apply on a localized time series should not cause an error
    if aware:
        index = dti.tz_localize("UTC").index
    else:
        index = dti.index
    result = Series(index).apply(lambda x: Series([1, 2]))
    tm.assert_frame_equal(result, exp)


def test_apply_scalar_on_date_time_index_aware_series():
    # GH 25959
    # Calling apply on a localized time series should not cause an error
    series = tm.makeTimeSeries(nper=30).tz_localize("UTC")
    result = Series(series.index).apply(lambda x: 1)
    tm.assert_series_equal(result, Series(np.ones(30), dtype="int64"))


def test_apply_to_timedelta():
    list_of_valid_strings = ["00:00:01", "00:00:02"]
    a = pd.to_timedelta(list_of_valid_strings)
    b = Series(list_of_valid_strings).apply(pd.to_timedelta)
    tm.assert_series_equal(Series(a), b)

    list_of_strings = ["00:00:01", np.nan, pd.NaT, pd.NaT]

    a = pd.to_timedelta(list_of_strings)
    ser = Series(list_of_strings)
    b = ser.apply(pd.to_timedelta)
    tm.assert_series_equal(Series(a), b)


@pytest.mark.parametrize(
    "ops, names",
    [
        ([np.sum], ["sum"]),
        ([np.sum, np.mean], ["sum", "mean"]),
        (np.array([np.sum]), ["sum"]),
        (np.array([np.sum, np.mean]), ["sum", "mean"]),
    ],
)
@pytest.mark.parametrize("how", ["agg", "apply"])
def test_apply_listlike_reducer(string_series, ops, names, how):
    # GH 39140
    expected = Series({name: op(string_series) for name, op in zip(names, ops)})
    expected.name = "series"
    result = getattr(string_series, how)(ops)
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    "ops",
    [
        {"A": np.sum},
        {"A": np.sum, "B": np.mean},
        Series({"A": np.sum}),
        Series({"A": np.sum, "B": np.mean}),
    ],
)
@pytest.mark.parametrize("how", ["agg", "apply"])
def test_apply_dictlike_reducer(string_series, ops, how):
    # GH 39140
    expected = Series({name: op(string_series) for name, op in ops.items()})
    expected.name = string_series.name
    result = getattr(string_series, how)(ops)
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    "ops, names",
    [
        ([np.sqrt], ["sqrt"]),
        ([np.abs, np.sqrt], ["absolute", "sqrt"]),
        (np.array([np.sqrt]), ["sqrt"]),
        (np.array([np.abs, np.sqrt]), ["absolute", "sqrt"]),
    ],
)
def test_apply_listlike_transformer(string_series, ops, names):
    # GH 39140
    with np.errstate(all="ignore"):
        expected = concat([op(string_series) for op in ops], axis=1)
        expected.columns = names
        result = string_series.apply(ops)
        tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "ops",
    [
        {"A": np.sqrt},
        {"A": np.sqrt, "B": np.exp},
        Series({"A": np.sqrt}),
        Series({"A": np.sqrt, "B": np.exp}),
    ],
)
def test_apply_dictlike_transformer(string_series, ops):
    # GH 39140
    with np.errstate(all="ignore"):
        expected = concat({name: op(string_series) for name, op in ops.items()})
        expected.name = string_series.name
        result = string_series.apply(ops)
        tm.assert_series_equal(result, expected)


def test_apply_retains_column_name():
    # GH 16380
    df = DataFrame({"x": range(3)}, Index(range(3), name="x"))
    result = df.x.apply(lambda x: Series(range(x + 1), Index(range(x + 1), name="y")))
    expected = DataFrame(
        [[0.0, np.nan, np.nan], [0.0, 1.0, np.nan], [0.0, 1.0, 2.0]],
        columns=Index(range(3), name="y"),
        index=Index(range(3), name="x"),
    )
    tm.assert_frame_equal(result, expected)


def test_apply_type():
    # GH 46719
    s = Series([3, "string", float], index=["a", "b", "c"])
    result = s.apply(type)
    expected = Series([int, str, type], index=["a", "b", "c"])
    tm.assert_series_equal(result, expected)

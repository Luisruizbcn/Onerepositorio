"""
This file contains a minimal set of tests for compliance with the extension
array interface test suite, and should contain no other tests.
The test suite for the full functionality of the array is located in
`pandas/tests/arrays/`.

The tests in this file are inherited from the BaseExtensionTests, and only
minimal tweaks should be applied to get the tests passing (by overwriting a
parent method).

Additional tests should either be added to one of the BaseExtensionTests
classes (if they are relevant for the extension interface for all dtypes), or
be added to the array-specific tests in `pandas/tests/arrays/`.

"""

import numpy as np
import pytest

from pandas.errors import PerformanceWarning

import pandas as pd
from pandas import SparseDtype
import pandas._testing as tm
from pandas.arrays import SparseArray
from pandas.tests.extension import base


def make_data(fill_value):
    rng = np.random.default_rng(2)
    if np.isnan(fill_value):
        data = rng.uniform(size=100)
    else:
        data = rng.integers(1, 100, size=100, dtype=int)
        if data[0] == data[1]:
            data[0] += 1

    data[2::3] = fill_value
    return data


@pytest.fixture
def dtype():
    return SparseDtype()


@pytest.fixture(params=[0, np.nan])
def data(request):
    """Length-100 PeriodArray for semantics test."""
    res = SparseArray(make_data(request.param), fill_value=request.param)
    return res


@pytest.fixture
def data_for_twos():
    return SparseArray(np.ones(100) * 2)


@pytest.fixture(params=[0, np.nan])
def data_missing(request):
    """Length 2 array with [NA, Valid]"""
    return SparseArray([np.nan, 1], fill_value=request.param)


@pytest.fixture(params=[0, np.nan])
def data_repeated(request):
    """Return different versions of data for count times"""

    def gen(count):
        for _ in range(count):
            yield SparseArray(make_data(request.param), fill_value=request.param)

    yield gen


@pytest.fixture(params=[0, np.nan])
def data_for_sorting(request):
    return SparseArray([2, 3, 1], fill_value=request.param)


@pytest.fixture(params=[0, np.nan])
def data_missing_for_sorting(request):
    return SparseArray([2, np.nan, 1], fill_value=request.param)


@pytest.fixture
def na_value():
    return np.nan


@pytest.fixture
def na_cmp():
    return lambda left, right: pd.isna(left) and pd.isna(right)


@pytest.fixture(params=[0, np.nan])
def data_for_grouping(request):
    return SparseArray([1, 1, np.nan, np.nan, 2, 2, 1, 3], fill_value=request.param)


@pytest.fixture(params=[0, np.nan])
def data_for_compare(request):
    return SparseArray([0, 0, np.nan, -2, -1, 4, 2, 3, 0, 0], fill_value=request.param)


class BaseSparseTests:
    def _check_unsupported(self, data):
        if data.dtype == SparseDtype(int, 0):
            pytest.skip("Can't store nan in int array.")

    @pytest.mark.xfail(reason="SparseArray does not support setitem")
    def test_ravel(self, data):
        super().test_ravel(data)


class TestDtype(BaseSparseTests, base.BaseDtypeTests):
    def test_array_type_with_arg(self, data, dtype):
        assert dtype.construct_array_type() is SparseArray


class TestInterface(BaseSparseTests, base.BaseInterfaceTests):
    def test_copy(self, data):
        # __setitem__ does not work, so we only have a smoke-test
        data.copy()

    def test_view(self, data):
        # __setitem__ does not work, so we only have a smoke-test
        data.view()


class TestConstructors(BaseSparseTests, base.BaseConstructorsTests):
    pass


class TestReshaping(BaseSparseTests, base.BaseReshapingTests):
    def test_concat_mixed_dtypes(self, data):
        # https://github.com/pandas-dev/pandas/issues/20762
        # This should be the same, aside from concat([sparse, float])
        df1 = pd.DataFrame({"A": data[:3]})
        df2 = pd.DataFrame({"A": [1, 2, 3]})
        df3 = pd.DataFrame({"A": ["a", "b", "c"]}).astype("category")
        dfs = [df1, df2, df3]

        # dataframes
        result = pd.concat(dfs)
        expected = pd.concat(
            [x.apply(lambda s: np.asarray(s).astype(object)) for x in dfs]
        )
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize(
        "columns",
        [
            ["A", "B"],
            pd.MultiIndex.from_tuples(
                [("A", "a"), ("A", "b")], names=["outer", "inner"]
            ),
        ],
    )
    @pytest.mark.parametrize("future_stack", [True, False])
    def test_stack(self, data, columns, future_stack):
        super().test_stack(data, columns, future_stack)

    def test_concat_columns(self, data, na_value):
        self._check_unsupported(data)
        super().test_concat_columns(data, na_value)

    def test_concat_extension_arrays_copy_false(self, data, na_value):
        self._check_unsupported(data)
        super().test_concat_extension_arrays_copy_false(data, na_value)

    def test_align(self, data, na_value):
        self._check_unsupported(data)
        super().test_align(data, na_value)

    def test_align_frame(self, data, na_value):
        self._check_unsupported(data)
        super().test_align_frame(data, na_value)

    def test_align_series_frame(self, data, na_value):
        self._check_unsupported(data)
        super().test_align_series_frame(data, na_value)

    def test_merge(self, data, na_value):
        self._check_unsupported(data)
        super().test_merge(data, na_value)

    @pytest.mark.xfail(reason="SparseArray does not support setitem")
    def test_transpose(self, data):
        super().test_transpose(data)


class TestGetitem(BaseSparseTests, base.BaseGetitemTests):
    def test_get(self, data):
        ser = pd.Series(data, index=[2 * i for i in range(len(data))])
        if np.isnan(ser.values.fill_value):
            assert np.isnan(ser.get(4)) and np.isnan(ser.iloc[2])
        else:
            assert ser.get(4) == ser.iloc[2]
        assert ser.get(2) == ser.iloc[1]

    def test_reindex(self, data, na_value):
        self._check_unsupported(data)
        super().test_reindex(data, na_value)


# Skipping TestSetitem, since we don't implement it.


class TestIndex(base.BaseIndexTests):
    pass


class TestMissing(BaseSparseTests, base.BaseMissingTests):
    def test_isna(self, data_missing):
        sarr = SparseArray(data_missing)
        expected_dtype = SparseDtype(bool, pd.isna(data_missing.dtype.fill_value))
        expected = SparseArray([True, False], dtype=expected_dtype)
        result = sarr.isna()
        tm.assert_sp_array_equal(result, expected)

        # test isna for arr without na
        sarr = sarr.fillna(0)
        expected_dtype = SparseDtype(bool, pd.isna(data_missing.dtype.fill_value))
        expected = SparseArray([False, False], fill_value=False, dtype=expected_dtype)
        tm.assert_equal(sarr.isna(), expected)

    def test_fillna_limit_backfill(self, data_missing):
        warns = (PerformanceWarning, FutureWarning)
        with tm.assert_produces_warning(warns, check_stacklevel=False):
            super().test_fillna_limit_backfill(data_missing)

    def test_fillna_no_op_returns_copy(self, data, request):
        if np.isnan(data.fill_value):
            request.node.add_marker(
                pytest.mark.xfail(reason="returns array with different fill value")
            )
        super().test_fillna_no_op_returns_copy(data)

    @pytest.mark.xfail(reason="Unsupported")
    def test_fillna_series(self):
        # this one looks doable.
        super().test_fillna_series()

    def test_fillna_frame(self, data_missing):
        # Have to override to specify that fill_value will change.
        fill_value = data_missing[1]

        result = pd.DataFrame({"A": data_missing, "B": [1, 2]}).fillna(fill_value)

        if pd.isna(data_missing.fill_value):
            dtype = SparseDtype(data_missing.dtype, fill_value)
        else:
            dtype = data_missing.dtype

        expected = pd.DataFrame(
            {
                "A": data_missing._from_sequence([fill_value, fill_value], dtype=dtype),
                "B": [1, 2],
            }
        )

        tm.assert_frame_equal(result, expected)


class TestMethods(BaseSparseTests, base.BaseMethodsTests):
    _combine_le_expected_dtype = "Sparse[bool]"

    def test_fillna_copy_frame(self, data_missing, using_copy_on_write):
        arr = data_missing.take([1, 1])
        df = pd.DataFrame({"A": arr}, copy=False)

        filled_val = df.iloc[0, 0]
        result = df.fillna(filled_val)

        if hasattr(df._mgr, "blocks"):
            if using_copy_on_write:
                assert df.values.base is result.values.base
            else:
                assert df.values.base is not result.values.base
        assert df.A._values.to_dense() is arr.to_dense()

    def test_fillna_copy_series(self, data_missing, using_copy_on_write):
        arr = data_missing.take([1, 1])
        ser = pd.Series(arr, copy=False)

        filled_val = ser[0]
        result = ser.fillna(filled_val)

        if using_copy_on_write:
            assert ser._values is result._values

        else:
            assert ser._values is not result._values
        assert ser._values.to_dense() is arr.to_dense()

    @pytest.mark.xfail(reason="Not Applicable")
    def test_fillna_length_mismatch(self, data_missing):
        super().test_fillna_length_mismatch(data_missing)

    def test_where_series(self, data, na_value):
        assert data[0] != data[1]
        cls = type(data)
        a, b = data[:2]

        ser = pd.Series(cls._from_sequence([a, a, b, b], dtype=data.dtype))

        cond = np.array([True, True, False, False])
        result = ser.where(cond)

        new_dtype = SparseDtype("float", 0.0)
        expected = pd.Series(
            cls._from_sequence([a, a, na_value, na_value], dtype=new_dtype)
        )
        tm.assert_series_equal(result, expected)

        other = cls._from_sequence([a, b, a, b], dtype=data.dtype)
        cond = np.array([True, False, True, True])
        result = ser.where(cond, other)
        expected = pd.Series(cls._from_sequence([a, b, b, b], dtype=data.dtype))
        tm.assert_series_equal(result, expected)

    def test_searchsorted(self, data_for_sorting, as_series):
        with tm.assert_produces_warning(PerformanceWarning, check_stacklevel=False):
            super().test_searchsorted(data_for_sorting, as_series)

    def test_shift_0_periods(self, data):
        # GH#33856 shifting with periods=0 should return a copy, not same obj
        result = data.shift(0)

        data._sparse_values[0] = data._sparse_values[1]
        assert result._sparse_values[0] != result._sparse_values[1]

    @pytest.mark.parametrize("method", ["argmax", "argmin"])
    def test_argmin_argmax_all_na(self, method, data, na_value):
        # overriding because Sparse[int64, 0] cannot handle na_value
        self._check_unsupported(data)
        super().test_argmin_argmax_all_na(method, data, na_value)

    @pytest.mark.parametrize("box", [pd.array, pd.Series, pd.DataFrame])
    def test_equals(self, data, na_value, as_series, box):
        self._check_unsupported(data)
        super().test_equals(data, na_value, as_series, box)

    @pytest.mark.parametrize(
        "func, na_action, expected",
        [
            (lambda x: x, None, SparseArray([1.0, np.nan])),
            (lambda x: x, "ignore", SparseArray([1.0, np.nan])),
            (str, None, SparseArray(["1.0", "nan"], fill_value="nan")),
            (str, "ignore", SparseArray(["1.0", np.nan])),
        ],
    )
    def test_map(self, func, na_action, expected):
        # GH52096
        data = SparseArray([1, np.nan])
        result = data.map(func, na_action=na_action)
        tm.assert_extension_array_equal(result, expected)

    @pytest.mark.parametrize("na_action", [None, "ignore"])
    def test_map_raises(self, data, na_action):
        # GH52096
        msg = "fill value in the sparse values not supported"
        with pytest.raises(ValueError, match=msg):
            data.map(lambda x: np.nan, na_action=na_action)


class TestCasting(BaseSparseTests, base.BaseCastingTests):
    def test_astype_str(self, data):
        # pre-2.0 this would give a SparseDtype even if the user asked
        #  for a non-sparse dtype.
        result = pd.Series(data[:5]).astype(str)
        expected = pd.Series([str(x) for x in data[:5]], dtype=object)
        tm.assert_series_equal(result, expected)

    @pytest.mark.xfail(raises=TypeError, reason="no sparse StringDtype")
    def test_astype_string(self, data):
        super().test_astype_string(data)


class TestArithmeticOps(BaseSparseTests, base.BaseArithmeticOpsTests):
    series_scalar_exc = None
    frame_scalar_exc = None
    divmod_exc = None
    series_array_exc = None

    def _skip_if_different_combine(self, data):
        if data.fill_value == 0:
            # arith ops call on dtype.fill_value so that the sparsity
            # is maintained. Combine can't be called on a dtype in
            # general, so we can't make the expected. This is tested elsewhere
            pytest.skip("Incorrected expected from Series.combine and tested elsewhere")

    def test_arith_series_with_scalar(self, data, all_arithmetic_operators):
        self._skip_if_different_combine(data)
        super().test_arith_series_with_scalar(data, all_arithmetic_operators)

    def test_arith_series_with_array(self, data, all_arithmetic_operators):
        self._skip_if_different_combine(data)
        super().test_arith_series_with_array(data, all_arithmetic_operators)

    def test_arith_frame_with_scalar(self, data, all_arithmetic_operators, request):
        if data.dtype.fill_value != 0:
            pass
        elif all_arithmetic_operators.strip("_") not in [
            "mul",
            "rmul",
            "floordiv",
            "rfloordiv",
            "pow",
            "mod",
            "rmod",
        ]:
            mark = pytest.mark.xfail(reason="result dtype.fill_value mismatch")
            request.node.add_marker(mark)
        super().test_arith_frame_with_scalar(data, all_arithmetic_operators)

    def _check_divmod_op(self, ser, op, other, exc=NotImplementedError):
        # We implement divmod
        super()._check_divmod_op(ser, op, other, exc=None)


class TestComparisonOps(BaseSparseTests):
    def _compare_other(self, data_for_compare: SparseArray, comparison_op, other):
        op = comparison_op

        result = op(data_for_compare, other)
        assert isinstance(result, SparseArray)
        assert result.dtype.subtype == np.bool_

        if isinstance(other, SparseArray):
            fill_value = op(data_for_compare.fill_value, other.fill_value)
        else:
            fill_value = np.all(
                op(np.asarray(data_for_compare.fill_value), np.asarray(other))
            )

            expected = SparseArray(
                op(data_for_compare.to_dense(), np.asarray(other)),
                fill_value=fill_value,
                dtype=np.bool_,
            )
        tm.assert_sp_array_equal(result, expected)

    def test_scalar(self, data_for_compare: SparseArray, comparison_op):
        self._compare_other(data_for_compare, comparison_op, 0)
        self._compare_other(data_for_compare, comparison_op, 1)
        self._compare_other(data_for_compare, comparison_op, -1)
        self._compare_other(data_for_compare, comparison_op, np.nan)

    @pytest.mark.xfail(reason="Wrong indices")
    def test_array(self, data_for_compare: SparseArray, comparison_op):
        arr = np.linspace(-4, 5, 10)
        self._compare_other(data_for_compare, comparison_op, arr)

    @pytest.mark.xfail(reason="Wrong indices")
    def test_sparse_array(self, data_for_compare: SparseArray, comparison_op):
        arr = data_for_compare + 1
        self._compare_other(data_for_compare, comparison_op, arr)
        arr = data_for_compare * 2
        self._compare_other(data_for_compare, comparison_op, arr)


class TestPrinting(BaseSparseTests, base.BasePrintingTests):
    @pytest.mark.xfail(reason="Different repr")
    def test_array_repr(self, data, size):
        super().test_array_repr(data, size)


class TestParsing(BaseSparseTests, base.BaseParsingTests):
    @pytest.mark.parametrize("engine", ["c", "python"])
    def test_EA_types(self, engine, data):
        expected_msg = r".*must implement _from_sequence_of_strings.*"
        with pytest.raises(NotImplementedError, match=expected_msg):
            super().test_EA_types(engine, data)


class TestNoNumericAccumulations(base.BaseAccumulateTests):
    pass

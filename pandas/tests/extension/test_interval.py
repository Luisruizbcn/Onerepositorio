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

from pandas.core.dtypes.dtypes import IntervalDtype

from pandas import (
    Interval,
    Series,
)
from pandas.core.arrays import IntervalArray
from pandas.tests.extension import base


def make_data():
    N = 100
    left_array = np.random.default_rng(2).uniform(size=N).cumsum()
    right_array = left_array + np.random.default_rng(2).uniform(size=N)
    return [Interval(left, right) for left, right in zip(left_array, right_array)]


@pytest.fixture
def dtype():
    return IntervalDtype()


@pytest.fixture
def data():
    """Length-100 PeriodArray for semantics test."""
    return IntervalArray(make_data())


@pytest.fixture
def data_missing():
    """Length 2 array with [NA, Valid]"""
    return IntervalArray.from_tuples([None, (0, 1)])


@pytest.fixture
def data_for_twos():
    pytest.skip("Not a numeric dtype")


@pytest.fixture
def data_for_sorting():
    return IntervalArray.from_tuples([(1, 2), (2, 3), (0, 1)])


@pytest.fixture
def data_missing_for_sorting():
    return IntervalArray.from_tuples([(1, 2), None, (0, 1)])


@pytest.fixture
def na_value():
    return np.nan


@pytest.fixture
def data_for_grouping():
    a = (0, 1)
    b = (1, 2)
    c = (2, 3)
    return IntervalArray.from_tuples([b, b, None, None, a, a, b, c])


class TestIntervalArray(base.ExtensionTests):
    divmod_exc = TypeError

    @pytest.mark.parametrize("skipna", [True, False])
    def test_reduce_series_numeric(self, data, all_numeric_reductions, skipna):
        op_name = all_numeric_reductions
        ser = Series(data)

        if op_name in ["min", "max"]:
            # IntervalArray *does* implement these
            assert getattr(ser, op_name)(skipna=skipna) in data
            assert getattr(data, op_name)(skipna=skipna) in data
            return

        super().test_reduce_series_numeric(data, all_numeric_reductions, skipna)

    @pytest.mark.xfail(
        reason="Raises with incorrect message bc it disallows *all* listlikes "
        "instead of just wrong-length listlikes"
    )
    def test_fillna_length_mismatch(self, data_missing):
        super().test_fillna_length_mismatch(data_missing)

    @pytest.mark.parametrize("engine", ["c", "python"])
    def test_EA_types(self, engine, data):
        expected_msg = r".*must implement _from_sequence_of_strings.*"
        with pytest.raises(NotImplementedError, match=expected_msg):
            super().test_EA_types(engine, data)

    @pytest.mark.xfail(
        reason="Looks like the test (incorrectly) implicitly assumes int/bool dtype"
    )
    def test_invert(self, data):
        super().test_invert(data)


# TODO: either belongs in tests.arrays.interval or move into base tests.
def test_fillna_non_scalar_raises(data_missing):
    msg = "can only insert Interval objects and NA into an IntervalArray"
    with pytest.raises(TypeError, match=msg):
        data_missing.fillna([1, 1])

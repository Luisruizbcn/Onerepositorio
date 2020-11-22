"""
The tests in this package are to ensure the proper resultant dtypes of
set operations.
"""
import numpy as np
import pytest

from pandas.core.dtypes.common import is_dtype_equal

import pandas as pd
from pandas import (
    CategoricalIndex,
    DatetimeIndex,
    Float64Index,
    Index,
    Int64Index,
    RangeIndex,
    TimedeltaIndex,
    UInt64Index,
)
import pandas._testing as tm
from pandas.api.types import pandas_dtype

COMPATIBLE_INCONSISTENT_PAIRS = {
    (Int64Index, RangeIndex): (tm.makeIntIndex, tm.makeRangeIndex),
    (Float64Index, Int64Index): (tm.makeFloatIndex, tm.makeIntIndex),
    (Float64Index, RangeIndex): (tm.makeFloatIndex, tm.makeIntIndex),
    (Float64Index, UInt64Index): (tm.makeFloatIndex, tm.makeUIntIndex),
}


def test_union_same_types(index):
    # Union with a non-unique, non-monotonic index raises error
    # Only needed for bool index factory
    idx1 = index.sort_values()
    idx2 = index.sort_values()
    assert idx1.union(idx2).dtype == idx1.dtype


def test_union_different_types(index, index_fixture2):
    # This test only considers combinations of indices
    # GH 23525
    idx1, idx2 = index, index_fixture2
    type_pair = tuple(sorted([type(idx1), type(idx2)], key=lambda x: str(x)))
    if type_pair in COMPATIBLE_INCONSISTENT_PAIRS:
        pytest.xfail("This test only considers non compatible indexes.")

    if any(isinstance(idx, pd.MultiIndex) for idx in (idx1, idx2)):
        pytest.xfail("This test doesn't consider multiindixes.")

    if is_dtype_equal(idx1.dtype, idx2.dtype):
        pytest.xfail("This test only considers non matching dtypes.")

    # A union with a CategoricalIndex (even as dtype('O')) and a
    # non-CategoricalIndex can only be made if both indices are monotonic.
    # This is true before this PR as well.

    # Union with a non-unique, non-monotonic index raises error
    # This applies to the boolean index
    idx1 = idx1.sort_values()
    idx2 = idx2.sort_values()

    assert idx1.union(idx2).dtype == np.dtype("O")
    assert idx2.union(idx1).dtype == np.dtype("O")


@pytest.mark.parametrize("idx_fact1,idx_fact2", COMPATIBLE_INCONSISTENT_PAIRS.values())
def test_compatible_inconsistent_pairs(idx_fact1, idx_fact2):
    # GH 23525
    idx1 = idx_fact1(10)
    idx2 = idx_fact2(20)

    res1 = idx1.union(idx2)
    res2 = idx2.union(idx1)

    assert res1.dtype in (idx1.dtype, idx2.dtype)
    assert res2.dtype in (idx1.dtype, idx2.dtype)


@pytest.mark.parametrize(
    "left, right, expected",
    [
        ("int64", "int64", "int64"),
        ("int64", "uint64", "object"),
        ("int64", "float64", "float64"),
        ("uint64", "float64", "float64"),
        ("uint64", "uint64", "uint64"),
        ("float64", "float64", "float64"),
        ("datetime64[ns]", "int64", "object"),
        ("datetime64[ns]", "uint64", "object"),
        ("datetime64[ns]", "float64", "object"),
        ("datetime64[ns, CET]", "int64", "object"),
        ("datetime64[ns, CET]", "uint64", "object"),
        ("datetime64[ns, CET]", "float64", "object"),
        ("Period[D]", "int64", "object"),
        ("Period[D]", "uint64", "object"),
        ("Period[D]", "float64", "object"),
    ],
)
def test_union_dtypes(left, right, expected):
    left = pandas_dtype(left)
    right = pandas_dtype(right)
    a = Index([], dtype=left)
    b = Index([], dtype=right)
    result = (a | b).dtype
    assert result == expected


@pytest.mark.parametrize(
    "cls",
    [
        Int64Index,
        Float64Index,
        DatetimeIndex,
        CategoricalIndex,
        TimedeltaIndex,
        lambda x: Index(x, dtype=object),
    ],
)
def test_union_duplicate_index_subsets_of_each_other(cls):
    # GH#31326
    a = cls([1, 2, 2, 3])
    b = cls([3, 3, 4])
    expected = cls([1, 2, 2, 3, 3, 4])
    if cls is CategoricalIndex:
        expected = Index([1, 2, 2, 3, 3, 4], dtype="object")
    result = a.union(b)
    tm.assert_index_equal(result, expected)
    result = a.union(b, sort=False)
    tm.assert_index_equal(result, expected)


@pytest.mark.parametrize(
    "cls",
    [
        Int64Index,
        Float64Index,
        DatetimeIndex,
        CategoricalIndex,
        TimedeltaIndex,
        lambda x: Index(x, dtype=object),
    ],
)
def test_union_with_duplicate_index(cls):
    # GH#36289
    idx1 = cls([1, 0, 0])
    idx2 = cls([0, 1])
    expected = cls([0, 0, 1])

    result = idx1.union(idx2)
    tm.assert_index_equal(result, expected)

    result = idx2.union(idx1)
    tm.assert_index_equal(result, expected)


def test_union_duplicate_index_different_dtypes():
    # GH#36289
    idx1 = Index([1, 2, 2, 3])
    idx2 = Index(["1", "0", "0"])
    expected = Index([1, 2, 2, 3, "1", "0", "0"])
    result = idx1.union(idx2, sort=False)
    tm.assert_index_equal(result, expected)

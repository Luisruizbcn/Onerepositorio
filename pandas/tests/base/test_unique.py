import numpy as np
import pytest

from pandas._libs.tslib import iNaT

from pandas.core.dtypes.common import is_datetime64tz_dtype, needs_i8_conversion
from pandas.core.dtypes.generic import ABCMultiIndex

import pandas as pd
import pandas._testing as tm
from pandas.tests.base.common import allow_na_ops


def test_unique(index_or_series_obj):
    obj = index_or_series_obj
    obj = np.repeat(obj, range(1, len(obj) + 1))
    result = obj.unique()

    # dict.fromkeys preserves the order
    unique_values = list(dict.fromkeys(obj.values))
    if isinstance(obj, ABCMultiIndex):
        expected = pd.MultiIndex.from_tuples(unique_values)
        expected.names = obj.names
        tm.assert_index_equal(result, expected)
    elif isinstance(obj, pd.Index):
        expected = pd.Index(unique_values, dtype=obj.dtype)
        if is_datetime64tz_dtype(obj):
            expected = expected.normalize()
        tm.assert_index_equal(result, expected)
    else:
        expected = np.array(unique_values)
        tm.assert_numpy_array_equal(result, expected)


@pytest.mark.parametrize("null_obj", [np.nan, None])
def test_unique_null(null_obj, index_or_series_obj):
    obj = index_or_series_obj

    if not allow_na_ops(obj):
        pytest.skip("type doesn't allow for NA operations")
    elif len(obj) < 1:
        pytest.skip("Test doesn't make sense on empty data")
    elif isinstance(obj, ABCMultiIndex):
        pytest.skip(f"MultiIndex can't hold '{null_obj}'")

    values = obj.values
    if needs_i8_conversion(obj):
        values[0:2] = iNaT
    else:
        values[0:2] = null_obj

    klass = type(obj)
    repeated_values = np.repeat(values, range(1, len(values) + 1))
    obj = klass(repeated_values, dtype=obj.dtype)
    result = obj.unique()

    unique_values_raw = dict.fromkeys(obj.values)
    # because np.nan == np.nan is False, but None == None is True
    # np.nan would be duplicated, whereas None wouldn't
    unique_values_not_null = [val for val in unique_values_raw if not pd.isnull(val)]
    unique_values = [null_obj] + unique_values_not_null

    if isinstance(obj, pd.Index):
        expected = pd.Index(unique_values, dtype=obj.dtype)
        if is_datetime64tz_dtype(obj):
            result = result.normalize()
            expected = expected.normalize()
        elif isinstance(obj, pd.CategoricalIndex):
            expected = expected.set_categories(unique_values_not_null)
        tm.assert_index_equal(result, expected)
    else:
        expected = np.array(unique_values, dtype=obj.dtype)
        tm.assert_numpy_array_equal(result, expected)


def test_nunique(index_or_series_obj):
    obj = index_or_series_obj
    obj = np.repeat(obj, range(1, len(obj) + 1))
    expected = len(obj.unique())
    assert obj.nunique(dropna=False) == expected


@pytest.mark.parametrize("null_obj", [np.nan, None])
def test_nunique_null(null_obj, index_or_series_obj):
    obj = index_or_series_obj

    if not allow_na_ops(obj):
        pytest.skip("type doesn't allow for NA operations")
    elif isinstance(obj, ABCMultiIndex):
        pytest.skip(f"MultiIndex can't hold '{null_obj}'")

    values = obj.values
    if needs_i8_conversion(obj):
        values[0:2] = iNaT
    else:
        values[0:2] = null_obj

    klass = type(obj)
    repeated_values = np.repeat(values, range(1, len(values) + 1))
    obj = klass(repeated_values, dtype=obj.dtype)

    if isinstance(obj, pd.CategoricalIndex):
        assert obj.nunique() == len(obj.categories)
        assert obj.nunique(dropna=False) == len(obj.categories) + 1
    else:
        num_unique_values = len(obj.unique())
        assert obj.nunique() == max(0, num_unique_values - 1)
        assert obj.nunique(dropna=False) == max(0, num_unique_values)

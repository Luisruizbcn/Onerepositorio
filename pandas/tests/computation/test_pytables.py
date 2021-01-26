from typing import Any
import pytest
import numpy as np

from pandas.core.computation.pytables import TermValue, BinOp
from pandas import Series


@pytest.mark.parametrize(
    "value, expected_results",
    [("q", TermValue(-1, -1, "integer")), ("a", TermValue(0, 0, "integer"))],
)
def test__convert_value(value: Any, expected_results: TermValue):
    metadata = Series(np.array(['a', 'b', 's']))

    result = BinOp._convert_category_value(metadata, value)

    assert (
        result.kind == expected_results.kind
        and result.value == expected_results.value
        and result.converted == expected_results.converted
    )
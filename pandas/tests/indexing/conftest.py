import numpy as np
import pytest

from pandas import (
    DataFrame,
    Series,
    date_range,
)
from pandas.core.api import (
    Float64Index,
    UInt64Index,
)


@pytest.fixture
def series_ints():
    return Series(np.random.rand(4), index=np.arange(0, 8, 2))


@pytest.fixture
def frame_ints():
    return DataFrame(
        np.random.randn(4, 4), index=np.arange(0, 8, 2), columns=np.arange(0, 12, 3)
    )


@pytest.fixture
def series_uints():
    return Series(np.random.rand(4), index=UInt64Index(np.arange(0, 8, 2)))


@pytest.fixture
def frame_uints():
    return DataFrame(
        np.random.randn(4, 4),
        index=UInt64Index(range(0, 8, 2)),
        columns=UInt64Index(range(0, 12, 3)),
    )


@pytest.fixture
def series_labels():
    return Series(np.random.randn(4), index=list("abcd"))


@pytest.fixture
def frame_labels():
    return DataFrame(np.random.randn(4, 4), index=list("abcd"), columns=list("ABCD"))


@pytest.fixture
def series_ts():
    return Series(np.random.randn(4), index=date_range("20130101", periods=4))


@pytest.fixture
def frame_ts():
    return DataFrame(np.random.randn(4, 4), index=date_range("20130101", periods=4))


@pytest.fixture
def series_floats():
    return Series(np.random.rand(4), index=Float64Index(range(0, 8, 2)))


@pytest.fixture
def frame_floats():
    return DataFrame(
        np.random.randn(4, 4),
        index=Float64Index(range(0, 8, 2)),
        columns=Float64Index(range(0, 12, 3)),
    )


@pytest.fixture
def series_mixed():
    return Series(np.random.randn(4), index=[2, 4, "null", 8])


@pytest.fixture
def frame_mixed():
    return DataFrame(np.random.randn(4, 4), index=[2, 4, "null", 8])


@pytest.fixture
def frame_empty():
    return DataFrame()


@pytest.fixture
def series_empty():
    return Series(dtype=object)

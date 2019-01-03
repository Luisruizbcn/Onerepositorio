# -*- coding: utf-8 -*-

import numpy as np
import pytest

from pandas.core.dtypes.dtypes import CategoricalDtype

from pandas.util.testing import assert_copy


def test_astype(idx):
    expected = idx.copy()
    actual = idx.astype('O')
    assert_copy(actual.levels, expected.levels)
    assert_copy(actual.codes, expected.codes)
    assert [level.name for level in actual.levels] == list(expected.names)

    with pytest.raises(TypeError, match="^Setting.*dtype.*object"):
        idx.astype(np.dtype(int))


@pytest.mark.parametrize('ordered', [True, False])
def test_astype_category(idx, ordered):
    # GH 18630
    msg = '> 1 ndim Categorical are not supported at this time'
    with pytest.raises(NotImplementedError, match=msg):
        idx.astype(CategoricalDtype(ordered=ordered))

    if ordered is False:
        # dtype='category' defaults to ordered=False, so only test once
        with pytest.raises(NotImplementedError, match=msg):
            idx.astype('category')

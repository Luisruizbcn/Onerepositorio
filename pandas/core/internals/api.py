"""
This is a pseudo-public API for downstream libraries.  We ask that downstream
authors

1) Try to avoid using internals directly altogether, and failing that,
2) Use only functions exposed here (or in core.internals)

"""
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Optional,
    Sequence,
    cast,
)

import numpy as np

from pandas._libs.internals import BlockPlacement
from pandas._typing import Dtype

from pandas.core.dtypes.common import is_datetime64tz_dtype

from pandas.core.arrays import DatetimeArray
from pandas.core.internals.blocks import (
    Block,
    DatetimeTZBlock,
    check_ndim,
    ensure_block_shape,
    extract_pandas_array,
    get_block_type,
    maybe_coerce_values,
)
from pandas.core.internals.managers import BlockManager as BM

if TYPE_CHECKING:
    from pandas import Index


def make_block(
    values, placement, klass=None, ndim=None, dtype: Optional[Dtype] = None
) -> Block:
    """
    This is a pseudo-public analogue to blocks.new_block.

    We ask that downstream libraries use this rather than any fully-internal
    APIs, including but not limited to:

    - core.internals.blocks.make_block
    - Block.make_block
    - Block.make_block_same_class
    - Block.__init__
    """
    # error: Argument 2 to "extract_pandas_array" has incompatible type
    # "Union[ExtensionDtype, str, dtype[Any], Type[str], Type[float], Type[int],
    # Type[complex], Type[bool], Type[object], None]"; expected "Union[dtype[Any],
    # ExtensionDtype, None]"
    values, dtype = extract_pandas_array(values, dtype, ndim)  # type: ignore[arg-type]

    needs_reshape = False
    if klass is None:
        dtype = dtype or values.dtype
        klass = get_block_type(values, dtype)

    elif klass is DatetimeTZBlock and not is_datetime64tz_dtype(values.dtype):
        # pyarrow calls get here
        values = DatetimeArray._simple_new(values, dtype=dtype)
        needs_reshape = True

    if not isinstance(placement, BlockPlacement):
        placement = BlockPlacement(placement)

    ndim = _maybe_infer_ndim(values, placement, ndim)
    if needs_reshape:
        values = ensure_block_shape(values, ndim)

    check_ndim(values, placement, ndim)
    values = maybe_coerce_values(values)
    return klass(values, ndim=ndim, placement=placement)


def _maybe_infer_ndim(values, placement: BlockPlacement, ndim: Optional[int]) -> int:
    """
    If `ndim` is not provided, infer it from placment and values.
    """
    if ndim is None:
        # GH#38134 Block constructor now assumes ndim is not None
        if not isinstance(values.dtype, np.dtype):
            if len(placement) != 1:
                ndim = 1
            else:
                ndim = 2
        else:
            ndim = values.ndim
    return ndim


# TODO: deprecate following https://github.com/dask/fastparquet/pull/571
class BlockManager(BM):
    """
    For backwards-compatibility for fastparquet, we patch incorrectly-shaped
    blocks on construction.
    """

    def __new__(
        cls,
        blocks: Sequence[Block],
        axes: Sequence[Index],
        verify_integrity: bool = True,
    ):
        blocks = list(blocks)
        for blk in blocks:
            if isinstance(blk, DatetimeTZBlock):
                fixed = ensure_block_shape(blk.values, 2)
                fixed = cast(DatetimeArray, fixed)
                blk.values = fixed

        return BM(blocks, axes, verify_integrity=verify_integrity)

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "No instance of this wrapper class should ever by fully instantiated."
        )

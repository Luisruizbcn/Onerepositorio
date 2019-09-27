"""
Arithmetic operations for PandasObjects

This is not a public API.
"""
import datetime
import operator
from typing import Tuple

import numpy as np

from pandas._libs import Timedelta, Timestamp, lib
from pandas.util._decorators import Appender

from pandas.core.dtypes.common import (
    is_extension_array_dtype,
    is_list_like,
    is_timedelta64_dtype,
)
from pandas.core.dtypes.generic import ABCDataFrame, ABCIndexClass, ABCSeries
from pandas.core.dtypes.missing import isna

from pandas.core.construction import extract_array
from pandas.core.ops.array_ops import (
    arithmetic_op,
    array_op,
    comparison_op,
    define_na_arithmetic_op,
    logical_op,
)
from pandas.core.ops.array_ops import comp_method_OBJECT_ARRAY  # noqa:F401
from pandas.core.ops.dispatch import maybe_dispatch_ufunc_to_dunder_op  # noqa:F401
from pandas.core.ops.dispatch import should_series_dispatch
from pandas.core.ops.docstrings import (
    _arith_doc_FRAME,
    _flex_comp_doc_FRAME,
    _make_flex_doc,
    _op_descriptions,
)
from pandas.core.ops.invalid import invalid_comparison  # noqa:F401
from pandas.core.ops.methods import (  # noqa:F401
    add_flex_arithmetic_methods,
    add_special_arithmetic_methods,
)
from pandas.core.ops.roperator import (  # noqa:F401
    radd,
    rand_,
    rdiv,
    rdivmod,
    rfloordiv,
    rmod,
    rmul,
    ror_,
    rpow,
    rsub,
    rtruediv,
    rxor,
)

# -----------------------------------------------------------------------------
# Ops Wrapping Utilities


def get_op_result_name(left, right):
    """
    Find the appropriate name to pin to an operation result.  This result
    should always be either an Index or a Series.

    Parameters
    ----------
    left : {Series, Index}
    right : object

    Returns
    -------
    name : object
        Usually a string
    """
    # `left` is always a Series when called from within ops
    if isinstance(right, (ABCSeries, ABCIndexClass)):
        name = _maybe_match_name(left, right)
    else:
        name = left.name
    return name


def _maybe_match_name(a, b):
    """
    Try to find a name to attach to the result of an operation between
    a and b.  If only one of these has a `name` attribute, return that
    name.  Otherwise return a consensus name if they match of None if
    they have different names.

    Parameters
    ----------
    a : object
    b : object

    Returns
    -------
    name : str or None

    See Also
    --------
    pandas.core.common.consensus_name_attr
    """
    a_has = hasattr(a, "name")
    b_has = hasattr(b, "name")
    if a_has and b_has:
        if a.name == b.name:
            return a.name
        else:
            # TODO: what if they both have np.nan for their names?
            return None
    elif a_has:
        return a.name
    elif b_has:
        return b.name
    return None


def maybe_upcast_for_op(obj, shape: Tuple[int, ...]):
    """
    Cast non-pandas objects to pandas types to unify behavior of arithmetic
    and comparison operations.

    Parameters
    ----------
    obj: object
    shape : tuple[int]

    Returns
    -------
    out : object

    Notes
    -----
    Be careful to call this *after* determining the `name` attribute to be
    attached to the result of the arithmetic operation.
    """
    from pandas.core.arrays import DatetimeArray, TimedeltaArray

    if type(obj) is datetime.timedelta:
        # GH#22390  cast up to Timedelta to rely on Timedelta
        # implementation; otherwise operation against numeric-dtype
        # raises TypeError
        return Timedelta(obj)
    elif isinstance(obj, np.datetime64):
        # GH#28080 numpy casts integer-dtype to datetime64 when doing
        #  array[int] + datetime64, which we do not allow
        if isna(obj):
            # Avoid possible ambiguities with pd.NaT
            obj = obj.astype("datetime64[ns]")
            right = np.broadcast_to(obj, shape)
            return DatetimeArray(right)

        return Timestamp(obj)

    elif isinstance(obj, np.timedelta64):
        if isna(obj):
            # wrapping timedelta64("NaT") in Timedelta returns NaT,
            #  which would incorrectly be treated as a datetime-NaT, so
            #  we broadcast and wrap in a TimedeltaArray
            obj = obj.astype("timedelta64[ns]")
            right = np.broadcast_to(obj, shape)
            return TimedeltaArray(right)

        # In particular non-nanosecond timedelta64 needs to be cast to
        #  nanoseconds, or else we get undesired behavior like
        #  np.timedelta64(3, 'D') / 2 == np.timedelta64(1, 'D')
        return Timedelta(obj)

    elif isinstance(obj, np.ndarray) and is_timedelta64_dtype(obj.dtype):
        # GH#22390 Unfortunately we need to special-case right-hand
        # timedelta64 dtypes because numpy casts integer dtypes to
        # timedelta64 when operating with timedelta64
        return TimedeltaArray._from_sequence(obj)
    return obj


# -----------------------------------------------------------------------------


def _gen_eval_kwargs(name):
    """
    Find the keyword arguments to pass to numexpr for the given operation.

    Parameters
    ----------
    name : str

    Returns
    -------
    eval_kwargs : dict

    Examples
    --------
    >>> _gen_eval_kwargs("__add__")
    {}

    >>> _gen_eval_kwargs("rtruediv")
    {'reversed': True, 'truediv': True}
    """
    kwargs = {}

    # Series appear to only pass __add__, __radd__, ...
    # but DataFrame gets both these dunder names _and_ non-dunder names
    # add, radd, ...
    name = name.replace("__", "")

    if name.startswith("r"):
        if name not in ["radd", "rand", "ror", "rxor"]:
            # Exclude commutative operations
            kwargs["reversed"] = True

    return kwargs


def _get_frame_op_default_axis(name):
    """
    Only DataFrame cares about default_axis, specifically:
    special methods have default_axis=None and flex methods
    have default_axis='columns'.

    Parameters
    ----------
    name : str

    Returns
    -------
    default_axis: str or None
    """
    if name.replace("__r", "__") in ["__and__", "__or__", "__xor__"]:
        # bool methods
        return "columns"
    elif name.startswith("__"):
        # __add__, __mul__, ...
        return None
    else:
        # add, mul, ...
        return "columns"


def _get_opstr(op):
    """
    Find the operation string, if any, to pass to numexpr for this
    operation.

    Parameters
    ----------
    op : binary operator

    Returns
    -------
    op_str : string or None
    """

    return {
        operator.add: "+",
        radd: "+",
        operator.mul: "*",
        rmul: "*",
        operator.sub: "-",
        rsub: "-",
        operator.truediv: "/",
        rtruediv: "/",
        operator.floordiv: "//",
        rfloordiv: "//",
        operator.mod: None,  # TODO: Why None for mod but '%' for rmod?
        rmod: "%",
        operator.pow: "**",
        rpow: "**",
        operator.eq: "==",
        operator.ne: "!=",
        operator.le: "<=",
        operator.lt: "<",
        operator.ge: ">=",
        operator.gt: ">",
        operator.and_: "&",
        rand_: "&",
        operator.or_: "|",
        ror_: "|",
        operator.xor: "^",
        rxor: "^",
        divmod: None,
        rdivmod: None,
    }[op]


def _get_op_name(op, special):
    """
    Find the name to attach to this method according to conventions
    for special and non-special methods.

    Parameters
    ----------
    op : binary operator
    special : bool

    Returns
    -------
    op_name : str
    """
    opname = op.__name__.strip("_")
    if special:
        opname = "__{opname}__".format(opname=opname)
    return opname


# -----------------------------------------------------------------------------
# Masking NA values and fallbacks for operations numpy does not support


def fill_binop(left, right, fill_value):
    """
    If a non-None fill_value is given, replace null entries in left and right
    with this value, but only in positions where _one_ of left/right is null,
    not both.

    Parameters
    ----------
    left : array-like
    right : array-like
    fill_value : object

    Returns
    -------
    left : array-like
    right : array-like

    Notes
    -----
    Makes copies if fill_value is not None
    """
    # TODO: can we make a no-copy implementation?
    if fill_value is not None:
        left_mask = isna(left)
        right_mask = isna(right)
        left = left.copy()
        right = right.copy()

        # one but not both
        mask = left_mask ^ right_mask
        left[left_mask & mask] = fill_value
        right[right_mask & mask] = fill_value
    return left, right


# -----------------------------------------------------------------------------
# Dispatch logic

def dispatch_to_series(left, right, func, str_rep=None, axis=None, eval_kwargs=None):
    """
    Evaluate the frame operation func(left, right) by evaluating
    column-by-column, dispatching to the Series implementation.

    Parameters
    ----------
    left : DataFrame
    right : scalar or DataFrame
    func : arithmetic or comparison operator
    str_rep : str or None, default None
    axis : {None, 0, 1, "index", "columns"}

    Returns
    -------
    DataFrame
    """
    # Note: we use iloc to access columns for compat with cases
    #       with non-unique columns.
    eval_kwargs = eval_kwargs or {}

    import pandas.core.computation.expressions as expressions

    right = lib.item_from_zerodim(right)

    if lib.is_scalar(right) or np.ndim(right) == 0:

        new_blocks = []
        mgr = left._data
        for blk in mgr.blocks:
            # Reshape for EA Block
            blk_vals = blk.values
            if hasattr(blk_vals, "reshape"):
                # ndarray, DTA/TDA/PA
                blk_vals = blk_vals.reshape(blk.shape)
                blk_vals = blk_vals.T

            new_vals = array_op(blk_vals, right, func, str_rep, eval_kwargs)

            # Reshape for EA Block
            if is_extension_array_dtype(new_vals.dtype):
                from pandas.core.internals.blocks import make_block

                if hasattr(new_vals, "reshape"):
                    # ndarray, DTA/TDA/PA
                    new_vals = new_vals.reshape(blk.shape[::-1])
                    assert new_vals.shape[-1] == len(blk.mgr_locs)
                    for i in range(new_vals.shape[-1]):
                        nb = make_block(new_vals[..., i], placement=[blk.mgr_locs[i]])
                        new_blocks.append(nb)
                else:
                    # Categorical, IntegerArray
                    assert len(blk.mgr_locs) == 1
                    assert new_vals.shape == (blk.shape[-1],)
                    nb = make_block(new_vals, placement=blk.mgr_locs, ndim=2)
                    new_blocks.append(nb)
            elif blk.values.ndim == 1:
                # need to bump up to 2D
                new_vals = new_vals.reshape(-1, 1)
                assert new_vals.T.shape == blk.shape
                nb = blk.make_block(new_vals.T)
                new_blocks.append(nb)
            else:
                assert new_vals.T.shape == blk.shape
                nb = blk.make_block(new_vals.T)
                new_blocks.append(nb)

        bm = type(mgr)(new_blocks, mgr.axes)
        return type(left)(bm)

        def column_op(a, b):
            return {i: func(a.iloc[:, i], b) for i in range(len(a.columns))}

    elif isinstance(right, ABCDataFrame):
        assert right._indexed_same(left)

        def column_op(a, b):
            return {i: func(a.iloc[:, i], b.iloc[:, i]) for i in range(len(a.columns))}

    elif isinstance(right, ABCSeries) and axis == "columns":
        # We only get here if called via left._combine_match_columns,
        # in which case we specifically want to operate row-by-row
        assert right.index.equals(left.columns)

        if right.dtype == "timedelta64[ns]":
            # ensure we treat NaT values as the correct dtype
            # Note: we do not do this unconditionally as it may be lossy or
            #  expensive for EA dtypes.
            right = np.asarray(right)

            def column_op(a, b):
                return {i: func(a.iloc[:, i], b[i]) for i in range(len(a.columns))}

        else:

            def column_op(a, b):
                return {i: func(a.iloc[:, i], b.iloc[i]) for i in range(len(a.columns))}

    elif isinstance(right, ABCSeries):
        assert right.index.equals(left.index)  # Handle other cases later

        def column_op(a, b):
            return {i: func(a.iloc[:, i], b) for i in range(len(a.columns))}

    else:
        # Remaining cases have less-obvious dispatch rules
        raise NotImplementedError(right)

    new_data = expressions.evaluate(column_op, str_rep, left, right)
    return new_data


# -----------------------------------------------------------------------------
# Series


def _align_method_SERIES(left, right, align_asobject=False):
    """ align lhs and rhs Series """

    # ToDo: Different from _align_method_FRAME, list, tuple and ndarray
    # are not coerced here
    # because Series has inconsistencies described in #13637

    if isinstance(right, ABCSeries):
        # avoid repeated alignment
        if not left.index.equals(right.index):

            if align_asobject:
                # to keep original value's dtype for bool ops
                left = left.astype(object)
                right = right.astype(object)

            left, right = left.align(right, copy=False)

    return left, right


def _construct_result(left, result, index, name, dtype=None):
    """
    If the raw op result has a non-None name (e.g. it is an Index object) and
    the name argument is None, then passing name to the constructor will
    not be enough; we still need to override the name attribute.
    """
    out = left._constructor(result, index=index, dtype=dtype)
    out = out.__finalize__(left)

    # Set the result's name after __finalize__ is called because __finalize__
    #  would set it back to self.name
    out.name = name
    return out


def _construct_divmod_result(left, result, index, name, dtype=None):
    """divmod returns a tuple of like indexed series instead of a single series.
    """
    return (
        _construct_result(left, result[0], index=index, name=name, dtype=dtype),
        _construct_result(left, result[1], index=index, name=name, dtype=dtype),
    )


def _arith_method_SERIES(cls, op, special):
    """
    Wrapper function for Series arithmetic operations, to avoid
    code duplication.
    """
    str_rep = _get_opstr(op)
    op_name = _get_op_name(op, special)
    eval_kwargs = _gen_eval_kwargs(op_name)
    construct_result = (
        _construct_divmod_result if op in [divmod, rdivmod] else _construct_result
    )

    def wrapper(left, right):
        if isinstance(right, ABCDataFrame):
            return NotImplemented

        left, right = _align_method_SERIES(left, right)
        res_name = get_op_result_name(left, right)

        lvalues = extract_array(left, extract_numpy=True)
        result = arithmetic_op(lvalues, right, op, str_rep, eval_kwargs)

        # We do not pass dtype to ensure that the Series constructor
        #  does inference in the case where `result` has object-dtype.
        return construct_result(left, result, index=left.index, name=res_name)

    wrapper.__name__ = op_name
    return wrapper


def _comp_method_SERIES(cls, op, special):
    """
    Wrapper function for Series arithmetic operations, to avoid
    code duplication.
    """
    op_name = _get_op_name(op, special)

    def wrapper(self, other):

        res_name = get_op_result_name(self, other)

        if isinstance(other, ABCDataFrame):  # pragma: no cover
            # Defer to DataFrame implementation; fail early
            return NotImplemented

        if isinstance(other, ABCSeries) and not self._indexed_same(other):
            raise ValueError("Can only compare identically-labeled Series objects")

        lvalues = extract_array(self, extract_numpy=True)
        rvalues = extract_array(other, extract_numpy=True)

        res_values = comparison_op(lvalues, rvalues, op, None, {})

        return _construct_result(self, res_values, index=self.index, name=res_name)

    wrapper.__name__ = op_name
    return wrapper


def _bool_method_SERIES(cls, op, special):
    """
    Wrapper function for Series arithmetic operations, to avoid
    code duplication.
    """
    op_name = _get_op_name(op, special)

    def wrapper(self, other):
        self, other = _align_method_SERIES(self, other, align_asobject=True)
        res_name = get_op_result_name(self, other)

        if isinstance(other, ABCDataFrame):
            # Defer to DataFrame implementation; fail early
            return NotImplemented

        lvalues = extract_array(self, extract_numpy=True)
        rvalues = extract_array(other, extract_numpy=True)

        res_values = logical_op(lvalues, rvalues, op, None, {})
        return _construct_result(self, res_values, index=self.index, name=res_name)

    wrapper.__name__ = op_name
    return wrapper


def _flex_method_SERIES(cls, op, special):
    name = _get_op_name(op, special)
    doc = _make_flex_doc(name, "series")

    @Appender(doc)
    def flex_wrapper(self, other, level=None, fill_value=None, axis=0):
        # validate axis
        if axis is not None:
            self._get_axis_number(axis)
        if isinstance(other, ABCSeries):
            return self._binop(other, op, level=level, fill_value=fill_value)
        elif isinstance(other, (np.ndarray, list, tuple)):
            if len(other) != len(self):
                raise ValueError("Lengths must be equal")
            other = self._constructor(other, self.index)
            return self._binop(other, op, level=level, fill_value=fill_value)
        else:
            if fill_value is not None:
                self = self.fillna(fill_value)

            return self._constructor(op(self, other), self.index).__finalize__(self)

    flex_wrapper.__name__ = name
    return flex_wrapper


# -----------------------------------------------------------------------------
# DataFrame


def _combine_series_frame(self, other, func, fill_value=None, axis=None, level=None):
    """
    Apply binary operator `func` to self, other using alignment and fill
    conventions determined by the fill_value, axis, and level kwargs.

    Parameters
    ----------
    self : DataFrame
    other : Series
    func : binary operator
    fill_value : object, default None
    axis : {0, 1, 'columns', 'index', None}, default None
    level : int or None, default None

    Returns
    -------
    result : DataFrame
    """
    if fill_value is not None:
        raise NotImplementedError(
            "fill_value {fill} not supported.".format(fill=fill_value)
        )

    if axis is not None:
        axis = self._get_axis_number(axis)
        if axis == 0:
            return self._combine_match_index(other, func, level=level)
        else:
            return self._combine_match_columns(other, func, level=level)

    # default axis is columns
    return self._combine_match_columns(other, func, level=level)


def _align_method_FRAME(left, right, axis):
    """ convert rhs to meet lhs dims if input is list, tuple or np.ndarray """

    def to_series(right):
        msg = "Unable to coerce to Series, length must be {req_len}: given {given_len}"
        if axis is not None and left._get_axis_name(axis) == "index":
            if len(left.index) != len(right):
                raise ValueError(
                    msg.format(req_len=len(left.index), given_len=len(right))
                )
            right = left._constructor_sliced(right, index=left.index)
        else:
            if len(left.columns) != len(right):
                raise ValueError(
                    msg.format(req_len=len(left.columns), given_len=len(right))
                )
            right = left._constructor_sliced(right, index=left.columns)
        return right

    if isinstance(right, np.ndarray):

        if right.ndim == 1:
            right = to_series(right)

        elif right.ndim == 2:
            if right.shape == left.shape:
                right = left._constructor(right, index=left.index, columns=left.columns)

            elif right.shape[0] == left.shape[0] and right.shape[1] == 1:
                # Broadcast across columns
                right = np.broadcast_to(right, left.shape)
                right = left._constructor(right, index=left.index, columns=left.columns)

            elif right.shape[1] == left.shape[1] and right.shape[0] == 1:
                # Broadcast along rows
                right = to_series(right[0, :])

            else:
                raise ValueError(
                    "Unable to coerce to DataFrame, shape "
                    "must be {req_shape}: given {given_shape}".format(
                        req_shape=left.shape, given_shape=right.shape
                    )
                )

        elif right.ndim > 2:
            raise ValueError(
                "Unable to coerce to Series/DataFrame, dim "
                "must be <= 2: {dim}".format(dim=right.shape)
            )

    elif is_list_like(right) and not isinstance(right, (ABCSeries, ABCDataFrame)):
        # GH17901
        right = to_series(right)

    return right


def _arith_method_FRAME(cls, op, special):
    str_rep = _get_opstr(op)
    op_name = _get_op_name(op, special)
    eval_kwargs = _gen_eval_kwargs(op_name)
    default_axis = _get_frame_op_default_axis(op_name)

    na_op = define_na_arithmetic_op(op, str_rep, eval_kwargs)

    if op_name in _op_descriptions:
        # i.e. include "add" but not "__add__"
        doc = _make_flex_doc(op_name, "dataframe")
    else:
        doc = _arith_doc_FRAME % op_name

    @Appender(doc)
    def f(self, other, axis=default_axis, level=None, fill_value=None):

        other = _align_method_FRAME(self, other, axis)

        if isinstance(other, ABCDataFrame):
            # Another DataFrame
            pass_op = op if should_series_dispatch(self, other, op) else na_op
            return self._combine_frame(other, pass_op, fill_value, level)
        elif isinstance(other, ABCSeries):
            # For these values of `axis`, we end up dispatching to Series op,
            # so do not want the masked op.
            pass_op = op if axis in [0, "columns", None] else na_op
            return _combine_series_frame(
                self, other, pass_op, fill_value=fill_value, axis=axis, level=level
            )
        else:
            # in this case we always have `np.ndim(other) == 0`
            if fill_value is not None:
                self = self.fillna(fill_value)

            new_data = dispatch_to_series(self, other, op, str_rep=str_rep, eval_kwargs=eval_kwargs)
            return self._construct_result(new_data)

    f.__name__ = op_name

    return f


def _flex_comp_method_FRAME(cls, op, special):
    str_rep = _get_opstr(op)
    op_name = _get_op_name(op, special)
    default_axis = _get_frame_op_default_axis(op_name)

    doc = _flex_comp_doc_FRAME.format(
        op_name=op_name, desc=_op_descriptions[op_name]["desc"]
    )

    @Appender(doc)
    def f(self, other, axis=default_axis, level=None):

        other = _align_method_FRAME(self, other, axis)

        if isinstance(other, ABCDataFrame):
            # Another DataFrame
            if not self._indexed_same(other):
                self, other = self.align(other, "outer", level=level, copy=False)
            new_data = dispatch_to_series(self, other, op, str_rep=str_rep, eval_kwargs={})
            return self._construct_result(new_data)

        elif isinstance(other, ABCSeries):
            return _combine_series_frame(
                self, other, op, fill_value=None, axis=axis, level=level
            )
        else:
            # in this case we always have `np.ndim(other) == 0`
            new_data = dispatch_to_series(self, other, op)
            return self._construct_result(new_data)

    f.__name__ = op_name

    return f


def _comp_method_FRAME(cls, func, special):
    str_rep = _get_opstr(func)
    op_name = _get_op_name(func, special)

    @Appender("Wrapper for comparison method {name}".format(name=op_name))
    def f(self, other):

        other = _align_method_FRAME(self, other, axis=None)

        if isinstance(other, ABCDataFrame):
            # Another DataFrame
            if not self._indexed_same(other):
                raise ValueError(
                    "Can only compare identically-labeled DataFrame objects"
                )
            new_data = dispatch_to_series(self, other, func, str_rep=str_rep, eval_kwargs={})
            return self._construct_result(new_data)

        elif isinstance(other, ABCSeries):
            return _combine_series_frame(
                self, other, func, fill_value=None, axis=None, level=None
            )
        else:

            # straight boolean comparisons we want to allow all columns
            # (regardless of dtype to pass thru) See #4537 for discussion.
            new_data = dispatch_to_series(self, other, func)
            return self._construct_result(new_data)

    f.__name__ = op_name

    return f

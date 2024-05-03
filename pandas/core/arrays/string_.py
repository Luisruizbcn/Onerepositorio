from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    ClassVar,
    Literal,
    cast,
)

import numpy as np

from pandas._config import get_option

from pandas._libs import (
    lib,
    missing as libmissing,
)
from pandas._libs.arrays import NDArrayBacked
from pandas._libs.lib import ensure_string_array
from pandas.compat import (
    is_numpy_dev,
    pa_version_under10p1,
)
from pandas.compat.numpy import function as nv
from pandas.util._decorators import doc

from pandas.core.dtypes.base import (
    ExtensionDtype,
    StorageExtensionDtype,
    register_extension_dtype,
)
from pandas.core.dtypes.common import (
    get_numpy_string_dtype_instance,
    is_array_like,
    is_bool_dtype,
    is_integer_dtype,
    is_object_dtype,
    is_string_dtype,
    pandas_dtype,
)

from pandas.core import ops
from pandas.core.array_algos import masked_reductions
from pandas.core.arrays.base import ExtensionArray
from pandas.core.arrays.boolean import BooleanArray
from pandas.core.arrays.floating import (
    FloatingArray,
    FloatingDtype,
)
from pandas.core.arrays.integer import (
    IntegerArray,
    IntegerDtype,
)
from pandas.core.arrays.numpy_ import NumpyExtensionArray
from pandas.core.construction import extract_array
from pandas.core.indexers import check_array_indexer
from pandas.core.missing import isna

if TYPE_CHECKING:
    import pyarrow

    from pandas._typing import (
        AxisInt,
        Dtype,
        DtypeObj,
        NumpySorter,
        NumpyValueArrayLike,
        Scalar,
        Self,
        npt,
        type_t,
    )

    from pandas import Series


@register_extension_dtype
class StringDtype(StorageExtensionDtype):
    """
    Extension dtype for string data.

    .. warning::

       StringDtype is considered experimental. The implementation and
       parts of the API may change without warning.

    Parameters
    ----------
    storage : {"python", "pyarrow", "numpy", "pyarrow_numpy"}, optional
        If not given, the value of ``pd.options.mode.string_storage``.

    Attributes
    ----------
    None

    Methods
    -------
    None

    See Also
    --------
    BooleanDtype : Extension dtype for boolean data.

    Examples
    --------
    >>> pd.StringDtype()
    string[python]

    >>> pd.StringDtype(storage="pyarrow")
    string[pyarrow]
    """

    # error: Cannot override instance variable (previously declared on
    # base class "StorageExtensionDtype") with class variable
    name: ClassVar[str] = "string"  # type: ignore[misc]

    #: StringDtype().na_value uses pandas.NA except the implementation that
    # follows NumPy semantics, which uses nan.
    @property
    def na_value(self) -> libmissing.NAType | float:  # type: ignore[override]
        if self.storage == "pyarrow_numpy":
            return np.nan
        else:
            return libmissing.NA

    _metadata = ("storage",)

    def __init__(self, storage=None) -> None:
        if storage is None:
            infer_string = get_option("future.infer_string")
            if infer_string:
                storage = "pyarrow_numpy"
            else:
                storage = get_option("mode.string_storage")
        if storage not in {"python", "pyarrow", "numpy", "pyarrow_numpy"}:
            raise ValueError(
                "Storage must be 'python', 'pyarrow', 'pyarrow_numpy', "
                f"or 'numpy'. Got {storage} instead."
            )
        if storage in ("pyarrow", "pyarrow_numpy") and pa_version_under10p1:
            raise ImportError(
                "pyarrow>=10.0.1 is required for PyArrow backed StringArray."
            )
        if storage == "numpy" and not is_numpy_dev:
            raise ImportError("NumPy backed string storage requires numpy dev")
        self.storage = storage

    @property
    def type(self) -> type[str]:
        return str

    @classmethod
    def construct_from_string(cls, string) -> Self:
        """
        Construct a StringDtype from a string.

        Parameters
        ----------
        string : str
            The type of the name. The storage type will be taking from `string`.
            Valid options and their storage types are

            ========================== ==============================================
            string                     result storage
            ========================== ==============================================
            ``'string'``               pd.options.mode.string_storage, default python
            ``'string[python]'``       python
            ``'string[pyarrow]'``      pyarrow
            ``'string[numpy]'``        numpy
            ========================== ==============================================

        Returns
        -------
        StringDtype

        Raise
        -----
        TypeError
            If the string is not a valid option.
        """
        if not isinstance(string, str):
            raise TypeError(
                f"'construct_from_string' expects a string, got {type(string)}"
            )
        if string == "string":
            return cls()
        elif string == "string[python]":
            return cls(storage="python")
        elif string == "string[pyarrow]":
            return cls(storage="pyarrow")
        elif string == "string[numpy]":
            return cls(storage="numpy")
        elif string == "string[pyarrow_numpy]":
            return cls(storage="pyarrow_numpy")
        else:
            raise TypeError(f"Cannot construct a '{cls.__name__}' from '{string}'")

    # https://github.com/pandas-dev/pandas/issues/36126
    # error: Signature of "construct_array_type" incompatible with supertype
    # "ExtensionDtype"
    def construct_array_type(  # type: ignore[override]
        self,
    ) -> type_t[BaseStringArray]:
        """
        Return the array type associated with this dtype.

        Returns
        -------
        type
        """
        from pandas.core.arrays.string_arrow import (
            ArrowStringArray,
            ArrowStringArrayNumpySemantics,
        )

        if self.storage == "python":
            return ObjectStringArray
        elif self.storage == "pyarrow":
            return ArrowStringArray
        elif self.storage == "numpy":
            return NumpyStringArray
        elif self.storage == "pyarrow_numpy":
            return ArrowStringArrayNumpySemantics
        else:
            raise NotImplementedError

    def __from_arrow__(
        self, array: pyarrow.Array | pyarrow.ChunkedArray
    ) -> BaseStringArray:
        """
        Construct StringArray from pyarrow Array/ChunkedArray.
        """
        if self.storage == "pyarrow":
            from pandas.core.arrays.string_arrow import ArrowStringArray

            return ArrowStringArray(array)
        elif self.storage == "pyarrow_numpy":
            from pandas.core.arrays.string_arrow import ArrowStringArrayNumpySemantics

            return ArrowStringArrayNumpySemantics(array)
        else:
            import pyarrow

            if isinstance(array, pyarrow.Array):
                chunks = [array]
            else:
                # pyarrow.ChunkedArray
                chunks = array.chunks

            results = []
            for arr in chunks:
                # convert chunk by chunk to numpy and concatenate then, to avoid
                # overflow for large string data when concatenating the pyarrow arrays
                arr = arr.to_numpy(zero_copy_only=False)
                arr = ensure_string_array(arr, na_value=libmissing.NA)
                results.append(arr)

        if len(chunks) == 0:
            arr = np.array([], dtype=object)
        else:
            arr = np.concatenate(results)

        # Bypass validation inside StringArray constructor, see GH#47781
        new_string_array = StringArray.__new__(StringArray)
        NDArrayBacked.__init__(
            new_string_array,
            arr,
            StringDtype(storage="python"),
        )
        return new_string_array


class BaseStringArray(ExtensionArray):
    """
    Mixin class for StringArray, ArrowStringArray.
    """

    @doc(ExtensionArray.tolist)
    def tolist(self) -> list:
        if self.ndim > 1:
            return [x.tolist() for x in self]
        return list(self.to_numpy())

    @classmethod
    def _from_scalars(cls, scalars, dtype: DtypeObj) -> Self:
        if lib.infer_dtype(scalars, skipna=True) not in ["string", "empty"]:
            # TODO: require any NAs be valid-for-string
            raise ValueError
        return cls._from_sequence(scalars, dtype=dtype)


# error: Definition of "_concat_same_type" in base class "NDArrayBacked" is
# incompatible with definition in base class "ExtensionArray"
class BaseNumpyStringArray(BaseStringArray, NumpyExtensionArray):  # type: ignore[misc]
    """
    Extension array for string data.

    .. warning::

       StringArray is considered experimental. The implementation and
       parts of the API may change without warning.

    Parameters
    ----------
    values : array-like
        The array of data.

        .. warning::

           Currently, this expects an object-dtype ndarray
           where the elements are Python strings
           or nan-likes (``None``, ``np.nan``, ``NA``).
           This may change without warning in the future. Use
           :meth:`pandas.array` with ``dtype="string"`` for a stable way of
           creating a `StringArray` from any sequence.

        .. versionchanged:: 1.5.0

           StringArray now accepts array-likes containing
           nan-likes(``None``, ``np.nan``) for the ``values`` parameter
           in addition to strings and :attr:`pandas.NA`

    copy : bool, default False
        Whether to copy the array of data.

    Attributes
    ----------
    None

    Methods
    -------
    None

    See Also
    --------
    :func:`array`
        The recommended function for creating a StringArray.
    Series.str
        The string methods are available on Series backed by
        a StringArray.

    Notes
    -----
    StringArray returns a BooleanArray for comparison methods.

    Examples
    --------
    >>> pd.array(["This is", "some text", None, "data."], dtype="string")
    <StringArray>
    ['This is', 'some text', <NA>, 'data.']
    Length: 4, dtype: string

    Unlike arrays instantiated with ``dtype="object"``, ``StringArray``
    will convert the values to strings.

    >>> pd.array(["1", 1], dtype="object")
    <NumpyExtensionArray>
    ['1', 1]
    Length: 2, dtype: object
    >>> pd.array(["1", 1], dtype="string")
    <StringArray>
    ['1', '1']
    Length: 2, dtype: string

    However, instantiating StringArrays directly with non-strings will raise an error.

    For comparison methods, `StringArray` returns a :class:`pandas.BooleanArray`:

    >>> pd.array(["a", None, "c"], dtype="string") == "a"
    <BooleanArray>
    [True, <NA>, False]
    Length: 3, dtype: boolean
    """

    # undo the NumpyExtensionArray hack
    _typ = "extension"

    def __init__(self, values, copy: bool = False) -> None:
        values = extract_array(values)

        super().__init__(values, copy=copy)
        if not isinstance(values, type(self)):
            self._validate()
        NDArrayBacked.__init__(self, self._ndarray, StringDtype(storage=self._storage))

    def _validate(self) -> None:
        """Validate that we only store NA or strings."""
        if len(self._ndarray) and not lib.is_string_array(self._ndarray, skipna=True):
            raise ValueError("StringArray requires a sequence of strings or pandas.NA")
        if self._ndarray.dtype != "object":
            raise ValueError(
                "StringArray requires a sequence of strings or pandas.NA. Got "
                f"'{self._ndarray.dtype}' dtype instead."
            )

    @classmethod
    def _from_sequence_of_strings(
        cls, strings, *, dtype: ExtensionDtype, copy: bool = False
    ) -> Self:
        return cls._from_sequence(strings, dtype=dtype, copy=copy)

    @classmethod
    def _empty(cls, shape, dtype) -> StringArray:
        values = np.empty(shape, dtype=get_numpy_string_dtype_instance())
        values[:] = libmissing.NA
        return cls(values).astype(dtype, copy=False)

    def __arrow_array__(self, type=None):
        """
        Convert myself into a pyarrow Array.
        """
        import pyarrow as pa

        if type is None:
            type = pa.string()

        values = self._ndarray.astype("object").copy()
        values[self.isna()] = None
        return pa.array(values, type=type, from_pandas=True)

    def _values_for_factorize(self) -> tuple[np.ndarray, None]:
        arr = self._ndarray.copy()
        mask = self.isna()
        arr[mask] = None
        return arr, None

    def __setitem__(self, key, value) -> None:
        value = extract_array(value, extract_numpy=True)
        if isinstance(value, type(self)):
            # extract_array doesn't extract NumpyExtensionArray subclasses
            value = value._ndarray

        key = check_array_indexer(self, key)
        scalar_key = lib.is_scalar(key)
        scalar_value = lib.is_scalar(value)
        if scalar_key and not scalar_value:
            raise ValueError("setting an array element with a sequence.")

        # validate new items
        if scalar_value:
            if isna(value):
                value = libmissing.NA
            elif not isinstance(value, str):
                raise TypeError(
                    f"Cannot set non-string value '{value}' into a StringArray."
                )
        else:
            if not is_array_like(value):
                value = np.asarray(value, dtype=object)
            if len(value) and not lib.is_string_array(value, skipna=True):
                raise TypeError("Must provide strings.")

            mask = isna(value)
            if mask.any():
                value = value.copy()
                value[isna(value)] = libmissing.NA

        super().__setitem__(key, value)

    def _putmask(self, mask: npt.NDArray[np.bool_], value) -> None:
        # the super() method NDArrayBackedExtensionArray._putmask uses
        # np.putmask which doesn't properly handle None/pd.NA, so using the
        # base class implementation that uses __setitem__
        ExtensionArray._putmask(self, mask, value)

    def _validate(self):
        """Validate that we only store NA or strings."""
        if len(self._ndarray) and not lib.is_string_array(self._ndarray, skipna=True):
            raise ValueError("StringArray requires a sequence of strings or pandas.NA")
        if self._ndarray.dtype != "object":
            raise ValueError(
                f"{type(self).__name__} requires a sequence of strings or "
                "pandas.NA convertible to a NumPy array with dtype "
                f"'object'. Got '{self._ndarray.dtype}' dtype instead."
            )

    def astype(self, dtype, copy: bool = True):
        dtype = pandas_dtype(dtype)

        if dtype == self.dtype:
            if copy:
                return self.copy()
            return self

        elif isinstance(dtype, IntegerDtype):
            arr = self._ndarray.copy()
            mask = self.isna()
            arr[mask] = "0"
            values = arr.astype(dtype.numpy_dtype)
            return IntegerArray(values, mask, copy=False)
        elif isinstance(dtype, FloatingDtype):
            arr_ea = self.copy()
            mask = self.isna()
            arr_ea[mask] = "0"
            values = arr_ea.astype(dtype.numpy_dtype)
            return FloatingArray(values, mask, copy=False)
        elif isinstance(dtype, ExtensionDtype):
            # Skip the NumpyExtensionArray.astype method
            return ExtensionArray.astype(self, dtype, copy)
        elif np.issubdtype(dtype, np.floating):
            arr = self._ndarray.copy()
            mask = self.isna()
            arr[mask] = "0"
            values = arr.astype(dtype)
            values[mask] = np.nan
            return values

        return super().astype(dtype, copy)

    def _reduce(
        self, name: str, *, skipna: bool = True, axis: AxisInt | None = 0, **kwargs
    ):
        if name in ["min", "max"]:
            return getattr(self, name)(skipna=skipna, axis=axis)

        raise TypeError(f"Cannot perform reduction '{name}' with string dtype")

    def min(self, axis=None, skipna: bool = True, **kwargs) -> Scalar:
        nv.validate_min((), kwargs)
        result = masked_reductions.min(
            values=self.to_numpy(), mask=self.isna(), skipna=skipna
        )
        return self._wrap_reduction_result(axis, result)

    def max(self, axis=None, skipna: bool = True, **kwargs) -> Scalar:
        nv.validate_max((), kwargs)
        result = masked_reductions.max(
            values=self.to_numpy(), mask=self.isna(), skipna=skipna
        )
        return self._wrap_reduction_result(axis, result)

    def value_counts(self, dropna: bool = True) -> Series:
        from pandas.core.algorithms import value_counts_internal as value_counts

        result = value_counts(self._ndarray, sort=False, dropna=dropna).astype("Int64")
        result.index = result.index.astype(self.dtype)
        return result

    def memory_usage(self, deep: bool = False) -> int:
        result = self._ndarray.nbytes
        return result

    @doc(ExtensionArray.searchsorted)
    def searchsorted(
        self,
        value: NumpyValueArrayLike | ExtensionArray,
        side: Literal["left", "right"] = "left",
        sorter: NumpySorter | None = None,
    ) -> npt.NDArray[np.intp] | np.intp:
        if self._hasna:
            raise ValueError(
                "searchsorted requires array to be sorted, which is impossible "
                "with NAs present."
            )
        return super().searchsorted(value=value, side=side, sorter=sorter)

    def _cmp_method(self, other, op):
        from pandas.arrays import BooleanArray

        if isinstance(other, StringArray):
            other = other._ndarray

        mask = isna(self) | isna(other)
        valid = ~mask

        if not lib.is_scalar(other):
            if len(other) != len(self):
                # prevent improper broadcasting when other is 2D
                raise ValueError(
                    f"Lengths of operands do not match: {len(self)} != {len(other)}"
                )

            other = np.asarray(other)
            other = other[valid].astype(self._ndarray.dtype)

        if op.__name__ in ops.ARITHMETIC_BINOPS:
            result = np.empty_like(self._ndarray)
            result[mask] = libmissing.NA
            result[valid] = op(self._ndarray[valid], other)
            return type(self)(result)
        else:
            # logical
            result = np.zeros(len(self._ndarray), dtype="bool")
            try:
                result[valid] = op(self._ndarray[valid], other)
            except TypeError:
                if hasattr(other, "_ndarray"):
                    other_type = other._ndarray.dtype
                else:
                    other_type = type(other)
                raise TypeError(
                    f"'{op.__name__}' operator not supported between "
                    f"'{self._ndarray.dtype}' and '{other_type}'"
                )
            return BooleanArray(result, mask)

    _arith_method = _cmp_method

    # ------------------------------------------------------------------------
    # String methods interface
    # error: Incompatible types in assignment (expression has type "NAType",
    # base class "NumpyExtensionArray" defined the type as "float")
    _str_na_value = libmissing.NA  # type: ignore[assignment]

    def _str_map(
        self, f, na_value=None, dtype: Dtype | None = None, convert: bool = True
    ):
        from pandas.arrays import BooleanArray

        if dtype is None:
            dtype = StringDtype(storage="python")
        if na_value is None:
            na_value = self.dtype.na_value

        mask = isna(self)
        arr = np.asarray(self)

        if is_integer_dtype(dtype) or is_bool_dtype(dtype):
            constructor: type[IntegerArray | BooleanArray]
            if is_integer_dtype(dtype):
                constructor = IntegerArray
            else:
                constructor = BooleanArray

            na_value_is_na = isna(na_value)
            if na_value_is_na:
                na_value = 1
            elif dtype == np.dtype("bool"):
                na_value = bool(na_value)
            result = lib.map_infer_mask(
                arr,
                f,
                mask.view("uint8"),
                convert=False,
                na_value=na_value,
                # error: Argument 1 to "dtype" has incompatible type
                # "Union[ExtensionDtype, str, dtype[Any], Type[object]]"; expected
                # "Type[object]"
                dtype=np.dtype(cast(type, dtype)),
            )

            if not na_value_is_na:
                mask[:] = False

            return constructor(result, mask)

        elif is_string_dtype(dtype) and not is_object_dtype(dtype):
            # i.e. StringDtype
            result = lib.map_infer_mask(
                arr, f, mask.view("uint8"), convert=False, na_value=na_value
            )
            return StringArray(result)
        else:
            # This is when the result type is object. We reach this when
            # -> We know the result type is truly object (e.g. .encode returns bytes
            #    or .findall returns a list).
            # -> We don't know the result type. E.g. `.get` can return anything.
            return lib.map_infer_mask(arr, f, mask.view("uint8"))


class ObjectStringArray(BaseNumpyStringArray):
    _na_value = None
    _storage = "python"

    @classmethod
    def _empty(cls, shape, dtype) -> StringArray:
        values = np.empty(shape, dtype=object)
        values[:] = libmissing.NA
        return cls(values).astype(dtype, copy=False)

    def _validate(self):
        super()._validate()
        # Check to see if need to convert Na values to pd.NA
        if self._ndarray.ndim > 2:
            # Ravel if ndims > 2 b/c no cythonized version available
            lib.convert_nans_to_NA(self._ndarray.ravel("K"))
        else:
            lib.convert_nans_to_NA(self._ndarray)

    def _values_for_factorize(self):
        arr = self._ndarray.copy()
        mask = self.isna()
        arr[mask] = None
        return arr, None

    @classmethod
    def _from_sequence(
        cls, scalars, *, dtype: Dtype | None = None, copy: bool = False
    ) -> Self:
        if dtype and not (isinstance(dtype, str) and dtype == "string"):
            dtype = pandas_dtype(dtype)
            assert isinstance(dtype, StringDtype) and dtype.storage == "python"

        from pandas.core.arrays.masked import BaseMaskedArray

        if isinstance(scalars, BaseMaskedArray):
            # avoid costly conversion to object dtype
            na_values = scalars._mask
            result = scalars._data
            result = lib.ensure_string_array(result, copy=copy, convert_na_value=False)
            result[na_values] = libmissing.NA

        else:
            if lib.is_pyarrow_array(scalars):
                # pyarrow array; we cannot rely on the "to_numpy" check in
                #  ensure_string_array because calling scalars.to_numpy would set
                #  zero_copy_only to True which caused problems see GH#52076
                scalars = np.array(scalars)
            # convert non-na-likes to str, and nan-likes to StringDtype().na_value
            result = lib.ensure_string_array(scalars, na_value=libmissing.NA, copy=copy)

        # Manually creating new array avoids the validation step in the __init__, so is
        # faster. Refactor need for validation?
        new_string_array = cls.__new__(cls)
        NDArrayBacked.__init__(new_string_array, result, StringDtype(storage="python"))

        return new_string_array

    def memory_usage(self, deep: bool = False) -> int:
        ret = super().memory_usage()
        if deep:
            ret += lib.memory_usage_of_objects(self._ndarray)
        return ret


StringArray = ObjectStringArray


class NumpyStringArray(BaseNumpyStringArray):
    _na_value = libmissing.NA
    _storage = "numpy"
    _ctor_err_msg = "StringArray requires a sequence of strings or pandas.NA"

    def __init__(self, values, copy: bool = False) -> None:
        try:
            arr_values = np.asarray(values)
        except (TypeError, ValueError):
            raise ValueError(self._ctor_err_msg)
        default_dtype = get_numpy_string_dtype_instance(
            possible_dtype=getattr(arr_values, "dtype", None))
        # this check exists purely to satisfy test_constructor_raises and could
        # be deleted if that restriction was relaxed for NumpyStringArray
        if (((arr_values.dtype.char == "d" and arr_values.size == 0) or
             (arr_values.dtype.char == "S"))):
            raise ValueError(self._ctor_err_msg)
        try:
            str_values = arr_values.astype(default_dtype, copy=copy)
        except ValueError:
            # we want to emulate ObjectStringArray, which accepts nan and None
            # as valid missing values
            if arr_values.dtype.kind == "O":
                # try again with NA set to np.nan or None
                str_values = None
                for na_object in (np.nan, None):
                    try:
                        dtype = get_numpy_string_dtype_instance(
                            na_object=na_object, coerce=False)
                        str_values = arr_values.astype(dtype)
                        continue
                    except ValueError:
                        pass
                if str_values is None:
                    raise ValueError(self._ctor_err_msg)
                else:
                    str_values = str_values.astype(default_dtype)
            else:
                raise ValueError(self._ctor_err_msg)
        super().__init__(str_values, copy=copy)

    @classmethod
    def _from_sequence(cls, scalars, *, dtype: Dtype | None = None, copy: bool = False):
        na_mask, any_na = libmissing.isnaobj(np.array(scalars, dtype=object), check_for_any_na=True)
        arr = np.asarray(scalars)
        if is_object_dtype(arr.dtype):
            result = np.empty(arr.shape, dtype=get_numpy_string_dtype_instance(coerce=True))
            result[~na_mask] = arr[~na_mask]
            if any_na:
                result[na_mask] = libmissing.NA
            # TODO avoid copy
            # could temporarily set coerce=True but that's not possible at the moment
            result = result.astype(get_numpy_string_dtype_instance())
        else:
            result = arr.astype(get_numpy_string_dtype_instance(), copy=False)
            if any_na:
                result[na_mask] = libmissing.NA

        # Manually creating with new array avoids the validation step in the
        # __init__, so is faster. Refactor need for validation?
        new_string_array = cls.__new__(cls)
        NDArrayBacked.__init__(
            new_string_array, result, StringDtype(storage=cls._storage)
        )

        return new_string_array

    def _values_for_factorize(self):
        arr = self._ndarray.copy()
        # sentinel value used by StringHashTable
        arr[np.isnan(arr)] = "__nan__"
        return arr, "__nan__"

    @classmethod
    def _from_factorized(cls, values, original):
        values[values == "__nan__"] = libmissing.NA
        return original._from_backing_data(values)

    @classmethod
    def _empty(cls, shape, dtype) -> StringArray:
        values = np.empty(shape, dtype=get_numpy_string_dtype_instance())
        return cls(values).astype(dtype, copy=False)

    def _validate(self):
        """Validate that we only store NA or strings."""
        if len(self._ndarray) and not lib.is_string_array(self._ndarray, skipna=True):
            raise ValueError("StringArray requires a sequence of strings or pandas.NA")
        if self._ndarray.dtype != get_numpy_string_dtype_instance():
            raise ValueError(
                f"{type(self).__name__} requires a sequence of strings or "
                "pandas.NA convertible to a NumPy array with dtype "
                f"{get_numpy_string_dtype_instance()}. Got "
                f"'{self._ndarray.dtype}' dtype instead."
            )

    def _validate_setitem_value(self, value):
        if value is np.nan:
            value = np.array(libmissing.NA, dtype=get_numpy_string_dtype_instance())
        return value

    def _validate_scalar(self, fill_value):
        fill_value = super()._validate_scalar(fill_value)
        if fill_value is np.nan:
            fill_value = self.dtype.na_value
        if not isinstance(fill_value, str) and fill_value is not self.dtype.na_value:
            raise ValueError("StringArray requires a sequence of strings or pandas.NA")
        return fill_value

    def to_numpy(
        self,
        dtype: npt.DTypeLike | None = None,
        copy: bool = False,
        na_value: object = lib.no_default,
    ) -> np.ndarray:
        if dtype is None and na_value is not lib.no_default:
            dtype = get_numpy_string_dtype_instance(na_object=na_value)
        return super().to_numpy(dtype, copy, na_value)

    def _str_endswith(self, pat, na=None) -> BooleanArray:
        if isinstance(pat, tuple) or na is not None:
            return super()._str_endswith(pat, na)
        pat = np.asarray(pat, dtype=get_numpy_string_dtype_instance())
        result = np.strings.endswith(self._ndarray, pat)
        return BooleanArray(result, isna(self._ndarray))

    def _str_find(self, sub, start: int = 0, end=None) -> IntegerArray:
        sub = np.asarray(sub, dtype=get_numpy_string_dtype_instance())
        na_mask = isna(self._ndarray)
        result = np.empty_like(self._ndarray, dtype='int64')
        result[~na_mask] = np.strings.find(
            self._ndarray[~na_mask], sub, start, end)
        return IntegerArray(result, na_mask)

    def _str_rfind(self, sub, start: int = 0, end=None) -> IntegerArray:
        sub = np.asarray(sub, dtype=get_numpy_string_dtype_instance())
        na_mask = isna(self._ndarray)
        result = np.empty_like(self._ndarray, dtype='int64')
        result[~na_mask] = np.strings.rfind(
            self._ndarray[~na_mask], sub, start, end)
        return IntegerArray(result, na_mask)

    def _str_index(self, sub, start: int = 0, end=None) -> IntegerArray:
        sub = np.asarray(sub, dtype=get_numpy_string_dtype_instance())
        na_mask = isna(self._ndarray)
        result = np.empty_like(self._ndarray, dtype='int64')
        result[~na_mask] = np.strings.index(
            self._ndarray[~na_mask], sub, start, end)
        return IntegerArray(result, na_mask)

    def _str_rindex(self, sub, start: int = 0, end=None) -> IntegerArray:
        sub = np.asarray(sub, dtype=get_numpy_string_dtype_instance())
        na_mask = isna(self._ndarray)
        result = np.empty_like(self._ndarray, dtype='int64')
        result[~na_mask] = np.strings.rindex(
            self._ndarray[~na_mask], sub, start, end)
        return IntegerArray(result, na_mask)

    def _str_isalnum(self) -> BooleanArray:
        result = np.strings.isalnum(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_isalpha(self) -> BooleanArray:
        result = np.strings.isalpha(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_isdigit(self) -> BooleanArray:
        result = np.strings.isdigit(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_isdecimal(self) -> BooleanArray:
        result = np.strings.isdecimal(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_islower(self) -> BooleanArray:
        result = np.strings.islower(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_isnumeric(self) -> BooleanArray:
        result = np.strings.isnumeric(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_isspace(self) -> BooleanArray:
        result = np.strings.isspace(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_istitle(self) -> BooleanArray:
        result = np.strings.istitle(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_isupper(self) -> BooleanArray:
        result = np.strings.isupper(self._ndarray)
        return BooleanArray(result, isna(self._ndarray))

    def _str_len(self) -> IntegerArray:
        result = np.strings.str_len(self._ndarray)
        return IntegerArray(result, isna(self._ndarray))

    def _str_lstrip(self, to_strip=None):
        if to_strip is not None:
            to_strip = np.asarray(to_strip, dtype=get_numpy_string_dtype_instance())
        return np.strings.lstrip(self._ndarray, to_strip)

    def _str_replace(self, pat, repl, n=-1, case=None, flags=0, regex=False):
        if regex:
            super()._str_replace(pat, repl, n, case, flags, regex)
        pat = np.asarray(pat, dtype=get_numpy_string_dtype_instance())
        repl = np.asarray(repl, dtype=get_numpy_string_dtype_instance())
        return np.strings.replace(self._ndarray, pat, repl, n)

    def _str_rstrip(self, to_strip=None):
        if to_strip is not None:
            to_strip = np.asarray(to_strip, dtype=get_numpy_string_dtype_instance())
        return np.strings.rstrip(self._ndarray, to_strip)

    def _str_strip(self, to_strip=None):
        if to_strip is not None:
            to_strip = np.asarray(to_strip, dtype=get_numpy_string_dtype_instance())
        return np.strings.strip(self._ndarray, to_strip)

    def _str_startswith(self, pat, na=None) -> BooleanArray:
        if isinstance(pat, tuple) or na is not None:
            return super()._str_startswith(pat, na)
        pat = np.asarray(pat, dtype=get_numpy_string_dtype_instance())
        result = np.strings.startswith(self._ndarray, pat)
        return BooleanArray(result, isna(self._ndarray))

    def _str_zfill(self, width):
        return np.strings.zfill(self._ndarray, width)

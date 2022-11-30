from __future__ import annotations

import bz2
from functools import wraps
import gzip
import io
import socket
import tarfile
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
)
import urllib.error
import zipfile

from pandas._typing import (
    FilePath,
    ReadPickleBuffer,
)
from pandas.compat import get_lzma_file
from pandas.compat._optional import import_optional_dependency

import pandas as pd
from pandas._testing._random import rands
from pandas._testing.contexts import ensure_clean

from pandas.io.common import urlopen

if TYPE_CHECKING:
    from pandas import (
        DataFrame,
        Series,
    )

# skip tests on exceptions with these messages
_network_error_messages = (
    # 'urlopen error timed out',
    # 'timeout: timed out',
    # 'socket.timeout: timed out',
    "timed out",
    "Server Hangup",
    "HTTP Error 503: Service Unavailable",
    "502: Proxy Error",
    "HTTP Error 502: internal error",
    "HTTP Error 502",
    "HTTP Error 503",
    "HTTP Error 403",
    "HTTP Error 400",
    "Temporary failure in name resolution",
    "Name or service not known",
    "Connection refused",
    "certificate verify",
)

# or this e.errno/e.reason.errno
_network_errno_vals = (
    101,  # Network is unreachable
    111,  # Connection refused
    110,  # Connection timed out
    104,  # Connection reset Error
    54,  # Connection reset by peer
    60,  # urllib.error.URLError: [Errno 60] Connection timed out
)

# Both of the above shouldn't mask real issues such as 404's
# or refused connections (changed DNS).
# But some tests (test_data yahoo) contact incredibly flakey
# servers.

# and conditionally raise on exception types in _get_default_network_errors


def _get_default_network_errors():
    # Lazy import for http.client
    # because it imports many things from the stdlib
    import http.client

    return (
        OSError,
        http.client.HTTPException,
        TimeoutError,
        urllib.error.URLError,
        socket.timeout,
    )


def optional_args(decorator):
    """
    allows a decorator to take optional positional and keyword arguments.
    Assumes that taking a single, callable, positional argument means that
    it is decorating a function, i.e. something like this::

        @my_decorator
        def function(): pass

    Calls decorator with decorator(f, *args, **kwargs)
    """

    @wraps(decorator)
    def wrapper(*args, **kwargs):
        def dec(f):
            return decorator(f, *args, **kwargs)

        is_decorating = not kwargs and len(args) == 1 and callable(args[0])
        if is_decorating:
            f = args[0]
            args = ()
            return dec(f)
        else:
            return dec

    return wrapper


# error: Untyped decorator makes function "network" untyped
@optional_args  # type: ignore[misc]
def network(
    t,
    url: str = "https://www.google.com",
    raise_on_error: bool = False,
    check_before_test: bool = False,
    error_classes=None,
    skip_errnos=_network_errno_vals,
    _skip_on_messages=_network_error_messages,
):
    """
    Label a test as requiring network connection and, if an error is
    encountered, only raise if it does not find a network connection.

    In comparison to ``network``, this assumes an added contract to your test:
    you must assert that, under normal conditions, your test will ONLY fail if
    it does not have network connectivity.

    You can call this in 3 ways: as a standard decorator, with keyword
    arguments, or with a positional argument that is the url to check.

    Parameters
    ----------
    t : callable
        The test requiring network connectivity.
    url : path
        The url to test via ``pandas.io.common.urlopen`` to check
        for connectivity. Defaults to 'https://www.google.com'.
    raise_on_error : bool
        If True, never catches errors.
    check_before_test : bool
        If True, checks connectivity before running the test case.
    error_classes : tuple or Exception
        error classes to ignore. If not in ``error_classes``, raises the error.
        defaults to OSError. Be careful about changing the error classes here.
    skip_errnos : iterable of int
        Any exception that has .errno or .reason.erno set to one
        of these values will be skipped with an appropriate
        message.
    _skip_on_messages: iterable of string
        any exception e for which one of the strings is
        a substring of str(e) will be skipped with an appropriate
        message. Intended to suppress errors where an errno isn't available.

    Notes
    -----
    * ``raise_on_error`` supersedes ``check_before_test``

    Returns
    -------
    t : callable
        The decorated test ``t``, with checks for connectivity errors.

    Example
    -------

    Tests decorated with @network will fail if it's possible to make a network
    connection to another URL (defaults to google.com)::

      >>> from pandas import _testing as tm
      >>> @tm.network
      ... def test_network():
      ...     with pd.io.common.urlopen("rabbit://bonanza.com"):
      ...         pass
      >>> test_network()  # doctest: +SKIP
      Traceback
         ...
      URLError: <urlopen error unknown url type: rabbit>

      You can specify alternative URLs::

        >>> @tm.network("https://www.yahoo.com")
        ... def test_something_with_yahoo():
        ...    raise OSError("Failure Message")
        >>> test_something_with_yahoo()  # doctest: +SKIP
        Traceback (most recent call last):
            ...
        OSError: Failure Message

    If you set check_before_test, it will check the url first and not run the
    test on failure::

        >>> @tm.network("failing://url.blaher", check_before_test=True)
        ... def test_something():
        ...     print("I ran!")
        ...     raise ValueError("Failure")
        >>> test_something()  # doctest: +SKIP
        Traceback (most recent call last):
            ...

    Errors not related to networking will always be raised.
    """
    import pytest

    if error_classes is None:
        error_classes = _get_default_network_errors()

    t.network = True

    @wraps(t)
    def wrapper(*args, **kwargs):
        if (
            check_before_test
            and not raise_on_error
            and not can_connect(url, error_classes)
        ):
            pytest.skip(
                f"May not have network connectivity because cannot connect to {url}"
            )
        try:
            return t(*args, **kwargs)
        except Exception as err:  # pylint: disable=broad-except
            errno = getattr(err, "errno", None)
            if not errno and hasattr(errno, "reason"):
                # error: "Exception" has no attribute "reason"
                errno = getattr(err.reason, "errno", None)  # type: ignore[attr-defined]

            if errno in skip_errnos:
                pytest.skip(f"Skipping test due to known errno and error {err}")

            e_str = str(err)

            if any(m.lower() in e_str.lower() for m in _skip_on_messages):
                pytest.skip(
                    f"Skipping test because exception message is known and error {err}"
                )

            if not isinstance(err, error_classes) or raise_on_error:
                raise
            pytest.skip(f"Skipping test due to lack of connectivity and error {err}")

    return wrapper


def can_connect(url, error_classes=None) -> bool:
    """
    Try to connect to the given url. True if succeeds, False if OSError
    raised

    Parameters
    ----------
    url : basestring
        The URL to try to connect to

    Returns
    -------
    connectable : bool
        Return True if no OSError (unable to connect) or URLError (bad url) was
        raised
    """
    if error_classes is None:
        error_classes = _get_default_network_errors()

    try:
        with urlopen(url, timeout=20) as response:
            # Timeout just in case rate-limiting is applied
            if response.status != 200:
                return False
    except error_classes:
        return False
    else:
        return True


# ------------------------------------------------------------------
# File-IO


def round_trip_pickle(
    obj: Any, path: FilePath | ReadPickleBuffer | None = None
) -> DataFrame | Series:
    """
    Pickle an object and then read it again.

    Parameters
    ----------
    obj : any object
        The object to pickle and then re-read.
    path : str, path object or file-like object, default None
        The path where the pickled object is written and then read.

    Returns
    -------
    pandas object
        The original object that was pickled and then re-read.
    """
    _path = path
    if _path is None:
        _path = f"__{rands(10)}__.pickle"
    with ensure_clean(_path) as temp_path:
        pd.to_pickle(obj, temp_path)
        return pd.read_pickle(temp_path)


def round_trip_pathlib(writer, reader, path: str | None = None):
    """
    Write an object to file specified by a pathlib.Path and read it back

    Parameters
    ----------
    writer : callable bound to pandas object
        IO writing function (e.g. DataFrame.to_csv )
    reader : callable
        IO reading function (e.g. pd.read_csv )
    path : str, default None
        The path where the object is written and then read.

    Returns
    -------
    pandas object
        The original object that was serialized and then re-read.
    """
    import pytest

    Path = pytest.importorskip("pathlib").Path
    if path is None:
        path = "___pathlib___"
    with ensure_clean(path) as path:
        writer(Path(path))
        obj = reader(Path(path))
    return obj


def round_trip_localpath(writer, reader, path: str | None = None):
    """
    Write an object to file specified by a py.path LocalPath and read it back.

    Parameters
    ----------
    writer : callable bound to pandas object
        IO writing function (e.g. DataFrame.to_csv )
    reader : callable
        IO reading function (e.g. pd.read_csv )
    path : str, default None
        The path where the object is written and then read.

    Returns
    -------
    pandas object
        The original object that was serialized and then re-read.
    """
    import pytest

    LocalPath = pytest.importorskip("py.path").local
    if path is None:
        path = "___localpath___"
    with ensure_clean(path) as path:
        writer(LocalPath(path))
        obj = reader(LocalPath(path))
    return obj


def write_to_compressed(compression, path, data, dest: str = "test"):
    """
    Write data to a compressed file.

    Parameters
    ----------
    compression : {'gzip', 'bz2', 'zip', 'xz', 'zstd'}
        The compression type to use.
    path : str
        The file path to write the data.
    data : str
        The data to write.
    dest : str, default "test"
        The destination file (for ZIP only)

    Raises
    ------
    ValueError : An invalid compression value was passed in.
    """
    args: tuple[Any, ...] = (data,)
    mode = "wb"
    method = "write"
    compress_method: Callable

    if compression == "zip":
        compress_method = zipfile.ZipFile
        mode = "w"
        args = (dest, data)
        method = "writestr"
    elif compression == "tar":
        compress_method = tarfile.TarFile
        mode = "w"
        file = tarfile.TarInfo(name=dest)
        bytes = io.BytesIO(data)
        file.size = len(data)
        args = (file, bytes)
        method = "addfile"
    elif compression == "gzip":
        compress_method = gzip.GzipFile
    elif compression == "bz2":
        compress_method = bz2.BZ2File
    elif compression == "zstd":
        compress_method = import_optional_dependency("zstandard").open
    elif compression == "xz":
        compress_method = get_lzma_file()
    else:
        raise ValueError(f"Unrecognized compression type: {compression}")

    with compress_method(path, mode=mode) as f:
        getattr(f, method)(*args)


# ------------------------------------------------------------------
# Plotting


def close(fignum=None) -> None:
    from matplotlib.pyplot import (
        close as _close,
        get_fignums,
    )

    if fignum is None:
        for fignum in get_fignums():
            _close(fignum)
    else:
        _close(fignum)

# being a bit too dynamic
from distutils.version import LooseVersion
import operator


def _mpl_version(version, op):
    def inner():
        try:
            # error: No library stub file for module 'matplotlib'
            import matplotlib as mpl  # type: ignore
        except ImportError:
            return False
        return (
            op(LooseVersion(mpl.__version__), LooseVersion(version))
            and str(mpl.__version__)[0] != "0"
        )

    return inner


_mpl_ge_2_2_3 = _mpl_version("2.2.3", operator.ge)
_mpl_ge_3_0_0 = _mpl_version("3.0.0", operator.ge)
_mpl_ge_3_1_0 = _mpl_version("3.1.0", operator.ge)

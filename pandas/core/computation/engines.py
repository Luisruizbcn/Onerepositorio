"""
Engine classes for :func:`~pandas.eval`
"""

import abc
from typing import Dict, Type

from pandas.core.computation.align import _align, _reconstruct_object
from pandas.core.computation.ops import UndefinedVariableError, _mathops, _reductions

import pandas.io.formats.printing as printing

_ne_builtins = frozenset(_mathops + _reductions)


class NumExprClobberingError(NameError):
    pass


def _check_ne_builtin_clash(expr):
    """
    Attempt to prevent foot-shooting in a helpful way.

    Parameters
    ----------
    terms : Term
        Terms can contain
    """
    names = expr.names
    overlap = names & _ne_builtins

    if overlap:
        s = ", ".join(repr(x) for x in overlap)
        raise NumExprClobberingError(
            'Variables in expression "{expr}" '
            "overlap with builtins: ({s})".format(expr=expr, s=s)
        )


class AbstractEngine(metaclass=abc.ABCMeta):
    """Object serving as a base class for all engines."""

    has_neg_frac = False

    def __init__(self, expr):
        self.expr = expr
        self.aligned_axes = None
        self.result_type = None

    def convert(self) -> str:
        """Convert an expression for evaluation.

        Defaults to return the expression as a string.
        """
        return printing.pprint_thing(self.expr)

    def evaluate(self) -> object:
        """
        Run the engine on the expression.

        This method performs alignment which is necessary no matter what engine
        is being used, thus its implementation is in the base class.

        Returns
        -------
        obj : object
            The result of the passed expression.
        """
        if not self._is_aligned:
            self.result_type, self.aligned_axes = _align(self.expr.terms)

        # make sure no names in resolvers and locals/globals clash
        res = self._evaluate()
        return _reconstruct_object(
            self.result_type, res, self.aligned_axes, self.expr.terms.return_type
        )

    @property
    def _is_aligned(self) -> bool:
        return self.aligned_axes is not None and self.result_type is not None

    @abc.abstractmethod
    def _evaluate(self):
        """
        Return an evaluated expression.

        Parameters
        ----------
        env : Scope
            The local and global environment in which to evaluate an
            expression.

        Notes
        -----
        Must be implemented by subclasses.
        """
        pass


class NumExprEngine(AbstractEngine):
    """NumExpr engine class"""

    has_neg_frac = True

    def _evaluate(self):
        import numexpr as ne

        # convert the expression to a valid numexpr expression
        s = self.convert()

        try:
            env = self.expr.env
            scope = env.full_scope
            _check_ne_builtin_clash(self.expr)
            return ne.evaluate(s, local_dict=scope)
        except KeyError as e:
            name = str(e)
            raise UndefinedVariableError(name=name)


class PythonEngine(AbstractEngine):
    """
    Evaluate an expression in Python space.

    Mostly for testing purposes.
    """

    has_neg_frac = False

    def evaluate(self):
        return self.expr()

    def _evaluate(self) -> None:
        pass


_engines: Dict[str, Type[AbstractEngine]] = {
    "numexpr": NumExprEngine,
    "python": PythonEngine,
}

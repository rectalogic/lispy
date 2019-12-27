from __future__ import annotations
from typing import Optional, Dict, List, Any, TYPE_CHECKING
import time

from .mal_types import (
    MalExpression,
    MalExecutionLimitError,
    MalSymbol,
    MalList,
    MalUnknownSymbolException,
    MalInvalidArgumentException,
    expression_from_native,
)

if TYPE_CHECKING:
    from .mal_types import Restrictions


class Env(object):
    """MAL Environment"""

    def __init__(
        self,
        outer: Optional[Env],
        binds: Optional[List[MalExpression]] = None,
        exprs: Optional[List[MalExpression]] = None,
        execution_limit: Optional[ExecutionLimit] = None,
    ) -> None:
        self._outer = outer
        self._execution_limit: Optional[
            ExecutionLimit
        ] = outer._execution_limit if outer else execution_limit
        self._data: Dict[str, MalExpression] = {}
        if binds is not None and exprs is not None:
            for x in range(0, len(binds)):
                if not isinstance(binds[x], MalSymbol):
                    raise MalInvalidArgumentException(binds[x], "not a symbol")
                if binds[x].native() == "&":
                    self.set(str(binds[x + 1]), MalList(exprs[x:]))
                    break
                else:
                    self.set(str(binds[x]), exprs[x])

    def set(self, key: str, value: MalExpression) -> MalExpression:
        self._data[key] = value
        return value

    def find(self, key: MalExpression) -> Optional[Env]:
        if str(key) in self._data:
            return self
        if self._outer is not None:
            return self._outer.find(key)
        return None

    def get(self, key: MalExpression) -> MalExpression:
        strkey = str(key)
        if strkey in self._data:
            return self._data[strkey]

        location = self.find(key)
        if location is None:
            raise MalUnknownSymbolException(strkey)
        return location.get(key)

    def inject_native(
        self, injections: Dict[str, Any], restrictions: Optional[Restrictions] = None
    ):
        for var, obj in injections.items():
            self.set(var, expression_from_native(obj, restrictions))

    def check_execution_limit(self):
        if self._execution_limit:
            self._execution_limit.check()

    def reset_execution_limit(self):
        if self._execution_limit:
            self._execution_limit.reset()

    def __repr__(self) -> str:
        env_str = "{"
        for d in self._data:
            env_str += str(d) + ": " + str(self._data[d]) + ", "
        env_str += "}"
        return f"environment: (data: {env_str} outer: {repr(self._outer) if self._outer is not None else 'None'})"


class ExecutionLimit:
    def __init__(self, time_limit: float):
        self.time_limit = time_limit
        self.reset()

    def reset(self):
        self.start_time = time.perf_counter()

    def check(self):
        if (time.perf_counter() - self.start_time) >= self.time_limit:
            raise MalExecutionLimitError("execution time limit exceeded")

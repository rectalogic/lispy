from __future__ import annotations
from typing import Optional, Dict, List, Any, TYPE_CHECKING

from .mal_types import (
    MalExpression,
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
    ) -> None:
        self._outer = outer
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

    def __repr__(self) -> str:
        env_str = "{"
        for d in self._data:
            env_str += str(d) + ": " + str(self._data[d]) + ", "
        env_str += "}"
        return f"environment: (data: {env_str} outer: {repr(self._outer) if self._outer is not None else 'None'})"

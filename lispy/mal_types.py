from __future__ import annotations
from typing import Callable, Dict, List, Any, Optional, TYPE_CHECKING
import abc

if TYPE_CHECKING:
    from .env import Env

    Restrictions = Dict[type, List[str]]


class MalExpression(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def native(self) -> Any:
        """Return a shallow native Python equivalent for the expression.

        For example, (1 2 3) might become [MalInt(1), MalInt(2), MalInt(3)]"""

    def __str__(self) -> str:
        return self.readable_str()

    @abc.abstractmethod
    def readable_str(self) -> str:
        """Return a human-readable (preferably Mal input format) form of the expression."""

    def unreadable_str(self) -> str:
        """Returns an unescaped/raw str. Defaults to being the same as readable_str."""
        return self.readable_str()


class MalPythonObject(MalExpression):
    def __init__(self, native: Any, restrictions: Optional[Restrictions] = None):
        self._python_native = native
        self._restrictions = restrictions

    def native(self) -> Any:
        return self._python_native

    def readable_str(self) -> str:
        return repr(repr(self._python_native))

    def dot(self, attr: str, value: Optional[MalExpression]) -> MalExpression:
        if self._restrictions:
            attrs = self._restrictions.get(type(self._python_native))
            if not attrs or attr not in attrs:
                raise MalInvalidArgumentException(
                    self, f'Access restricted to attribute "{attr}"'
                )
        try:
            if value is not None:
                setattr(self._python_native, attr, expression_to_native(value))
                return MalNil()
            else:
                return expression_from_native(
                    getattr(self._python_native, attr, None), self._restrictions
                )
        except MalException:
            raise
        except Exception as e:
            raise MalException(MalString(f"{e} raised from python")) from e


class MalString(MalExpression):
    def __init__(self, input_value: str) -> None:
        self._value = input_value

    def readable_str(self) -> str:
        val = self._value

        val = val.replace("\\", "\\\\")  # escape backslashes
        val = val.replace("\n", "\\n")  # escape newlines
        val = val.replace('"', '\\"')  # escape quotes
        val = '"' + val + '"'  # add surrounding quotes
        return val

    def unreadable_str(self) -> str:
        return self._value

    def native(self) -> str:
        return self._value

    def __hash__(self):
        return hash(self._value)

    def __eq__(self, other):
        if type(other) == type(self):
            return self._value == other._value
        return False


class MalKeyword(MalString):
    def __init__(self, input_value: str):
        super().__init__(input_value)

    def readable_str(self) -> str:
        return ":" + self._value

    def unreadable_str(self) -> str:
        return ":" + self._value


class MalList(MalExpression):
    def __init__(self, values: List[MalExpression]) -> None:
        for x in values:
            if not isinstance(x, MalExpression):
                raise MalInvalidArgumentException(x, "not an expression")
        self._values = values

    def readable_str(self) -> str:
        return "(" + " ".join(map(lambda x: x.readable_str(), self._values)) + ")"

    def unreadable_str(self) -> str:
        return "(" + " ".join(map(lambda x: x.unreadable_str(), self._values)) + ")"

    def native(self) -> List[MalExpression]:
        return self._values


class MalSymbol(MalExpression):
    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise MalSyntaxException(f"{value} not a string")

        self._value = str(value)

    def readable_str(self) -> str:
        return str(self._value)

    def eval(self, environment: Env) -> MalExpression:
        # print("Evaluating: " + repr(self))
        return environment.get(self)

    def native(self) -> str:
        return self._value


class MalException(MalExpression, Exception):
    def __init__(self, value: MalExpression) -> None:
        self._value = value

    def readable_str(self) -> str:
        return str(self._value)

    def native(self) -> MalExpression:
        return self._value


class MalIndexError(MalException):
    def __init__(self, index: int) -> None:
        super().__init__(MalString("Index out of bounds: " + str(index)))


class MalSyntaxException(MalException):
    def __init__(self, message: str) -> None:
        super().__init__(MalString(message))


class MalUnknownTypeException(MalException):
    def __init__(self, message: str) -> None:
        super().__init__(MalString(message))


class MalInvalidArgumentException(MalException):
    def __init__(self, arg: MalExpression, reason: str) -> None:
        super().__init__(
            MalString(arg.readable_str() + ": invalid argument: " + reason)
        )


class MalUnknownSymbolException(MalException):
    def __init__(self, func: str) -> None:
        super().__init__(MalString("'" + func + "' not found"))
        self.func = func


class MalNotImplementedException(MalException):
    def __init__(self, func: str) -> None:
        super().__init__(MalString("not implemented: " + func))


class MalFunction(MalExpression, metaclass=abc.ABCMeta):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_macro = False

    def readable_str(self):
        return "#<macro>" if self._is_macro else "#<function>"

    @abc.abstractmethod
    def call(self, args: List[MalExpression]) -> MalExpression:
        pass

    def is_macro(self) -> bool:
        return self._is_macro

    def make_macro(self) -> None:
        self._is_macro = True


class MalFunctionCompiled(MalFunction):
    def __init__(
        self, native_function: Callable[[List[MalExpression]], MalExpression]
    ) -> None:
        super().__init__()
        self._native_function = native_function

    def native(self) -> Callable[[List[MalExpression]], MalExpression]:
        return self._native_function

    def call(self, args: List[MalExpression]) -> MalExpression:
        # print("CALL: " + str([str(arg) for arg in args]))
        return self._native_function(args)


class MalFunctionRaw(MalFunction):
    def __init__(
        self,
        fn: Callable[[List[MalExpression]], MalExpression],
        ast: MalExpression,
        params: MalList,
        env,
    ) -> None:
        super().__init__()
        self._ast = ast
        self._params = params
        self._env = env
        self._native_function = fn

    def ast(self) -> MalExpression:
        return self._ast

    def params(self) -> MalList:
        return self._params

    def env(self):
        return self._env

    def native(self) -> Callable[[List[MalExpression]], MalExpression]:
        return self._native_function

    def call(self, args: List[MalExpression]) -> MalExpression:
        return self._native_function(args)


class MalFunctionPython(MalFunction, MalPythonObject):
    def __init__(
        self, python_function: Callable, restrictions: Optional[Restrictions]
    ) -> None:
        super().__init__(native=python_function, restrictions=restrictions)

    def native(self) -> Callable[[List[MalExpression]], MalExpression]:
        return self._python_native

    def call(self, mal_args: List[MalExpression]) -> MalExpression:
        args = []
        kwargs: Dict[str, Any] = {}
        args_iter = iter(mal_args)
        for a in args_iter:
            if isinstance(a, MalKeyword):
                try:
                    v = next(args_iter)
                except StopIteration:
                    raise MalInvalidArgumentException(
                        a, "expected value following keyword"
                    )
                k = a.native()
                if k in kwargs:
                    raise MalInvalidArgumentException(a, "duplicate keyword")
                kwargs[k] = expression_to_native(v)
            else:
                args.append(expression_to_native(a))
        try:
            return expression_from_native(
                self._python_native(*args, **kwargs), self._restrictions,
            )
        except MalException:
            raise
        except Exception as e:
            raise MalException(MalString(f"{e} raised from python")) from e


class MalInt(MalExpression):
    def __init__(self, value: int) -> None:
        if not isinstance(value, int):
            raise MalSyntaxException(f"{value} not an int")
        self._value = value

    def readable_str(self) -> str:
        return str(self._value)

    def native(self) -> int:
        return self._value


class MalVector(MalExpression):
    def __init__(self, values: List[MalExpression]) -> None:
        self._values = values

    def readable_str(self) -> str:
        return "[" + " ".join(map(lambda x: x.readable_str(), self._values)) + "]"

    def unreadable_str(self) -> str:
        return "[" + " ".join(map(lambda x: x.unreadable_str(), self._values)) + "]"

    def native(self) -> List[MalExpression]:
        return self._values


class MalHash_map(MalExpression):
    def __init__(self, values: Dict[MalString, MalExpression]) -> None:
        self._dict = values.copy()

    def readable_str(self) -> str:
        result_list: List[str] = []
        for x in self._dict:
            result_list.append(x.readable_str())
            result_list.append(self._dict[x].readable_str())
        return "{" + " ".join(result_list) + "}"

    def unreadable_str(self) -> str:
        result_list: List[str] = []
        for x in self._dict:
            result_list.append(x.unreadable_str())
            result_list.append(self._dict[x].unreadable_str())
        return "{" + " ".join(result_list) + "}"

    def native(self) -> Dict[MalString, MalExpression]:
        return self._dict


class MalNil(MalExpression):
    def __init__(self) -> None:
        pass

    def readable_str(self) -> str:
        return "nil"

    def eval(self, environment) -> MalExpression:
        return self

    def native(self) -> None:
        return None


class MalBoolean(MalExpression):
    def __init__(self, value: bool) -> None:
        self._value = value

    def readable_str(self) -> str:
        if self._value:
            return "true"
        return "false"

    def native(self) -> bool:
        return self._value


class MalAtom(MalExpression):
    def __init__(self, value: MalExpression) -> None:
        self._value = value

    def native(self) -> MalExpression:
        return self._value

    def readable_str(self) -> str:
        return "(atom " + str(self._value) + ")"

    def reset(self, value: MalExpression) -> None:
        self._value = value


def expression_from_native(
    obj: Any, restrictions: Optional[Restrictions]
) -> MalExpression:
    if callable(obj):
        return MalFunctionPython(obj, restrictions)
    if isinstance(obj, str):
        return MalString(obj)
    if isinstance(obj, bool):
        return MalBoolean(obj)
    if isinstance(obj, int):
        return MalInt(obj)
    if obj is None:
        return MalNil()
    if isinstance(obj, (list, tuple)):
        return MalList([expression_from_native(x, restrictions) for x in obj])
    return MalPythonObject(obj, restrictions)


def expression_to_native(expr: MalExpression) -> Any:
    if isinstance(expr, (MalList, MalVector)):
        return [expression_to_native(e) for e in expr.native()]
    if isinstance(expr, MalHash_map):
        return {
            expression_to_native(k): expression_to_native(v)
            for k, v in expr.native().items()
        }
    return expr.native()

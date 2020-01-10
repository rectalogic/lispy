from __future__ import annotations
from typing import (
    Callable,
    Dict,
    List,
    Iterable,
    Any,
    Optional,
    Union,
    TYPE_CHECKING,
    cast,
)
import abc

if TYPE_CHECKING:
    from .env import Env

    Restrictions = Dict[type, Iterable[str]]
    HashMapDict = Dict[Union["MalString", "MalKeyword"], "MalExpression"]


class MalExpression(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def native(self) -> Any:
        """Return a shallow native Python equivalent for the expression.

        For example, (1 2 3) might become [MalInt(1), MalInt(2), MalInt(3)]"""

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.native() == other.native()
        return False

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

    @property
    def restrictions(self) -> Optional[Restrictions]:
        return self._restrictions

    def to_expression(self) -> MalExpression:
        obj = self.native()
        if isinstance(obj, str):
            return MalString(obj)
        if isinstance(obj, bool):
            return MalBoolean(obj)
        if isinstance(obj, float):
            return MalFloat(obj)
        if isinstance(obj, int):
            return MalInt(obj)
        if obj is None:
            return MalNil()
        if isinstance(obj, (list, tuple)):
            return MalList([expression_from_native(x, self.restrictions) for x in obj])
        return self

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
            raise MalException(MalString(f"'{repr(e)}' raised from python")) from e


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


class MalKeyword(MalExpression):
    def __init__(self, input_value: str):
        self._value = input_value

    def readable_str(self) -> str:
        return ":" + self._value

    def unreadable_str(self) -> str:
        return ":" + self._value

    def native(self) -> str:
        return self._value

    def __hash__(self):
        return hash(self._value)


class MalMeta(metaclass=abc.ABCMeta):
    def __init__(self, *args, **kwargs):
        self._meta: Optional[MalExpression] = None

    @abc.abstractmethod
    def copy(self) -> MalMeta:
        pass

    @property
    def meta(self) -> MalExpression:
        return MalNil() if self._meta is None else self._meta

    @meta.setter
    def meta(self, meta: MalExpression):
        self._meta = meta


class MalList(MalExpression, MalMeta):
    def __init__(self, values: Iterable[MalExpression]) -> None:
        super().__init__()
        self._values = list(values)
        for x in self._values:
            if not isinstance(x, MalExpression):
                raise MalInvalidArgumentException(x, "not an expression")

    def __eq__(self, other):
        if isinstance(other, (MalList, MalVector)):
            return self.native() == other.native()
        return False

    def copy(self) -> MalList:
        return self.__class__(self._values)

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
        self.backtrace: List[MalExpression] = []

    def readable_str(self) -> str:
        return str(self._value)

    def readable_backtrace(self) -> str:
        return "\n".join(str(f) for f in self.backtrace)

    def native(self) -> MalExpression:
        return self._value


class MalIndexError(MalException):
    def __init__(self, index: int) -> None:
        super().__init__(MalString("Index out of bounds: " + str(index)))


class MalExecutionLimitError(MalException):
    def __init__(self, message: str) -> None:
        super().__init__(MalString(message))


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


class MalFunction(MalExpression, MalMeta):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_macro = False

    @abc.abstractmethod
    def copy(self) -> MalFunction:
        pass

    def __eq__(self, other):
        if super().__eq__(other):
            return self.is_macro() == other.is_macro()
        return False

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

    def copy(self) -> MalFunctionCompiled:
        f = self.__class__(self.native())
        if self.is_macro():
            f.make_macro()
        return f

    def native(self) -> Callable[[List[MalExpression]], MalExpression]:
        return self._native_function

    def call(self, args: List[MalExpression]) -> MalExpression:
        # print("CALL: " + str([str(arg) for arg in args]))
        return self._native_function(args)


class MalFunctionRaw(MalFunction, MalMeta):
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

    def __eq__(self, other):
        if super().__eq__(other):
            f = cast(MalFunctionRaw, other)
            return (
                self.ast() == f.ast()
                and self.params() == f.params()
                and self.env() == f.env()
            )
        return False

    def copy(self) -> MalFunctionRaw:
        f = self.__class__(self.native(), self.ast(), self.params(), self.env())
        if self.is_macro():
            f.make_macro()
        return f

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

    def copy(self) -> MalFunctionPython:
        f = self.__class__(self.native(), self.restrictions)
        if self.is_macro():
            f.make_macro()
        return f

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
            raise MalException(MalString(f"'{repr(e)}' raised from python")) from e


class MalFloat(MalExpression):
    def __init__(self, value: float) -> None:
        if not isinstance(value, float):
            raise MalSyntaxException(f"{value} not a float")
        self._value = value

    def readable_str(self) -> str:
        return str(self._value)

    def native(self) -> float:
        return self._value


class MalInt(MalExpression):
    def __init__(self, value: int) -> None:
        if not isinstance(value, int):
            raise MalSyntaxException(f"{value} not an int")
        self._value = value

    def readable_str(self) -> str:
        return str(self._value)

    def native(self) -> int:
        return self._value


class MalVector(MalExpression, MalMeta):
    def __init__(self, values: Iterable[MalExpression]) -> None:
        super().__init__()
        self._values = list(values)
        for x in self._values:
            if not isinstance(x, MalExpression):
                raise MalInvalidArgumentException(x, "not an expression")

    def __eq__(self, other):
        if isinstance(other, (MalList, MalVector)):
            return self.native() == other.native()
        return False

    def copy(self) -> MalVector:
        return self.__class__(self._values)

    def readable_str(self) -> str:
        return "[" + " ".join(map(lambda x: x.readable_str(), self._values)) + "]"

    def unreadable_str(self) -> str:
        return "[" + " ".join(map(lambda x: x.unreadable_str(), self._values)) + "]"

    def native(self) -> List[MalExpression]:
        return self._values


class MalHash_map(MalExpression, MalMeta):
    def __init__(self, values: HashMapDict) -> None:
        super().__init__()
        self._dict = values.copy()

    def copy(self) -> MalHash_map:
        return self.__class__(self._dict)

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

    def native(self) -> HashMapDict:
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


class MalBlank(MalNil):
    def readable_str(self) -> str:
        return ""


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

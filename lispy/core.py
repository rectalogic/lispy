from __future__ import annotations
import time
import operator
from typing import List, Union, NoReturn, Optional, cast, TYPE_CHECKING

from . import reader
from .mal_types import (
    MalInt,
    MalNil,
    MalList,
    MalBoolean,
    MalExpression,
    MalFunction,
    MalFunctionCompiled,
    MalPythonObject,
    MalAtom,
    MalHash_map,
    MalVector,
    MalMeta,
)
from .mal_types import (
    MalInvalidArgumentException,
    MalString,
    MalKeyword,
    MalException,
    MalSymbol,
    MalNotImplementedException,
    MalIndexError,
    MalSyntaxException,
)

if TYPE_CHECKING:
    from .mal_types import HashMapDict


def python_print(s: str):
    print(s)


def prn(args: List[MalExpression]) -> MalNil:
    result_string = " ".join(map(lambda x: x.readable_str(), args))
    python_print(result_string)
    return MalNil()


def pr_str(args: List[MalExpression]) -> MalString:
    result_string = " ".join(map(lambda x: x.readable_str(), args))
    return MalString(result_string)


def println(args: List[MalExpression]) -> MalNil:
    result_string = " ".join(map(lambda x: x.unreadable_str(), args))
    python_print(result_string)
    return MalNil()


def list_q(x: MalExpression) -> MalBoolean:
    if isinstance(x, MalList):
        return MalBoolean(True)
    return MalBoolean(False)


def empty_q(x: MalExpression) -> MalBoolean:
    if sequential_q(x):
        return MalBoolean(len(x.native()) == 0)
    raise MalInvalidArgumentException(x, "not a list")


def count(x: MalExpression) -> MalInt:
    if isinstance(x, MalList) or isinstance(x, MalVector):
        return MalInt(len(x.native()))
    elif isinstance(x, MalNil):
        return MalInt(0)
    raise MalInvalidArgumentException(x, "not a list")


def equal(a: MalExpression, b: MalExpression) -> MalBoolean:
    return MalBoolean(a == b)


def less(a: MalExpression, b: MalExpression) -> MalBoolean:
    if not isinstance(a, MalInt):
        raise MalInvalidArgumentException(a, "not an int")
    if not isinstance(b, MalInt):
        raise MalInvalidArgumentException(b, "not an int")
    return MalBoolean(a.native() < b.native())


def less_equal(a: MalExpression, b: MalExpression) -> MalBoolean:
    if not isinstance(a, MalInt):
        raise MalInvalidArgumentException(a, "not an int")
    if not isinstance(b, MalInt):
        raise MalInvalidArgumentException(b, "not an int")
    return MalBoolean(a.native() <= b.native())


def read_string(a: MalExpression) -> MalExpression:
    if isinstance(a, MalString):
        result = reader.read(a.native())
        return result
    raise MalInvalidArgumentException(a, "not a string")


def slurp(filename: MalExpression) -> MalString:
    if not isinstance(filename, MalString):
        raise MalInvalidArgumentException(filename, "not a string")
    with open(filename.native(), "r") as the_file:
        contents = the_file.read()
    return MalString(contents)


def core_str(args: List[MalExpression]) -> MalString:
    result = ""
    for a in args:
        result += a.unreadable_str()
    return MalString(result)


def deref_q(atom: MalExpression) -> MalExpression:
    if not isinstance(atom, MalAtom):
        raise MalInvalidArgumentException(atom, "not an atom")
    return atom.native()


def reset(atom: MalExpression, val: MalExpression) -> MalExpression:
    if not isinstance(atom, MalAtom):
        raise MalInvalidArgumentException(atom, "not an atom")
    atom.reset(val)
    return val


def cons(first: MalExpression, rest: MalExpression) -> MalExpression:
    if not isinstance(rest, MalList) and not isinstance(rest, MalVector):
        raise MalInvalidArgumentException(rest, "not a list or vector")
    return MalList([first] + rest.native())


def concat(args: List[MalExpression]) -> MalExpression:
    result_list: List[MalExpression] = []
    for x in args:
        if not isinstance(x, MalList) and not isinstance(x, MalVector):
            raise MalInvalidArgumentException(x, "not a list or vector")
        result_list = result_list + x.native()
    return MalList(result_list)


def not_(expr: MalExpression) -> MalExpression:
    if isinstance(expr, MalNil) or (
        isinstance(expr, MalBoolean) and expr.native() is False
    ):
        return MalBoolean(True)
    else:
        return MalBoolean(False)


def nth(list_: MalExpression, index: MalExpression) -> MalExpression:
    if not isinstance(list_, MalList) and not isinstance(list_, MalVector):
        raise MalInvalidArgumentException(list_, "not a list or vector")
    if not isinstance(index, MalInt):
        raise MalInvalidArgumentException(index, "not an int")
    list_native = list_.native()
    if index.native() > len(list_native) - 1:
        raise MalIndexError(index.native())
    return list_native[index.native()]


def apply(args: List[MalExpression]) -> MalExpression:
    func = args[0]
    if not isinstance(func, MalFunction):
        raise MalInvalidArgumentException(func, "not a function")
    rest_args: List[MalExpression] = []
    for i in range(1, len(args) - 1):
        rest_args.append(args[i])
    last_arg = args[len(args) - 1]
    if not isinstance(last_arg, MalList) and not isinstance(last_arg, MalVector):
        raise MalInvalidArgumentException(last_arg, "not a list or vector")
    rest_args = rest_args + last_arg.native()
    return func.call(rest_args)


def map_(func: MalExpression, map_list: MalExpression) -> MalExpression:
    if not isinstance(func, MalFunction):
        raise MalInvalidArgumentException(func, "not a function")
    if not isinstance(map_list, MalList) and not isinstance(map_list, MalVector):
        raise MalInvalidArgumentException(map_list, "not a list or vector")
    result_list: List[MalExpression] = []
    for i in range(len(map_list.native())):
        elem = map_list.native()[i]
        result_list.append(func.call([elem]))
    return MalList(result_list)


def seq(obj: MalExpression) -> MalExpression:
    if isinstance(obj, MalList):
        return obj if obj.native() else MalNil()
    elif isinstance(obj, MalVector):
        return MalList(obj.native()) if obj.native() else MalNil()
    elif isinstance(obj, MalString):
        return (
            MalList([MalString(c) for c in obj.native()]) if obj.native() else MalNil()
        )
    elif isinstance(obj, MalNil):
        return obj
    else:
        raise MalInvalidArgumentException(obj, "not a sequence")


def conj(args: List[MalExpression]) -> MalExpression:
    if len(args) < 2:
        raise MalSyntaxException("requires at least 2 arguments")
    list_ = args[0]
    rest = args[1:]
    if isinstance(list_, MalList):
        return MalList(list(reversed(rest)) + list_.native())
    elif isinstance(list_, MalVector):
        return MalVector(list_.native() + rest)
    else:
        raise MalInvalidArgumentException(list_, "not a list or vector")


def throw(exception: MalExpression) -> NoReturn:
    raise MalException(exception)


def nil_q(arg: MalExpression) -> MalExpression:
    return MalBoolean(isinstance(arg, MalNil))


def true_q(arg: MalExpression) -> MalExpression:
    return MalBoolean(isinstance(arg, MalBoolean) and arg.native())


def false_q(arg: MalExpression) -> MalExpression:
    return MalBoolean(isinstance(arg, MalBoolean) and not arg.native())


def symbol_q(arg: MalExpression) -> MalExpression:
    return MalBoolean(isinstance(arg, MalSymbol))


def keyword_q(arg: MalExpression) -> MalExpression:
    return MalBoolean(isinstance(arg, MalKeyword))


def keyword(arg: MalExpression) -> MalExpression:
    if isinstance(arg, MalKeyword):
        return arg
    elif isinstance(arg, MalString):
        return MalKeyword(arg.unreadable_str())
    else:
        raise MalInvalidArgumentException(arg, "not a string")


def symbol(arg: MalExpression) -> MalExpression:
    if not isinstance(arg, MalString):
        raise MalInvalidArgumentException(arg, "not a string")
    return MalSymbol(arg.unreadable_str())


def readline(arg: MalExpression) -> Union[MalString, MalNil]:
    try:
        if not isinstance(arg, MalString):
            raise MalInvalidArgumentException(arg, "not a string")
        line = input(arg.native())
    except EOFError:
        return MalNil()
    return MalString(line)


def meta(arg: MalExpression) -> MalExpression:
    if isinstance(arg, MalMeta):
        return arg.meta
    return MalNil()


def with_meta(arg: MalExpression, meta: MalExpression) -> MalExpression:
    if isinstance(arg, MalMeta):
        c = arg.copy()
        c.meta = meta
        return c
    else:
        return MalNil()


def fn_q(arg: MalExpression) -> MalExpression:
    if isinstance(arg, MalFunction):
        f = cast(MalFunction, arg)
        return MalBoolean(not f.is_macro())
    return MalBoolean(False)


def macro_q(arg: MalExpression) -> MalExpression:
    if isinstance(arg, MalFunction):
        f = cast(MalFunction, arg)
        return MalBoolean(f.is_macro())
    return MalBoolean(False)


def not_implemented(func: str) -> MalExpression:
    raise MalNotImplementedException(func)


def get(map: MalExpression, key: MalExpression) -> MalExpression:
    if isinstance(map, MalNil):
        return MalNil()
    if not isinstance(map, MalHash_map):
        raise MalInvalidArgumentException(map, "not a hash map")
    if isinstance(key, (MalString, MalKeyword)) and key in map.native():
        return map.native()[key]
    else:
        return MalNil()


def first(args: List[MalExpression]) -> MalExpression:
    try:
        if isinstance(args[0], MalNil):
            return MalNil()
        return args[0].native()[0]
    except IndexError:
        return MalNil()
    except TypeError:
        raise MalInvalidArgumentException(args[0], "not a list")


def rest(args: List[MalExpression]) -> MalExpression:
    try:
        if isinstance(args[0], MalNil):
            return MalList([])
        return MalList(args[0].native()[1:])
    except TypeError:
        raise MalInvalidArgumentException(args[0], "not a list or vector")


def vector_q(arg: MalExpression) -> MalExpression:
    return MalBoolean(isinstance(arg, MalVector))


def map_q(arg: MalExpression) -> MalExpression:
    return MalBoolean(isinstance(arg, MalHash_map))


def sequential_q(arg: MalExpression) -> MalExpression:
    return MalBoolean(isinstance(arg, MalList) or isinstance(arg, MalVector))


def vector(args: List[MalExpression]) -> MalExpression:
    return MalVector(args)


def hash_map(args: List[MalExpression]) -> MalExpression:
    if len(args) % 2 != 0:
        raise MalSyntaxException("hash-map requires even number of arguments")
    map_: HashMapDict = {}
    for i in range(0, len(args) - 1, 2):
        if not isinstance(args[i], (MalString, MalKeyword)):
            raise MalInvalidArgumentException(args[i], "not a string or keyword")
        map_[cast(Union[MalString, MalKeyword], args[i])] = args[i + 1]
    return MalHash_map(map_)


def assoc(args: List[MalExpression]) -> MalExpression:
    if len(args) == 0:
        raise MalInvalidArgumentException(MalNil(), "no arguments supplied to assoc")
    elif len(args) == 1:
        return args[0]
    if not isinstance(args[0], MalHash_map):
        raise MalInvalidArgumentException(args[0], "not a hash map")
    dict_a_copy: HashMapDict = args[0].native().copy()
    dict_b: HashMapDict = hash_map(args[1:]).native()
    for key in dict_b:
        dict_a_copy[key] = dict_b[key]
    return MalHash_map(dict_a_copy)


def contains_q(args: List[MalExpression]) -> MalExpression:
    if len(args) < 2:
        raise MalInvalidArgumentException(MalNil(), "contains? requires two arguments")
    if not isinstance(args[0], MalHash_map):
        raise MalInvalidArgumentException(args[0], "not a hash-map")
    if not isinstance(args[1], (MalString, MalKeyword)):
        return MalBoolean(False)
    return MalBoolean(args[1] in args[0].native())


def keys(args: List[MalExpression]) -> MalExpression:
    if len(args) != 1:
        raise MalInvalidArgumentException(
            MalNil(), "keys requires exactly one argument"
        )
    if not isinstance(args[0], MalHash_map):
        raise MalInvalidArgumentException(args[0], "not a hash map")
    return MalList([x for x in args[0].native()])


def vals(args: List[MalExpression]) -> MalExpression:
    if len(args) != 1:
        raise MalInvalidArgumentException(
            MalNil(), "vals requires exactly one argument"
        )
    if not isinstance(args[0], MalHash_map):
        raise MalInvalidArgumentException(args[0], "not a hash map")
    return MalList(list(args[0].native().values()))


def dissoc(args: List[MalExpression]) -> MalExpression:
    if len(args) == 0:
        raise MalInvalidArgumentException(MalNil(), "no arguments supplied to dissoc")
    elif len(args) == 1:
        return args[0]
    if not isinstance(args[0], MalHash_map):
        raise MalInvalidArgumentException(args[0], "not a hash map")
    dict_a_copy: HashMapDict = args[0].native().copy()
    list_b: List[MalExpression] = MalList(args[1:]).native()
    for key in list_b:
        if key in dict_a_copy:
            del dict_a_copy[cast(Union[MalString, MalKeyword], key)]
    return MalHash_map(dict_a_copy)


def swap(args: List[MalExpression]) -> MalExpression:
    if len(args) < 2:
        raise MalSyntaxException("requires atom and function")
    atom = args[0]
    if not isinstance(atom, MalAtom):
        raise MalInvalidArgumentException(atom, "not an atom")
    func = args[1]
    if not isinstance(func, MalFunction):
        raise MalInvalidArgumentException(func, "not a function")
    atom.reset(func.call([atom.native()] + args[2:]))
    return atom.native()


def dot(args: List[MalExpression]) -> MalExpression:
    if len(args) != 2 and len(args) != 3:
        raise MalSyntaxException(". requires object and attribute and optional value")
    python_object = args[0]
    if not isinstance(python_object, MalPythonObject):
        raise MalInvalidArgumentException(python_object, "not python object")
    attr = args[1]
    if not isinstance(attr, (MalString, MalSymbol, MalKeyword)):
        raise MalInvalidArgumentException(attr, "cannot convert to string")
    if len(args) == 3:
        value: Optional[MalExpression] = args[2]
    else:
        value = None
    return python_object.dot(attr.native(), value)


def require_args(args: List[MalExpression], count: int) -> List[MalExpression]:
    if len(args) != count:
        raise MalSyntaxException("not enough arguments")
    return args


ns = {
    "+": MalFunctionCompiled(
        lambda args: MalInt(operator.add(*[a.native() for a in require_args(args, 2)]))
    ),
    "-": MalFunctionCompiled(
        lambda args: MalInt(operator.sub(*[a.native() for a in require_args(args, 2)]))
    ),
    "*": MalFunctionCompiled(
        lambda args: MalInt(operator.mul(*[a.native() for a in require_args(args, 2)]))
    ),
    "/": MalFunctionCompiled(
        lambda args: MalInt(
            operator.floordiv(*[a.native() for a in require_args(args, 2)])
        )
    ),
    "prn": MalFunctionCompiled(lambda args: prn(args)),
    "pr-str": MalFunctionCompiled(lambda args: pr_str(args)),
    "println": MalFunctionCompiled(lambda args: println(args)),
    "list": MalFunctionCompiled(lambda args: MalList(args)),
    "list?": MalFunctionCompiled(lambda args: list_q(require_args(args, 1)[0])),
    "empty?": MalFunctionCompiled(lambda args: empty_q(require_args(args, 1)[0])),
    "count": MalFunctionCompiled(lambda args: count(require_args(args, 1)[0])),
    "=": MalFunctionCompiled(lambda args: equal(*require_args(args, 2))),
    "<": MalFunctionCompiled(lambda args: less(*require_args(args, 2))),
    "<=": MalFunctionCompiled(lambda args: less_equal(*require_args(args, 2))),
    ">": MalFunctionCompiled(lambda args: less(*list(reversed(require_args(args, 2))))),
    ">=": MalFunctionCompiled(
        lambda args: less_equal(*list(reversed(require_args(args, 2))))
    ),
    "read-string": MalFunctionCompiled(
        lambda args: read_string(require_args(args, 1)[0])
    ),
    "slurp": MalFunctionCompiled(lambda args: slurp(require_args(args, 1)[0])),
    "str": MalFunctionCompiled(lambda args: core_str(args)),
    "atom": MalFunctionCompiled(lambda args: MalAtom(require_args(args, 1)[0])),
    "atom?": MalFunctionCompiled(
        lambda args: MalBoolean(isinstance(require_args(args, 1)[0], MalAtom))
    ),
    "deref": MalFunctionCompiled(lambda args: deref_q(require_args(args, 1)[0])),
    "reset!": MalFunctionCompiled(lambda args: reset(*require_args(args, 2))),
    "cons": MalFunctionCompiled(lambda args: cons(*require_args(args, 2))),
    "concat": MalFunctionCompiled(concat),
    "not": MalFunctionCompiled(lambda args: not_(require_args(args, 1)[0])),
    "nth": MalFunctionCompiled(lambda args: nth(*require_args(args, 2))),
    "apply": MalFunctionCompiled(lambda args: apply(args)),
    "map": MalFunctionCompiled(lambda args: map_(*require_args(args, 2))),
    "throw": MalFunctionCompiled(lambda args: throw(require_args(args, 1)[0])),
    "nil?": MalFunctionCompiled(lambda args: nil_q(require_args(args, 1)[0])),
    "true?": MalFunctionCompiled(lambda args: true_q(require_args(args, 1)[0])),
    "false?": MalFunctionCompiled(lambda args: false_q(require_args(args, 1)[0])),
    "symbol": MalFunctionCompiled(lambda args: symbol(require_args(args, 1)[0])),
    "symbol?": MalFunctionCompiled(lambda args: symbol_q(require_args(args, 1)[0])),
    "readline": MalFunctionCompiled(lambda args: readline(require_args(args, 1)[0])),
    "time-ms": MalFunctionCompiled(lambda args: MalInt(int(time.time() * 1000))),
    "meta": MalFunctionCompiled(lambda args: meta(require_args(args, 1)[0])),
    "with-meta": MalFunctionCompiled(lambda args: with_meta(*require_args(args, 2))),
    "fn?": MalFunctionCompiled(lambda args: fn_q(require_args(args, 1)[0])),
    "macro?": MalFunctionCompiled(lambda args: macro_q(require_args(args, 1)[0])),
    "string?": MalFunctionCompiled(
        lambda args: MalBoolean(isinstance(require_args(args, 1)[0], MalString))
    ),
    "number?": MalFunctionCompiled(
        lambda args: MalBoolean(isinstance(require_args(args, 1)[0], MalInt))
    ),
    "seq": MalFunctionCompiled(lambda args: seq(require_args(args, 1)[0])),
    "conj": MalFunctionCompiled(lambda args: conj(args)),
    "get": MalFunctionCompiled(lambda args: get(*require_args(args, 2))),
    "first": MalFunctionCompiled(lambda args: first(args)),
    "rest": MalFunctionCompiled(lambda args: rest(args)),
    "keyword?": MalFunctionCompiled(lambda args: keyword_q(require_args(args, 1)[0])),
    "keyword": MalFunctionCompiled(lambda args: keyword(require_args(args, 1)[0])),
    "vector?": MalFunctionCompiled(lambda args: vector_q(require_args(args, 1)[0])),
    "map?": MalFunctionCompiled(lambda args: map_q(require_args(args, 1)[0])),
    "sequential?": MalFunctionCompiled(
        lambda args: sequential_q(require_args(args, 1)[0])
    ),
    "vector": MalFunctionCompiled(lambda args: vector(args)),
    "hash-map": MalFunctionCompiled(lambda args: hash_map(args)),
    "assoc": MalFunctionCompiled(lambda args: assoc(args)),
    "contains?": MalFunctionCompiled(lambda args: contains_q(args)),
    "keys": MalFunctionCompiled(lambda args: keys(args)),
    "vals": MalFunctionCompiled(lambda args: vals(args)),
    "dissoc": MalFunctionCompiled(lambda args: dissoc(args)),
    "swap!": MalFunctionCompiled(lambda args: swap(args)),
    ".": MalFunctionCompiled(lambda args: dot(args)),
}

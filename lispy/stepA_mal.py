from __future__ import annotations
import readline
import sys
import traceback
from typing import Optional, List, TYPE_CHECKING

from . import core
from . import reader
from .env import Env
from .mal_types import (
    MalExpression,
    MalSymbol,
    MalException,
    MalList,
    MalNil,
    MalBoolean,
    MalFunction,
    MalFunctionCompiled,
    MalFunctionRaw,
    MalFunctionPython,
    MalVector,
    MalHash_map,
    MalUnknownSymbolException,
    MalInvalidArgumentException,
    MalSyntaxException,
    MalString,
)

if TYPE_CHECKING:
    from .mal_types import HashMapDict


def READ(x: str) -> MalExpression:
    return reader.read(x)


def eval_ast(ast: MalExpression, env: Env) -> MalExpression:
    if isinstance(ast, MalSymbol):
        return env.get(ast)
    if isinstance(ast, MalList):
        return MalList([EVAL(x, env) for x in ast.native()])
    if isinstance(ast, MalVector):
        return MalVector([EVAL(x, env) for x in ast.native()])
    if isinstance(ast, MalHash_map):
        new_dict: HashMapDict = {}
        for key in ast.native():
            new_dict[key] = EVAL(ast.native()[key], env)
        return MalHash_map(new_dict)
    return ast


def is_pair(x: MalExpression) -> bool:
    if (isinstance(x, MalList) or isinstance(x, MalVector)) and len(x.native()) > 0:
        return True
    return False


def quasiquote(ast: MalExpression) -> MalExpression:
    if not is_pair(ast):
        return MalList([MalSymbol("quote"), ast])
    elif core.equal(ast.native()[0], MalSymbol("unquote")).native():
        return ast.native()[1]
    elif (
        is_pair(ast.native()[0])
        and core.equal(
            ast.native()[0].native()[0], MalSymbol("splice-unquote")
        ).native()
    ):
        return MalList(
            [
                MalSymbol("concat"),
                ast.native()[0].native()[1],
                quasiquote(MalList(ast.native()[1:])),
            ]
        )
    else:
        return MalList(
            [
                MalSymbol("cons"),
                quasiquote(ast.native()[0]),
                quasiquote(MalList(ast.native()[1:])),
            ]
        )


def EVAL(ast: MalExpression, env: Env) -> MalExpression:
    while True:
        # print("EVAL: " + str(ast))
        ast = macroexpand(ast, env)
        ast_native = ast.native()
        if not isinstance(ast, MalList):
            return eval_ast(ast, env)
        elif len(ast_native) == 0:
            return ast

        first_str = str(ast_native[0])
        if first_str == "macroexpand":
            return macroexpand(ast.native()[1], env)
        elif first_str == "def!":
            name: str = str(ast_native[1])
            value: MalExpression = EVAL(ast_native[2], env)
            return env.set(name, value)
        if first_str == "defmacro!":
            name = str(ast_native[1])
            value = EVAL(ast_native[2], env)
            if not isinstance(value, MalFunction):
                raise MalInvalidArgumentException(value, "not a function")
            value.make_macro()
            return env.set(name, value)
        elif first_str == "let*":
            if len(ast_native) != 3:
                raise MalSyntaxException("let* must be length 3")
            let_env = Env(env)
            bindings: MalExpression = ast_native[1]
            if not isinstance(bindings, MalList) and not isinstance(
                bindings, MalVector
            ):
                raise MalInvalidArgumentException(bindings, "not a list or vector")
            bindings_list: List[MalExpression] = bindings.native()
            if len(bindings_list) % 2 != 0:
                raise MalInvalidArgumentException(bindings, "must be an even length")
            for i in range(0, len(bindings_list), 2):
                if not isinstance(bindings_list[i], MalSymbol):
                    raise MalInvalidArgumentException(bindings_list[i], "not a symbol")
                if not isinstance(bindings_list[i + 1], MalExpression):
                    raise MalInvalidArgumentException(
                        bindings_list[i], "not an expression"
                    )
                let_env.set(str(bindings_list[i]), EVAL(bindings_list[i + 1], let_env))
            env = let_env
            ast = ast_native[2]
            continue
        elif first_str == "do":
            for x in range(1, len(ast_native) - 1):
                EVAL(ast_native[x], env)
            ast = ast_native[len(ast_native) - 1]
            continue
        elif first_str == "if":
            condition = EVAL(ast_native[1], env)

            if isinstance(condition, MalNil) or (
                isinstance(condition, MalBoolean) and condition.native() is False
            ):
                if len(ast_native) >= 4:
                    ast = ast_native[3]
                    continue
                else:
                    return MalNil()
            else:
                ast = ast_native[2]
                continue
        elif first_str == "fn*":
            raw_ast = ast_native[2]
            raw_params = ast_native[1]

            def fn(args: List[MalExpression]) -> MalExpression:
                f_ast = raw_ast
                f_env = Env(outer=env, binds=raw_params.native(), exprs=args)
                return EVAL(f_ast, f_env)

            return MalFunctionRaw(fn=fn, ast=raw_ast, params=raw_params, env=env)
        elif first_str == "quote":
            return (
                MalList(ast_native[1].native())
                if isinstance(ast_native[1], MalVector)
                else ast_native[1]
            )
        elif first_str == "quasiquote":
            ast = quasiquote(ast_native[1])
            continue
        elif first_str == "try*":
            try:
                return EVAL(ast_native[1], env)
            except MalException as e:
                if len(ast_native) < 3:
                    raise e
                catch_block = ast_native[2]
                if not isinstance(catch_block, MalList):
                    raise MalInvalidArgumentException(catch_block, "not a list")
                if (
                    not isinstance(catch_block.native()[0], MalSymbol)
                    or not str(catch_block.native()[0]) == "catch*"
                ):
                    raise MalInvalidArgumentException(
                        catch_block.native()[0], "must be catch* symbol"
                    )
                if len(catch_block.native()) != 3:
                    raise MalInvalidArgumentException(catch_block, "must be length 3")
                exception_symbol = catch_block.native()[1]
                if not isinstance(exception_symbol, MalSymbol):
                    raise MalInvalidArgumentException(exception_symbol, "not a symbol")
                env = Env(env)
                env.set(str(exception_symbol), e.native())
                ast = catch_block.native()[2]
                continue
        else:
            evaled_ast = eval_ast(ast, env)
            f = evaled_ast.native()[0]
            args = evaled_ast.native()[1:]
            if isinstance(f, MalFunctionRaw):
                ast = f.ast()

                env = Env(outer=f.env(), binds=f.params().native(), exprs=args,)
                continue
            elif isinstance(f, (MalFunctionCompiled, MalFunctionPython)):
                return f.call(args)
            else:
                raise MalInvalidArgumentException(f, "not a function")


def PRINT(x: MalExpression) -> str:
    return str(x)


def rep(x: str, env: Env) -> str:
    return PRINT(EVAL(READ(x), env))


def init_repl_env(argv: Optional[List[str]] = None, restricted: bool = False) -> Env:
    def eval_func(args: List[MalExpression], env: Env) -> MalExpression:
        a0 = args[0]
        if not isinstance(a0, MalExpression):
            raise MalInvalidArgumentException(a0, "not an expression")
        return EVAL(a0, env)

    env = Env(None)
    for key in core.ns:
        if not restricted or key not in {"slurp", "readline"}:
            env.set(key, core.ns[key])

    env.set("eval", MalFunctionCompiled(lambda args: eval_func(args, env)))
    rep('(def! *host-language* "python")', env)

    if not restricted:
        rep(
            '(def! load-file (fn* (f) (eval (read-string (str "(do " (slurp f) "\nnil)")))))',
            env,
        )

    if restricted and argv is None:
        argv = []
    mal_argv = MalList([MalString(x) for x in (sys.argv[2:] if argv is None else argv)])
    env.set("*ARGV*", mal_argv)

    rep(
        "(defmacro! cond (fn* (& xs) (if (> (count xs) 0) (list 'if (first xs) (if (> (count xs) 1) (nth xs 1) (throw \"odd number of forms to cond\")) (cons 'cond (rest (rest xs)))))))",
        env,
    )

    return env


def is_macro_call(ast: MalExpression, env: Env) -> bool:
    try:
        x = env.get(ast.native()[0].native())
        if not isinstance(x, MalFunction):
            return False
        return x.is_macro()
    except TypeError:
        return False
    except MalUnknownSymbolException:
        return False
    except AttributeError:
        return False
    except IndexError:
        return False
    except KeyError:
        return False


def macroexpand(ast: MalExpression, env: Env) -> MalExpression:
    while True:
        if not is_macro_call(ast, env):
            return ast
        if not isinstance(ast, MalList):
            raise MalInvalidArgumentException(ast, "not a list")
        macro_func = env.get(ast.native()[0].native())
        if not isinstance(macro_func, MalFunction):
            raise MalInvalidArgumentException(macro_func, "not a function")
        ast = macro_func.call(ast.native()[1:])
        continue


def print_exc():
    core.python_print(traceback.format_exc())


def rep_handling_exceptions(line: str, repl_env: Env, verbose: bool = False) -> str:
    try:
        return rep(line, repl_env)
    except MalUnknownSymbolException as e:
        m = "'" + e.func + "' not found"
        if verbose:
            m += "\n" + traceback.format_exc()
        return m
    except MalException as e:
        m = "ERROR: " + str(e)
        if verbose:
            m += "\n" + traceback.format_exc()
        return m


def repl(env: Env, verbose: bool = False):
    # repl loop
    eof: bool = False

    rep('(println (str "Mal [" *host-language* "]"))', env)

    while not eof:
        try:
            line = input("user> ")
            readline.add_history(line)
            core.python_print(rep_handling_exceptions(line, env, verbose))
        except EOFError:
            eof = True


def load_file(env: Env, filename: str) -> str:
    return rep_handling_exceptions('(load-file "' + filename + '")', env)

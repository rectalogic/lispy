################ Scheme Interpreter in Python

## (c) Peter Norvig, 2010; See http://norvig.com/lispy2.html

from __future__ import annotations
import typing as ta
import re
import sys
import math
import operator as op
import time
from io import StringIO
from contextlib import contextmanager

__version__ = "0.3"
sentinel = object()

if ta.TYPE_CHECKING:
    Atom = ta.Union[bool, str, int, float, Symbol]
    # https://github.com/python/mypy/issues/731
    AtomList = ta.List[Atom, AtomList]  # type: ignore


class InPort:
    "An input port. Retains a line of chars."
    tokenizer = re.compile(
        r"""\s*(,@|[('`,)]|"(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)"""
    )

    def __init__(self, file):
        self.file = file
        self.line = ""

    def next_token(self) -> ta.Union[str, Symbol]:
        "Return the next token, reading new text into line buffer if needed."
        while True:
            if self.line == "":
                self.line = self.file.readline()
            if self.line == "":
                return SymbolTable.eof
            match = InPort.tokenizer.match(self.line)
            if match:
                token, self.line = match.groups()
                if token != "" and not token.startswith(";"):
                    return token


class Lispy:
    def __init__(
        self,
        env: ta.Optional[Env] = None,
        dotaccess: ta.Dict[ta.Type, ta.Set[str]] = {},
    ):
        self.dotaccess = dotaccess
        self.limit = None
        self.symbol_table = SymbolTable()
        self.global_env = Env(outer=env)
        self.add_globals()
        self.macro_table = {
            SymbolTable._let: self.macro_let
        }  ## More macros can go here

        self.eval(
            self.parse(
                """(begin

                    (define-macro and (lambda args
                    (if (null? args) #t
                        (if (= (length args) 1) (car args)
                            `(if ,(car args) (and ,@(cdr args)) #f)))))
                    (define-macro or (lambda args
                    (if (null? args) #f
                        (if (= (length args) 1) (car args)
                            `(if (not ,(car args)) (or ,@(cdr args)) #t)))))
                    (define-macro when (lambda args
                    `(if ,(car args) (begin ,@(cdr args)))))
                    (define-macro unless (lambda args
                    `(if (not ,(car args)) (begin ,@(cdr args)))))

                    ;; More macros can also go here

                    )
                """
            )
        )

    def add_globals(self):
        "Add some Scheme standard procedures."

        self.global_env.update(vars(math))
        self.global_env.update(
            {
                "+": op.add,
                "-": op.sub,
                "*": op.mul,
                "/": op.truediv,
                "not": op.not_,
                ">": op.gt,
                "<": op.lt,
                ">=": op.ge,
                "<=": op.le,
                "=": op.eq,
                "equal?": op.eq,
                "eq?": op.is_,
                "length": len,
                "cons": cons,
                "car": lambda x: x[0],
                "cdr": lambda x: x[1:],
                "append": op.add,
                "contains": contains,
                "list": lambda *x: list(x),
                "list?": lambda x: isinstance(x, list),
                "null?": lambda x: x == [],
                "symbol?": lambda x: isinstance(x, Symbol),
                "boolean?": lambda x: isinstance(x, bool),
                "pair?": is_pair,
                "apply": lambda proc, l: proc(*l),
                "eval": lambda x: self.eval(self.expand(x)),
                "call/cc": callcc,
                "display": lambda x: sys.stdout.write(
                    x if isinstance(x, str) else to_string(x)
                ),
                "format": lambda f, *x: str(f) % tuple(x),
                ".": self.proc_dot,
            }
        )

    def atom(self, token: str) -> Atom:
        'Numbers become numbers; #t and #f are booleans; "..." string; otherwise Symbol.'
        if token == "#t":
            return True
        elif token == "#f":
            return False
        elif token[0] == '"':
            return token[1:-1].encode("utf-8").decode("unicode_escape")
        try:
            return int(token)
        except ValueError:
            try:
                return float(token)
            except ValueError:
                return self.symbol_table.symbolize(token)

    def proc_dot(self, obj: ta.Any, attr: str, value: ta.Any = sentinel):
        if type(obj) in self.dotaccess and attr in self.dotaccess[type(obj)]:
            if value is sentinel:
                return getattr(obj, attr)
            else:
                return setattr(obj, attr, value)
        raise TypeError("Access not allowed to %s.%s" % (obj, attr))

    def macro_let(self, *args):
        args = list(args)
        x = cons(SymbolTable._let, args)
        require(x, len(args) > 1)
        bindings, body = args[0], args[1:]
        require(
            x,
            all(
                isinstance(b, list) and len(b) == 2 and isinstance(b[0], Symbol)
                for b in bindings
            ),
            "illegal binding list",
        )
        vars, vals = zip(*bindings)
        return [[SymbolTable._lambda, list(vars)] + [self.expand(e) for e in body]] + [
            self.expand(e) for e in vals
        ]

    def read(self, inport: InPort) -> ta.Union[Atom, AtomList]:
        "Read a Scheme expression from an input port."

        def read_ahead(token: str) -> ta.Union[Atom, AtomList]:
            if "(" == token:
                L: AtomList = []
                while True:
                    token = inport.next_token()
                    if token == ")":
                        return L
                    else:
                        L.append(read_ahead(token))
            elif ")" == token:
                raise SyntaxError("unexpected )")
            elif token in SymbolTable.quotes:
                return [SymbolTable.quotes[token], self.read(inport)]
            elif token is SymbolTable.eof:
                raise SyntaxError("unexpected EOF in list")
            else:
                return self.atom(token)

        # body of read:
        token1 = inport.next_token()
        return SymbolTable.eof if token1 is SymbolTable.eof else read_ahead(token1)

    def parse(self, inport: ta.Union[InPort, str]):
        "Parse a program: read and expand/error-check it."
        # Backwards compatibility: given a str, convert it to an InPort
        if isinstance(inport, str):
            inport = InPort(StringIO(inport))
        return self.expand(self.read(inport), toplevel=True)

    def expand(self, x, toplevel: bool = False):
        "Walk tree of x, making optimizations/fixes, and signaling SyntaxError."
        require(x, x != [])  # () => Error
        if not isinstance(x, list):  # constant => unchanged
            return x
        elif x[0] is SymbolTable._quote:  # (quote exp)
            require(x, len(x) == 2)
            return x
        elif x[0] is SymbolTable._if:
            if len(x) == 3:
                x = x + [None]  # (if t c) => (if t c None)
            require(x, len(x) == 4)
            return [self.expand(e) for e in x]
        elif x[0] is SymbolTable._set:
            require(x, len(x) == 3)
            var = x[1]  # (set! non-var exp) => Error
            require(x, isinstance(var, Symbol), "can set! only a symbol")
            return [SymbolTable._set, var, self.expand(x[2])]
        elif x[0] is SymbolTable._define or x[0] is SymbolTable._definemacro:
            require(x, len(x) >= 3)
            define, v, body = x[0], x[1], x[2:]
            if isinstance(v, list) and v:  # (define (f args) body)
                f, args = v[0], v[1:]  #  => (define f (lambda (args) body))
                return self.expand([define, f, [SymbolTable._lambda, args] + body])
            else:
                require(x, len(x) == 3)  # (define non-var/list exp) => Error
                require(x, isinstance(v, Symbol), "can define only a symbol")
                v = ta.cast(Symbol, v)
                exp = self.expand(x[2])
                if define is SymbolTable._definemacro:
                    require(x, toplevel, "define-macro only allowed at top level")
                    proc = self.eval(exp)
                    require(x, callable(proc), "macro must be a procedure")
                    self.macro_table[v] = proc  # (define-macro v proc)
                    return None  #  => None; add v:proc to macro_table
                return [SymbolTable._define, v, exp]
        elif x[0] is SymbolTable._begin:
            if len(x) == 1:
                return None  # (begin) => None
            else:
                return [self.expand(xi, toplevel) for xi in x]
        elif x[0] is SymbolTable._lambda:  # (lambda (x) e1 e2)
            require(x, len(x) >= 3)  #  => (lambda (x) (begin e1 e2))
            vars, body = x[1], x[2:]
            require(
                x,
                (isinstance(vars, list) and all(isinstance(v, Symbol) for v in vars))
                or isinstance(vars, Symbol),
                "illegal lambda argument list",
            )
            exp = body[0] if len(body) == 1 else [SymbolTable._begin] + body
            return [SymbolTable._lambda, vars, self.expand(exp)]
        elif x[0] is SymbolTable._quasiquote:  # `x => expand_quasiquote(x)
            require(x, len(x) == 2)
            return expand_quasiquote(x[1])
        elif isinstance(x[0], Symbol) and x[0] in self.macro_table:
            return self.expand(self.macro_table[x[0]](*x[1:]), toplevel)  # (m arg...)
        else:  #        => macroexpand if m isinstance macro
            return [self.expand(e) for e in x]  # (f arg...) => expand each

    def eval(self, x, env: ta.Optional[Env] = None):
        "Evaluate an expression in an environment."
        if env is None:
            env = self.global_env
        while True:
            # Limit runtime
            if self.limit:
                self.limit.check()

            if isinstance(x, Symbol):  # variable reference
                return env.find(x)[x]
            elif not isinstance(x, list):  # constant literal
                return x
            elif x[0] is SymbolTable._quote:  # (quote exp)
                (_, exp) = x
                return exp
            elif x[0] is SymbolTable._if:  # (if test conseq alt)
                (_, test, conseq, alt) = x
                x = conseq if self.eval(test, env) else alt
            elif x[0] is SymbolTable._set:  # (set! var exp)
                (_, var, exp) = x
                env.find(var)[var] = self.eval(exp, env)
                return None
            elif x[0] is SymbolTable._define:  # (define var exp)
                (_, var, exp) = x
                env[var] = self.eval(exp, env)
                return None
            elif x[0] is SymbolTable._lambda:  # (lambda (var*) exp)
                (_, vars, exp) = x
                return Procedure(self, vars, exp, env)
            elif x[0] is SymbolTable._begin:  # (begin exp+)
                for exp in x[1:-1]:
                    self.eval(exp, env)
                x = x[-1]
            else:  # (proc exp*)
                exps = [self.eval(exp, env) for exp in x]
                proc = exps.pop(0)
                if isinstance(proc, Procedure):
                    x = proc.exp
                    env = Env(proc.parms, exps, proc.env)
                else:
                    return proc(*exps)

    @contextmanager
    def limited(self, limit: ta.Optional[Limit]):
        try:
            self.limit = limit
            yield
        finally:
            self.limit = None

    def load(self, expressions: str, limit: ta.Optional[Limit] = None):
        "Eval every expression."
        with self.limited(limit):
            return self.eval(self.parse(expressions))

    def repl(self, prompt="lispy> ", inport=InPort(sys.stdin), out=sys.stdout):
        "A prompt-read-eval-print loop."
        print("Lispy version 2.0", file=sys.stderr)
        while True:
            try:
                if prompt:
                    print(prompt, file=sys.stderr, end="", flush=True)
                x = self.parse(inport)
                if x is SymbolTable.eof:
                    return
                val = self.eval(x)
                if val is not None and out:
                    print(to_string(val), file=out)
            except Exception as e:
                print("%s: %s" % (type(e).__name__, e))


def is_pair(x) -> bool:
    return x != [] and isinstance(x, list)


def cons(x: Atom, y):
    return [x] + y


class Escape(RuntimeWarning):
    retval: ta.Any

    def __init__(
        self, msg: str = "Sorry, can't continue this continuation any longer."
    ):
        super().__init__(msg)
        self.retval = None


def callcc(proc: Procedure):
    "Call proc with current continuation; escape only"

    ball = Escape()

    def throw(retval):
        ball.retval = retval
        raise ball

    try:
        return proc(throw)
    except Escape as w:
        if w is ball:
            return ball.retval
        raise w


def expand_quasiquote(x):
    """Expand `x => 'x; `,x => x; `(,@x y) => (append x y) """
    if not is_pair(x):
        return [SymbolTable._quote, x]
    require(x, x[0] is not SymbolTable._unquotesplicing, "can't splice here")
    if x[0] is SymbolTable._unquote:
        require(x, len(x) == 2)
        return x[1]
    elif is_pair(x[0]) and x[0][0] is SymbolTable._unquotesplicing:
        require(x[0], len(x[0]) == 2)
        return [SymbolTable._append, x[0][1], expand_quasiquote(x[1:])]
    else:
        return [SymbolTable._cons, expand_quasiquote(x[0]), expand_quasiquote(x[1:])]


def contains(l, x):
    require(l, isinstance(l, list), "expected list")
    return x in l


class Env(dict):
    "An environment: a dict of {'var':val} pairs, with an outer Env."

    def __init__(
        self,
        parms: ta.Union[str, ta.Tuple[str, ...]] = (),
        args: ta.Sequence = (),
        outer: ta.Optional[Env] = None,
        **kwargs,
    ):
        if kwargs:
            super().__init__(**kwargs)
        # Bind parm list to corresponding args, or single parm to list of args
        self.outer = outer
        if isinstance(parms, Symbol):
            self.update({parms: list(args)})
        else:
            if len(args) != len(parms):
                raise TypeError(
                    "expected %s, given %s, " % (to_string(parms), to_string(args))
                )
            self.update(zip(parms, args))

    def find(self, var) -> Env:
        "Find the innermost Env where var appears."
        if var in self:
            return self
        elif self.outer is None:
            raise LookupError(var)
        else:
            return self.outer.find(var)


class Symbol(str):
    pass


class SymbolTable(dict):
    _quote = Symbol("quote")
    _if = Symbol("if")
    _set = Symbol("set!")
    _define = Symbol("define")
    _lambda = Symbol("lambda")
    _begin = Symbol("begin")
    _definemacro = Symbol("define-macro")
    _quasiquote = Symbol("quasiquote")
    _unquote = Symbol("unquote")
    _unquotesplicing = Symbol("unquote-splicing")
    _append = Symbol("append")
    _cons = Symbol("cons")
    _let = Symbol("let")

    eof = Symbol("#<eof-object>")  # Note: uninterned; can't be read

    quotes = {"'": _quote, "`": _quasiquote, ",": _unquote, ",@": _unquotesplicing}

    def __init__(self):
        super().__init__(
            (
                (self._quote, self._quote),
                (self._if, self._if),
                (self._set, self._set),
                (self._define, self._define),
                (self._lambda, self._lambda),
                (self._begin, self._begin),
                (self._definemacro, self._definemacro),
                (self._quasiquote, self._quasiquote),
                (self._unquote, self._unquote),
                (self._unquotesplicing, self._unquotesplicing),
                (self._append, self._append),
                (self._cons, self._cons),
                (self._let, self._let),
            )
        )

    def symbolize(self, s: str) -> Symbol:
        if s not in self:
            self[s] = Symbol(s)
        return self[s]


class Procedure:
    "A user-defined Scheme procedure."

    def __init__(
        self,
        lispy: Lispy,
        parms: ta.Union[Symbol, ta.Tuple[Symbol, ...]],
        exp: ta.Sequence,
        env: Env,
    ):
        self.lispy, self.parms, self.exp, self.env = lispy, parms, exp, env

    def limit_call(self, *args, limit: ta.Optional[Limit] = None):
        with self.lispy.limited(limit):
            self(*args)

    def __call__(self, *args):
        return self.lispy.eval(self.exp, Env(self.parms, args, self.env))


class Limit:
    def __init__(self, time_limit: float):
        self.start_time = time.perf_counter()
        self.time_limit = time_limit

    def check(self):
        if (time.perf_counter() - self.start_time) >= self.time_limit:
            raise LimitError("time limit exceeded")


class LimitError(RuntimeError):
    pass


def to_string(x: ta.Any) -> str:
    "Convert a Python object back into a Lisp-readable string."
    if x is True:
        return "#t"
    elif x is False:
        return "#f"
    elif isinstance(x, Symbol):
        return x
    elif isinstance(x, str):
        return '"%s"' % x.encode("unicode_escape").decode("utf-8").replace('"', r"\"")
    elif isinstance(x, list):
        return "(" + " ".join(map(to_string, x)) + ")"
    else:
        return str(x)


def require(x, predicate, msg="wrong length"):
    "Signal a syntax error if predicate is false."
    if not predicate:
        raise SyntaxError(to_string(x) + ": " + msg)


if __name__ == "__main__":
    Lispy().repl()

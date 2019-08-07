################ Scheme Interpreter in Python

## (c) Peter Norvig, 2010; See http://norvig.com/lispy2.html

################ Symbol, Procedure, classes

import re, sys
import math, operator as op
from io import StringIO

isa = isinstance


class Lispy:
    def __init__(self, env=None):
        self.symbol_table = SymbolTable()
        self.global_env = env if env is not None else Env()
        self.add_globals()
        self.macro_table = {SymbolTable._let: self.macro_let}  ## More macros can go here

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
                "list": lambda *x: list(x),
                "list?": lambda x: isa(x, list),
                "null?": lambda x: x == [],
                "symbol?": lambda x: isa(x, Symbol),
                "boolean?": lambda x: isa(x, bool),
                "pair?": is_pair,
                "apply": lambda proc, l: proc(*l),
                "eval": lambda x: self.eval(self.expand(x)),
                "call/cc": callcc,
                "display": lambda x: sys.stdout.write(
                    x if isa(x, str) else to_string(x)
                ),
            }
        )

    def atom(self, token):
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

    def macro_let(self, *args):
        args = list(args)
        x = cons(SymbolTable._let, args)
        require(x, len(args) > 1)
        bindings, body = args[0], args[1:]
        require(
            x,
            all(isa(b, list) and len(b) == 2 and isa(b[0], Symbol) for b in bindings),
            "illegal binding list",
        )
        vars, vals = zip(*bindings)
        return [[SymbolTable._lambda, list(vars)] + [self.expand(e) for e in body]] + [
            self.expand(e) for e in vals
        ]

    def read(self, inport):
        "Read a Scheme expression from an input port."

        def read_ahead(token):
            if "(" == token:
                L = []
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

    def parse(self, inport):
        "Parse a program: read and expand/error-check it."
        # Backwards compatibility: given a str, convert it to an InPort
        if isinstance(inport, str):
            inport = InPort(StringIO(inport))
        return self.expand(self.read(inport), toplevel=True)

    def expand(self, x, toplevel=False):
        "Walk tree of x, making optimizations/fixes, and signaling SyntaxError."
        require(x, x != [])  # () => Error
        if not isa(x, list):  # constant => unchanged
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
            require(x, isa(var, Symbol), "can set! only a symbol")
            return [SymbolTable._set, var, self.expand(x[2])]
        elif x[0] is SymbolTable._define or x[0] is SymbolTable._definemacro:
            require(x, len(x) >= 3)
            define, v, body = x[0], x[1], x[2:]
            if isa(v, list) and v:  # (define (f args) body)
                f, args = v[0], v[1:]  #  => (define f (lambda (args) body))
                return self.expand([define, f, [SymbolTable._lambda, args] + body])
            else:
                require(x, len(x) == 3)  # (define non-var/list exp) => Error
                require(x, isa(v, Symbol), "can define only a symbol")
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
                (isa(vars, list) and all(isa(v, Symbol) for v in vars))
                or isa(vars, Symbol),
                "illegal lambda argument list",
            )
            exp = body[0] if len(body) == 1 else [SymbolTable._begin] + body
            return [SymbolTable._lambda, vars, self.expand(exp)]
        elif x[0] is SymbolTable._quasiquote:  # `x => expand_quasiquote(x)
            require(x, len(x) == 2)
            return expand_quasiquote(x[1])
        elif isa(x[0], Symbol) and x[0] in self.macro_table:
            return self.expand(self.macro_table[x[0]](*x[1:]), toplevel)  # (m arg...)
        else:  #        => macroexpand if m isa macro
            return [self.expand(e) for e in x]  # (f arg...) => expand each

    def eval(self, x, env=None):
        "Evaluate an expression in an environment."
        if env is None:
            env = self.global_env
        while True:
            if isa(x, Symbol):  # variable reference
                return env.find(x)[x]
            elif not isa(x, list):  # constant literal
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
                if isa(proc, Procedure):
                    x = proc.exp
                    env = Env(proc.parms, exps, proc.env)
                else:
                    return proc(*exps)


def is_pair(x):
    return x != [] and isa(x, list)


def cons(x, y):
    return [x] + y


def callcc(proc):
    "Call proc with current continuation; escape only"
    ball = RuntimeWarning("Sorry, can't continue this continuation any longer.")

    def throw(retval):
        ball.retval = retval
        raise ball

    try:
        return proc(throw)
    except RuntimeWarning as w:
        if w is ball:
            return ball.retval
        else:
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


class Env(dict):
    "An environment: a dict of {'var':val} pairs, with an outer Env."

    def __init__(self, parms=(), args=(), outer=None):
        # Bind parm list to corresponding args, or single parm to list of args
        self.outer = outer
        if isa(parms, Symbol):
            self.update({parms: list(args)})
        else:
            if len(args) != len(parms):
                raise TypeError(
                    "expected %s, given %s, " % (to_string(parms), to_string(args))
                )
            self.update(zip(parms, args))

    def find(self, var):
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
        super().__init__((
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
        ))

    def symbolize(self, s):
        if s not in self:
            self[s] = Symbol(s)
        return self[s]


class Procedure(object):
    "A user-defined Scheme procedure."

    def __init__(self, lispy, parms, exp, env):
        self.lispy, self.parms, self.exp, self.env = lispy, parms, exp, env

    def __call__(self, *args):
        return self.lispy.eval(self.exp, Env(self.parms, args, self.env))


class InPort(object):
    "An input port. Retains a line of chars."
    tokenizer = r"""\s*(,@|[('`,)]|"(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)"""

    def __init__(self, file):
        self.file = file
        self.line = ""

    def next_token(self):
        "Return the next token, reading new text into line buffer if needed."
        while True:
            if self.line == "":
                self.line = self.file.readline()
            if self.line == "":
                return SymbolTable.eof
            token, self.line = re.match(InPort.tokenizer, self.line).groups()
            if token != "" and not token.startswith(";"):
                return token


def readchar(inport):
    "Read the next character from an input port."
    if inport.line != "":
        ch, inport.line = inport.line[0], inport.line[1:]
        return ch
    else:
        return inport.file.read(1) or SymbolTable.eof


def to_string(x):
    "Convert a Python object back into a Lisp-readable string."
    if x is True:
        return "#t"
    elif x is False:
        return "#f"
    elif isa(x, Symbol):
        return x
    elif isa(x, str):
        return '"%s"' % x.encode("unicode_escape").decode("utf-8").replace('"', r"\"")
    elif isa(x, list):
        return "(" + " ".join(map(to_string, x)) + ")"
    else:
        return str(x)


def require(x, predicate, msg="wrong length"):
    "Signal a syntax error if predicate is false."
    if not predicate:
        raise SyntaxError(to_string(x) + ": " + msg)


def load(filename):
    "Eval every expression from a file."
    repl(None, InPort(open(filename)), None)


def repl(prompt="lispy> ", inport=InPort(sys.stdin), out=sys.stdout):
    "A prompt-read-eval-print loop."
    lispy = Lispy()
    print("Lispy version 2.0", file=sys.stderr)
    while True:
        try:
            if prompt:
                print(prompt, file=sys.stderr, end="", flush=True)
            x = lispy.parse(inport)
            if x is SymbolTable.eof:
                return
            val = lispy.eval(x)
            if val is not None and out:
                print(to_string(val), file=out)
        except Exception as e:
            print("%s: %s" % (type(e).__name__, e))


if __name__ == "__main__":
    repl()

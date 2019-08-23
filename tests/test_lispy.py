import inspect
import pytest
import lispy


@pytest.fixture(scope="module")
def interpreter():
    return lispy.Lispy(
        env=lispy.Env(native=Native()), dotaccess={Native: {"count", "name", "adder"}}
    )


@pytest.mark.parametrize(
    "expression, limit, expected",
    [
        ("(quote (testing 1 (2.0) -3.14e159))", None, ["testing", 1, [2.0], -3.14e159]),
        ("(+ 2 2)", None, 4),
        ("(+ (* 2 100) (* 1 10))", None, 210),
        ("(if (> 6 5) (+ 1 1) (+ 2 2))", None, 2),
        ("(if (< 6 5) (+ 1 1) (+ 2 2))", None, 4),
        ("(define x 3)", None, None),
        ("x", None, 3),
        ("(+ x x)", None, 6),
        ("(begin (define x 1) (set! x (+ x 1)) (+ x 1))", None, 3),
        ("((lambda (x) (+ x x)) 5)", None, 10),
        ("(define twice (lambda (x) (* 2 x)))", None, None),
        ("(twice 5)", None, 10),
        ("(define compose (lambda (f g) (lambda (x) (f (g x)))))", None, None),
        ("((compose list twice) 5)", None, [10]),
        ("(define repeat (lambda (f) (compose f f)))", None, None),
        ("((repeat twice) 5)", None, 20),
        ("((repeat (repeat twice)) 5)", None, 80),
        ("(define fact (lambda (n) (if (<= n 1) 1 (* n (fact (- n 1))))))", None, None),
        ("(fact 3)", None, 6),
        (
            "(fact 50)",
            None,
            30414093201713378043612608166064768844377641568960512000000000000,
        ),
        ("(define abs (lambda (n) ((if (> n 0) + -) 0 n)))", None, None),
        ("(list (abs -3) (abs 0) (abs 3))", None, [3, 0, 3]),
        (
            """(define combine (lambda (f)
            (lambda (x y)
            (if (null? x) (quote ())
                (f (list (car x) (car y))
                    ((combine f) (cdr x) (cdr y)))))))""",
            None,
            None,
        ),
        ("(define zip (combine cons))", None, None),
        ("(zip (list 1 2 3 4) (list 5 6 7 8))", None, [[1, 5], [2, 6], [3, 7], [4, 8]]),
        (
            """(define riff-shuffle (lambda (deck) (begin
            (define take (lambda (n seq) (if (<= n 0) (quote ()) (cons (car seq) (take (- n 1) (cdr seq))))))
            (define drop (lambda (n seq) (if (<= n 0) seq (drop (- n 1) (cdr seq)))))
            (define mid (lambda (seq) (/ (length seq) 2)))
            ((combine append) (take (mid deck) deck) (drop (mid deck) deck)))))""",
            None,
            None,
        ),
        ("(riff-shuffle (list 1 2 3 4 5 6 7 8))", None, [1, 5, 2, 6, 3, 7, 4, 8]),
        (
            "((repeat riff-shuffle) (list 1 2 3 4 5 6 7 8))",
            None,
            [1, 3, 5, 7, 2, 4, 6, 8],
        ),
        (
            "(riff-shuffle (riff-shuffle (riff-shuffle (list 1 2 3 4 5 6 7 8))))",
            None,
            [1, 2, 3, 4, 5, 6, 7, 8],
        ),
        ("()", None, SyntaxError),
        ("(set! x)", None, SyntaxError),
        ("(define 3 4)", None, SyntaxError),
        ("(quote 1 2)", None, SyntaxError),
        ("(if 1 2 3 4)", None, SyntaxError),
        ("(lambda 3 3)", None, SyntaxError),
        ("(lambda (x))", None, SyntaxError),
        (
            """(if (= 1 2) (define-macro a 'a) 
            (define-macro a 'b))""",
            None,
            SyntaxError,
        ),
        ("(define (twice x) (* 2 x))", None, None),
        ("(twice 2)", None, 4),
        ("(twice 2 2)", None, TypeError),
        ("(define lyst (lambda items items))", None, None),
        ("(lyst 1 2 3 (+ 2 2))", None, [1, 2, 3, 4]),
        ("(if 1 2)", None, 2),
        ("(if (= 3 4) 2)", None, None),
        ("(define ((account bal) amt) (set! bal (+ bal amt)) bal)", None, None),
        ("(define a1 (account 100))", None, None),
        ("(a1 0)", None, 100),
        ("(a1 10)", None, 110),
        ("(a1 10)", None, 120),
        (
            """(define (newton guess function derivative epsilon)
            (define guess2 (- guess (/ (function guess) (derivative guess))))
            (if (< (abs (- guess guess2)) epsilon) guess2
                (newton guess2 function derivative epsilon)))""",
            None,
            None,
        ),
        (
            """(define (square-root a)
            (newton 1 (lambda (x) (- (* x x) a)) (lambda (x) (* 2 x)) 1e-8))""",
            None,
            None,
        ),
        ("(> (square-root 200.) 14.14213)", None, True),
        ("(< (square-root 200.) 14.14215)", None, True),
        ("(= (square-root 200.) (sqrt 200.))", None, True),
        (
            """(define (sum-squares-range start end)
                (define (sumsq-acc start end acc)
                    (if (> start end) acc (sumsq-acc (+ start 1) end (+ (* start start) acc))))
                (sumsq-acc start end 0))""",
            None,
            None,
        ),
        ("(sum-squares-range 1 3000)", None, 9004500500),  ## Tests tail recursion
        ("(call/cc (lambda (throw) (+ 5 (* 10 (throw 1))))) ;; throw", None, 1),
        ("(call/cc (lambda (throw) (+ 5 (* 10 1)))) ;; do not throw", None, 15),
        (
            """(call/cc (lambda (throw) 
                (+ 5 (* 10 (call/cc (lambda (escape) (* 100 (escape 3)))))))) ; 1 level""",
            None,
            35,
        ),
        (
            """(call/cc (lambda (throw) 
                (+ 5 (* 10 (call/cc (lambda (escape) (* 100 (throw 3)))))))) ; 2 levels""",
            None,
            3,
        ),
        (
            """(call/cc (lambda (throw) 
                (+ 5 (* 10 (call/cc (lambda (escape) (* 100 1))))))) ; 0 levels""",
            None,
            1005,
        ),
        ("(let ((a 1) (b 2)) (+ a b))", None, 3),
        ("(let ((a 1) (b 2 3)) (+ a b))", None, SyntaxError),
        ("(and 1 2 3)", None, 3),
        ("(and (> 2 1) 2 3)", None, 3),
        ("(and)", None, True),
        ("(and (> 2 1) (> 2 3))", None, False),
        (
            "(define-macro unless (lambda args `(if (not ,(car args)) (begin ,@(cdr args))))) ; test `",
            None,
            None,
        ),
        ("(unless (= 2 (+ 1 1)) (display 2) 3 4)", None, None),
        (r'(unless (= 4 (+ 1 1)) (display 2) (display "\n") 3 4)', None, 4),
        ("(quote x)", None, "x"),
        ("(quote (1 2 three))", None, [1, 2, "three"]),
        ("'x", None, "x"),
        ("'(one 2 3)", None, ["one", 2, 3]),
        ("(define L (list 1 2 3))", None, None),
        ("`(testing ,@L testing)", None, ["testing", 1, 2, 3, "testing"]),
        ("`(testing ,L testing)", None, ["testing", [1, 2, 3], "testing"]),
        ("`,@L", None, SyntaxError),
        (
            """'(1 ;test comments '
            ;skip this line
            2 ; more ; comments ; ) )
            3) ; final comment""",
            None,
            [1, 2, 3],
        ),
        ("(. native 'count)", None, 7),
        ("(. native 'private)", None, TypeError),
        (
            """(begin
            ((. native 'adder) 4)
            (. native 'count)
            )""",
            None,
            11,
        ),
        (
            """(begin
            (. native 'count 44)
            (. native 'count)
            )""",
            None,
            44,
        ),
        ("(. native 'name)", None, "native"),
        (
            """(begin
            (. native 'name "changed")
            (. native 'name)
            )""",
            None,
            "changed",
        ),
        ("(define (infinite) (infinite))", None, None),
        ("(infinite))", 1, lispy.LimitError),
        (
            """(format "now is the %s for all %d men" "time" 33)""",
            None,
            "now is the time for all 33 men",
        ),
    ],
)
def test_expressions(interpreter, expression, limit, expected):
    limit = lispy.Limit(limit) if limit else None
    if inspect.isclass(expected) and issubclass(expected, Exception):
        with pytest.raises(expected):
            interpreter.load(expression, limit=limit)
    else:
        assert expected == interpreter.load(expression, limit=limit)


class Native:
    def __init__(self):
        self._count = 7
        self.name = "native"

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, v):
        self._count = v

    def adder(self, v):
        self._count += v

    def private(self):
        pass

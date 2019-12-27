import unittest

from lispy import rep as step7_quote


class TestStep7(unittest.TestCase):
    def setUp(self) -> None:
        self._repl_env = step7_quote.init_repl_env()

    def test_step7_cons(self):
        self.assertEqual("(1)", step7_quote.rep("(cons 1 (list))", self._repl_env))

    def test_step7_concat(self):
        self.assertEqual("()", step7_quote.rep("(concat)", self._repl_env))

    def test_step7_quote(self):
        self.assertEqual("(+ 1 2)", step7_quote.rep("(quote (+ 1 2))", self._repl_env))

    def test_step7_quasiquote(self):
        self.assertEqual(
            "(+ 1 3)",
            step7_quote.rep("(quasiquote (+ 1 (unquote (+ 1 2))))", self._repl_env),
        )

    def test_step7_quasiquote_advanced(self):
        self.assertEqual("(2)", step7_quote.rep("(def! c '(2))", self._repl_env))
        self.assertEqual("(1 2 3)", step7_quote.rep("`[1 ~@c 3]", self._repl_env))


if __name__ == "__main__":
    unittest.main()

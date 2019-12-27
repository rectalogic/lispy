import unittest

from lispy import rep as step5_tco


class TestStep5(unittest.TestCase):
    def setUp(self) -> None:
        self._repl_env = step5_tco.init_repl_env()

    def test_step5_tco(self):
        self.assertEqual(
            "#<function>",
            step5_tco.rep(
                "(def! sum2 (fn* (n acc) (if (= n 0) acc (sum2 (- n 1) (+ n acc)))))",
                self._repl_env,
            ),
        )
        self.assertEqual("55", step5_tco.rep("(sum2 10 0)", self._repl_env))
        self.assertEqual("nil", step5_tco.rep("(def! res2 nil)", self._repl_env))
        self.assertEqual(
            "500500", step5_tco.rep("(def! res2 (sum2 1000 0))", self._repl_env)
        )
        self.assertEqual("500500", step5_tco.rep("res2", self._repl_env))


if __name__ == "__main__":
    unittest.main()

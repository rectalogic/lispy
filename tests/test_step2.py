import unittest

from lispy import rep as step2_eval


class TestStep2(unittest.TestCase):
    def setUp(self) -> None:
        self._repl_env = step2_eval.init_repl_env()

    def test_step2_let_multiple(self):
        self.assertEqual('{"a" 15}', step2_eval.rep('{"a" (+ 7 8)} ', self._repl_env))


if __name__ == "__main__":
    unittest.main()

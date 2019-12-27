import unittest

from lispy import rep
from lispy.env import ExecutionLimit
from lispy.mal_types import MalExecutionLimitError


class TestLimit(unittest.TestCase):
    def setUp(self) -> None:
        self._repl_env = rep.init_repl_env(execution_limit=ExecutionLimit(1))

    def rep(self, input: str) -> str:
        return rep.rep(input, self._repl_env)

    def test_infinite_recursion(self):
        self.rep("""(def! recurse (fn* () (recurse)))""")
        with self.assertRaises(MalExecutionLimitError):
            self.rep("(recurse)")


if __name__ == "__main__":
    unittest.main()

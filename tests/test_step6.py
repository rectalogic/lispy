import os
import unittest

from lispy import reader
from lispy import rep as step6_file
from lispy.env import Env
from lispy.mal_types import MalList, MalAtom, MalInt
from lispy.mal_types import MalSyntaxException, MalString


class TestStep6(unittest.TestCase):
    def setUp(self) -> None:
        self._repl_env = step6_file.init_repl_env()

    def test_step6_string_unbalanced(self):
        with self.assertRaises(MalSyntaxException):
            step6_file.rep('"foo', self._repl_env)

    def test_step6_standard_string(self):
        self.assertEqual(
            '"foo"', step6_file.EVAL(MalString('"foo"'), Env(None)).native()
        )
        self.assertEqual('"foo"', step6_file.rep('"foo"', self._repl_env).__str__())
        self.assertEqual('"foo"', MalString('"foo"').native())
        self.assertEqual('"\\"foo\\""', MalString('"foo"').__str__())

    def test_step6_reader_read_string(self):
        read = reader.read('(read-string "(1 2   (3  4) nil)")')
        self.assertTrue(isinstance(read, MalList))
        arg = read.native()[1]
        self.assertTrue(isinstance(arg, MalString))
        native_str = arg.native()
        self.assertEqual("(1 2   (3  4) nil)", native_str)

    def test_step6_read_string_no_escapes(self):
        self.assertEqual(
            "(1 2 (3 4) nil)",
            step6_file.rep('(read-string "(1 2   (3  4) nil)")', self._repl_env),
        )

    def test_step6_slurp(self):
        f = os.path.join(os.path.dirname(__file__), "mal", "tests", "test.txt")
        self.assertEqual(
            '"A line of text\\n"', step6_file.rep(f'(slurp "{f}")', self._repl_env)
        )

    def test_step6_eval(self):
        self.assertEqual(
            "2", step6_file.rep('(eval (read-string "(+ 1 1)"))', self._repl_env)
        )

    def test_step6_str(self):
        self.assertEqual(
            '"abc2def ghi"',
            step6_file.rep('(str "abc" 2 "def" " ghi")', self._repl_env),
        )

    def test_step6_atom_type(self):
        atom = step6_file.EVAL(MalAtom(MalInt(1)), Env(None))
        self.assertEqual(1, atom.native().native())

    def test_step6_read_atom(self):
        atom = step6_file.EVAL(step6_file.READ("(atom 1)"), self._repl_env)
        self.assertEqual(1, atom.native().native())

    def test_step6_atom_deref(self):
        self.assertEqual("1", step6_file.rep("(deref (atom 1))", self._repl_env))

    def test_step6_atom_p(self):
        self.assertEqual("true", step6_file.rep("(atom? (atom 1))", self._repl_env))
        self.assertEqual("false", step6_file.rep("(atom? (+ 1 2))", self._repl_env))

    def test_step6_reset(self):
        self.assertEqual(
            "3", step6_file.rep("(do (def! a (atom 2)) (reset! a 3))", self._repl_env)
        )

    def test_step6_swap(self):
        self.assertEqual(
            "#<function>",
            step6_file.rep("(def! inc3 (fn* (a) (+ 3 a)))", self._repl_env),
        )
        self.assertEqual(
            "(atom 2)", step6_file.rep("(def! a (atom 2))", self._repl_env)
        )
        self.assertEqual("3", step6_file.rep("(swap! a + 1)", self._repl_env))


if __name__ == "__main__":
    unittest.main()

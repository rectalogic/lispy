from __future__ import annotations
from typing import Iterator
import unittest

from lispy import rep


class TestTokenize(unittest.TestCase):
    def setUp(self) -> None:
        self._repl_env = rep.init_repl_env()

    def test_tokenize_single_line(self):
        self.assertEqual("5", rep.rep("(+ 3 2)", self._repl_env))

    def test_tokenize_line_iter(self):
        lines = [
            "(def! contains (fn* (m l)\n",
            "                    (let* (f (first l))\n",
            "                          (if (nil? f)\n",
            "                            false\n",
            "                            (if (= m f)\n",
            "                              true\n",
            "                              (contains m (rest l)))))))\n",
        ]
        self.assertEqual("#<function>", rep.rep(iter(lines), self._repl_env))
        self.assertEqual("true", rep.rep("(contains 3 '(2 3 1))", self._repl_env))

    def test_tokenize_line_generator(self):
        lines = [
            "(+\n",
            " 3\n",
            " 2)\n",
        ]

        def line_reader() -> Iterator[str]:
            for l in lines:
                yield l

        self.assertEqual("5", rep.rep(line_reader(), self._repl_env))


if __name__ == "__main__":
    unittest.main()

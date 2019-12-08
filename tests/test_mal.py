import os
import glob
import functools
import logging
import unittest

from lispy import stepA_mal
from lispy.mal_types import MalString
from tests.runner import Runner

log = logging.getLogger(__name__)


class TestMal(Runner):
    def test_mal(self):
        for test_file in sorted(
            glob.glob(os.path.join(os.path.dirname(__file__), "step*.mal"))
        ):
            test_basename = os.path.basename(test_file)
            cwd = os.getcwd()
            try:
                os.chdir(os.path.dirname(__file__))
                repl_env = stepA_mal.init_repl_env(argv=[])
                with self.subTest(test_file=test_basename):
                    self.run_tests(
                        test_file, functools.partial(stepA_mal.rep, env=repl_env),
                    )
            finally:
                os.chdir(cwd)

    def test_mal_in_mal(self):
        EXCLUDES = ("step5_tco.mal", "step_test_errors.mal")
        for test_file in sorted(
            glob.glob(os.path.join(os.path.dirname(__file__), "step*.mal"))
        ):
            test_basename = os.path.basename(test_file)
            if test_basename in EXCLUDES:
                continue
            cwd = os.getcwd()
            try:
                os.chdir(os.path.dirname(__file__))
                repl_env = stepA_mal.init_repl_env(argv=[test_file])
                mal_script = os.path.join(
                    os.path.dirname(__file__), "..", "mal", "stepA_mal.mal"
                )
                stepA_mal.rep_handling_exceptions(
                    '(load-file "' + mal_script + '")', repl_env
                )
                mal_function = repl_env.get("rep")

                def rep(s):
                    return mal_function.call([MalString(s)]).native()

                with self.subTest(test_file=test_basename):
                    self.run_tests(test_file, rep)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()

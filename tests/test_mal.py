import os
from pathlib import Path
import functools
import logging
import unittest

from lispy import rep
from lispy.mal_types import MalString
from tests.runner import Runner

log = logging.getLogger(__name__)

TEST_DIR = Path(__file__).parent / "mal" / "tests"

STEP_TEST_FILES = sorted(TEST_DIR.glob("step*.mal"))
EXTRA_TEST_FILES = sorted(
    TEST_DIR / "lib" / f
    for f in [
        "protocols.mal",
        "alias-hacks.mal",
        "equality.mal",
        "load-file-once.mal",
        # "memoize.mal",
        "pprint.mal",
        "protocols.mal",
        "reducers.mal",
        "test_cascade.mal",
        "threading.mal",
        "trivial.mal",
    ]
)


class TestMal(Runner):
    def test_mal_steps(self):
        self.run_mal(STEP_TEST_FILES)

    def test_mal_extra(self):
        self.run_mal(STEP_TEST_FILES)

    def test_mal_perf(self):
        self.run_mal(TEST_DIR.glob("perf*.mal"))

    def run_mal(self, test_files):
        for test_file in test_files:
            test_basename = test_file.name
            cwd = Path.cwd()
            try:
                os.chdir(TEST_DIR)
                repl_env = rep.init_repl_env(argv=[])
                with self.subTest(test_file=test_basename):
                    self.run_tests(
                        test_file, functools.partial(rep.rep, env=repl_env), hard=True,
                    )
            finally:
                os.chdir(cwd)

    def test_mal_in_mal_steps(self):
        excludes = ("step5_tco.mal", "step_test_errors.mal")
        self.run_mal_in_mal(STEP_TEST_FILES, excludes)

    def run_mal_in_mal(self, test_files, excludes=None):
        for test_file in test_files:
            test_basename = test_file.name
            if excludes and test_basename in excludes:
                continue
            cwd = Path.cwd()
            try:
                os.chdir(TEST_DIR)
                repl_env = rep.init_repl_env(argv=[str(test_file)])
                mal_script = TEST_DIR / ".." / "mal" / "stepA_mal.mal"
                rep.load_file(repl_env, mal_script)
                mal_function = repl_env.get("rep")

                def mal_rep(s):
                    return mal_function.call([MalString(s)]).native()

                with self.subTest(test_file=test_basename):
                    self.run_tests(test_file, mal_rep, hard=True)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()

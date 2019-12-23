import os
import glob
import functools
import logging
import unittest

from lispy import stepA_mal
from lispy.mal_types import MalString
from tests.runner import Runner

log = logging.getLogger(__name__)

TEST_DIR = os.path.join(os.path.dirname(__file__), "mal", "tests")

STEP_TEST_FILES = sorted(glob.glob(os.path.join(TEST_DIR, "step*.mal")))
EXTRA_TEST_FILES = sorted(
    os.path.join(TEST_DIR, "lib", f)
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
        self.run_mal(glob.glob(os.path.join(TEST_DIR, "perf*.mal")))

    def run_mal(self, test_files):
        for test_file in test_files:
            test_basename = os.path.basename(test_file)
            cwd = os.getcwd()
            try:
                os.chdir(os.path.join(TEST_DIR))
                repl_env = stepA_mal.init_repl_env(argv=[])
                with self.subTest(test_file=test_basename):
                    self.run_tests(
                        test_file,
                        functools.partial(stepA_mal.rep, env=repl_env),
                        hard=True,
                    )
            finally:
                os.chdir(cwd)

    def test_mal_in_mal_steps(self):
        excludes = ("step5_tco.mal", "step_test_errors.mal")
        self.run_mal_in_mal(STEP_TEST_FILES, excludes)

    def run_mal_in_mal(self, test_files, excludes=None):
        for test_file in test_files:
            test_basename = os.path.basename(test_file)
            if excludes and test_basename in excludes:
                continue
            cwd = os.getcwd()
            try:
                os.chdir(os.path.join(TEST_DIR))
                repl_env = stepA_mal.init_repl_env(argv=[test_file])
                mal_script = os.path.join(TEST_DIR, "..", "mal", "stepA_mal.mal")
                stepA_mal.load_file(repl_env, mal_script)
                mal_function = repl_env.get("rep")

                def rep(s):
                    return mal_function.call([MalString(s)]).native()

                with self.subTest(test_file=test_basename):
                    self.run_tests(test_file, rep, hard=True)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()

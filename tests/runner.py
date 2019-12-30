from pathlib import Path
import re
import logging
import unittest
from unittest import mock

from lispy.mal_types import MalException, MalUnknownSymbolException

log = logging.getLogger(__name__)


# From https://github.com/kanaka/mal/blob/master/runtest.py
class MalTestReader:
    def __init__(self, test_file):
        self.line_num = 0
        with open(test_file, newline="") as f:
            self.data = f.read().split("\n")
        self.soft = False
        self.deferrable = False
        self.optional = False

    def __iter__(self):
        return self

    def __next__(self):
        if not self.next():
            raise StopIteration()
        return (self.form, self.msg, self.ret, self.out, self.soft, self.line_num)

    def next(self):
        self.msg = None
        self.form = None
        self.out = ""
        self.ret = None

        while self.data:
            self.line_num += 1
            line = self.data.pop(0)
            if re.match(r"^\s*$", line):  # blank line
                continue
            elif line[0:3] == ";;;":  # ignore comment
                continue
            elif line[0:2] == ";;":  # output comment
                self.msg = line[3:]
                return True
            elif line[0:5] == ";>>> ":  # settings/commands
                settings = {}
                exec(line[5:], {}, settings)
                if "soft" in settings:
                    self.soft = settings["soft"]
                if "deferrable" in settings and settings["deferrable"]:
                    self.deferrable = "\nSkipping deferrable and optional tests"
                    return True
                if "optional" in settings and settings["optional"]:
                    self.optional = "\nSkipping optional tests"
                    return True
                continue
            elif line[0:1] == ";":  # unexpected comment
                raise Exception(
                    "Test data error at line %d:\n%s" % (self.line_num, line)
                )
            self.form = line  # the line is a form to send

            # Now find the output and return value
            while self.data:
                line = self.data[0]
                if line[0:3] == ";=>":
                    self.ret = line[3:]
                    self.line_num += 1
                    self.data.pop(0)
                    break
                elif line[0:2] == ";/":
                    self.out = self.out + line[2:] + "\n"
                    self.line_num += 1
                    self.data.pop(0)
                else:
                    self.ret = ""
                    break
            if self.ret is not None:
                break

        return self.form


class Runner(unittest.TestCase):
    def run_tests(self, test_file, rep, hard=False):
        for form, msg, ret, out, soft, line_num in MalTestReader(test_file):
            if msg is not None:
                log.info(msg)
                continue
            if form is None:
                continue
            with self.subTest(line=line_num, form=form):
                log.debug(
                    "TEST: %s -> [%s,%s]" % (repr(form), repr(out), ret), end="",
                )
                with mock.patch("lispy.core.python_print") as p:
                    err = ""
                    test_ret = ""
                    try:
                        test_ret = rep(form)
                    except MalUnknownSymbolException as e:
                        err = "'" + e.func + "' not found\n"
                    except MalException as e:
                        err = "ERROR: " + str(e) + "\n"
                    if ret == "" and out == "":
                        continue
                    if p.call_args_list:
                        test_out = (
                            "\n".join(arg[0][0] for arg in p.call_args_list) + "\n"
                        )
                    elif err:
                        test_out = err
                    else:
                        test_out = ""

                    expects = out + re.escape(ret)
                    if not hard and soft:
                        if not re.search(expects, test_out + test_ret):
                            test_name = Path(test_file).name
                            self.skipTest(
                                f"soft failure {test_name}:{line_num} --> {form}"
                            )
                    else:
                        self.assertRegex(test_out + test_ret, expects)

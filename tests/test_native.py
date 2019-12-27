from __future__ import annotations
from typing import List, Optional
import os
import logging
import unittest
import glob
import functools
import dataclasses
from urllib.parse import urlparse

from lispy import rep
from tests.runner import Runner
from tests.test_mal import TEST_DIR

log = logging.getLogger(__name__)


class Person:
    def __init__(
        self,
        name: Name,
        address: Address,
        friends: Optional[List[Person]] = None,
        living: bool = True,
    ):
        self.name = name
        self.address = address
        self.friends = friends
        self.living = living

    def set_name(self, name: Name):
        self.name = name

    @property
    def formatted_name(self) -> str:
        return f"{self.name.given} {self.name.family}"

    def is_friend(self, persion: Person) -> bool:
        return bool(self.friends and persion in self.friends)

    def raise_error(self):
        raise ValueError("this method always raises")


@dataclasses.dataclass
class Name:
    given: str
    family: str

    def same_family(self, family: str) -> bool:
        return self.family == family


@dataclasses.dataclass
class Address:
    number: int = 0
    city: Optional[str] = None
    state: Optional[str] = None


p1 = Person(
    Name(given="Donald", family="Duck"),
    Address(number=100, city="New York", state="NY"),
)
p2 = Person(
    Name(given="Mickey", family="Mouse"),
    Address(number=22, city="Falstaff", state="AZ"),
    friends=[p1],
)
p3 = Person(
    Name(given="Snow", family="White"),
    Address(number=33, city="Edison", state="NJ"),
    friends=[p1, p2],
)

INJECTIONS = {
    "native_unrestricted.mal": {
        "injections": {
            "p1": p1,
            "p2": p2,
            "p3": p3,
            "make-name": Name,
            "make-address": Address,
            "urlparse": urlparse,
        },
    },
    "native_restricted.mal": {
        "injections": {"p1": p1, "p2": p2},
        "restrictions": {Person: ["name", "is_friend"], Name: ["family"]},
    },
}


class TestNative(Runner):
    def test_native(self):
        for test_file in sorted(glob.glob(os.path.join(TEST_DIR, "native*.mal"))):
            test_basename = os.path.basename(test_file)
            cwd = os.getcwd()
            try:
                os.chdir(os.path.dirname(__file__))
                repl_env = rep.init_repl_env(argv=[])
                repl_env.inject_native(**INJECTIONS[test_basename])
                with self.subTest(test_file=test_basename):
                    self.run_tests(
                        test_file, functools.partial(rep.rep, env=repl_env),
                    )
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()

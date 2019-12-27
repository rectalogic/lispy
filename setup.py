import re
import sys

from setuptools import setup, find_packages
from setuptools.command.test import test


def get_version(filename):
    with open(filename) as fh:
        metadata = dict(re.findall('__([a-z]+)__ = "([^"]+)"', fh.read()))
        return metadata["version"]


class Tox(test):
    user_options = [(b"tox-args=", b"a", "Arguments to pass to tox")]

    def initialize_options(self):
        test.initialize_options(self)
        self.tox_args = None

    def finalize_options(self):
        test.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import tox
        import shlex

        args = self.tox_args
        if args:
            args = shlex.split(self.tox_args)
        errno = tox.cmdline(args=args)
        sys.exit(errno)


setup(
    name="lispy",
    version=get_version("lispy/__init__.py"),
    url="https://github.com/rectalogic/lispy",
    license="Mozilla Public License, v. 2.0",
    description="Clojure interpreter extension language for Python based on mal (Make a Lisp)",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(include=["lispy", "lispy.*"]),
    install_requires=["Arpeggio>=1.9.2"],
    tests_require=["tox"],
    cmdclass={"test": Tox},
    python_requires="~=3.7",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
)

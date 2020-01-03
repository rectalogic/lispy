import argparse

from .interpreter import Lispy
from .core import python_print


parser = argparse.ArgumentParser(prog="lispy", description="Lispy")
parser.add_argument(
    "-v", "--verbose", action="store_true", help="Verbose error messages"
)
parser.add_argument("filename", nargs="?", help="Lisp file to load and run")
args = parser.parse_args()

lispy = Lispy(restricted=False, verbose=args.verbose)
if args.filename:
    python_print(lispy.load_file(args.filename))
else:
    lispy.repl()

from __future__ import annotations
from typing import Dict, Optional, Any, TYPE_CHECKING
from .stepA_mal import init_repl_env, repl, load_file, EVAL, READ
from .mal_types import expression_to_native

if TYPE_CHECKING:
    from .mal_types import Restrictions


class Lispy:
    def __init__(
        self,
        injections: Optional[Dict[str, Any]] = None,
        restrictions: Optional[Restrictions] = None,
        restricted: bool = False,
        verbose: bool = False,
    ):
        self.env = init_repl_env(argv=[], restricted=restricted)
        self.verbose = verbose
        if injections:
            self.env.inject_native(injections)

    def eval(self, expr: str) -> Any:
        return expression_to_native(EVAL(READ(expr), self.env))

    def load_file(self, filename: str) -> str:
        return load_file(self.env, filename)

    def repl(self):
        repl(self.env, self.verbose)

from __future__ import annotations
from typing import Dict, Optional, Any, TYPE_CHECKING
from .rep import init_repl_env, repl, load_file, EVAL, READ
from .mal_types import expression_to_native

if TYPE_CHECKING:
    from .mal_types import Restrictions
    from .env import ExecutionLimit


class Lispy:
    def __init__(
        self,
        injections: Optional[Dict[str, Any]] = None,
        restrictions: Optional[Restrictions] = None,
        restricted: bool = False,
        execution_limit: Optional[ExecutionLimit] = None,
        verbose: bool = False,
    ):
        self.env = init_repl_env(
            argv=[], restricted=restricted, execution_limit=execution_limit
        )
        self.verbose = verbose
        if injections:
            self.env.inject_native(injections, restrictions)

    def eval(self, expr: str) -> Any:
        self.env.reset_execution_limit()
        return expression_to_native(EVAL(READ(expr), self.env))

    def load_file(self, filename: str) -> str:
        self.env.reset_execution_limit()
        return load_file(self.env, filename)

    def repl(self):
        repl(self.env, self.verbose)

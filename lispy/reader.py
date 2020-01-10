from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Union, cast
import re

from .mal_types import (
    MalExpression,
    MalFloat,
    MalInt,
    MalList,
    MalBoolean,
    MalNil,
    MalBlank,
    MalVector,
    MalHash_map,
)
from .mal_types import MalSymbol, MalString, MalKeyword, MalSyntaxException

if TYPE_CHECKING:
    from .mal_types import HashMapDict


class Reader:
    INT_RE = re.compile(r"-?[0-9]+$")
    FLOAT_RE = re.compile(r"-?[0-9]*\.[0-9]+$")
    STRING_RE = re.compile(r'"(?:[\\].|[^\\"])*"')

    def __init__(self, tokens: List[str], position: int = 0):
        self.tokens = tokens
        self.position = position

    def next(self) -> str:
        self.position += 1
        return self.tokens[self.position - 1]

    def peek(self) -> Optional[str]:
        if len(self.tokens) > self.position:
            return self.tokens[self.position]
        else:
            return None

    def read_atom(self) -> MalExpression:
        token = self.next()
        if re.match(self.INT_RE, token):
            return MalInt(int(token))
        elif re.match(self.FLOAT_RE, token):
            return MalFloat(float(token))
        elif re.match(self.STRING_RE, token):
            return MalString(self._unescape(token[1:-1]))
        elif token[0] == '"':
            raise MalSyntaxException("expected '\"', got EOF")
        elif token[0] == ":":
            return MalKeyword(token[1:])
        elif token == "nil":
            return MalNil()
        elif token == "true":
            return MalBoolean(True)
        elif token == "false":
            return MalBoolean(False)
        else:
            return MalSymbol(token)

    def _read_sequence(self, start: str, end: str) -> List[MalExpression]:
        ast = []
        token: Optional[str] = self.next()
        if token != start:
            raise MalSyntaxException("expected '" + start + "'")

        token = self.peek()
        while token != end:
            if not token:
                raise MalSyntaxException("expected '" + end + "', got EOF")
            ast.append(self.read_form())
            token = self.peek()
        self.next()
        return ast

    def read_list(self) -> MalList:
        return MalList(self._read_sequence("(", ")"))

    def read_vector(self) -> MalVector:
        return MalVector(self._read_sequence("[", "]"))

    def read_hash_map(self) -> MalHash_map:
        items = self._read_sequence("{", "}")
        if len(items) % 2 != 0:
            raise MalSyntaxException("invalid hash-map entries")
        hashmap: HashMapDict = {}
        for i in range(0, len(items), 2):
            if not isinstance(items[i], (MalString, MalKeyword)):
                raise MalSyntaxException("hash-map key not string or keyword")
            hashmap[cast(Union[MalString, MalKeyword], items[i])] = items[i + 1]
        return MalHash_map(hashmap)

    def read_form(self) -> MalExpression:
        token = self.peek()
        if token is None:
            raise MalSyntaxException("incomplete form")
        # reader macros/transforms
        if token == "'":
            self.next()
            return MalList([MalSymbol("quote"), self.read_form()])
        elif token == "`":
            self.next()
            return MalList([MalSymbol("quasiquote"), self.read_form()])
        elif token == "~":
            self.next()
            return MalList([MalSymbol("unquote"), self.read_form()])
        elif token == "~@":
            self.next()
            return MalList([MalSymbol("splice-unquote"), self.read_form()])
        elif token == "^":
            self.next()
            meta = self.read_form()
            return MalList([MalSymbol("with-meta"), self.read_form(), meta])
        elif token == "@":
            self.next()
            return MalList([MalSymbol("deref"), self.read_form()])

        # list
        elif token == ")":
            raise MalSyntaxException("unexpected ')'")
        elif token == "(":
            return self.read_list()

        # vector
        elif token == "]":
            raise MalSyntaxException("unexpected ']'")
        elif token == "[":
            return self.read_vector()

        # hash-map
        elif token == "}":
            raise MalSyntaxException("unexpected '}'")
        elif token == "{":
            return self.read_hash_map()

        # atom
        else:
            return self.read_atom()

    def _unescape(self, x: str) -> str:
        return (
            x.replace("\\\\", "\N{REPLACEMENT CHARACTER}")
            .replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\N{REPLACEMENT CHARACTER}", "\\")
        )


TOKENS_RE = re.compile(
    r"""[\s,]*(~@|[\[\]{}()'`~^@]|"(?:[\\].|[^\\"])*"?|;.*|[^\s\[\]{}()'"`@,;]+)"""
)


def tokenize(x: str) -> List[str]:
    return [t for t in re.findall(TOKENS_RE, x) if t[0] != ";"]


def read(x: str) -> MalExpression:
    tokens = tokenize(x)
    if len(tokens) == 0:
        return MalBlank()
    return Reader(tokens).read_form()

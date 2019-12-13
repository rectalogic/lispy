from __future__ import annotations
from typing import TYPE_CHECKING

from arpeggio import (
    ParserPython,
    PTNodeVisitor,
    visit_parse_tree,
    ZeroOrMore,
)
from arpeggio import RegExMatch as _, NoMatch

from .mal_types import (
    MalExpression,
    MalInt,
    MalList,
    MalBoolean,
    MalNil,
    MalVector,
    MalHash_map,
)
from .mal_types import MalSymbol, MalString, MalKeyword, MalSyntaxException

if TYPE_CHECKING:
    from arpeggio import ParseTreeNode, SemanticActionResults
    from .mal_types import HashMapDict


# Arpeggio grammar
def mExpression():
    return [
        mQuotedExpression,
        mQuasiQuotedExpression,
        mSpliceUnquotedExpression,
        mUnquotedExpression,
        mDerefExpression,
        mWithMetaExpression,
        mList,
        mVector,
        mHash_map,
        mInt,
        mString,
        mKeyword,
        mNil,
        mBoolean,
        mSymbol,
    ]


def mQuotedExpression():
    return "'", mExpression


def mQuasiQuotedExpression():
    return "`", mExpression


def mSpliceUnquotedExpression():
    return "~@", mExpression


def mUnquotedExpression():
    return "~", mExpression


def mDerefExpression():
    return "@", mExpression


def mWithMetaExpression():
    return "^", mExpression, mExpression


def mList():
    return "(", ZeroOrMore(mExpression), ")"


def mVector():
    return "[", ZeroOrMore(mExpression), "]"


def mHash_map():
    return ("{", ZeroOrMore(mExpression), "}")


def mInt():
    return _(r"-?[0123456789]+")


def mString():
    return _(r""""(?:\\.|[^\\"])*"?""")


def mKeyword():
    return _(r""":[^\s\[\]{}('"`,;)]*""")


def mSymbol():
    return _(r"""[^\s\[\]{}('"`,;)]*""")


def mNil():
    return _(r"""nil(?!\?)""")


def mBoolean():
    return _(r"""(true|false)(?!\?)""")


class ReadASTVisitor(PTNodeVisitor):
    def visit_mExpression(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalExpression:
        return children[0]  # children should already be Mal types

    def visit_mInt(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalInt:
        return MalInt(int(node.value))

    def visit_mString(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalString:
        # node.value will have quotes, escape sequences
        if not isinstance(node.value, str):
            raise MalSyntaxException("node not a string")
        if node.value[0] != '"':
            raise MalSyntaxException(
                "internal error: parsed a string with no start quote"
            )
        val: str = node.value
        if len(val) < 2 or val[-1] != '"':
            raise MalSyntaxException("unbalanced string")
        val = val[1:-1]  # remove outer quotes

        # handle escaped characters
        i = 0
        result = ""
        while i < len(val):
            if val[i] == "\\":
                if (i + 1) < len(val):
                    if val[i + 1] == "n":
                        result += "\n"
                    elif val[i + 1] == "\\":
                        result += "\\"
                    elif val[i + 1] == '"':
                        result += '"'
                    i += 2
                else:
                    raise MalSyntaxException(
                        "unbalanced string or invalid escape sequence"
                    )
            else:
                result += val[i]
                i += 1

        return MalString(result)

    def visit_mKeyword(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalKeyword:
        if not isinstance(node.value, str) or len(node.value) <= 1:
            raise MalSyntaxException("invalid keyword")
        return MalKeyword(node.value[1:])

    def visit_mList(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalList:
        return MalList(children)

    def visit_mVector(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalVector:
        return MalVector(children)

    def visit_mHash_map(self, node: ParseTreeNode, children) -> MalHash_map:
        if len(children) % 2 != 0:
            raise MalSyntaxException("invalid hash-map entries")
        hashmap: HashMapDict = {}
        for i in range(0, len(children), 2):
            if not isinstance(children[i], (MalString, MalKeyword)):
                raise MalSyntaxException("hash-map key not string or keyword")
            hashmap[children[i]] = children[i + 1]
        return MalHash_map(hashmap)

    def visit_mSymbol(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalSymbol:
        return MalSymbol(node.value)

    def visit_mBoolean(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalBoolean:
        if node.value == "true":
            return MalBoolean(True)
        if node.value == "false":
            return MalBoolean(False)
        raise Exception("Internal reader error")

    def visit_mNil(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalNil:
        return MalNil()

    def visit_mQuotedExpression(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalList:
        return MalList([MalSymbol("quote"), children[0]])

    def visit_mQuasiQuotedExpression(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalList:
        return MalList([MalSymbol("quasiquote"), children[0]])

    def visit_mSpliceUnquotedExpression(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalList:
        return MalList([MalSymbol("splice-unquote"), children[0]])

    def visit_mUnquotedExpression(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalList:
        return MalList([MalSymbol("unquote"), children[0]])

    def visit_mDerefExpression(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalList:
        return MalList([MalSymbol("deref"), children[0]])

    def visit_mWithMetaExpression(
        self, node: ParseTreeNode, children: SemanticActionResults
    ) -> MalList:
        if len(children) != 2:
            raise MalSyntaxException("^ macro requires two arguments")
        return MalList([MalSymbol("with-meta"), children[1], children[0]])


def comment():
    return _(";.*")


def read(x: str) -> MalExpression:
    """Parse a string into a MalExpression"""
    reader = ParserPython(mExpression, comment_def=comment, ws="\t\n\r ,", debug=False)

    try:
        parsed = visit_parse_tree(reader.parse(x), ReadASTVisitor())
        if not isinstance(parsed, MalExpression):
            raise MalSyntaxException("invalid expression")
        return parsed
    except NoMatch as e:
        raise MalSyntaxException("invalid syntax or unexpected EOF") from e

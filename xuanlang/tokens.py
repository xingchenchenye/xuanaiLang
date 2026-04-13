from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    IDENT = auto()
    NUMBER = auto()
    STRING = auto()

    LET = auto()
    CONST = auto()
    FUN = auto()
    RETURN = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    IN = auto()
    MATCH = auto()
    CASE = auto()
    DEFAULT = auto()
    BREAK = auto()
    CONTINUE = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    IMPORT = auto()
    AS = auto()
    ASSERT = auto()
    TRY = auto()
    CATCH = auto()
    THROW = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    STRUCT = auto()
    NEW = auto()

    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    DOT = auto()
    COLON = auto()
    SEMICOLON = auto()
    ARROW = auto()

    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    MATMUL = auto()
    ASSIGN = auto()
    EQ = auto()
    NE = auto()
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()

    EOF = auto()


KEYWORDS = {
    "令": TokenKind.LET,
    "常": TokenKind.CONST,
    "术": TokenKind.FUN,
    "返": TokenKind.RETURN,
    "若": TokenKind.IF,
    "否则": TokenKind.ELSE,
    "当": TokenKind.WHILE,
    "遍": TokenKind.FOR,
    "于": TokenKind.IN,
    "配": TokenKind.MATCH,
    "例": TokenKind.CASE,
    "默": TokenKind.DEFAULT,
    "停": TokenKind.BREAK,
    "续": TokenKind.CONTINUE,
    "真": TokenKind.TRUE,
    "假": TokenKind.FALSE,
    "空": TokenKind.NULL,
    "引": TokenKind.IMPORT,
    "为": TokenKind.AS,
    "断": TokenKind.ASSERT,
    "试": TokenKind.TRY,
    "捕": TokenKind.CATCH,
    "抛": TokenKind.THROW,
    "且": TokenKind.AND,
    "或": TokenKind.OR,
    "非": TokenKind.NOT,
    "构": TokenKind.STRUCT,
    "新": TokenKind.NEW,
}


@dataclass(slots=True)
class Token:
    kind: TokenKind
    value: str
    line: int
    column: int

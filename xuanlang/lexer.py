from __future__ import annotations

from .errors import XuanError
from .tokens import KEYWORDS, Token, TokenKind


FULLWIDTH_MAP = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "｛": "{",
        "｝": "}",
        "，": ",",
        "：": ":",
        "；": ";",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)


class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source.translate(FULLWIDTH_MAP)
        self.length = len(self.source)
        self.index = 0
        self.line = 1
        self.column = 1

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while not self._is_at_end():
            ch = self._peek()
            if ch in " \r\t":
                self._advance()
                continue
            if ch == "\n":
                self._advance_line()
                continue
            if ch == "#":
                self._skip_comment()
                continue
            if ch == "/" and self._peek_next() == "/":
                self._skip_comment()
                continue
            if ch.isdigit():
                tokens.append(self._number())
                continue
            if ch in {'"', "'"}:
                tokens.append(self._string())
                continue
            if self._is_ident_start(ch):
                tokens.append(self._identifier())
                continue
            tokens.append(self._symbol())
        tokens.append(Token(TokenKind.EOF, "", self.line, self.column))
        return tokens

    def _symbol(self) -> Token:
        line, column = self.line, self.column
        ch = self._advance()
        two = ch + self._peek()
        if two == "->":
            self._advance()
            return Token(TokenKind.ARROW, "->", line, column)
        if two == "==":
            self._advance()
            return Token(TokenKind.EQ, "==", line, column)
        if two == "!=":
            self._advance()
            return Token(TokenKind.NE, "!=", line, column)
        if two == "<=":
            self._advance()
            return Token(TokenKind.LE, "<=", line, column)
        if two == ">=":
            self._advance()
            return Token(TokenKind.GE, ">=", line, column)

        singles = {
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            "{": TokenKind.LBRACE,
            "}": TokenKind.RBRACE,
            "[": TokenKind.LBRACKET,
            "]": TokenKind.RBRACKET,
            ",": TokenKind.COMMA,
            ".": TokenKind.DOT,
            ":": TokenKind.COLON,
            ";": TokenKind.SEMICOLON,
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "*": TokenKind.STAR,
            "/": TokenKind.SLASH,
            "%": TokenKind.PERCENT,
            "@": TokenKind.MATMUL,
            "=": TokenKind.ASSIGN,
            "<": TokenKind.LT,
            ">": TokenKind.GT,
        }
        kind = singles.get(ch)
        if kind is None:
            raise XuanError(f"无法识别的字符: {ch}", line, column)
        return Token(kind, ch, line, column)

    def _number(self) -> Token:
        line, column = self.line, self.column
        start = self.index
        while self._peek().isdigit():
            self._advance()
        if self._peek() == "." and self._peek_next().isdigit():
            self._advance()
            while self._peek().isdigit():
                self._advance()
        return Token(TokenKind.NUMBER, self.source[start:self.index], line, column)

    def _string(self) -> Token:
        quote = self._advance()
        line, column = self.line, self.column - 1
        chars: list[str] = []
        while not self._is_at_end() and self._peek() != quote:
            ch = self._advance()
            if ch == "\\":
                nxt = self._advance()
                escape_map = {"n": "\n", "t": "\t", '"': '"', "'": "'", "\\": "\\"}
                chars.append(escape_map.get(nxt, nxt))
            else:
                if ch == "\n":
                    self._advance_line(internal=True)
                chars.append(ch)
        if self._is_at_end():
            raise XuanError("字符串未闭合", line, column)
        self._advance()
        return Token(TokenKind.STRING, "".join(chars), line, column)

    def _identifier(self) -> Token:
        line, column = self.line, self.column
        start = self.index
        while self._is_ident_continue(self._peek()):
            self._advance()
        value = self.source[start:self.index]
        return Token(KEYWORDS.get(value, TokenKind.IDENT), value, line, column)

    def _skip_comment(self) -> None:
        while not self._is_at_end() and self._peek() != "\n":
            self._advance()

    def _advance_line(self, internal: bool = False) -> None:
        if not internal:
            self._advance()
        self.line += 1
        self.column = 1

    def _advance(self) -> str:
        ch = self.source[self.index]
        self.index += 1
        self.column += 1
        return ch

    def _peek(self) -> str:
        if self._is_at_end():
            return "\0"
        return self.source[self.index]

    def _peek_next(self) -> str:
        if self.index + 1 >= self.length:
            return "\0"
        return self.source[self.index + 1]

    def _is_at_end(self) -> bool:
        return self.index >= self.length

    @staticmethod
    def _is_ident_start(ch: str) -> bool:
        if ch == "\0":
            return False
        return ch == "_" or ch.isalpha() or "\u4e00" <= ch <= "\u9fff"

    @staticmethod
    def _is_ident_continue(ch: str) -> bool:
        if ch == "\0":
            return False
        return Lexer._is_ident_start(ch) or ch.isdigit()

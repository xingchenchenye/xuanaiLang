from dataclasses import dataclass


@dataclass(slots=True)
class SourceSpan:
    line: int
    column: int


class XuanError(Exception):
    def __init__(self, message: str, line: int = 0, column: int = 0) -> None:
        self.message = message
        self.line = line
        self.column = column
        suffix = f" (第 {line} 行, 第 {column} 列)" if line and column else ""
        super().__init__(f"{message}{suffix}")

from __future__ import annotations

from ..errors import XuanError


class XuanThrowSignal(Exception):
    def __init__(self, value: object) -> None:
        self.value = value
        message = value if isinstance(value, str) else repr(value)
        super().__init__(f"未捕获异常: {message}")


def make_throw_signal(value: object) -> XuanThrowSignal:
    return XuanThrowSignal(value)


def error_payload(error: Exception) -> object:
    if isinstance(error, XuanThrowSignal):
        return error.value
    if isinstance(error, XuanError):
        return {"类型": type(error).__name__, "信息": error.message}
    return {"类型": type(error).__name__, "信息": str(error)}

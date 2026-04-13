from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class XuanStructType:
    name: str
    fields: dict[str, str]

    def create(self, values: dict[str, Any]) -> "XuanStructInstance":
        missing = [name for name in self.fields if name not in values]
        extra = [name for name in values if name not in self.fields]
        if missing:
            raise ValueError(f"结构 {self.name} 缺少字段: {', '.join(missing)}")
        if extra:
            raise ValueError(f"结构 {self.name} 存在未知字段: {', '.join(extra)}")
        return XuanStructInstance(self, dict(values))

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}: {kind}" for name, kind in self.fields.items())
        return f"<结构 {self.name} {{{fields}}}>"


class XuanStructInstance:
    def __init__(self, struct_type: XuanStructType, values: dict[str, Any]) -> None:
        object.__setattr__(self, "_type", struct_type)
        object.__setattr__(self, "_values", values)

    def __getattr__(self, name: str) -> Any:
        values = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_type", "_values"}:
            object.__setattr__(self, name, value)
            return
        struct_type = object.__getattribute__(self, "_type")
        values = object.__getattribute__(self, "_values")
        if name not in struct_type.fields:
            raise AttributeError(f"{struct_type.name} 没有字段 {name}")
        values[name] = value

    def to_dict(self) -> dict[str, Any]:
        return dict(object.__getattribute__(self, "_values"))

    def __repr__(self) -> str:
        struct_type = object.__getattribute__(self, "_type")
        values = object.__getattribute__(self, "_values")
        inner = ", ".join(f"{name}={values[name]!r}" for name in struct_type.fields)
        return f"{struct_type.name}({inner})"

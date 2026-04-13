from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from .tensor import Tensor, QuantizedTensor, quantize_int4


def _transpose_2d(data: list[list[float]]) -> list[list[float]]:
    if not data:
        return []
    rows = len(data)
    cols = len(data[0])
    return [[float(data[r][c]) for r in range(rows)] for c in range(cols)]


@dataclass(slots=True)
class KVCache:
    max_entries: int = 256
    keys: list[Tensor] = field(default_factory=list)
    values: list[Tensor] = field(default_factory=list)

    def append(self, key: object, value: object) -> None:
        self.keys.append(Tensor.from_value(key))
        self.values.append(Tensor.from_value(value))
        if len(self.keys) > self.max_entries:
            self.keys.pop(0)
            self.values.pop(0)

    def clear(self) -> None:
        self.keys.clear()
        self.values.clear()

    def size(self) -> int:
        return len(self.keys)

    def snapshot(self) -> dict[str, object]:
        return {
            "size": self.size(),
            "keys": [item.tolist() for item in self.keys],
            "values": [item.tolist() for item in self.values],
        }


def attention(query: object, key: object, value: object, mask_future: bool = False) -> Tensor:
    q = Tensor.from_value(query)
    k = Tensor.from_value(key)
    v = Tensor.from_value(value)
    scores = q @ Tensor.from_value(_transpose_2d(k.tolist()))
    scale = math.sqrt(k.shape[-1]) if k.shape else 1.0
    scaled = Tensor.from_value([[float(item) / scale for item in row] for row in scores.tolist()])
    if mask_future:
        masked_rows: list[list[float]] = []
        rows = scaled.tolist()
        for i, row in enumerate(rows):
            masked_rows.append([val if j <= i else -1e9 for j, val in enumerate(row)])
        scaled = Tensor.from_value(masked_rows)
    probs = scaled.softmax()
    return probs @ v


def layer_norm(value: object, eps: float = 1e-5) -> Tensor:
    tensor = Tensor.from_value(value)
    rows = tensor.tolist()
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], list):
        raise ValueError("layer_norm 目前只支持二维张量")
    out: list[list[float]] = []
    for row in rows:
        mean = sum(float(item) for item in row) / len(row)
        var = sum((float(item) - mean) ** 2 for item in row) / len(row)
        denom = math.sqrt(var + eps)
        out.append([(float(item) - mean) / denom for item in row])
    return Tensor.from_value(out)


def transformer_step(hidden: object, wq: object, wk: object, wv: object, wo: object, cache: KVCache | None = None) -> Tensor:
    hidden_t = Tensor.from_value(hidden)
    q = hidden_t @ Tensor.from_value(wq)
    k = hidden_t @ Tensor.from_value(wk)
    v = hidden_t @ Tensor.from_value(wv)
    if cache is not None:
        cache.append(k, v)
        key_bank = Tensor.from_value([row for tensor in cache.keys for row in tensor.tolist()])
        value_bank = Tensor.from_value([row for tensor in cache.values for row in tensor.tolist()])
    else:
        key_bank = k
        value_bank = v
    attn = attention(q, key_bank, value_bank, mask_future=True)
    return layer_norm(attn @ Tensor.from_value(wo))


def sparse_prune(tensor: object, threshold: float = 0.0) -> Tensor:
    value = Tensor.from_value(tensor)
    rows = value.tolist()
    if isinstance(rows, list):
        def walk(item):
            if isinstance(item, list):
                return [walk(x) for x in item]
            return 0.0 if abs(float(item)) <= threshold else float(item)
        return Tensor.from_value(walk(rows))
    return value


def quantize_int8(tensor: object) -> QuantizedTensor:
    tensor = Tensor.from_value(tensor)
    peak = max(abs(float(v)) for row in tensor.tolist() for v in (row if isinstance(row, list) else [row])) or 1.0
    scale = peak / 127.0
    def walk(item):
        if isinstance(item, list):
            return [walk(x) for x in item]
        return max(-128, min(127, int(round(float(item) / scale))))
    return QuantizedTensor(walk(tensor.tolist()), scale=scale, bits=8)


def token_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "KVCache",
    "attention",
    "layer_norm",
    "transformer_step",
    "sparse_prune",
    "quantize_int4",
    "quantize_int8",
    "token_hash",
]

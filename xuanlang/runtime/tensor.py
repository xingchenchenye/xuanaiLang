from __future__ import annotations

from dataclasses import dataclass
from math import exp


def _infer_shape(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        return ()
    if not value:
        return (0,)
    return (len(value),) + _infer_shape(value[0])


def _deep_copy(value: object) -> object:
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value


def _elementwise(lhs: object, rhs: object, fn) -> object:
    if isinstance(lhs, list) and isinstance(rhs, list):
        return [_elementwise(a, b, fn) for a, b in zip(lhs, rhs, strict=True)]
    if isinstance(lhs, list):
        return [_elementwise(a, rhs, fn) for a in lhs]
    if isinstance(rhs, list):
        return [_elementwise(lhs, b, fn) for b in rhs]
    return fn(lhs, rhs)


def _sum_axis_last(values: list[float]) -> list[float]:
    denom = sum(exp(item) for item in values)
    return [exp(item) / denom for item in values]


def _flatten(value: object) -> float:
    if isinstance(value, list):
        return sum(_flatten(item) for item in value)
    return float(value)


def _collect_numbers(value: object) -> list[float]:
    if isinstance(value, list):
        result: list[float] = []
        for item in value:
            result.extend(_collect_numbers(item))
        return result
    return [float(value)]


@dataclass(slots=True)
class Tensor:
    data: object
    shape: tuple[int, ...]

    @classmethod
    def from_value(cls, value: object) -> "Tensor":
        if isinstance(value, Tensor):
            return value
        return cls(_deep_copy(value), _infer_shape(value))

    def tolist(self) -> object:
        return _deep_copy(self.data)

    def relu(self) -> "Tensor":
        return Tensor.from_value(_elementwise(self.data, 0, lambda a, b: a if a > b else b))

    def softmax(self) -> "Tensor":
        if len(self.shape) == 1:
            return Tensor.from_value(_sum_axis_last([float(x) for x in self.data]))
        if len(self.shape) == 2:
            return Tensor.from_value([_sum_axis_last([float(x) for x in row]) for row in self.data])
        raise ValueError("softmax 目前只支持 1D 或 2D 张量")

    def sum(self) -> float:
        return float(_flatten(self.data))

    def __add__(self, other: object) -> "Tensor":
        other_tensor = Tensor.from_value(other)
        return Tensor.from_value(_elementwise(self.data, other_tensor.data, lambda a, b: a + b))

    def __sub__(self, other: object) -> "Tensor":
        other_tensor = Tensor.from_value(other)
        return Tensor.from_value(_elementwise(self.data, other_tensor.data, lambda a, b: a - b))

    def __mul__(self, other: object) -> "Tensor":
        other_tensor = Tensor.from_value(other)
        return Tensor.from_value(_elementwise(self.data, other_tensor.data, lambda a, b: a * b))

    def __matmul__(self, other: object) -> "Tensor":
        other_tensor = Tensor.from_value(other)
        if len(self.shape) != 2 or len(other_tensor.shape) != 2:
            raise ValueError("矩阵乘法目前只支持二维张量")
        rows, inner = self.shape
        inner_other, cols = other_tensor.shape
        if inner != inner_other:
            raise ValueError("矩阵乘法维度不匹配")
        result: list[list[float]] = []
        for i in range(rows):
            row: list[float] = []
            for j in range(cols):
                value = 0.0
                for k in range(inner):
                    value += float(self.data[i][k]) * float(other_tensor.data[k][j])
                row.append(value)
            result.append(row)
        return Tensor.from_value(result)

    def __repr__(self) -> str:
        return f"张量(shape={self.shape}, data={self.data})"


@dataclass(slots=True)
class QuantizedTensor:
    data: object
    scale: float
    bits: int = 4

    def dequantize(self) -> Tensor:
        return Tensor.from_value(_elementwise(self.data, 0, lambda a, _: a * self.scale))

    def __repr__(self) -> str:
        return f"量化张量(bits={self.bits}, scale={self.scale}, data={self.data})"


def quantize_int4(tensor: Tensor) -> QuantizedTensor:
    tensor = Tensor.from_value(tensor)
    flat_values = _collect_numbers(tensor.data)
    peak = max((abs(value) for value in flat_values), default=1.0) or 1.0
    scale = peak / 7.0
    quantized = _elementwise(tensor.data, 0, lambda a, _: max(-8, min(7, int(round(float(a) / scale)))))
    return QuantizedTensor(quantized, scale=scale, bits=4)

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..stdlib.modules import build_stdlib_registry
from .ai import KVCache, attention, layer_norm, quantize_int8, transformer_step
from .records import XuanStructType
from .tensor import Tensor, quantize_int4


class ModuleLoader:
    def __init__(self) -> None:
        self.cache: dict[tuple[str, str], SimpleNamespace] = {}
        self.stdlib = build_stdlib_registry()

    def load(self, module_name: str, current_file: str, backend: str = "interp") -> SimpleNamespace:
        if module_name in self.stdlib:
            return self.stdlib[module_name]
        resolved = self._resolve(module_name, current_file)
        cache_key = (backend, resolved)
        if cache_key in self.cache:
            return self.cache[cache_key]
        from xuanlang.pipeline import CompilerPipeline

        pipeline = CompilerPipeline(loader=self)
        if backend == "interp":
            env = pipeline.execute_file(resolved, module_name=Path(resolved).stem)
        elif backend == "python":
            env = pipeline.execute_file_python(resolved, module_name=Path(resolved).stem)
        elif backend == "vm":
            env = pipeline.execute_file_vm(resolved, module_name=Path(resolved).stem)
        else:
            raise ValueError(f"未知的模块加载后端: {backend}")
        exports = env.get("__xuan_exports__") or {
            key: value
            for key, value in env.items()
            if not key.startswith("__") and key not in {"create_runtime_scope"}
        }
        module = SimpleNamespace(**exports)
        self.cache[cache_key] = module
        return module

    def _resolve(self, module_name: str, current_file: str) -> str:
        current = Path(current_file).resolve()
        if module_name.endswith((".xy", ".玄")):
            candidate = (current.parent / module_name).resolve()
        else:
            candidate = (current.parent / module_name.replace(".", "/")).with_suffix(".xy").resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"无法找到模块: {module_name} -> {candidate}")
        return str(candidate)


def create_runtime_scope(
    module_name: str,
    file_path: str,
    shared_loader: ModuleLoader | None = None,
    backend: str = "interp",
) -> dict[str, object]:
    loader = shared_loader or ModuleLoader()
    builtins = {
        "显": 显,
        "张": Tensor.from_value,
        "形": 形,
        "量化4": lambda x: quantize_int4(Tensor.from_value(x)),
        "量化8": lambda x: quantize_int8(Tensor.from_value(x)),
        "软最大": lambda x: Tensor.from_value(x).softmax(),
        "relu": lambda x: Tensor.from_value(x).relu(),
        "类型": lambda x: type(x).__name__,
        "列长": lambda x: len(x),
        "范": lambda n: list(range(int(n))),
        "缓存": lambda size=256: KVCache(max_entries=int(size)),
        "注意": attention,
        "归一": layer_norm,
        "转步": transformer_step,
    }
    return {
        "builtins": builtins,
        "importer": lambda module, current=file_path, engine=backend: loader.load(module, current, backend=engine),
        "member": 读取成员,
        "set_member": 写入成员,
        "define_struct": 定义结构,
        "new_struct": 创建结构,
        "collect_exports": lambda namespace: {
            key: value
            for key, value in namespace.items()
            if not key.startswith("__") and key not in builtins
        },
        "loader": loader,
        "module_name": module_name,
        "file_path": file_path,
    }


def 显(*values: object) -> None:
    print(*values)


def 形(value: object) -> list[int]:
    return list(Tensor.from_value(value).shape)


def 读取成员(value: object, name: str) -> object:
    if hasattr(value, name):
        return getattr(value, name)
    if isinstance(value, dict):
        return value[name]
    raise AttributeError(name)


def 写入成员(value: object, name: str, data: object) -> object:
    if isinstance(value, dict):
        value[name] = data
        return data
    setattr(value, name, data)
    return data


def 定义结构(name: str, fields: dict[str, str]) -> XuanStructType:
    return XuanStructType(name, fields)


def 创建结构(struct_type: XuanStructType, values: dict[str, object]) -> object:
    return struct_type.create(values)

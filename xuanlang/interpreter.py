from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import ast_nodes as ast
from .errors import XuanError
from .runtime.prelude import ModuleLoader, create_runtime_scope
from .runtime.tensor import Tensor


class ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class XuanRuntimeError(XuanError):
    pass


class Environment:
    def __init__(self, parent: "Environment | None" = None) -> None:
        self.parent = parent
        self.values: dict[str, Any] = {}

    def define(self, name: str, value: Any) -> Any:
        self.values[name] = value
        return value

    def assign(self, name: str, value: Any) -> Any:
        if name in self.values:
            self.values[name] = value
            return value
        if self.parent is not None:
            return self.parent.assign(name, value)
        raise XuanRuntimeError(f"未定义的名称: {name}")

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise XuanRuntimeError(f"未定义的名称: {name}")

    def flatten(self) -> dict[str, Any]:
        data = self.parent.flatten() if self.parent is not None else {}
        data.update(self.values)
        return data


@dataclass(slots=True)
class XuanFunction:
    name: str
    params: list[str]
    body: list[ast.Statement]
    closure: Environment
    interpreter: "Interpreter"

    def __call__(self, *args: Any) -> Any:
        local = Environment(self.closure)
        for index, name in enumerate(self.params):
            local.define(name, args[index] if index < len(args) else None)
        try:
            self.interpreter.execute_block(self.body, local)
        except ReturnSignal as signal:
            return signal.value
        return None

    def __repr__(self) -> str:
        return f"<玄言函数 {self.name}>"


class Interpreter:
    def __init__(self, loader: ModuleLoader | None = None) -> None:
        self.loader = loader or ModuleLoader()
        self.export_filter: set[str] = set()

    def execute(self, program: ast.Program, file_path: str, module_name: str = "__main__") -> dict[str, Any]:
        runtime = create_runtime_scope(module_name, file_path, self.loader, backend="interp")
        global_env = Environment()
        builtins = runtime["builtins"]
        self.export_filter = set(builtins.keys()) | {"__name__", "__file__", "__xuan_exports__", "__backend__"}
        for key, value in builtins.items():
            global_env.define(key, value)
        global_env.define("__name__", module_name)
        global_env.define("__file__", file_path)
        global_env.define("__loader__", self.loader)
        global_env.define("__importer__", runtime["importer"])
        global_env.define("__define_struct__", runtime["define_struct"])
        global_env.define("__new_struct__", runtime["new_struct"])
        self.execute_block(program.statements, global_env)
        namespace = global_env.flatten()
        namespace["__xuan_exports__"] = {
            key: value
            for key, value in namespace.items()
            if not key.startswith("__") and key not in self.export_filter
        }
        namespace["__backend__"] = "interp"
        return namespace

    def execute_block(self, statements: list[ast.Statement], env: Environment) -> None:
        for statement in statements:
            self.execute_statement(statement, env)

    def execute_statement(self, statement: ast.Statement, env: Environment) -> None:
        match statement:
            case ast.ImportStmt(module=module, alias=alias):
                importer = env.get("__importer__")
                env.define(alias, importer(module))
            case ast.VarDecl(name=name, annotation=_, value=value, mutable=_):
                env.define(name, self.evaluate(value, env))
            case ast.Assign(target=target, value=value):
                self.assign_target(target, self.evaluate(value, env), env)
            case ast.FunctionDecl(name=name, params=params, return_type=_, body=body):
                function = XuanFunction(
                    name=name,
                    params=[param.name for param in params],
                    body=body,
                    closure=env,
                    interpreter=self,
                )
                env.define(name, function)
            case ast.StructDecl(name=name, fields=fields):
                env.define(name, env.get("__define_struct__")(name, {field.name: field.annotation.name for field in fields}))
            case ast.IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                if self._truthy(self.evaluate(condition, env)):
                    self.execute_block(then_branch, Environment(env))
                elif else_branch is not None:
                    self.execute_block(else_branch, Environment(env))
            case ast.WhileStmt(condition=condition, body=body):
                while self._truthy(self.evaluate(condition, env)):
                    try:
                        self.execute_block(body, Environment(env))
                    except ContinueSignal:
                        continue
                    except BreakSignal:
                        break
            case ast.ForStmt(name=name, iterable=iterable, body=body):
                values = self.evaluate(iterable, env)
                for item in values:
                    loop_env = Environment(env)
                    loop_env.define(name, item)
                    try:
                        self.execute_block(body, loop_env)
                    except ContinueSignal:
                        continue
                    except BreakSignal:
                        break
            case ast.MatchStmt(subject=subject, cases=cases):
                value = self.evaluate(subject, env)
                matched = False
                for case in cases:
                    if case.pattern is None:
                        if not matched:
                            self.execute_block(case.body, Environment(env))
                        break
                    pattern = self.evaluate(case.pattern, env)
                    if value == pattern:
                        self.execute_block(case.body, Environment(env))
                        matched = True
                        break
            case ast.BreakStmt():
                raise BreakSignal()
            case ast.ContinueStmt():
                raise ContinueSignal()
            case ast.ReturnStmt(value=value):
                raise ReturnSignal(self.evaluate(value, env) if value is not None else None)
            case ast.AssertStmt(condition=condition, message=message):
                result = self.evaluate(condition, env)
                if not self._truthy(result):
                    extra = self.evaluate(message, env) if message is not None else "断言失败"
                    raise XuanRuntimeError(str(extra))
            case ast.ExprStmt(value=value):
                self.evaluate(value, env)
            case _:
                raise XuanRuntimeError(f"不支持的语句节点: {type(statement).__name__}")

    def evaluate(self, expr: ast.Expression, env: Environment) -> Any:
        match expr:
            case ast.Literal(value=value):
                return value
            case ast.Name(value=name):
                return env.get(name)
            case ast.ListLiteral(items=items):
                return [self.evaluate(item, env) for item in items]
            case ast.DictLiteral(items=items):
                return {self.evaluate(item.key, env): self.evaluate(item.value, env) for item in items}
            case ast.StructInit(name=name, fields=fields):
                struct_type = env.get(name)
                values = {field.name: self.evaluate(field.value, env) for field in fields}
                return env.get("__new_struct__")(struct_type, values)
            case ast.Unary(op=op, operand=operand):
                value = self.evaluate(operand, env)
                if op == "-":
                    return -value
                if op == "+":
                    return +value
                if op == "非":
                    return not self._truthy(value)
                raise XuanRuntimeError(f"不支持的一元运算: {op}")
            case ast.Binary(left=left, op=op, right=right):
                if op == "且":
                    lhs = self.evaluate(left, env)
                    return self.evaluate(right, env) if self._truthy(lhs) else lhs
                if op == "或":
                    lhs = self.evaluate(left, env)
                    return lhs if self._truthy(lhs) else self.evaluate(right, env)
                lhs = self.evaluate(left, env)
                rhs = self.evaluate(right, env)
                return self._binary(lhs, op, rhs)
            case ast.Call(callee=callee, args=args):
                fn = self.evaluate(callee, env)
                values = [self.evaluate(item, env) for item in args]
                return fn(*values)
            case ast.MemberAccess(target=target, name=name):
                value = self.evaluate(target, env)
                if hasattr(value, name):
                    return getattr(value, name)
                if isinstance(value, dict):
                    return value[name]
                raise XuanRuntimeError(f"对象没有成员: {name}")
            case ast.IndexAccess(target=target, index=index):
                value = self.evaluate(target, env)
                slot = self.evaluate(index, env)
                return value[slot]
            case _:
                raise XuanRuntimeError(f"不支持的表达式节点: {type(expr).__name__}")

    def assign_target(self, target: ast.Assignable, value: Any, env: Environment) -> Any:
        match target:
            case ast.Name(value=name):
                return env.assign(name, value)
            case ast.MemberAccess(target=owner, name=name):
                container = self.evaluate(owner, env)
                if isinstance(container, dict):
                    container[name] = value
                    return value
                setattr(container, name, value)
                return value
            case ast.IndexAccess(target=owner, index=index):
                container = self.evaluate(owner, env)
                slot = self.evaluate(index, env)
                container[slot] = value
                return value
            case _:
                raise XuanRuntimeError(f"无效的赋值目标: {type(target).__name__}")

    def _binary(self, lhs: Any, op: str, rhs: Any) -> Any:
        if op == "+":
            return lhs + rhs
        if op == "-":
            return lhs - rhs
        if op == "*":
            return lhs * rhs
        if op == "/":
            return lhs / rhs
        if op == "%":
            return lhs % rhs
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        if op == ">":
            return lhs > rhs
        if op == ">=":
            return lhs >= rhs
        if op == "<":
            return lhs < rhs
        if op == "<=":
            return lhs <= rhs
        if op == "@":
            if hasattr(lhs, "__matmul__"):
                return lhs @ rhs
            return Tensor.from_value(lhs) @ rhs
        raise XuanRuntimeError(f"不支持的二元运算: {op}")

    @staticmethod
    def _truthy(value: Any) -> bool:
        return bool(value)

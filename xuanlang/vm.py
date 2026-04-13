from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import ast_nodes as ast
from .interpreter import (
    BreakSignal,
    ContinueSignal,
    Environment,
    ReturnSignal,
    XuanRuntimeError,
)
from .runtime.prelude import ModuleLoader, create_runtime_scope
from .runtime.tensor import Tensor


@dataclass(slots=True)
class ExprInstruction:
    op: str
    arg: Any = None


@dataclass(slots=True)
class ExprCode:
    instructions: list[ExprInstruction] = field(default_factory=list)


@dataclass(slots=True)
class MatchCaseCode:
    pattern: ExprCode | None
    body: "BytecodeBlock"


@dataclass(slots=True)
class StoreTargetCode:
    kind: str
    name: str | None = None
    owner: ExprCode | None = None
    index: ExprCode | None = None


@dataclass(slots=True)
class BytecodeInstruction:
    op: str
    args: tuple[Any, ...] = ()


@dataclass(slots=True)
class BytecodeBlock:
    instructions: list[BytecodeInstruction] = field(default_factory=list)


@dataclass(slots=True)
class XuanVmFunction:
    name: str
    params: list[str]
    body: BytecodeBlock
    closure: Environment
    vm: "VirtualMachine"

    def __call__(self, *args: Any) -> Any:
        local = Environment(self.closure)
        for index, name in enumerate(self.params):
            local.define(name, args[index] if index < len(args) else None)
        try:
            self.vm.execute_block(self.body, local)
        except ReturnSignal as signal:
            return signal.value
        return None

    def __repr__(self) -> str:
        return f"<玄言VM函数 {self.name}>"


class BytecodeCompiler:
    def compile_program(self, program: ast.Program) -> BytecodeBlock:
        return BytecodeBlock([self._statement(statement) for statement in program.statements])

    def _statement(self, statement: ast.Statement) -> BytecodeInstruction:
        match statement:
            case ast.ImportStmt(module=module, alias=alias):
                return BytecodeInstruction("IMPORT", (module, alias))
            case ast.VarDecl(name=name, annotation=_, value=value, mutable=mutable):
                return BytecodeInstruction("DECLARE", (name, self._expression(value), mutable))
            case ast.Assign(target=target, value=value):
                return BytecodeInstruction("ASSIGN", (self._store_target(target), self._expression(value)))
            case ast.FunctionDecl(name=name, params=params, return_type=_, body=body):
                compiled_body = BytecodeBlock([self._statement(item) for item in body])
                return BytecodeInstruction(
                    "FUNCTION",
                    (name, [param.name for param in params], compiled_body),
                )
            case ast.StructDecl(name=name, fields=fields):
                return BytecodeInstruction("STRUCT", (name, {field.name: field.annotation.name for field in fields}))
            case ast.IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                then_code = BytecodeBlock([self._statement(item) for item in then_branch])
                else_code = None
                if else_branch is not None:
                    else_code = BytecodeBlock([self._statement(item) for item in else_branch])
                return BytecodeInstruction("IF", (self._expression(condition), then_code, else_code))
            case ast.WhileStmt(condition=condition, body=body):
                body_code = BytecodeBlock([self._statement(item) for item in body])
                return BytecodeInstruction("WHILE", (self._expression(condition), body_code))
            case ast.ForStmt(name=name, iterable=iterable, body=body):
                body_code = BytecodeBlock([self._statement(item) for item in body])
                return BytecodeInstruction("FOR", (name, self._expression(iterable), body_code))
            case ast.MatchStmt(subject=subject, cases=cases):
                compiled_cases = [
                    MatchCaseCode(
                        None if case.pattern is None else self._expression(case.pattern),
                        BytecodeBlock([self._statement(item) for item in case.body]),
                    )
                    for case in cases
                ]
                return BytecodeInstruction("MATCH", (self._expression(subject), compiled_cases))
            case ast.BreakStmt():
                return BytecodeInstruction("BREAK")
            case ast.ContinueStmt():
                return BytecodeInstruction("CONTINUE")
            case ast.ReturnStmt(value=value):
                return BytecodeInstruction("RETURN", (None if value is None else self._expression(value),))
            case ast.AssertStmt(condition=condition, message=message):
                return BytecodeInstruction(
                    "ASSERT",
                    (self._expression(condition), None if message is None else self._expression(message)),
                )
            case ast.ThrowStmt(value=value):
                return BytecodeInstruction("THROW", (self._expression(value),))
            case ast.TryStmt(try_branch=try_branch, catch_name=catch_name, catch_branch=catch_branch):
                try_code = BytecodeBlock([self._statement(item) for item in try_branch])
                catch_code = BytecodeBlock([self._statement(item) for item in catch_branch])
                return BytecodeInstruction("TRY", (try_code, catch_name, catch_code))
            case ast.ExprStmt(value=value):
                return BytecodeInstruction("EVAL", (self._expression(value),))
            case _:
                raise TypeError(f"不支持的 VM 语句节点: {type(statement).__name__}")

    def _store_target(self, target: ast.Assignable) -> StoreTargetCode:
        match target:
            case ast.Name(value=name):
                return StoreTargetCode("name", name=name)
            case ast.MemberAccess(target=owner, name=name):
                return StoreTargetCode("member", name=name, owner=self._expression(owner))
            case ast.IndexAccess(target=owner, index=index):
                return StoreTargetCode("index", owner=self._expression(owner), index=self._expression(index))
            case _:
                raise TypeError(f"不支持的 VM 赋值目标: {type(target).__name__}")

    def _expression(self, expr: ast.Expression) -> ExprCode:
        instructions: list[ExprInstruction] = []
        self._emit_expr(expr, instructions)
        return ExprCode(instructions)

    def _emit_expr(self, expr: ast.Expression, instructions: list[ExprInstruction]) -> None:
        match expr:
            case ast.Literal(value=value):
                instructions.append(ExprInstruction("CONST", value))
            case ast.Name(value=name):
                instructions.append(ExprInstruction("NAME", name))
            case ast.ListLiteral(items=items):
                for item in items:
                    self._emit_expr(item, instructions)
                instructions.append(ExprInstruction("LIST", len(items)))
            case ast.DictLiteral(items=items):
                for item in items:
                    self._emit_expr(item.key, instructions)
                    self._emit_expr(item.value, instructions)
                instructions.append(ExprInstruction("DICT", len(items)))
            case ast.StructInit(name=name, fields=fields):
                for field in fields:
                    self._emit_expr(field.value, instructions)
                instructions.append(ExprInstruction("STRUCT_INIT", (name, [field.name for field in fields])))
            case ast.Unary(op=op, operand=operand):
                self._emit_expr(operand, instructions)
                instructions.append(ExprInstruction("UNARY", op))
            case ast.Binary(left=left, op=op, right=right):
                if op == "且":
                    self._emit_expr(left, instructions)
                    instructions.append(ExprInstruction("SHORT_AND", self._expression(right)))
                    return
                if op == "或":
                    self._emit_expr(left, instructions)
                    instructions.append(ExprInstruction("SHORT_OR", self._expression(right)))
                    return
                self._emit_expr(left, instructions)
                self._emit_expr(right, instructions)
                instructions.append(ExprInstruction("BINARY", op))
            case ast.Call(callee=callee, args=args):
                self._emit_expr(callee, instructions)
                for item in args:
                    self._emit_expr(item, instructions)
                instructions.append(ExprInstruction("CALL", len(args)))
            case ast.MemberAccess(target=target, name=name):
                self._emit_expr(target, instructions)
                instructions.append(ExprInstruction("MEMBER", name))
            case ast.IndexAccess(target=target, index=index):
                self._emit_expr(target, instructions)
                self._emit_expr(index, instructions)
                instructions.append(ExprInstruction("INDEX"))
            case _:
                raise TypeError(f"不支持的 VM 表达式节点: {type(expr).__name__}")


class BytecodeDisassembler:
    def format_block(self, block: BytecodeBlock, depth: int = 0) -> str:
        pad = "    " * depth
        lines: list[str] = []
        for index, instruction in enumerate(block.instructions):
            label = f"{pad}{index:03d} {instruction.op}"
            op = instruction.op
            args = instruction.args
            if op == "IMPORT":
                module, alias = args
                lines.append(f"{label} {module!r} -> {alias}")
                continue
            if op == "DECLARE":
                name, expr, mutable = args
                lines.append(f"{label} {'令' if mutable else '常'} {name}")
                lines.extend(self._expr_lines(expr, depth + 1))
                continue
            if op == "ASSIGN":
                target, expr = args
                lines.append(f"{label} {self._store_target_text(target)}")
                if target.owner is not None:
                    lines.append(f"{pad}    TARGET:")
                    lines.extend(self._expr_lines(target.owner, depth + 2))
                if target.index is not None:
                    lines.append(f"{pad}    INDEX:")
                    lines.extend(self._expr_lines(target.index, depth + 2))
                lines.extend(self._expr_lines(expr, depth + 1))
                continue
            if op == "FUNCTION":
                name, params, body = args
                lines.append(f"{label} {name}({', '.join(params)})")
                lines.append(f"{pad}    BODY:")
                lines.extend(self.format_block(body, depth + 2).splitlines())
                continue
            if op == "STRUCT":
                name, fields = args
                lines.append(f"{label} {name} {fields}")
                continue
            if op == "IF":
                condition, then_code, else_code = args
                lines.append(label)
                lines.append(f"{pad}    CONDITION:")
                lines.extend(self._expr_lines(condition, depth + 2))
                lines.append(f"{pad}    THEN:")
                lines.extend(self.format_block(then_code, depth + 2).splitlines())
                if else_code is not None:
                    lines.append(f"{pad}    ELSE:")
                    lines.extend(self.format_block(else_code, depth + 2).splitlines())
                continue
            if op == "WHILE":
                condition, body = args
                lines.append(label)
                lines.append(f"{pad}    CONDITION:")
                lines.extend(self._expr_lines(condition, depth + 2))
                lines.append(f"{pad}    BODY:")
                lines.extend(self.format_block(body, depth + 2).splitlines())
                continue
            if op == "FOR":
                name, iterable, body = args
                lines.append(f"{label} {name}")
                lines.append(f"{pad}    ITERABLE:")
                lines.extend(self._expr_lines(iterable, depth + 2))
                lines.append(f"{pad}    BODY:")
                lines.extend(self.format_block(body, depth + 2).splitlines())
                continue
            if op == "MATCH":
                subject, cases = args
                lines.append(label)
                lines.append(f"{pad}    SUBJECT:")
                lines.extend(self._expr_lines(subject, depth + 2))
                for case_index, case in enumerate(cases):
                    title = f"{pad}    CASE {case_index}:"
                    if case.pattern is None:
                        title += " DEFAULT"
                    lines.append(title)
                    if case.pattern is not None:
                        lines.append(f"{pad}        PATTERN:")
                        lines.extend(self._expr_lines(case.pattern, depth + 3))
                    lines.append(f"{pad}        BODY:")
                    lines.extend(self.format_block(case.body, depth + 3).splitlines())
                continue
            if op == "RETURN":
                lines.append(label)
                if args[0] is not None:
                    lines.extend(self._expr_lines(args[0], depth + 1))
                continue
            if op == "ASSERT":
                condition, message = args
                lines.append(label)
                lines.append(f"{pad}    CONDITION:")
                lines.extend(self._expr_lines(condition, depth + 2))
                if message is not None:
                    lines.append(f"{pad}    MESSAGE:")
                    lines.extend(self._expr_lines(message, depth + 2))
                continue
            if op == "THROW":
                lines.append(label)
                lines.extend(self._expr_lines(args[0], depth + 1))
                continue
            if op == "TRY":
                try_code, catch_name, catch_code = args
                lines.append(f"{label} {catch_name or '_'}")
                lines.append(f"{pad}    TRY:")
                lines.extend(self.format_block(try_code, depth + 2).splitlines())
                lines.append(f"{pad}    CATCH:")
                lines.extend(self.format_block(catch_code, depth + 2).splitlines())
                continue
            if op == "EVAL":
                lines.append(label)
                lines.extend(self._expr_lines(args[0], depth + 1))
                continue
            lines.append(label)
        return "\n".join(lines)

    def _expr_lines(self, expr: ExprCode, depth: int) -> list[str]:
        pad = "    " * depth
        lines = [f"{pad}EXPR:"]
        for index, instruction in enumerate(expr.instructions):
            label = f"{pad}    {index:03d} {instruction.op}"
            if instruction.op in {"CONST", "NAME", "UNARY", "BINARY", "CALL", "LIST", "DICT", "MEMBER", "STRUCT_INIT"}:
                lines.append(f"{label} {instruction.arg!r}")
                continue
            if instruction.op in {"SHORT_AND", "SHORT_OR"}:
                lines.append(label)
                lines.append(f"{pad}        RIGHT:")
                lines.extend(self._expr_lines(instruction.arg, depth + 3))
                continue
            lines.append(label)
        return lines

    def _store_target_text(self, target: StoreTargetCode) -> str:
        if target.kind == "name":
            return target.name or "<?>"
        if target.kind == "member":
            return f".{target.name}"
        if target.kind == "index":
            return "[]"
        return "<?target>"


class VirtualMachine:
    def __init__(self, loader: ModuleLoader | None = None) -> None:
        self.loader = loader or ModuleLoader()
        self.export_filter: set[str] = set()

    def execute(self, block: BytecodeBlock, file_path: str, module_name: str = "__main__") -> dict[str, Any]:
        runtime = create_runtime_scope(module_name, file_path, self.loader, backend="vm")
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
        global_env.define("__make_error__", runtime["make_error"])
        global_env.define("__error_payload__", runtime["error_payload"])
        self.execute_block(block, global_env)
        namespace = global_env.flatten()
        namespace["__xuan_exports__"] = {
            key: value
            for key, value in namespace.items()
            if not key.startswith("__") and key not in self.export_filter
        }
        namespace["__backend__"] = "vm"
        return namespace

    def execute_block(self, block: BytecodeBlock, env: Environment) -> None:
        for instruction in block.instructions:
            self.execute_instruction(instruction, env)

    def execute_instruction(self, instruction: BytecodeInstruction, env: Environment) -> None:
        match instruction.op, instruction.args:
            case "IMPORT", (module, alias):
                importer = env.get("__importer__")
                env.define(alias, importer(module))
            case "DECLARE", (name, expr, _mutable):
                env.define(name, self.evaluate(expr, env))
            case "ASSIGN", (target, expr):
                self.assign_target(target, self.evaluate(expr, env), env)
            case "FUNCTION", (name, params, body):
                env.define(name, XuanVmFunction(name=name, params=params, body=body, closure=env, vm=self))
            case "STRUCT", (name, fields):
                env.define(name, env.get("__define_struct__")(name, fields))
            case "IF", (condition, then_code, else_code):
                if self._truthy(self.evaluate(condition, env)):
                    self.execute_block(then_code, Environment(env))
                elif else_code is not None:
                    self.execute_block(else_code, Environment(env))
            case "WHILE", (condition, body):
                while self._truthy(self.evaluate(condition, env)):
                    try:
                        self.execute_block(body, Environment(env))
                    except ContinueSignal:
                        continue
                    except BreakSignal:
                        break
            case "FOR", (name, iterable, body):
                for item in self.evaluate(iterable, env):
                    loop_env = Environment(env)
                    loop_env.define(name, item)
                    try:
                        self.execute_block(body, loop_env)
                    except ContinueSignal:
                        continue
                    except BreakSignal:
                        break
            case "MATCH", (subject, cases):
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
            case "BREAK", _:
                raise BreakSignal()
            case "CONTINUE", _:
                raise ContinueSignal()
            case "RETURN", (expr,):
                raise ReturnSignal(None if expr is None else self.evaluate(expr, env))
            case "ASSERT", (condition, message):
                result = self.evaluate(condition, env)
                if not self._truthy(result):
                    extra = self.evaluate(message, env) if message is not None else "断言失败"
                    raise env.get("__make_error__")(extra)
            case "THROW", (expr,):
                raise env.get("__make_error__")(self.evaluate(expr, env))
            case "TRY", (try_code, catch_name, catch_code):
                try:
                    self.execute_block(try_code, Environment(env))
                except (ReturnSignal, BreakSignal, ContinueSignal):
                    raise
                except Exception as error:
                    catch_env = Environment(env)
                    if catch_name is not None:
                        catch_env.define(catch_name, env.get("__error_payload__")(error))
                    self.execute_block(catch_code, catch_env)
            case "EVAL", (expr,):
                self.evaluate(expr, env)
            case _:
                raise XuanRuntimeError(f"不支持的 VM 指令: {instruction.op}")

    def assign_target(self, target: StoreTargetCode, value: Any, env: Environment) -> Any:
        if target.kind == "name" and target.name is not None:
            return env.assign(target.name, value)
        if target.kind == "member" and target.owner is not None and target.name is not None:
            container = self.evaluate(target.owner, env)
            if isinstance(container, dict):
                container[target.name] = value
                return value
            setattr(container, target.name, value)
            return value
        if target.kind == "index" and target.owner is not None and target.index is not None:
            container = self.evaluate(target.owner, env)
            slot = self.evaluate(target.index, env)
            container[slot] = value
            return value
        raise XuanRuntimeError(f"无效的 VM 赋值目标: {target.kind}")

    def evaluate(self, expr: ExprCode, env: Environment) -> Any:
        stack: list[Any] = []
        for instruction in expr.instructions:
            op = instruction.op
            arg = instruction.arg
            if op == "CONST":
                stack.append(arg)
                continue
            if op == "NAME":
                stack.append(env.get(arg))
                continue
            if op == "LIST":
                values = [stack.pop() for _ in range(arg)][::-1]
                stack.append(values)
                continue
            if op == "DICT":
                values = [stack.pop() for _ in range(arg * 2)][::-1]
                mapping = {values[index]: values[index + 1] for index in range(0, len(values), 2)}
                stack.append(mapping)
                continue
            if op == "STRUCT_INIT":
                type_name, field_names = arg
                values = [stack.pop() for _ in range(len(field_names))][::-1]
                struct_type = env.get(type_name)
                payload = {field_name: value for field_name, value in zip(field_names, values, strict=True)}
                stack.append(env.get("__new_struct__")(struct_type, payload))
                continue
            if op == "UNARY":
                value = stack.pop()
                stack.append(self._unary(arg, value))
                continue
            if op == "BINARY":
                rhs = stack.pop()
                lhs = stack.pop()
                stack.append(self._binary(lhs, arg, rhs))
                continue
            if op == "SHORT_AND":
                lhs = stack.pop()
                stack.append(self.evaluate(arg, env) if self._truthy(lhs) else lhs)
                continue
            if op == "SHORT_OR":
                lhs = stack.pop()
                stack.append(lhs if self._truthy(lhs) else self.evaluate(arg, env))
                continue
            if op == "CALL":
                args = [stack.pop() for _ in range(arg)][::-1]
                callee = stack.pop()
                stack.append(callee(*args))
                continue
            if op == "MEMBER":
                value = stack.pop()
                stack.append(self._member(value, arg))
                continue
            if op == "INDEX":
                index = stack.pop()
                value = stack.pop()
                stack.append(value[index])
                continue
            raise XuanRuntimeError(f"不支持的 VM 表达式指令: {op}")
        return stack[-1] if stack else None

    def _unary(self, op: str, value: Any) -> Any:
        if op == "-":
            return -value
        if op == "+":
            return +value
        if op == "非":
            return not self._truthy(value)
        raise XuanRuntimeError(f"不支持的一元运算: {op}")

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

    def _member(self, value: Any, name: str) -> Any:
        if hasattr(value, name):
            return getattr(value, name)
        if isinstance(value, dict):
            return value[name]
        raise XuanRuntimeError(f"对象没有成员: {name}")

    @staticmethod
    def _truthy(value: Any) -> bool:
        return bool(value)

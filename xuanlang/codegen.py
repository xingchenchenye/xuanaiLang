from __future__ import annotations

from . import ast_nodes as ast


class PythonCodeGenerator:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.indent = 0
        self.temp_index = 0

    def generate(self, program: ast.Program, source_path: str = "<memory>") -> str:
        self.lines = [
            "# 玄言 编译产物",
            "# 开发者星尘_尘夜",
            "from xuanlang.runtime.prelude import create_runtime_scope",
            "try:",
            "    __xuan_file__",
            "except NameError:",
            f"    __xuan_file__ = {source_path!r}",
            '__xuan_runtime = create_runtime_scope(__name__, __xuan_file__, globals().get("__xuan_loader__"), backend="python")',
            'globals().update(__xuan_runtime["builtins"])',
            '__xuan_import__ = __xuan_runtime["importer"]',
            '__xuan_member__ = __xuan_runtime["member"]',
            '__xuan_set_member__ = __xuan_runtime["set_member"]',
            '__xuan_define_struct__ = __xuan_runtime["define_struct"]',
            '__xuan_new_struct__ = __xuan_runtime["new_struct"]',
            "",
        ]
        self.indent = 0
        self.temp_index = 0
        for statement in program.statements:
            self._statement(statement)
        self._emit('__xuan_exports__ = __xuan_runtime["collect_exports"](globals())')
        return "\n".join(self.lines) + "\n"

    def _statement(self, statement: ast.Statement) -> None:
        match statement:
            case ast.ImportStmt(module=module, alias=alias):
                self._emit(f"{alias} = __xuan_import__({module!r}, __xuan_file__)")
            case ast.VarDecl(name=name, value=value, mutable=_):
                self._emit(f"{name} = {self._expr(value)}")
            case ast.Assign(target=target, value=value):
                self._emit_assign(target, value)
            case ast.FunctionDecl(name=name, params=params, body=body):
                param_text = ", ".join(param.name for param in params)
                self._emit(f"def {name}({param_text}):")
                self._with_indent(body)
            case ast.StructDecl(name=name, fields=fields):
                mapping = ", ".join(f'"{field.name}": "{field.annotation.name}"' for field in fields)
                self._emit(f'{name} = __xuan_define_struct__("{name}", {{{mapping}}})')
            case ast.IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                self._emit(f"if {self._expr(condition)}:")
                self._with_indent(then_branch)
                if else_branch is not None:
                    self._emit("else:")
                    self._with_indent(else_branch)
            case ast.WhileStmt(condition=condition, body=body):
                self._emit(f"while {self._expr(condition)}:")
                self._with_indent(body)
            case ast.ForStmt(name=name, iterable=iterable, body=body):
                self._emit(f"for {name} in {self._expr(iterable)}:")
                self._with_indent(body)
            case ast.MatchStmt(subject=subject, cases=cases):
                subject_name = f"__match_value_{len(self.lines)}"
                self._emit(f"{subject_name} = {self._expr(subject)}")
                first = True
                for case in cases:
                    if case.pattern is None:
                        self._emit("if True:" if first else "else:")
                        first = False
                        self._with_indent(case.body)
                        continue
                    keyword = "if" if first else "elif"
                    first = False
                    self._emit(f"{keyword} {subject_name} == {self._expr(case.pattern)}:")
                    self._with_indent(case.body)
            case ast.BreakStmt():
                self._emit("break")
            case ast.ContinueStmt():
                self._emit("continue")
            case ast.ReturnStmt(value=value):
                self._emit("return" if value is None else f"return {self._expr(value)}")
            case ast.AssertStmt(condition=condition, message=message):
                if message is None:
                    self._emit(f"assert {self._expr(condition)}")
                else:
                    self._emit(f"assert {self._expr(condition)}, {self._expr(message)}")
            case ast.ExprStmt(value=value):
                self._emit(self._expr(value))
            case _:
                raise TypeError(f"不支持的代码生成节点: {type(statement).__name__}")

    def _emit_assign(self, target: ast.Assignable, value: ast.Expression) -> None:
        match target:
            case ast.Name(value=name):
                self._emit(f"{name} = {self._expr(value)}")
            case ast.MemberAccess(target=owner, name=name):
                owner_temp = self._temp()
                value_temp = self._temp()
                self._emit(f"{owner_temp} = {self._expr(owner)}")
                self._emit(f"{value_temp} = {self._expr(value)}")
                self._emit(f'__xuan_set_member__({owner_temp}, "{name}", {value_temp})')
            case ast.IndexAccess(target=owner, index=index):
                owner_temp = self._temp()
                index_temp = self._temp()
                value_temp = self._temp()
                self._emit(f"{owner_temp} = {self._expr(owner)}")
                self._emit(f"{index_temp} = {self._expr(index)}")
                self._emit(f"{value_temp} = {self._expr(value)}")
                self._emit(f"{owner_temp}[{index_temp}] = {value_temp}")
            case _:
                raise TypeError(f"不支持的赋值目标: {type(target).__name__}")

    def _with_indent(self, body: list[ast.Statement]) -> None:
        self.indent += 1
        if not body:
            self._emit("pass")
        else:
            for item in body:
                self._statement(item)
        self.indent -= 1

    def _expr(self, expr: ast.Expression) -> str:
        match expr:
            case ast.Literal(value=value):
                return repr(value)
            case ast.Name(value=name):
                return name
            case ast.ListLiteral(items=items):
                return "[" + ", ".join(self._expr(item) for item in items) + "]"
            case ast.DictLiteral(items=items):
                return "{" + ", ".join(f"{self._expr(item.key)}: {self._expr(item.value)}" for item in items) + "}"
            case ast.StructInit(name=name, fields=fields):
                parts = ", ".join(f'"{field.name}": {self._expr(field.value)}' for field in fields)
                return f'__xuan_new_struct__({name}, {{{parts}}})'
            case ast.Unary(op=op, operand=operand):
                if op == "非":
                    return f"(not {self._expr(operand)})"
                return f"({op}{self._expr(operand)})"
            case ast.Binary(left=left, op=op, right=right):
                py_op = {"且": "and", "或": "or"}.get(op, op)
                return f"({self._expr(left)} {py_op} {self._expr(right)})"
            case ast.Call(callee=callee, args=args):
                return f"{self._expr(callee)}(" + ", ".join(self._expr(item) for item in args) + ")"
            case ast.MemberAccess(target=target, name=name):
                return f'__xuan_member__({self._expr(target)}, "{name}")'
            case ast.IndexAccess(target=target, index=index):
                return f"{self._expr(target)}[{self._expr(index)}]"
            case _:
                raise TypeError(f"不支持的表达式节点: {type(expr).__name__}")

    def _emit(self, line: str) -> None:
        self.lines.append("    " * self.indent + line)

    def _temp(self) -> str:
        name = f"__xuan_tmp_{self.temp_index}"
        self.temp_index += 1
        return name

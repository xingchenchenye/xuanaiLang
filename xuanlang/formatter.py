from __future__ import annotations

import json

from . import ast_nodes as ast


class SourceFormatter:
    def format_program(self, program: ast.Program) -> str:
        return "\n".join(self._statement(stmt, 0) for stmt in program.statements).rstrip() + "\n"

    def _statement(self, statement: ast.Statement, depth: int) -> str:
        pad = "    " * depth
        match statement:
            case ast.ImportStmt(module=module, alias=alias):
                module_text = repr(module) if "/" in module or module.endswith(".xy") else module
                return f"{pad}引 {module_text} 为 {alias}；"
            case ast.VarDecl(name=name, annotation=annotation, value=value, mutable=mutable):
                prefix = "令" if mutable else "常"
                if annotation is None:
                    return f"{pad}{prefix} {name} = {self._expr(value)}；"
                return f"{pad}{prefix} {name}: {self._type(annotation)} = {self._expr(value)}；"
            case ast.Assign(target=target, value=value):
                return f"{pad}{self._expr(target)} = {self._expr(value)}；"
            case ast.FunctionDecl(name=name, params=params, return_type=return_type, body=body):
                param_text = ", ".join(
                    param.name if param.annotation is None else f"{param.name}: {self._type(param.annotation)}"
                    for param in params
                )
                header = f"{pad}术 {name}({param_text})"
                if return_type is not None:
                    header += f" -> {self._type(return_type)}"
                return "\n".join([header + " {", *self._block(body, depth + 1), f"{pad}}}"])
            case ast.StructDecl(name=name, fields=fields):
                if not fields:
                    return f"{pad}构 {name} {{}}"
                field_lines = [f"{pad}    {field.name}: {self._type(field.annotation)}" for field in fields]
                return "\n".join([f"{pad}构 {name} {{", *field_lines, f"{pad}}}"])
            case ast.IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                lines = [f"{pad}若 {self._expr(condition)} {{", *self._block(then_branch, depth + 1), f"{pad}}}"]
                if else_branch is not None:
                    lines.extend([f"{pad}否则 {{", *self._block(else_branch, depth + 1), f"{pad}}}"])
                return "\n".join(lines)
            case ast.WhileStmt(condition=condition, body=body):
                return "\n".join([f"{pad}当 {self._expr(condition)} {{", *self._block(body, depth + 1), f"{pad}}}"])
            case ast.ForStmt(name=name, iterable=iterable, body=body):
                return "\n".join([f"{pad}遍 {name} 于 {self._expr(iterable)} {{", *self._block(body, depth + 1), f"{pad}}}"])
            case ast.MatchStmt(subject=subject, cases=cases):
                lines = [f"{pad}配 {self._expr(subject)} {{"]
                for case in cases:
                    if case.pattern is None:
                        lines.append(f"{pad}    默 {{")
                    else:
                        lines.append(f"{pad}    例 {self._expr(case.pattern)} {{")
                    lines.extend(self._block(case.body, depth + 2))
                    lines.append(f"{pad}    }}")
                lines.append(f"{pad}}}")
                return "\n".join(lines)
            case ast.BreakStmt():
                return f"{pad}停；"
            case ast.ContinueStmt():
                return f"{pad}续；"
            case ast.ReturnStmt(value=value):
                return f"{pad}返；" if value is None else f"{pad}返 {self._expr(value)}；"
            case ast.AssertStmt(condition=condition, message=message):
                return f"{pad}断 {self._expr(condition)}；" if message is None else f"{pad}断 {self._expr(condition)}, {self._expr(message)}；"
            case ast.ExprStmt(value=value):
                return f"{pad}{self._expr(value)}；"
            case _:
                return f"{pad}# 未知语句 {type(statement).__name__}"

    def _block(self, statements: list[ast.Statement], depth: int) -> list[str]:
        if not statements:
            return ["    " * depth + "# 空"]
        return [self._statement(stmt, depth) for stmt in statements]

    def _type(self, value: ast.TypeExpr) -> str:
        if not value.params:
            return value.name
        return f"{value.name}[{', '.join(self._type(item) for item in value.params)}]"

    def _expr(self, expr: ast.Expression) -> str:
        match expr:
            case ast.Literal(value=value):
                if value is True:
                    return "真"
                if value is False:
                    return "假"
                if value is None:
                    return "空"
                if isinstance(value, str):
                    return json.dumps(value, ensure_ascii=False)
                return repr(value)
            case ast.Name(value=name):
                return name
            case ast.ListLiteral(items=items):
                return "[" + ", ".join(self._expr(item) for item in items) + "]"
            case ast.DictLiteral(items=items):
                return "{" + ", ".join(f"{self._expr(item.key)}: {self._expr(item.value)}" for item in items) + "}"
            case ast.StructInit(name=name, fields=fields):
                parts = ", ".join(f"{item.name}: {self._expr(item.value)}" for item in fields)
                return f"新 {name} {{{parts}}}"
            case ast.Unary(op=op, operand=operand):
                return f"({op} {self._expr(operand)})" if op == "非" else f"({op}{self._expr(operand)})"
            case ast.Binary(left=left, op=op, right=right):
                return f"({self._expr(left)} {op} {self._expr(right)})"
            case ast.Call(callee=callee, args=args):
                return f"{self._expr(callee)}(" + ", ".join(self._expr(item) for item in args) + ")"
            case ast.MemberAccess(target=target, name=name):
                return f"{self._expr(target)}.{name}"
            case ast.IndexAccess(target=target, index=index):
                return f"{self._expr(target)}[{self._expr(index)}]"
            case _:
                return f"/*未支持:{type(expr).__name__}*/"

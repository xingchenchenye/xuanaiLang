from __future__ import annotations

import ast as pyast
import json


class PythonToXuanTranslator:
    def translate(self, source: str) -> str:
        tree = pyast.parse(source)
        parts: list[str] = []
        for node in tree.body:
            parts.extend(self._statement(node, 0))
        return "\n".join(parts).rstrip() + "\n"

    def _statement(self, node: pyast.stmt, depth: int) -> list[str]:
        pad = "    " * depth
        match node:
            case pyast.Assign(targets=[target], value=value):
                assign_target = self._assign_target(target)
                if assign_target is not None:
                    return [f"{pad}{assign_target} = {self._expr(value)}；"]
                return [f"{pad}# 不支持的 Python 赋值目标: {type(target).__name__}"]
            case pyast.AnnAssign(target=pyast.Name(id=name), annotation=annotation, value=value, simple=1):
                return [f"{pad}令 {name}: {self._type(annotation)} = {self._expr(value)}；"]
            case pyast.FunctionDef(name=name, args=args, body=body):
                params = []
                for arg in args.args:
                    if arg.annotation is not None:
                        params.append(f"{arg.arg}: {self._type(arg.annotation)}")
                    else:
                        params.append(arg.arg)
                header = f"{pad}术 {name}(" + ", ".join(params) + ")"
                if node.returns is not None:
                    header += f" -> {self._type(node.returns)}"
                header += " {"
                lines = [header]
                for item in body:
                    lines.extend(self._statement(item, depth + 1))
                lines.append(f"{pad}}}")
                return lines
            case pyast.For(target=pyast.Name(id=name), iter=iterable, body=body):
                lines = [f"{pad}遍 {name} 于 {self._expr(iterable)} {{"]
                for item in body:
                    lines.extend(self._statement(item, depth + 1))
                lines.append(f"{pad}}}")
                return lines
            case pyast.Return(value=value):
                return [f"{pad}返 {self._expr(value)}；" if value is not None else f"{pad}返；"]
            case pyast.If(test=test, body=body, orelse=orelse):
                lines = [f"{pad}若 {self._expr(test)} {{"] 
                for item in body:
                    lines.extend(self._statement(item, depth + 1))
                lines.append(f"{pad}}}")
                if orelse:
                    lines[-1] += " 否则 {"
                    else_lines: list[str] = []
                    for item in orelse:
                        else_lines.extend(self._statement(item, depth + 1))
                    lines.extend(else_lines)
                    lines.append(f"{pad}}}")
                return lines
            case pyast.While(test=test, body=body):
                lines = [f"{pad}当 {self._expr(test)} {{"] 
                for item in body:
                    lines.extend(self._statement(item, depth + 1))
                lines.append(f"{pad}}}")
                return lines
            case pyast.Expr(value=value):
                return [f"{pad}{self._expr(value)}；"]
            case _:
                return [f"{pad}# 不支持的 Python 节点: {type(node).__name__}"]

    def _expr(self, node: pyast.AST | None) -> str:
        if node is None:
            return "空"
        match node:
            case pyast.Constant(value=value):
                if value is True:
                    return "真"
                if value is False:
                    return "假"
                if value is None:
                    return "空"
                if isinstance(value, str):
                    return json.dumps(value, ensure_ascii=False)
                return repr(value)
            case pyast.Name(id=name):
                return name
            case pyast.List(elts=elts):
                return "[" + ", ".join(self._expr(item) for item in elts) + "]"
            case pyast.Dict(keys=keys, values=values):
                pairs: list[str] = []
                for key, value in zip(keys, values, strict=True):
                    if key is None:
                        continue
                    pairs.append(f"{self._expr(key)}: {self._expr(value)}")
                return "{" + ", ".join(pairs) + "}"
            case pyast.Call(func=func, args=args):
                if isinstance(func, pyast.Name) and func.id == "print":
                    return "显(" + ", ".join(self._expr(item) for item in args) + ")"
                if isinstance(func, pyast.Name) and func.id == "range":
                    return "范(" + ", ".join(self._expr(item) for item in args) + ")"
                return self._expr(func) + "(" + ", ".join(self._expr(item) for item in args) + ")"
            case pyast.Attribute(value=value, attr=attr):
                return f"{self._expr(value)}.{attr}"
            case pyast.BinOp(left=left, op=op, right=right):
                return f"({self._expr(left)} {self._binop(op)} {self._expr(right)})"
            case pyast.BoolOp(op=op, values=values):
                joiner = " 且 " if isinstance(op, pyast.And) else " 或 "
                return "(" + joiner.join(self._expr(item) for item in values) + ")"
            case pyast.UnaryOp(op=op, operand=operand):
                prefix = {pyast.USub: "-", pyast.UAdd: "+", pyast.Not: "非 "}.get(type(op), "")
                return f"({prefix}{self._expr(operand)})"
            case pyast.Compare(left=left, ops=ops, comparators=comparators):
                parts = [self._expr(left)]
                for op, comp in zip(ops, comparators, strict=True):
                    parts.append(self._cmp(op))
                    parts.append(self._expr(comp))
                return "(" + " ".join(parts) + ")"
            case pyast.Subscript(value=value, slice=slice_):
                return f"{self._expr(value)}[{self._expr(slice_)}]"
            case _:
                return f"/*未支持:{type(node).__name__}*/"

    def _assign_target(self, node: pyast.AST) -> str | None:
        match node:
            case pyast.Name(id=name):
                return f"令 {name}"
            case pyast.Attribute(value=value, attr=attr):
                return f"{self._expr(value)}.{attr}"
            case pyast.Subscript(value=value, slice=slice_):
                return f"{self._expr(value)}[{self._expr(slice_)}]"
            case _:
                return None

    def _type(self, node: pyast.AST) -> str:
        match node:
            case pyast.Name(id="int"):
                return "整"
            case pyast.Name(id="float"):
                return "浮"
            case pyast.Name(id="str"):
                return "文"
            case pyast.Name(id="bool"):
                return "真值"
            case pyast.Subscript(value=pyast.Name(id="list"), slice=slice_):
                return f"列[{self._type(slice_)}]"
            case pyast.Subscript(value=pyast.Name(id="dict"), slice=pyast.Tuple(elts=[key_type, value_type], ctx=_)):
                return f"映[{self._type(key_type)}, {self._type(value_type)}]"
            case pyast.Name(id=name):
                return name
            case _:
                return "任意"

    @staticmethod
    def _binop(op: pyast.operator) -> str:
        mapping = {
            pyast.Add: "+",
            pyast.Sub: "-",
            pyast.Mult: "*",
            pyast.Div: "/",
            pyast.Mod: "%",
            pyast.MatMult: "@",
        }
        return mapping.get(type(op), "?")

    @staticmethod
    def _cmp(op: pyast.cmpop) -> str:
        mapping = {
            pyast.Eq: "==",
            pyast.NotEq: "!=",
            pyast.Gt: ">",
            pyast.GtE: ">=",
            pyast.Lt: "<",
            pyast.LtE: "<=",
        }
        return mapping.get(type(op), "?")

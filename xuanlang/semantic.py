from __future__ import annotations

from dataclasses import dataclass, field

from . import ast_nodes as ast
from .errors import XuanError


@dataclass(slots=True)
class TypeInfo:
    name: str
    params: tuple["TypeInfo", ...] = field(default_factory=tuple)

    def __str__(self) -> str:
        if not self.params:
            return self.name
        return f"{self.name}[{', '.join(str(item) for item in self.params)}]"


任意 = TypeInfo("任意")
未知 = TypeInfo("未知")
整型 = TypeInfo("整")
浮型 = TypeInfo("浮")
文型 = TypeInfo("文")
真值型 = TypeInfo("真值")
空型 = TypeInfo("空")
张量型 = TypeInfo("张量")
映射型 = TypeInfo("映")


@dataclass(slots=True)
class Symbol:
    name: str
    type_info: TypeInfo
    mutable: bool = True
    is_function: bool = False
    return_type: TypeInfo | None = None


class Scope:
    def __init__(self, parent: "Scope | None" = None) -> None:
        self.parent = parent
        self.symbols: dict[str, Symbol] = {}

    def define(self, symbol: Symbol) -> None:
        self.symbols[symbol.name] = symbol

    def lookup(self, name: str) -> Symbol | None:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        return None


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.global_scope = Scope()
        self.scope = self.global_scope
        self.return_stack: list[TypeInfo] = []
        self.struct_defs: dict[str, dict[str, TypeInfo]] = {}
        self._install_builtins()

    def analyze(self, program: ast.Program) -> ast.Program:
        for statement in program.statements:
            self._statement(statement)
        return program

    def snapshot_global_symbols(self) -> dict[str, str]:
        return {
            name: str(symbol.return_type if symbol.is_function and symbol.return_type else symbol.type_info)
            for name, symbol in self.global_scope.symbols.items()
        }

    def _install_builtins(self) -> None:
        builtins = {
            "显": Symbol("显", 空型, mutable=False, is_function=True, return_type=空型),
            "张": Symbol("张", 张量型, mutable=False, is_function=True, return_type=张量型),
            "形": Symbol("形", TypeInfo("列", (整型,)), mutable=False, is_function=True, return_type=TypeInfo("列", (整型,))),
            "量化4": Symbol("量化4", TypeInfo("量化张量"), mutable=False, is_function=True, return_type=TypeInfo("量化张量")),
            "量化8": Symbol("量化8", TypeInfo("量化张量"), mutable=False, is_function=True, return_type=TypeInfo("量化张量")),
            "软最大": Symbol("软最大", 张量型, mutable=False, is_function=True, return_type=张量型),
            "relu": Symbol("relu", 张量型, mutable=False, is_function=True, return_type=张量型),
            "类型": Symbol("类型", 文型, mutable=False, is_function=True, return_type=文型),
            "列长": Symbol("列长", 整型, mutable=False, is_function=True, return_type=整型),
            "范": Symbol("范", TypeInfo("列", (整型,)), mutable=False, is_function=True, return_type=TypeInfo("列", (整型,))),
            "缓存": Symbol("缓存", TypeInfo("缓存"), mutable=False, is_function=True, return_type=TypeInfo("缓存")),
            "注意": Symbol("注意", 张量型, mutable=False, is_function=True, return_type=张量型),
            "归一": Symbol("归一", 张量型, mutable=False, is_function=True, return_type=张量型),
            "转步": Symbol("转步", 张量型, mutable=False, is_function=True, return_type=张量型),
        }
        for symbol in builtins.values():
            self.global_scope.define(symbol)

    def _statement(self, statement: ast.Statement) -> None:
        match statement:
            case ast.ImportStmt(module=_, alias=alias):
                self.scope.define(Symbol(alias, TypeInfo("模块"), mutable=False))
            case ast.VarDecl(name=name, annotation=annotation, value=value, mutable=mutable):
                value_type = self._expression(value)
                declared = self._from_annotation(annotation) if annotation else value_type
                if annotation and not self._compatible(declared, value_type):
                    raise XuanError(f"变量 {name} 的类型不匹配: 期望 {declared}, 得到 {value_type}")
                self.scope.define(Symbol(name, declared, mutable=mutable))
            case ast.StructDecl(name=name, fields=fields):
                if name in self.struct_defs:
                    raise XuanError(f"结构 {name} 已定义")
                self.struct_defs[name] = {field.name: self._from_annotation(field.annotation) for field in fields}
                self.scope.define(Symbol(name, TypeInfo("构型"), mutable=False))
            case ast.Assign(target=target, value=value):
                value_type = self._expression(value)
                self._check_assign_target(target, value_type)
            case ast.FunctionDecl(name=name, params=params, return_type=ret_type, body=body):
                return_info = self._from_annotation(ret_type) if ret_type else 未知
                self.scope.define(Symbol(name, TypeInfo("函数"), mutable=False, is_function=True, return_type=return_info))
                saved_scope = self.scope
                self.scope = Scope(saved_scope)
                self.return_stack.append(return_info)
                for param in params:
                    param_type = self._from_annotation(param.annotation) if param.annotation else 未知
                    self.scope.define(Symbol(param.name, param_type))
                for item in body:
                    self._statement(item)
                self.return_stack.pop()
                self.scope = saved_scope
            case ast.IfStmt(condition=cond, then_branch=then_body, else_branch=else_body):
                self._expression(cond)
                self._with_child_scope(then_body)
                if else_body is not None:
                    self._with_child_scope(else_body)
            case ast.WhileStmt(condition=cond, body=body):
                self._expression(cond)
                self._with_child_scope(body)
            case ast.ForStmt(name=name, iterable=iterable, body=body):
                iterable_type = self._expression(iterable)
                item_type = iterable_type.params[0] if iterable_type.name == "列" and iterable_type.params else 任意
                saved_scope = self.scope
                self.scope = Scope(saved_scope)
                self.scope.define(Symbol(name, item_type))
                for item in body:
                    self._statement(item)
                self.scope = saved_scope
            case ast.MatchStmt(subject=subject, cases=cases):
                subject_type = self._expression(subject)
                for case in cases:
                    if case.pattern is not None:
                        pattern_type = self._expression(case.pattern)
                        if not self._compatible(subject_type, pattern_type):
                            raise XuanError(f"匹配分支类型不匹配: 目标 {subject_type}, 模式 {pattern_type}")
                    self._with_child_scope(case.body)
            case ast.BreakStmt() | ast.ContinueStmt():
                return
            case ast.ReturnStmt(value=value):
                expected = self.return_stack[-1] if self.return_stack else 空型
                actual = self._expression(value) if value is not None else 空型
                if self.return_stack and not self._compatible(expected, actual):
                    raise XuanError(f"返回类型不匹配: 期望 {expected}, 得到 {actual}")
            case ast.AssertStmt(condition=cond, message=msg):
                self._expression(cond)
                if msg is not None:
                    self._expression(msg)
            case ast.ThrowStmt(value=value):
                self._expression(value)
            case ast.TryStmt(try_branch=try_branch, catch_name=catch_name, catch_branch=catch_branch):
                self._with_child_scope(try_branch)
                saved_scope = self.scope
                self.scope = Scope(saved_scope)
                if catch_name is not None:
                    self.scope.define(Symbol(catch_name, 任意))
                for item in catch_branch:
                    self._statement(item)
                self.scope = saved_scope
            case ast.ExprStmt(value=value):
                self._expression(value)
            case _:
                raise XuanError(f"暂不支持的语义节点: {type(statement).__name__}")

    def _with_child_scope(self, body: list[ast.Statement]) -> None:
        saved_scope = self.scope
        self.scope = Scope(saved_scope)
        for item in body:
            self._statement(item)
        self.scope = saved_scope

    def _expression(self, expr: ast.Expression | None) -> TypeInfo:
        if expr is None:
            return 空型
        match expr:
            case ast.Literal(value=value):
                if value is None:
                    return 空型
                if isinstance(value, bool):
                    return 真值型
                if isinstance(value, int):
                    return 整型
                if isinstance(value, float):
                    return 浮型
                if isinstance(value, str):
                    return 文型
                return 任意
            case ast.Name(value=name):
                symbol = self.scope.lookup(name)
                if symbol is None:
                    raise XuanError(f"名称未定义: {name}")
                return symbol.return_type if symbol.is_function and symbol.return_type else symbol.type_info
            case ast.ListLiteral(items=items):
                if not items:
                    return TypeInfo("列", (未知,))
                item_types = [self._expression(item) for item in items]
                first = item_types[0]
                if all(self._compatible(first, item) for item in item_types[1:]):
                    return TypeInfo("列", (first,))
                return TypeInfo("列", (任意,))
            case ast.DictLiteral(items=items):
                if not items:
                    return TypeInfo("映", (未知, 未知))
                key_types = [self._expression(item.key) for item in items]
                value_types = [self._expression(item.value) for item in items]
                key_type = key_types[0] if all(self._compatible(key_types[0], item) for item in key_types[1:]) else 任意
                value_type = value_types[0] if all(self._compatible(value_types[0], item) for item in value_types[1:]) else 任意
                return TypeInfo("映", (key_type, value_type))
            case ast.StructInit(name=name, fields=fields):
                if name not in self.struct_defs:
                    raise XuanError(f"结构 {name} 未定义")
                defined_fields = self.struct_defs[name]
                seen = {field.name for field in fields}
                missing = [field_name for field_name in defined_fields if field_name not in seen]
                extra = [field.name for field in fields if field.name not in defined_fields]
                if missing:
                    raise XuanError(f"结构 {name} 缺少字段: {', '.join(missing)}")
                if extra:
                    raise XuanError(f"结构 {name} 存在未知字段: {', '.join(extra)}")
                for field in fields:
                    actual = self._expression(field.value)
                    expected = defined_fields[field.name]
                    if not self._compatible(expected, actual):
                        raise XuanError(f"结构字段类型不匹配: {name}.{field.name} 需要 {expected}, 得到 {actual}")
                return TypeInfo(name)
            case ast.Unary(op=op, operand=operand):
                operand_type = self._expression(operand)
                if op == "非":
                    return 真值型
                return operand_type
            case ast.Binary(left=left, op=op, right=right):
                left_type = self._expression(left)
                right_type = self._expression(right)
                if op in {"==", "!=", "<", "<=", ">", ">=", "且", "或"}:
                    return 真值型
                if op == "@":
                    return 张量型
                if 文型 in (left_type, right_type) and op == "+":
                    return 文型
                if 浮型 in (left_type, right_type):
                    return 浮型
                if left_type == right_type:
                    return left_type
                if self._numeric(left_type) and self._numeric(right_type):
                    return 整型
                return 任意
            case ast.Call(callee=callee, args=args):
                for arg in args:
                    self._expression(arg)
                if isinstance(callee, ast.Name):
                    symbol = self.scope.lookup(callee.value)
                    if symbol and symbol.return_type:
                        return symbol.return_type
                return 任意
            case ast.MemberAccess(target=target, name=name):
                target_type = self._expression(target)
                if target_type.name in self.struct_defs:
                    return self.struct_defs[target_type.name].get(name, 任意)
                return 任意
            case ast.IndexAccess(target=target, index=index):
                target_type = self._expression(target)
                self._expression(index)
                if target_type.name == "列" and target_type.params:
                    return target_type.params[0]
                if target_type.name == "映" and len(target_type.params) == 2:
                    return target_type.params[1]
                return 任意
            case _:
                return 未知

    def _check_assign_target(self, target: ast.Assignable, value_type: TypeInfo) -> None:
        match target:
            case ast.Name(value=name):
                symbol = self.scope.lookup(name)
                if symbol is None:
                    raise XuanError(f"变量 {name} 未定义")
                if not symbol.mutable:
                    raise XuanError(f"常量 {name} 不允许重新赋值")
                if not self._compatible(symbol.type_info, value_type):
                    raise XuanError(f"赋值类型不匹配: {name} 需要 {symbol.type_info}, 得到 {value_type}")
            case ast.MemberAccess(target=owner, name=name):
                owner_type = self._expression(owner)
                if owner_type.name in self.struct_defs:
                    fields = self.struct_defs[owner_type.name]
                    if name not in fields:
                        raise XuanError(f"结构 {owner_type.name} 没有字段 {name}")
                    if not self._compatible(fields[name], value_type):
                        raise XuanError(f"成员赋值类型不匹配: {name} 需要 {fields[name]}, 得到 {value_type}")
                elif owner_type.name == "映" and len(owner_type.params) == 2:
                    key_type, item_type = owner_type.params
                    if not self._compatible(key_type, 文型):
                        raise XuanError(f"成员赋值键类型不匹配: {name} 需要 {key_type}")
                    if not self._compatible(item_type, value_type):
                        raise XuanError(f"成员赋值类型不匹配: {name} 需要 {item_type}, 得到 {value_type}")
                elif owner_type.name not in {"任意", "未知"} and not self._compatible(任意, owner_type):
                    return
            case ast.IndexAccess(target=owner, index=index):
                owner_type = self._expression(owner)
                index_type = self._expression(index)
                if owner_type.name == "列" and owner_type.params:
                    if not self._compatible(整型, index_type):
                        raise XuanError(f"列表索引必须为整, 得到 {index_type}")
                    if not self._compatible(owner_type.params[0], value_type):
                        raise XuanError(f"列表赋值类型不匹配: 需要 {owner_type.params[0]}, 得到 {value_type}")
                elif owner_type.name == "映" and len(owner_type.params) == 2:
                    key_type, item_type = owner_type.params
                    if not self._compatible(key_type, index_type):
                        raise XuanError(f"映射键类型不匹配: 需要 {key_type}, 得到 {index_type}")
                    if not self._compatible(item_type, value_type):
                        raise XuanError(f"映射赋值类型不匹配: 需要 {item_type}, 得到 {value_type}")
            case _:
                raise XuanError(f"无效的赋值目标: {type(target).__name__}")

    @staticmethod
    def _numeric(type_info: TypeInfo) -> bool:
        return type_info.name in {"整", "浮"}

    @staticmethod
    def _compatible(expected: TypeInfo, actual: TypeInfo) -> bool:
        if expected.name in {"任意", "未知"} or actual.name in {"任意", "未知"}:
            return True
        if expected == actual:
            return True
        if expected.name == "浮" and actual.name == "整":
            return True
        return expected.name == actual.name and expected.params == actual.params

    def _from_annotation(self, annotation: ast.TypeExpr | None) -> TypeInfo:
        if annotation is None:
            return 未知
        if annotation.name in self.struct_defs:
            return TypeInfo(annotation.name)
        return TypeInfo(annotation.name, tuple(self._from_annotation(item) for item in annotation.params))

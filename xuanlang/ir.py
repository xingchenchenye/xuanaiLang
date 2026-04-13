from __future__ import annotations

from dataclasses import dataclass

from . import ast_nodes as ast


@dataclass(slots=True)
class Instruction:
    op: str
    args: tuple[str, ...]

    def __str__(self) -> str:
        return " ".join((self.op, *self.args)).strip()


class IRLowerer:
    def __init__(self) -> None:
        self.instructions: list[Instruction] = []
        self.temp_index = 0
        self.label_index = 0

    def lower(self, program: ast.Program) -> list[Instruction]:
        self.instructions.clear()
        for statement in program.statements:
            self._statement(statement)
        return list(self.instructions)

    def _statement(self, statement: ast.Statement) -> None:
        match statement:
            case ast.ImportStmt(module=module, alias=alias):
                self.instructions.append(Instruction("IMPORT", (module, alias)))
            case ast.VarDecl(name=name, value=value, mutable=mutable):
                temp = self._expression(value)
                self.instructions.append(Instruction("DECLARE", (name, "令" if mutable else "常", temp)))
            case ast.Assign(target=target, value=value):
                temp = self._expression(value)
                self._store_target(target, temp)
            case ast.FunctionDecl(name=name, params=params, body=body):
                self.instructions.append(Instruction("FUNC_BEGIN", (name, ",".join(param.name for param in params))))
                for item in body:
                    self._statement(item)
                self.instructions.append(Instruction("FUNC_END", (name,)))
            case ast.StructDecl(name=name, fields=fields):
                field_text = ",".join(f"{field.name}:{self._type(field.annotation)}" for field in fields)
                self.instructions.append(Instruction("STRUCT", (name, field_text)))
            case ast.IfStmt(condition=cond, then_branch=then_body, else_branch=else_body):
                cond_temp = self._expression(cond)
                else_label = self._label("else")
                end_label = self._label("endif")
                self.instructions.append(Instruction("JUMP_IF_FALSE", (cond_temp, else_label)))
                for item in then_body:
                    self._statement(item)
                self.instructions.append(Instruction("JUMP", (end_label,)))
                self.instructions.append(Instruction("LABEL", (else_label,)))
                for item in else_body or []:
                    self._statement(item)
                self.instructions.append(Instruction("LABEL", (end_label,)))
            case ast.WhileStmt(condition=cond, body=body):
                begin = self._label("while")
                end = self._label("endwhile")
                self.instructions.append(Instruction("LABEL", (begin,)))
                cond_temp = self._expression(cond)
                self.instructions.append(Instruction("JUMP_IF_FALSE", (cond_temp, end)))
                for item in body:
                    self._statement(item)
                self.instructions.append(Instruction("JUMP", (begin,)))
                self.instructions.append(Instruction("LABEL", (end,)))
            case ast.ForStmt(name=name, iterable=iterable, body=body):
                iterable_temp = self._expression(iterable)
                self.instructions.append(Instruction("FOR_BEGIN", (name, iterable_temp)))
                for item in body:
                    self._statement(item)
                self.instructions.append(Instruction("FOR_END", (name,)))
            case ast.MatchStmt(subject=subject, cases=cases):
                subject_temp = self._expression(subject)
                end_label = self._label("match_end")
                default_label = None
                for case in cases:
                    if case.pattern is None:
                        default_label = self._label("match_default")
                        self.instructions.append(Instruction("LABEL", (default_label,)))
                        for item in case.body:
                            self._statement(item)
                        self.instructions.append(Instruction("JUMP", (end_label,)))
                        continue
                    next_label = self._label("match_next")
                    pattern_temp = self._expression(case.pattern)
                    cond_temp = self._temp()
                    self.instructions.append(Instruction("BINARY", (cond_temp, subject_temp, "==", pattern_temp)))
                    self.instructions.append(Instruction("JUMP_IF_FALSE", (cond_temp, next_label)))
                    for item in case.body:
                        self._statement(item)
                    self.instructions.append(Instruction("JUMP", (end_label,)))
                    self.instructions.append(Instruction("LABEL", (next_label,)))
                if default_label is None:
                    self.instructions.append(Instruction("NOP", ("match_no_default",)))
                self.instructions.append(Instruction("LABEL", (end_label,)))
            case ast.BreakStmt():
                self.instructions.append(Instruction("BREAK", ()))
            case ast.ContinueStmt():
                self.instructions.append(Instruction("CONTINUE", ()))
            case ast.ReturnStmt(value=value):
                if value is None:
                    self.instructions.append(Instruction("RETURN", ()))
                else:
                    self.instructions.append(Instruction("RETURN", (self._expression(value),)))
            case ast.AssertStmt(condition=condition, message=message):
                args = [self._expression(condition)]
                if message is not None:
                    args.append(self._expression(message))
                self.instructions.append(Instruction("ASSERT", tuple(args)))
            case ast.ThrowStmt(value=value):
                self.instructions.append(Instruction("THROW", (self._expression(value),)))
            case ast.TryStmt(try_branch=try_branch, catch_name=catch_name, catch_branch=catch_branch):
                catch_label = self._label("catch")
                end_label = self._label("try_end")
                self.instructions.append(Instruction("TRY_BEGIN", (catch_label,)))
                for item in try_branch:
                    self._statement(item)
                self.instructions.append(Instruction("TRY_END", ()))
                self.instructions.append(Instruction("JUMP", (end_label,)))
                self.instructions.append(Instruction("LABEL", (catch_label,)))
                if catch_name is not None:
                    self.instructions.append(Instruction("CATCH", (catch_name,)))
                for item in catch_branch:
                    self._statement(item)
                self.instructions.append(Instruction("LABEL", (end_label,)))
            case ast.ExprStmt(value=value):
                self.instructions.append(Instruction("EVAL", (self._expression(value),)))

    def _expression(self, expr: ast.Expression) -> str:
        match expr:
            case ast.Literal(value=value):
                temp = self._temp()
                self.instructions.append(Instruction("LOAD_CONST", (temp, repr(value))))
                return temp
            case ast.Name(value=name):
                temp = self._temp()
                self.instructions.append(Instruction("LOAD_NAME", (temp, name)))
                return temp
            case ast.ListLiteral(items=items):
                temp_items = [self._expression(item) for item in items]
                temp = self._temp()
                self.instructions.append(Instruction("BUILD_LIST", (temp, *temp_items)))
                return temp
            case ast.DictLiteral(items=items):
                temp_items: list[str] = []
                for item in items:
                    temp_items.append(self._expression(item.key))
                    temp_items.append(self._expression(item.value))
                temp = self._temp()
                self.instructions.append(Instruction("BUILD_DICT", (temp, *temp_items)))
                return temp
            case ast.StructInit(name=name, fields=fields):
                temp_items: list[str] = []
                for field in fields:
                    temp_items.append(field.name)
                    temp_items.append(self._expression(field.value))
                temp = self._temp()
                self.instructions.append(Instruction("BUILD_STRUCT", (temp, name, *temp_items)))
                return temp
            case ast.Unary(op=op, operand=operand):
                value = self._expression(operand)
                temp = self._temp()
                self.instructions.append(Instruction("UNARY", (temp, op, value)))
                return temp
            case ast.Binary(left=left, op=op, right=right):
                lhs = self._expression(left)
                rhs = self._expression(right)
                temp = self._temp()
                self.instructions.append(Instruction("BINARY", (temp, lhs, op, rhs)))
                return temp
            case ast.Call(callee=callee, args=args):
                callee_temp = self._expression(callee)
                arg_temps = [self._expression(item) for item in args]
                temp = self._temp()
                self.instructions.append(Instruction("CALL", (temp, callee_temp, *arg_temps)))
                return temp
            case ast.MemberAccess(target=target, name=name):
                target_temp = self._expression(target)
                temp = self._temp()
                self.instructions.append(Instruction("MEMBER", (temp, target_temp, name)))
                return temp
            case ast.IndexAccess(target=target, index=index):
                target_temp = self._expression(target)
                index_temp = self._expression(index)
                temp = self._temp()
                self.instructions.append(Instruction("INDEX", (temp, target_temp, index_temp)))
                return temp
            case _:
                temp = self._temp()
                self.instructions.append(Instruction("UNKNOWN_EXPR", (temp, type(expr).__name__)))
                return temp

    def _store_target(self, target: ast.Assignable, value_temp: str) -> None:
        match target:
            case ast.Name(value=name):
                self.instructions.append(Instruction("STORE", (name, value_temp)))
            case ast.MemberAccess(target=owner, name=name):
                owner_temp = self._expression(owner)
                self.instructions.append(Instruction("STORE_MEMBER", (owner_temp, name, value_temp)))
            case ast.IndexAccess(target=owner, index=index):
                owner_temp = self._expression(owner)
                index_temp = self._expression(index)
                self.instructions.append(Instruction("STORE_INDEX", (owner_temp, index_temp, value_temp)))
            case _:
                self.instructions.append(Instruction("STORE_UNKNOWN", (type(target).__name__, value_temp)))

    def _temp(self) -> str:
        value = f"%t{self.temp_index}"
        self.temp_index += 1
        return value

    def _label(self, base: str) -> str:
        value = f"{base}_{self.label_index}"
        self.label_index += 1
        return value

    def _type(self, value: ast.TypeExpr) -> str:
        if not value.params:
            return value.name
        return f"{value.name}[{', '.join(self._type(item) for item in value.params)}]"

from __future__ import annotations

from . import ast_nodes as ast


class AstOptimizer:
    def optimize(self, program: ast.Program) -> ast.Program:
        statements: list[ast.Statement] = []
        for statement in program.statements:
            statements.extend(self._statement(statement))
        return ast.Program(statements)

    def _statement(self, statement: ast.Statement) -> list[ast.Statement]:
        match statement:
            case ast.VarDecl(name=name, annotation=annotation, value=value, mutable=mutable):
                return [ast.VarDecl(name, annotation, self._expr(value), mutable)]
            case ast.Assign(target=target, value=value):
                return [ast.Assign(self._assign_target(target), self._expr(value))]
            case ast.FunctionDecl(name=name, params=params, return_type=return_type, body=body):
                new_body: list[ast.Statement] = []
                for item in body:
                    new_body.extend(self._statement(item))
                return [ast.FunctionDecl(name, params, return_type, new_body)]
            case ast.StructDecl(name=name, fields=fields):
                return [ast.StructDecl(name, fields)]
            case ast.IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                optimized_condition = self._expr(condition)
                then_items = self._opt_block(then_branch)
                else_items = self._opt_block(else_branch or [])
                if isinstance(optimized_condition, ast.Literal) and isinstance(optimized_condition.value, bool):
                    return then_items if optimized_condition.value else else_items
                return [ast.IfStmt(optimized_condition, then_items, else_items or None)]
            case ast.WhileStmt(condition=condition, body=body):
                optimized_condition = self._expr(condition)
                if isinstance(optimized_condition, ast.Literal) and optimized_condition.value is False:
                    return []
                return [ast.WhileStmt(optimized_condition, self._opt_block(body))]
            case ast.ForStmt(name=name, iterable=iterable, body=body):
                return [ast.ForStmt(name, self._expr(iterable), self._opt_block(body))]
            case ast.MatchStmt(subject=subject, cases=cases):
                optimized_subject = self._expr(subject)
                optimized_cases = [ast.MatchCase(self._expr(case.pattern) if case.pattern is not None else None, self._opt_block(case.body)) for case in cases]
                if isinstance(optimized_subject, ast.Literal):
                    for case in optimized_cases:
                        if case.pattern is None:
                            return case.body
                        if isinstance(case.pattern, ast.Literal) and case.pattern.value == optimized_subject.value:
                            return case.body
                return [ast.MatchStmt(optimized_subject, optimized_cases)]
            case ast.ReturnStmt(value=value):
                return [ast.ReturnStmt(self._expr(value) if value is not None else None)]
            case ast.AssertStmt(condition=condition, message=message):
                optimized = self._expr(condition)
                if isinstance(optimized, ast.Literal) and optimized.value is True:
                    return []
                return [ast.AssertStmt(optimized, self._expr(message) if message is not None else None)]
            case ast.ThrowStmt(value=value):
                return [ast.ThrowStmt(self._expr(value))]
            case ast.TryStmt(try_branch=try_branch, catch_name=catch_name, catch_branch=catch_branch):
                return [ast.TryStmt(self._opt_block(try_branch), catch_name, self._opt_block(catch_branch))]
            case ast.ExprStmt(value=value):
                return [ast.ExprStmt(self._expr(value))]
            case _:
                return [statement]

    def _opt_block(self, body: list[ast.Statement]) -> list[ast.Statement]:
        result: list[ast.Statement] = []
        for item in body:
            result.extend(self._statement(item))
        return result

    def _expr(self, expr: ast.Expression) -> ast.Expression:
        match expr:
            case ast.Unary(op=op, operand=operand):
                inner = self._expr(operand)
                if isinstance(inner, ast.Literal):
                    if op == "-" and isinstance(inner.value, (int, float)):
                        return ast.Literal(-inner.value)
                    if op == "+" and isinstance(inner.value, (int, float)):
                        return ast.Literal(+inner.value)
                    if op == "非":
                        return ast.Literal(not bool(inner.value))
                return ast.Unary(op, inner)
            case ast.Binary(left=left, op=op, right=right):
                lhs = self._expr(left)
                rhs = self._expr(right)
                if isinstance(lhs, ast.Literal) and isinstance(rhs, ast.Literal):
                    try:
                        return ast.Literal(self._fold_binary(lhs.value, op, rhs.value))
                    except Exception:
                        pass
                return ast.Binary(lhs, op, rhs)
            case ast.Call(callee=callee, args=args):
                return ast.Call(self._expr(callee), [self._expr(item) for item in args])
            case ast.ListLiteral(items=items):
                return ast.ListLiteral([self._expr(item) for item in items])
            case ast.DictLiteral(items=items):
                optimized_items = [ast.DictEntry(self._expr(item.key), self._expr(item.value)) for item in items]
                return ast.DictLiteral(optimized_items)
            case ast.StructInit(name=name, fields=fields):
                optimized_fields = [ast.StructFieldValue(item.name, self._expr(item.value)) for item in fields]
                return ast.StructInit(name, optimized_fields)
            case ast.MemberAccess(target=target, name=name):
                return ast.MemberAccess(self._expr(target), name)
            case ast.IndexAccess(target=target, index=index):
                target_expr = self._expr(target)
                index_expr = self._expr(index)
                if isinstance(target_expr, ast.ListLiteral) and isinstance(index_expr, ast.Literal) and isinstance(index_expr.value, int):
                    if 0 <= index_expr.value < len(target_expr.items):
                        return target_expr.items[index_expr.value]
                if isinstance(target_expr, ast.DictLiteral) and isinstance(index_expr, ast.Literal):
                    for item in target_expr.items:
                        if isinstance(item.key, ast.Literal) and item.key.value == index_expr.value:
                            return item.value
                return ast.IndexAccess(target_expr, index_expr)
            case _:
                return expr

    def _assign_target(self, target: ast.Assignable) -> ast.Assignable:
        match target:
            case ast.Name():
                return target
            case ast.MemberAccess(target=base, name=name):
                return ast.MemberAccess(self._expr(base), name)
            case ast.IndexAccess(target=base, index=index):
                return ast.IndexAccess(self._expr(base), self._expr(index))
            case _:
                return target

    @staticmethod
    def _fold_binary(lhs: object, op: str, rhs: object) -> object:
        match op:
            case "+":
                return lhs + rhs
            case "-":
                return lhs - rhs
            case "*":
                return lhs * rhs
            case "/":
                return lhs / rhs
            case "%":
                return lhs % rhs
            case "==":
                return lhs == rhs
            case "!=":
                return lhs != rhs
            case ">":
                return lhs > rhs
            case ">=":
                return lhs >= rhs
            case "<":
                return lhs < rhs
            case "<=":
                return lhs <= rhs
            case "且":
                return bool(lhs) and bool(rhs)
            case "或":
                return bool(lhs) or bool(rhs)
            case _:
                raise ValueError(op)

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Node:
    pass


@dataclass(slots=True)
class TypeExpr(Node):
    name: str
    params: list["TypeExpr"] = field(default_factory=list)


@dataclass(slots=True)
class Parameter(Node):
    name: str
    annotation: TypeExpr | None = None


@dataclass(slots=True)
class Program(Node):
    statements: list["Statement"]


class Statement(Node):
    pass


class Expression(Node):
    pass


class Assignable(Expression):
    pass


@dataclass(slots=True)
class DictEntry(Node):
    key: Expression
    value: Expression


@dataclass(slots=True)
class StructField(Node):
    name: str
    annotation: TypeExpr


@dataclass(slots=True)
class StructFieldValue(Node):
    name: str
    value: Expression


@dataclass(slots=True)
class ImportStmt(Statement):
    module: str
    alias: str


@dataclass(slots=True)
class VarDecl(Statement):
    name: str
    annotation: TypeExpr | None
    value: Expression
    mutable: bool = True


@dataclass(slots=True)
class Assign(Statement):
    target: Assignable
    value: Expression


@dataclass(slots=True)
class FunctionDecl(Statement):
    name: str
    params: list[Parameter]
    return_type: TypeExpr | None
    body: list[Statement]


@dataclass(slots=True)
class StructDecl(Statement):
    name: str
    fields: list[StructField]


@dataclass(slots=True)
class IfStmt(Statement):
    condition: Expression
    then_branch: list[Statement]
    else_branch: list[Statement] | None = None


@dataclass(slots=True)
class WhileStmt(Statement):
    condition: Expression
    body: list[Statement]


@dataclass(slots=True)
class ForStmt(Statement):
    name: str
    iterable: Expression
    body: list[Statement]


@dataclass(slots=True)
class MatchCase(Node):
    pattern: Expression | None
    body: list[Statement]


@dataclass(slots=True)
class MatchStmt(Statement):
    subject: Expression
    cases: list[MatchCase]


@dataclass(slots=True)
class BreakStmt(Statement):
    pass


@dataclass(slots=True)
class ContinueStmt(Statement):
    pass


@dataclass(slots=True)
class ReturnStmt(Statement):
    value: Expression | None = None


@dataclass(slots=True)
class AssertStmt(Statement):
    condition: Expression
    message: Expression | None = None


@dataclass(slots=True)
class ExprStmt(Statement):
    value: Expression


@dataclass(slots=True)
class Literal(Expression):
    value: object


@dataclass(slots=True)
class Name(Assignable):
    value: str


@dataclass(slots=True)
class ListLiteral(Expression):
    items: list[Expression]


@dataclass(slots=True)
class DictLiteral(Expression):
    items: list[DictEntry]


@dataclass(slots=True)
class StructInit(Expression):
    name: str
    fields: list[StructFieldValue]


@dataclass(slots=True)
class Unary(Expression):
    op: str
    operand: Expression


@dataclass(slots=True)
class Binary(Expression):
    left: Expression
    op: str
    right: Expression


@dataclass(slots=True)
class Call(Expression):
    callee: Expression
    args: list[Expression]


@dataclass(slots=True)
class MemberAccess(Assignable):
    target: Expression
    name: str


@dataclass(slots=True)
class IndexAccess(Assignable):
    target: Expression
    index: Expression

from __future__ import annotations

from . import ast_nodes as ast
from .errors import XuanError
from .tokens import Token, TokenKind


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse(self) -> ast.Program:
        statements: list[ast.Statement] = []
        while not self._check(TokenKind.EOF):
            statements.append(self._statement())
        return ast.Program(statements)

    def _statement(self) -> ast.Statement:
        if self._match(TokenKind.IMPORT):
            return self._import_stmt()
        if self._match(TokenKind.LET):
            return self._var_decl(True)
        if self._match(TokenKind.CONST):
            return self._var_decl(False)
        if self._match(TokenKind.FUN):
            return self._fun_decl()
        if self._match(TokenKind.STRUCT):
            return self._struct_decl()
        if self._match(TokenKind.IF):
            return self._if_stmt()
        if self._match(TokenKind.WHILE):
            return self._while_stmt()
        if self._match(TokenKind.FOR):
            return self._for_stmt()
        if self._match(TokenKind.MATCH):
            return self._match_stmt()
        if self._match(TokenKind.BREAK):
            self._consume(TokenKind.SEMICOLON, "停语句后缺少分号")
            return ast.BreakStmt()
        if self._match(TokenKind.CONTINUE):
            self._consume(TokenKind.SEMICOLON, "续语句后缺少分号")
            return ast.ContinueStmt()
        if self._match(TokenKind.RETURN):
            return self._return_stmt()
        if self._match(TokenKind.ASSERT):
            return self._assert_stmt()
        if self._match(TokenKind.THROW):
            return self._throw_stmt()
        if self._match(TokenKind.TRY):
            return self._try_stmt()
        assignment = self._try_assign_stmt()
        if assignment is not None:
            return assignment
        expr = self._expression()
        self._consume(TokenKind.SEMICOLON, "表达式语句后缺少分号")
        return ast.ExprStmt(expr)

    def _import_stmt(self) -> ast.ImportStmt:
        if self._check(TokenKind.STRING):
            module = self._advance().value
        else:
            parts = [self._consume(TokenKind.IDENT, "导入路径缺少模块名").value]
            while self._match(TokenKind.DOT):
                parts.append(self._consume(TokenKind.IDENT, "点号后缺少模块名").value)
            module = ".".join(parts)
        self._consume(TokenKind.AS, "导入语句缺少“为”")
        alias = self._consume(TokenKind.IDENT, "导入语句缺少别名").value
        self._consume(TokenKind.SEMICOLON, "导入语句后缺少分号")
        return ast.ImportStmt(module, alias)

    def _var_decl(self, mutable: bool) -> ast.VarDecl:
        name = self._consume(TokenKind.IDENT, "变量声明缺少名称").value
        annotation = None
        if self._match(TokenKind.COLON):
            annotation = self._type_expr()
        self._consume(TokenKind.ASSIGN, "变量声明缺少赋值符号")
        value = self._expression()
        self._consume(TokenKind.SEMICOLON, "变量声明后缺少分号")
        return ast.VarDecl(name, annotation, value, mutable=mutable)

    def _assign_stmt(self) -> ast.Assign:
        target = self._assign_target()
        self._consume(TokenKind.ASSIGN, "赋值语句缺少等号")
        value = self._expression()
        self._consume(TokenKind.SEMICOLON, "赋值语句后缺少分号")
        return ast.Assign(target, value)

    def _try_assign_stmt(self) -> ast.Assign | None:
        checkpoint = self.index
        try:
            target = self._assign_target()
        except XuanError:
            self.index = checkpoint
            return None
        if not self._check(TokenKind.ASSIGN):
            self.index = checkpoint
            return None
        self._advance()
        value = self._expression()
        self._consume(TokenKind.SEMICOLON, "赋值语句后缺少分号")
        return ast.Assign(target, value)

    def _assign_target(self) -> ast.Assignable:
        expr: ast.Expression = ast.Name(self._consume(TokenKind.IDENT, "赋值语句缺少名称").value)
        while True:
            if self._match(TokenKind.LBRACKET):
                index = self._expression()
                self._consume(TokenKind.RBRACKET, "索引访问缺少右中括号")
                expr = ast.IndexAccess(expr, index)
                continue
            if self._match(TokenKind.DOT):
                name = self._consume(TokenKind.IDENT, "成员访问缺少名称").value
                expr = ast.MemberAccess(expr, name)
                continue
            break
        if isinstance(expr, (ast.Name, ast.MemberAccess, ast.IndexAccess)):
            return expr
        token = self._peek()
        raise XuanError("无效的赋值目标", token.line, token.column)

    def _fun_decl(self) -> ast.FunctionDecl:
        name = self._consume(TokenKind.IDENT, "函数声明缺少名称").value
        self._consume(TokenKind.LPAREN, "函数参数列表缺少左括号")
        params: list[ast.Parameter] = []
        if not self._check(TokenKind.RPAREN):
            while True:
                param_name = self._consume(TokenKind.IDENT, "参数缺少名称").value
                annotation = None
                if self._match(TokenKind.COLON):
                    annotation = self._type_expr()
                params.append(ast.Parameter(param_name, annotation))
                if not self._match(TokenKind.COMMA):
                    break
        self._consume(TokenKind.RPAREN, "函数参数列表缺少右括号")
        return_type = self._type_expr() if self._match(TokenKind.ARROW) else None
        body = self._block()
        return ast.FunctionDecl(name, params, return_type, body)

    def _struct_decl(self) -> ast.StructDecl:
        name = self._consume(TokenKind.IDENT, "结构声明缺少名称").value
        self._consume(TokenKind.LBRACE, "结构声明缺少左花括号")
        fields: list[ast.StructField] = []
        if not self._check(TokenKind.RBRACE):
            while True:
                field_name = self._consume(TokenKind.IDENT, "结构字段缺少名称").value
                self._consume(TokenKind.COLON, "结构字段缺少冒号")
                annotation = self._type_expr()
                fields.append(ast.StructField(field_name, annotation))
                if self._match(TokenKind.COMMA):
                    continue
                if self._check(TokenKind.RBRACE):
                    break
        self._consume(TokenKind.RBRACE, "结构声明缺少右花括号")
        return ast.StructDecl(name, fields)

    def _if_stmt(self) -> ast.IfStmt:
        condition = self._expression()
        then_branch = self._block()
        else_branch = self._block() if self._match(TokenKind.ELSE) else None
        return ast.IfStmt(condition, then_branch, else_branch)

    def _while_stmt(self) -> ast.WhileStmt:
        condition = self._expression()
        body = self._block()
        return ast.WhileStmt(condition, body)

    def _for_stmt(self) -> ast.ForStmt:
        name = self._consume(TokenKind.IDENT, "遍历语句缺少变量名").value
        self._consume(TokenKind.IN, "遍历语句缺少“于”")
        iterable = self._expression()
        body = self._block()
        return ast.ForStmt(name, iterable, body)

    def _match_stmt(self) -> ast.MatchStmt:
        subject = self._expression()
        self._consume(TokenKind.LBRACE, "匹配语句缺少左花括号")
        cases: list[ast.MatchCase] = []
        while not self._check(TokenKind.RBRACE):
            if self._match(TokenKind.CASE):
                pattern = self._expression()
                body = self._block()
                cases.append(ast.MatchCase(pattern, body))
                continue
            if self._match(TokenKind.DEFAULT):
                body = self._block()
                cases.append(ast.MatchCase(None, body))
                continue
            token = self._peek()
            raise XuanError("匹配分支必须以“例”或“默”开始", token.line, token.column)
        self._consume(TokenKind.RBRACE, "匹配语句缺少右花括号")
        return ast.MatchStmt(subject, cases)

    def _return_stmt(self) -> ast.ReturnStmt:
        if self._check(TokenKind.SEMICOLON):
            self._advance()
            return ast.ReturnStmt(None)
        value = self._expression()
        self._consume(TokenKind.SEMICOLON, "返回语句后缺少分号")
        return ast.ReturnStmt(value)

    def _assert_stmt(self) -> ast.AssertStmt:
        condition = self._expression()
        message = self._expression() if self._match(TokenKind.COMMA) else None
        self._consume(TokenKind.SEMICOLON, "断言语句后缺少分号")
        return ast.AssertStmt(condition, message)

    def _throw_stmt(self) -> ast.ThrowStmt:
        value = self._expression()
        self._consume(TokenKind.SEMICOLON, "抛出语句后缺少分号")
        return ast.ThrowStmt(value)

    def _try_stmt(self) -> ast.TryStmt:
        try_branch = self._block()
        self._consume(TokenKind.CATCH, "试语句后缺少“捕”")
        catch_name = None
        if self._check(TokenKind.IDENT):
            catch_name = self._advance().value
        catch_branch = self._block()
        return ast.TryStmt(try_branch, catch_name, catch_branch)

    def _block(self) -> list[ast.Statement]:
        self._consume(TokenKind.LBRACE, "代码块缺少左花括号")
        statements: list[ast.Statement] = []
        while not self._check(TokenKind.RBRACE):
            if self._check(TokenKind.EOF):
                token = self._peek()
                raise XuanError("代码块未闭合", token.line, token.column)
            statements.append(self._statement())
        self._consume(TokenKind.RBRACE, "代码块缺少右花括号")
        return statements

    def _type_expr(self) -> ast.TypeExpr:
        name = self._consume(TokenKind.IDENT, "类型缺少名称").value
        params: list[ast.TypeExpr] = []
        if self._match(TokenKind.LBRACKET):
            if not self._check(TokenKind.RBRACKET):
                while True:
                    params.append(self._type_expr())
                    if not self._match(TokenKind.COMMA):
                        break
            self._consume(TokenKind.RBRACKET, "泛型类型缺少右中括号")
        return ast.TypeExpr(name, params)

    def _expression(self) -> ast.Expression:
        return self._logic_or()

    def _logic_or(self) -> ast.Expression:
        expr = self._logic_and()
        while self._match(TokenKind.OR):
            op = self._previous().value
            expr = ast.Binary(expr, op, self._logic_and())
        return expr

    def _logic_and(self) -> ast.Expression:
        expr = self._equality()
        while self._match(TokenKind.AND):
            op = self._previous().value
            expr = ast.Binary(expr, op, self._equality())
        return expr

    def _equality(self) -> ast.Expression:
        expr = self._comparison()
        while self._match(TokenKind.EQ, TokenKind.NE):
            op = self._previous().value
            expr = ast.Binary(expr, op, self._comparison())
        return expr

    def _comparison(self) -> ast.Expression:
        expr = self._term()
        while self._match(TokenKind.LT, TokenKind.LE, TokenKind.GT, TokenKind.GE):
            op = self._previous().value
            expr = ast.Binary(expr, op, self._term())
        return expr

    def _term(self) -> ast.Expression:
        expr = self._factor()
        while self._match(TokenKind.PLUS, TokenKind.MINUS):
            op = self._previous().value
            expr = ast.Binary(expr, op, self._factor())
        return expr

    def _factor(self) -> ast.Expression:
        expr = self._matmul()
        while self._match(TokenKind.STAR, TokenKind.SLASH, TokenKind.PERCENT):
            op = self._previous().value
            expr = ast.Binary(expr, op, self._matmul())
        return expr

    def _matmul(self) -> ast.Expression:
        expr = self._unary()
        while self._match(TokenKind.MATMUL):
            op = self._previous().value
            expr = ast.Binary(expr, op, self._unary())
        return expr

    def _unary(self) -> ast.Expression:
        if self._match(TokenKind.NOT, TokenKind.MINUS, TokenKind.PLUS):
            op = self._previous().value
            return ast.Unary(op, self._unary())
        return self._postfix()

    def _postfix(self) -> ast.Expression:
        expr = self._primary()
        while True:
            if self._match(TokenKind.LPAREN):
                args: list[ast.Expression] = []
                if not self._check(TokenKind.RPAREN):
                    while True:
                        args.append(self._expression())
                        if not self._match(TokenKind.COMMA):
                            break
                self._consume(TokenKind.RPAREN, "函数调用缺少右括号")
                expr = ast.Call(expr, args)
                continue
            if self._match(TokenKind.LBRACKET):
                index = self._expression()
                self._consume(TokenKind.RBRACKET, "索引访问缺少右中括号")
                expr = ast.IndexAccess(expr, index)
                continue
            if self._match(TokenKind.DOT):
                name = self._consume(TokenKind.IDENT, "成员访问缺少名称").value
                expr = ast.MemberAccess(expr, name)
                continue
            break
        return expr

    def _primary(self) -> ast.Expression:
        if self._match(TokenKind.NUMBER):
            raw = self._previous().value
            return ast.Literal(float(raw) if "." in raw else int(raw))
        if self._match(TokenKind.STRING):
            return ast.Literal(self._previous().value)
        if self._match(TokenKind.TRUE):
            return ast.Literal(True)
        if self._match(TokenKind.FALSE):
            return ast.Literal(False)
        if self._match(TokenKind.NULL):
            return ast.Literal(None)
        if self._match(TokenKind.NEW):
            return self._struct_init()
        if self._match(TokenKind.IDENT):
            return ast.Name(self._previous().value)
        if self._match(TokenKind.LBRACKET):
            items: list[ast.Expression] = []
            if not self._check(TokenKind.RBRACKET):
                while True:
                    items.append(self._expression())
                    if not self._match(TokenKind.COMMA):
                        break
            self._consume(TokenKind.RBRACKET, "列表字面量缺少右中括号")
            return ast.ListLiteral(items)
        if self._match(TokenKind.LBRACE):
            items: list[ast.DictEntry] = []
            if not self._check(TokenKind.RBRACE):
                while True:
                    key = self._expression()
                    self._consume(TokenKind.COLON, "映射字面量缺少冒号")
                    value = self._expression()
                    items.append(ast.DictEntry(key, value))
                    if not self._match(TokenKind.COMMA):
                        break
            self._consume(TokenKind.RBRACE, "映射字面量缺少右花括号")
            return ast.DictLiteral(items)
        if self._match(TokenKind.LPAREN):
            expr = self._expression()
            self._consume(TokenKind.RPAREN, "分组表达式缺少右括号")
            return expr
        token = self._peek()
        raise XuanError(f"无法解析的表达式起始符号: {token.value or token.kind.name}", token.line, token.column)

    def _struct_init(self) -> ast.StructInit:
        name = self._consume(TokenKind.IDENT, "结构实例缺少类型名称").value
        self._consume(TokenKind.LBRACE, "结构实例缺少左花括号")
        fields: list[ast.StructFieldValue] = []
        if not self._check(TokenKind.RBRACE):
            while True:
                field_name = self._consume(TokenKind.IDENT, "结构实例字段缺少名称").value
                self._consume(TokenKind.COLON, "结构实例字段缺少冒号")
                value = self._expression()
                fields.append(ast.StructFieldValue(field_name, value))
                if self._match(TokenKind.COMMA):
                    continue
                if self._check(TokenKind.RBRACE):
                    break
        self._consume(TokenKind.RBRACE, "结构实例缺少右花括号")
        return ast.StructInit(name, fields)

    def _match(self, *kinds: TokenKind) -> bool:
        if self._check(*kinds):
            self._advance()
            return True
        return False

    def _consume(self, kind: TokenKind, message: str) -> Token:
        if self._check(kind):
            return self._advance()
        token = self._peek()
        raise XuanError(message, token.line, token.column)

    def _check(self, *kinds: TokenKind) -> bool:
        return self._peek().kind in kinds

    def _advance(self) -> Token:
        if not self._check(TokenKind.EOF):
            self.index += 1
        return self._previous()

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _peek_next(self) -> Token:
        return self.tokens[min(self.index + 1, len(self.tokens) - 1)]

    def _previous(self) -> Token:
        return self.tokens[self.index - 1]

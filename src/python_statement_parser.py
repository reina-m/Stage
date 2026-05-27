import ast

from .notebook_statement import Notebook_Statement
from .python_ast_parser import Python_AST_Parser


class Python_Statement_Parser:
    # splits one Python notebook code cell into ordered top-level statements
    SUPPORTED_STMTS = (
        ast.Assign,
        ast.AnnAssign,
        ast.AugAssign,
        ast.Expr,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )

    def __init__(self, code, cell_id, cell_label):
        self.code = code
        self.cell_id = cell_id
        self.cell_lbl = cell_label
        self.stmts = []
        self.items = []
        self.stmt_idx = 0
        self.syntax_error = None

    def analyse(self):
        try:
            # ast.parse could return SyntaxError
            tree = ast.parse(self.code)
        except SyntaxError as error:
            self.syntax_error = error
            return

        self.items = self.parse_nodes(tree.body, self.cell_id, "")

    def parse_nodes(self, nodes, parent_subflow, condition):
        items = []
        for node in nodes:
            if isinstance(node, ast.If):
                items.append(self.parse_if(node, parent_subflow, condition))
                continue
            if isinstance(node, ast.For):
                items.append(self.parse_for(node, parent_subflow, condition))
                continue
            if isinstance(node, ast.While):
                items.append(self.parse_while(node, parent_subflow, condition))
                continue

            # only supported executable statements become expanded graph nodes
            if not isinstance(node, self.SUPPORTED_STMTS):
                continue

            statement = self.get_statement(node, condition, parent_subflow)
            if statement is not None:
                items.append({"kind": "stmt", "stmt": statement})

        return items

    def parse_if(self, node, parent_subflow, condition):
        # e.g. if flag: x = 1 else: x = 2 creates conditioned dataflow edges
        # nested ifs inherit the outer condition, e.g. "first and second"

        condition_text = ast.unparse(node.test)
        then_condition = self.merge_condition(condition, condition_text)
        else_condition = self.merge_condition(condition, f"not ({condition_text})")

        body = self.parse_nodes(
            node.body,
            parent_subflow,
            then_condition,
        )
        other = self.parse_nodes(
            node.orelse,
            parent_subflow,
            else_condition,
        )

        return {
            "kind": "if",
            "body": body,
            "orelse": other,
            "then_condition": then_condition,
            "else_condition": else_condition,
        }

    def parse_for(self, node, parent_subflow, condition):
        # e.g. for item in items: use(item) keeps items -> item -> use(item)
        # as define-use edges in the parent box, without a subworkflow for the loop
        # e.g. i = 0; for i in values: use(i) uses the loop definition of i
        # an if inside the loop can still create conditioned edges
        target = ast.unparse(node.target)
        iterable = ast.unparse(node.iter)
        header = self.get_loop_statement(
            code=f"for {target} in {iterable}",
            defines=self.get_target_names(node.target),
            expr=node.iter,
            condition=condition,
            parent_subflow=parent_subflow,
        )
        body = self.parse_nodes(node.body, parent_subflow, condition)
        return {"kind": "loop", "items": [{"kind": "stmt", "stmt": header}] + body}

    def parse_while(self, node, parent_subflow, condition):
        # e.g. while active: consume(active) keeps active as a define-use edge
        # in the parent box, without a subworkflow for the loop
        test = ast.unparse(node.test)
        header = self.get_loop_statement(
            code=f"while {test}",
            defines=[],
            expr=node.test,
            condition=condition,
            parent_subflow=parent_subflow,
        )
        body = self.parse_nodes(node.body, parent_subflow, condition)
        return {"kind": "loop", "items": [{"kind": "stmt", "stmt": header}] + body}

    def get_loop_statement(self, code, defines, expr, condition, parent_subflow):
        parser = Python_AST_Parser(ast.unparse(expr))
        parser.analyse()
        return self.add_statement(
            code=code,
            defines=defines,
            uses=parser.get_uses(),
            calls=parser.get_calls(),
            condition=condition,
            parent_subflow=parent_subflow,
        )

    def add_statement(self, code, defines, uses, calls, condition, parent_subflow):
        statement = Notebook_Statement(
            cell_id=self.cell_id,
            statement_index=self.stmt_idx,
            cell_label=self.cell_lbl,
            code=code,
            defines=defines,
            uses=uses,
            calls=calls,
            condition=condition,
            parent_subworkflow=parent_subflow,
        )
        self.stmt_idx += 1
        self.stmts.append(statement)
        return statement

    def get_target_names(self, target):
        names = []
        self.add_target_names(target, names)
        return names

    def add_target_names(self, target, names):
        if isinstance(target, ast.Name):
            if target.id not in names:
                names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self.add_target_names(element, names)

    def get_statement(self, node, condition, parent_subflow):
        stmt_code = self.get_statement_code(node)

        # reuse the cell parser on one statement to get defines/uses/calls
        parser = Python_AST_Parser(stmt_code)
        parser.analyse()
        if parser.get_syntax_error() is not None:
            return None

        return self.add_statement(
            code=stmt_code,
            defines=parser.get_defines(),
            uses=parser.get_uses(),
            calls=parser.get_calls(),
            condition=condition,
            parent_subflow=parent_subflow,
        )

    def get_statement_code(self, node):
        # keeps the exact notebook source for this statement when possible
        source = ast.get_source_segment(self.code, node)
        if source is not None:
            return source.strip()

        # in case Python cannot recover the original segment
        return ast.unparse(node).strip()

    def merge_condition(self, base, extra):
        if not base:
            return extra
        if not extra:
            return base
        if base == extra:
            return base
        return f"{base} and {extra}"

    # GETTERS
    def get_statements(self):
        return list(self.stmts)

    def get_items(self):
        return list(self.items)

    def get_statement_dicos(self):
        return [stmt.get_dico() for stmt in self.stmts]

    def get_syntax_error(self):
        return self.syntax_error

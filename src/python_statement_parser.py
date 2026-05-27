import ast

from .notebook_statement import Notebook_Statement
from .python_ast_parser import Python_AST_Parser


class Python_Statement_Parser:
    # splits one Python notebook code cell into statement-level graph nodes
    # reuses Python_AST_Parser to find defines/uses/calls inside each statement

    # only if creates colored condition edges 
    # all other statements are read by Python_AST_Parser as a dataflow node

    # so they don't create nodes by themselves :
    IGNORED_STMTS = (
        ast.Import,
        ast.ImportFrom,
        ast.Pass,
        ast.Break,
        ast.Continue,
        ast.Global,
        ast.Nonlocal,
    )

    def __init__(self, code, cell_id, cell_label):
        self.code = code
        self.cell_id = cell_id
        self.cell_lbl = cell_label

        # stmts is the list of nodes that will be displayed in the graph
        self.stmts = []

        # items keeps the control structure needed when graph edges are built
        # e.g. an *if* item contains *separate* body and else statement lists
        self.items = []

        # counter to keep generated graph ids unique inside this cell
        self.stmt_idx = 0
        self.syntax_error = None

    def analyse(self):
        try:
            tree = ast.parse(self.code)
        except SyntaxError as error:
            self.syntax_error = error
            return

        # start in the cell box with no active condition
        self.items = self.parse_nodes(tree.body, self.cell_id, "")

    def parse_nodes(self, nodes, parent_subflow, cond):
        # items can either be dataflow nodes or if branch structures
        # (TODO : nested ifs inside loops / try, except / match aren't yet supported :( )

        # Notebook_Graph later creates dataflow edges from this
        items = []
        for node in nodes:
            # if creates alternative definition paths represented on graph edges
            if isinstance(node, ast.If):
                items.append(self.parse_if(node, parent_subflow, cond))
                continue

            # not shown as dataflow nodes
            if isinstance(node, self.IGNORED_STMTS):
                continue

            # this path also reads while, for, assert, raise, try, and with.
            stmt = self.get_statement(node, cond, parent_subflow)
            if stmt is not None:
                items.append({"kind": "stmt", "stmt": stmt})

        return items

    def parse_if(self, node, parent_subflow, cond):
        # e.g. if cond: x = 1 else: x = 2 creates conditional edges
        # nested ifs inherit the outer condition, e.g. "first and second"

        # ast.unparse turns the test node back into readable python text
        # e.g. node.test for "if score > limit" becomes "score > limit"
        cond_text = ast.unparse(node.test)

        # a statement in either branch remembers when that statement can run
        # e.g. body uses "ready"; else uses "not (ready)"
        then_cond = self.merge_condition(cond, cond_text)
        else_cond = self.merge_condition(cond, f"not ({cond_text})")

        # recursively parsing branches finds nested conditions
        body = self.parse_nodes(
            node.body,
            parent_subflow,
            then_cond,
        )
        other = self.parse_nodes(
            node.orelse,
            parent_subflow,
            else_cond,
        )

        # the graph uses this branch structure when merging definitions later
        # e.g. if both branches define x, use(x) can depend on both definitions
        return {
            "kind": "if",
            "body": body,
            "orelse": other,
            "then_condition": then_cond,
            "else_condition": else_cond,
        }

    def merge_condition(self, c1, c2):
        # add an inner condition to the condition already inherited from its parent
        if not c1:
            return c2
        if not c2:
            return c1
        if c1 == c2:
            return c1
        return f"{c1} and {c2}"

    def add_statement(self, code, defines, uses, calls, cond, parent_subflow):
        # all statement creation passes here so ids preserve source traversal order
        stmt = Notebook_Statement(
            cell_id=self.cell_id,
            statement_index=self.stmt_idx,
            cell_label=self.cell_lbl,
            code=code,
            defines=defines,
            uses=uses,
            calls=calls,
            condition=cond,
            parent_subworkflow=parent_subflow,
        )

        # e.g. the first statement inside cell_0 receives id cell_0_stmt_0
        self.stmt_idx += 1
        self.stmts.append(stmt)
        return stmt

    # getters
    def get_statement(self, node, condition, parent_subflow):
        # recover this one statement as source code for its displayed graph node
        stmt_code = self.get_statement_code(node)

        # reuse the cell parser on one statement to get defines/uses/calls
        # e.g. "a = f(b)" defines a, uses b, and calls f
        parser = Python_AST_Parser(stmt_code)
        parser.analyse()
        if parser.get_syntax_error() is not None:
            # this normally occurs only if source recovery produced invalid code
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
        src = ast.get_source_segment(self.code, node)
        if src is not None:
            return src.strip()

        # in case Python cannot recover the original segment
        # ast.unparse still produces equivalent readable Python code
        return ast.unparse(node).strip()

    def get_statements(self):
        return list(self.stmts)

    def get_items(self):
        return list(self.items)

    def get_statement_dicos(self):
        return [stmt.get_dico() for stmt in self.stmts]

    def get_syntax_error(self):
        # None means ast.parse accepted the cell source
        return self.syntax_error
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
        ast.Import,
        ast.ImportFrom,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )

    IMPORT_STMTS = (ast.Import, ast.ImportFrom)

    def __init__(self, code, cell_id, cell_label):
        self.code = code
        self.cell_id = cell_id
        self.cell_lbl = cell_label
        self.stmts = []
        self.syntax_error = None

    def analyse(self):
        try:
            # ast.parse could return SyntaxError
            tree = ast.parse(self.code)
        except SyntaxError as error:
            self.syntax_error = error
            return

        stmt_idx = 0
        for node in tree.body:
            # only the first implementation's top level statement types
            if not isinstance(node, self.SUPPORTED_STMTS):
                continue

            # import only statements do not become expanded graph nodes
            if isinstance(node, self.IMPORT_STMTS):
                continue

            stmt_code = self.get_statement_code(node)

            # reuse the cell parser on one statement to get defines/uses/calls
            p = Python_AST_Parser(stmt_code)
            p.analyse()
            if p.get_syntax_error() is not None:
                continue

            self.stmts.append(
                Notebook_Statement(
                    cell_id=self.cell_id,
                    statement_index=stmt_idx,
                    cell_label=self.cell_lbl,
                    code=stmt_code,
                    defines=p.get_defines(),
                    uses=p.get_uses(),
                    calls=p.get_calls(),
                    parent_subworkflow=self.cell_id,
                )
            )
            stmt_idx += 1

    def get_statement_code(self, node):
        # keeps the exact notebook source for this statement when possible
        src = ast.get_source_segment(self.code, node)
        if src is not None:
            return src.strip()

        # in case Python cannot recover the original segment
        return ast.unparse(node).strip()

    # GETTERS
    def get_statements(self):
        return list(self.stmts)

    def get_statement_dicos(self):
        return [stmt.get_dico() for stmt in self.stmts]

    def get_syntax_error(self):
        return self.syntax_error

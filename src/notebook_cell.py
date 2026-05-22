from .python_ast_parser import Python_AST_Parser


class Notebook_Cell:
    # stores one code cell + what the AST parser found in it
    def __init__(self, id, idx, code_idx, code, output=None):
        self.id = id
        # original index in the .ipynb file, including markdown cells
        self.idx = idx
        # index among code cells only, used for labels A, B, C (temporary)...
        self.code_idx = code_idx
        self.code = code
        self.output = output or []
        self.imports = []
        self.defines = []
        self.callable_defines = []
        self.uses = []
        self.calls = []
        self.function_uses = {}
        self.syntax_error = None

    def analyse(self):
        parser = Python_AST_Parser(self.code)
        parser.analyse()

        self.imports = parser.get_imports()
        self.defines = parser.get_defines()
        self.callable_defines = parser.get_callable_defines()
        self.uses = parser.get_uses()
        self.calls = parser.get_calls()
        self.function_uses = parser.get_function_uses()
        self.syntax_error = parser.get_syntax_error()

    # GETTERS
    def get_id(self):
        return self.id

    def get_notebook_index(self):
        return self.idx

    def get_code_index(self):
        return self.code_idx

    def get_code(self):
        return self.code

    def get_output(self):
        return self.output

    def get_imports(self):
        return self.imports

    def get_defines(self):
        return self.defines

    def get_callable_defines(self):
        return self.callable_defines

    def get_uses(self):
        return self.uses

    def get_calls(self):
        return self.calls

    def get_function_uses(self):
        return self.function_uses

import os
import builtins
from pathlib import Path
import nbformat
from .python_ast_parser import Python_AST_Parser


class Notebook_Cell:
    # stores one code cell + what the AST parser found in it
    def __init__(self, id, notebook_index, code_index, code):
        self.id = id
        # original index in the .ipynb file, including markdown cells
        self.notebook_index = notebook_index
        # index among code cells only, used for labels A, B, C (temporary)...
        self.code_index = code_index
        self.code = code
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
        return self.notebook_index

    def get_code_index(self):
        return self.code_index

    def get_code(self):
        return self.code

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


class Notebook_File:
    # reads one .ipynb file and keeps only useful code cells
    def __init__(self, address):
        self.address = address
        self.cells = []
        # skipped cells are kept with a reason, useful for debugging
        self.skipped_cells = []
        # maps function name to variables used inside the function body
        self.function_uses = {}
        # imported names are not modelized as notebook data dependencies
        self.imported_names = set()
        self.initialised = False

        self.initialise()

    def clean_code_cell(self, code):
        # skip cell magics (line or whole cell if starting with %%)
        lines = code.splitlines()

        for line in lines:
            if line.strip() == "":
                continue
            if line.lstrip().startswith("%%"):
                return ""
            break

        clean_lines = []
        for line in lines:
            stripped_line = line.lstrip()
            # skips line magic e.g. %matplotlib inline
            if stripped_line.startswith("%"):
                continue
            # skips shell command e.g. !pip install biopython
            if stripped_line.startswith("!"):
                continue
            clean_lines.append(line)

        # return code that ast.parse can understand
        return "\n".join(clean_lines)

    def initialise(self):
        # nbformat reads the JSON notebook file as a notebook object
        # return type : NotebookNode (has attribute nb.cells)
        notebook = nbformat.read(str(self.get_file_address()), as_version=4)

        code_index = 0
        for notebook_index, cell in enumerate(notebook.cells):
            # markdown cells are ignored
            if cell.get("cell_type") != "code":
                continue

            # code_index counts code cells before filtering empty/ignored cells
            current_code_index = code_index
            code_index += 1

            # remove notebook syntax like %matplotlib or !pip install
            code = self.clean_code_cell(cell.get("source", ""))
            if code.strip() == "":
                continue

            # id counts accepted/analyzed cells, not original notebook cells
            notebook_cell = Notebook_Cell(
                id=f"cell_{len(self.cells)}",
                notebook_index=notebook_index,
                code_index=current_code_index,
                code=code,
            )
            notebook_cell.analyse()

            # invalid Python cells are skipped instead of crashing the parser
            if notebook_cell.syntax_error != None:
                self.skipped_cells.append(
                    {
                        "notebook_index": notebook_index,
                        "error": str(notebook_cell.syntax_error),
                    }
                )
                continue

            # function-only cells can be skipped later, but their body uses matter
            self.add_function_uses(notebook_cell)
            self.add_imported_names(notebook_cell)

            # skip cells that do not create useful graph nodes
            if self.is_ignored_cell(notebook_cell):
                self.skipped_cells.append(
                    {
                        "notebook_index": notebook_index,
                        "error": "ignored cell",
                    }
                )
                continue

            # accepted cells become graph nodes later
            self.cells.append(notebook_cell)

        self.initialised = True

    # GETTERS
    def get_file_address(self):
        # normalize path: ./tests/../tests/a.ipynb -> tests/a.ipynb
        return Path(os.path.normpath(self.address))

    def get_notebook_file(self):
        return self

    def get_cells(self):
        return self.cells

    def get_skipped_cells(self):
        return self.skipped_cells

    def get_function_uses(self):
        return self.function_uses

    def add_imported_names(self, notebook_cell):
        # imports are not modelized as data dependencies
        # e.g. from Bio.Data import CodonTable, CodonTable is ignored later
        for import_name in notebook_cell.get_imports():
            self.imported_names.add(import_name.split(".")[-1])
            self.imported_names.add(import_name.split(".")[0])

    def add_function_uses(self, notebook_cell):
        # merge one cell's function uses into the notebook-level map
        for function_name, uses in notebook_cell.get_function_uses().items():
            self.function_uses[function_name] = uses

    def is_ignored_cell(self, notebook_cell):
        # no meaningful defines, uses, or calls means no dependency information
        # e.g. import cells, version-print cells, or comment-only cells
        meaningful_uses = self.get_meaningful_uses(notebook_cell)
        meaningful_calls = self.get_meaningful_calls(notebook_cell)
        if (
            len(notebook_cell.get_defines()) == 0
            and len(meaningful_uses) == 0
            and len(meaningful_calls) == 0
        ):
            return True

        return self.is_callable_definition_only_cell(notebook_cell, meaningful_uses, meaningful_calls)

    def get_meaningful_uses(self, notebook_cell):
        # imported names and Python builtins do not create notebook data nodes
        # e.g. print(Bio.__version__) has only print + Bio, so it is not meaningful
        builtins_names = set(dir(builtins))
        return [
            use
            for use in notebook_cell.get_uses()
            if use not in self.imported_names and use not in builtins_names
        ]

    def get_meaningful_calls(self, notebook_cell):
        # builtin/imported calls alone should not keep a cell as a node
        # e.g. print(...) and CodonTable... are not notebook data transformations
        builtins_names = set(dir(builtins))
        calls = []
        for call in notebook_cell.get_calls():
            root_name = call.split(".")[0]
            if root_name in self.imported_names:
                continue
            if root_name in builtins_names:
                continue
            calls.append(call)
        return calls

    def is_callable_definition_only_cell(self, notebook_cell, meaningful_uses, meaningful_calls):
        # example: def f(): return a
        # we do not create a node for the definition cell itself
        # the dependency appears later when another cell calls f() (temporary)

        if len(notebook_cell.get_defines()) == 0:
            return False
        if len(meaningful_uses) != 0:
            return False
        if len(meaningful_calls) != 0:
            return False

        callable_defines = set(notebook_cell.get_callable_defines())
        for defined_name in notebook_cell.get_defines():
            if defined_name not in callable_defines:
                return False
        return True

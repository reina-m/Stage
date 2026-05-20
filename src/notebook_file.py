import os
import builtins
from pathlib import Path
import nbformat
from .python_ast_parser import Python_AST_Parser


class Notebook_Cell:
    # stores one code cell + what the AST parser found in it
    def __init__(self, id, idx, code_idx, code):
        self.id = id
        # original index in the .ipynb file, including markdown cells
        self.idx = idx
        # index among code cells only, used for labels A, B, C (temporary)...
        self.code_idx = code_idx
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
        return self.idx

    def get_code_index(self):
        return self.code_idx

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
        self.builtin_names = set(dir(builtins))
        self.initialised = False

        self.initialise()

    def clean_code_cell(self, code):
        # skip cell magics (line or whole cell if starting with %%)
        lines = code.splitlines()

        for l in lines:
            if l.strip() == "":
                continue
            if l.lstrip().startswith("%%"):
                return ""
            break

        clean_lines = []
        for l in lines:
            stripped = l.lstrip()
            # skips line magic e.g. %matplotlib inline
            if stripped.startswith("%"):
                continue
            # skips shell command e.g. !pip install biopython
            if stripped.startswith("!"):
                continue
            clean_lines.append(l)

        # return code that ast.parse can understand
        return "\n".join(clean_lines)

    def initialise(self):
        # nbformat reads the JSON notebook file as a notebook object
        # return type : NotebookNode (has attribute nb.cells)
        notebook = nbformat.read(str(self.get_file_address()), as_version=4)

        code_idx = 0
        for idx, c in enumerate(notebook.cells):
            # markdown cells are ignored
            if c.get("cell_type") != "code":
                continue

            # code_idx counts code cells before filtering empty/ignored cells
            current_code_idx = code_idx
            code_idx += 1

            # remove notebook syntax like %matplotlib or !pip install
            code = self.clean_code_cell(c.get("source", ""))
            if code.strip() == "":
                continue

            # id counts accepted/analyzed cells, not original notebook cells
            c = Notebook_Cell(
                id=f"cell_{len(self.cells)}",
                idx=idx,
                code_idx=current_code_idx,
                code=code,
            )
            c.analyse()

            # invalid Python cells are skipped instead of crashing the parser
            if c.syntax_error != None:
                self.skipped_cells.append(
                    {
                        "notebook_index": idx,
                        "error": str(c.syntax_error),
                    }
                )
                continue

            # function-only cells can be skipped later, but their body uses matter
            self.add_function_uses(c)
            self.add_imported_names(c)

            # skip cells that do not create useful graph nodes
            if self.is_ignored_cell(c):
                self.skipped_cells.append(
                    {
                        "notebook_index": idx,
                        "error": "ignored cell",
                    }
                )
                continue

            # accepted cells become graph nodes later
            self.cells.append(c)

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

    def add_imported_names(self, c):
        # imports are not modelized as data dependencies
        # e.g. from Bio.Data import CodonTable, CodonTable is ignored later
        for name in c.get_imports():
            self.imported_names.add(name.split(".")[-1])
            self.imported_names.add(name.split(".")[0])

    def add_function_uses(self, c):
        # merge one cell's function uses into the notebook-level map
        for name, uses in c.get_function_uses().items():
            self.function_uses[name] = uses

    def is_ignored_cell(self, c):
        # no meaningful defines, uses, or calls means no dependency information
        # e.g. import cells, version-print cells, or comment-only cells
        uses = self.get_meaningful_uses(c)
        calls = self.get_meaningful_calls(c)
        if (
            len(c.get_defines()) == 0
            and len(uses) == 0
            and len(calls) == 0
        ):
            return True

        return self.is_callable_definition_only_cell(c, uses, calls)

    def is_callable_definition_only_cell(self, c, uses, calls):
        # example: def f(): return a
        # we do not create a node for the definition cell itself
        # the dependency appears later when another cell calls f() (temporary)

        if len(c.get_defines()) == 0:
            return False
        if len(uses) != 0:
            return False
        if len(calls) != 0:
            return False

        callable_defines = set(c.get_callable_defines())
        for name in c.get_defines():
            if name not in callable_defines:
                return False
        return True

    def get_meaningful_uses(self, c):
        # imported names and Python builtins do not create notebook data nodes
        # e.g. print(Bio.__version__) has only print + Bio, so it is not meaningful
        return [
            name
            for name in c.get_uses()
            if not self.is_ignored_name(name)
        ]

    def get_meaningful_calls(self, c):
        # builtin/imported calls alone should not keep a cell as a node
        # e.g. print(...) and CodonTable... are not notebook data transformations
        calls = []
        for call in c.get_calls():
            name = call.split(".")[0]
            if self.is_ignored_name(name):
                continue
            calls.append(call)
        return calls

    def is_ignored_name(self, name):
        return name in self.imported_names or name in self.builtin_names

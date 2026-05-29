import nbformat
from nbformat.v4 import new_code_cell, new_notebook


def write_notebook(path, code_cells):
    notebook = new_notebook(
        cells=[new_code_cell(source=code) for code in code_cells]
    )
    nbformat.write(notebook, path)

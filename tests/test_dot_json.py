import json
import tempfile
import unittest
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_notebook

from scripts.notebook_flow_graph import get_graphviz_positions
from scripts.notebook_graph_outputs import generate_graph_outputs


def write_notebook(path, code_cells):
    notebook = new_notebook(
        cells=[new_code_cell(source=code) for code in code_cells]
    )
    nbformat.write(notebook, path)


class DotJsonTest(unittest.TestCase):
    def test_dot_and_json_have_same_nodes_and_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notebook_path = root / "flow.ipynb"
            write_notebook(notebook_path, ["a = 1", "b = a", "c = b"])

            dot_path, json_path, _ = generate_graph_outputs(
                notebook_path,
                dot_dir=root / "dot",
                json_dir=root / "json",
                png_dir=root / "png",
            )

            dot_text = dot_path.read_text(encoding="utf-8")
            data = json.loads(json_path.read_text(encoding="utf-8"))

            dot_nodes = set(get_graphviz_positions(dot_text))
            json_nodes = {node["id"] for node in data["nodes"]}

            self.assertEqual(json_nodes, dot_nodes)
            for edge in data["edges"]:
                self.assertIn(edge["id"], dot_text)


if __name__ == "__main__":
    unittest.main()

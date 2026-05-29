import json
import tempfile
import unittest
from pathlib import Path

from scripts.notebook_graph_outputs import (
    generate_expanded_graph_outputs,
    generate_graph_outputs,
)
from helpers import write_notebook


class GenerationOutputsTest(unittest.TestCase):
    def test_regular_dot_json_and_png_are_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notebook_path = root / "simple.ipynb"
            write_notebook(notebook_path, ["a = 1", "b = a"])

            dot_path, json_path, png_path = generate_graph_outputs(
                notebook_path,
                dot_dir=root / "dot",
                json_dir=root / "json",
                png_dir=root / "png",
            )

            self.assertTrue(dot_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(png_path.exists())

            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["nodes"]), 2)
            self.assertEqual(len(data["edges"]), 1)

    def test_expanded_dot_json_and_png_are_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notebook_path = root / "expanded.ipynb"
            write_notebook(notebook_path, ["a = 1\nb = a"])

            dot_path, json_path, png_path = generate_expanded_graph_outputs(
                notebook_path,
                dot_dir=root / "dot",
                json_dir=root / "json",
                png_dir=root / "png",
            )

            self.assertTrue(dot_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(png_path.exists())

            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["nodes"]), 2)
            self.assertEqual(len(data["edges"]), 1)
            self.assertIn("subworkflows", data)
            self.assertEqual(
                [node["id"] for node in data["nodes"]],
                ["cell_0_stmt_0", "cell_0_stmt_1"],
            )
            self.assertEqual(
                data["subworkflows"]["cell_0"]["nodes"],
                ["cell_0_stmt_0", "cell_0_stmt_1"],
            )


if __name__ == "__main__":
    unittest.main()

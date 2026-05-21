import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.notebook_graph_outputs import write_graph_outputs
from src.notebook_file import Notebook_File

DATA_DIR = ROOT_DIR / "data"

# simple patterns for the DOT format built by notebook_flow_graph.py.
# Accept both hand-written DOT and the formatting emitted by graphviz.Digraph.
NODE_RE = re.compile(
    r'^\s*"?(?P<id>cell_\d+)"?\s+\[(?P<attrs>.*?)\]\s*;?',
    re.MULTILINE | re.DOTALL,
)
EDGE_RE = re.compile(
    r'^\s*"?(?P<src>cell_\d+)"?\s*->\s*"?(?P<dst>cell_\d+)"?'
    r'(?:\s+\[(?P<attrs>.*?)\])?\s*;?',
    re.MULTILINE | re.DOTALL,
)
LABEL_RE = re.compile(r'label=(?:"(?P<quoted>[^"]*)"|(?P<plain>[^,\s\]]+))')


class TestDataDotOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # generated graphs are test artifacts, so keep them outside the repo
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls.temp_dir.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def check_notebook_outputs(self, notebook_path):
        # first test: the tool must be able to build graph files for the notebook
        dot_path, _, _ = write_graph_outputs(
            notebook_path,
            self.output_dir / "dot",
            self.output_dir / "json",
            self.output_dir / "png",
        )

        # second test: Graphviz must accept the generated DOT file
        result = subprocess.run(
            ["dot", "-Tdot", str(dot_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        nodes, edges = self.read_dot(dot_path)
        cells = Notebook_File(str(notebook_path)).get_cells()

        # rule 1: one accepted notebook code cell becomes one graph node
        self.assertEqual(len(nodes), len(cells))

        seen_edges = set()
        for source_id, target_id, label in edges:
            # rule 2: every edge must connect two existing cells
            self.assertIn(source_id, nodes)
            self.assertIn(target_id, nodes)

            # rule 3: dependencies must go from an earlier cell to a later cell
            self.assertLess(
                self.cell_number(source_id),
                self.cell_number(target_id),
            )

            # rule 4: each edge must say which variable created the dependency
            self.assertNotEqual(label, "")

            # rule 5: one source/target pair should only appear once
            edge_key = (source_id, target_id)
            self.assertNotIn(edge_key, seen_edges)
            seen_edges.add(edge_key)

    def read_dot(self, dot_path):
        # read only nodes and labelled edges from the generated DOT file
        nodes = set()
        edges = []
        dot_source = dot_path.read_text(encoding="utf-8")

        for node_match in NODE_RE.finditer(dot_source):
            if self.get_label(node_match.group("attrs")):
                nodes.add(node_match.group("id"))

        for edge_match in EDGE_RE.finditer(dot_source):
            edges.append(
                (
                    edge_match.group("src"),
                    edge_match.group("dst"),
                    self.get_label(edge_match.group("attrs") or ""),
                )
            )

        return nodes, edges

    def get_label(self, attrs):
        label_match = LABEL_RE.search(attrs)
        if not label_match:
            return ""
        return label_match.group("quoted") or label_match.group("plain") or ""

    def cell_number(self, cell_id):
        return int(cell_id.removeprefix("cell_"))


def make_notebook_test(notebook_path):
    def test(self):
        self.check_notebook_outputs(notebook_path)

    return test


for index, notebook_path in enumerate(sorted(DATA_DIR.rglob("*.ipynb")), start=1):
    safe_name = re.sub(r"\W+", "_", notebook_path.stem).strip("_")
    test_name = f"test_{index:03d}_{safe_name}"
    setattr(TestDataDotOutputs, test_name, make_notebook_test(notebook_path))


if __name__ == "__main__":
    unittest.main()

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.notebook_file import Notebook_File
from src.notebook_graph import Notebook_Graph


def format_tab(tab):
    if len(tab) == 0:
        return "-"
    return ", ".join(tab)


def main():
    if len(sys.argv) > 1:
        notebook_address = sys.argv[1]
    else:
        notebook_address = "example.ipynb"

    notebook_file = Notebook_File(notebook_address)
    notebook_graph = Notebook_Graph(notebook_file)
    notebook_graph.initialise()

    dependency_graph = notebook_graph.get_dependency_graph_dico()
    output = {
        "nodes": [node["name"] for node in dependency_graph["nodes"]],
        "edges": dependency_graph["edges"],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

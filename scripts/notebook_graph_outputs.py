import graphviz
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.notebook_flow_graph import build_dot, build_expanded_dot, get_graphviz_positions
from src.notebook_file import Notebook_File
from src.notebook_graph import Notebook_Graph

# to generate the outputs in clean seperated folders
EXAMPLE_NOTEBOOKS_DIR = ROOT_DIR / "data" / "notebooks" / "examples"
OUTPUT_DIR = ROOT_DIR / "output"
DOT_DIR = OUTPUT_DIR / "dot"
JSON_DIR = OUTPUT_DIR / "json"
PNG_DIR = OUTPUT_DIR / "png"
EXPANDED_OUTPUT_DIR = ROOT_DIR / "output_expanded"
EXPANDED_DOT_DIR = EXPANDED_OUTPUT_DIR / "dot"
EXPANDED_JSON_DIR = EXPANDED_OUTPUT_DIR / "json"
EXPANDED_PNG_DIR = EXPANDED_OUTPUT_DIR / "png"


def generate_graph_outputs(path, dot_dir=DOT_DIR, json_dir=JSON_DIR, png_dir=PNG_DIR):
    path = Path(path)
    notebook_file = Notebook_File(str(path))
    notebook_graph = Notebook_Graph(notebook_file)
    notebook_graph.initialise()

    dependency_graph = notebook_graph.get_dependency_graph_dico()

    dot_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    dot_path = dot_dir / f"{path.stem}.dot"
    json_path = json_dir / f"{path.stem}.json"
    png_path = png_dir / f"{path.stem}.png"

    dot_source = build_dot(dependency_graph)
    graphviz.Source(dot_source).render(format="dot", outfile=dot_path, cleanup=True)
    positioned_dot_source = dot_path.read_text(encoding="utf-8")
    positions = get_graphviz_positions(positioned_dot_source)
    graph_dico = notebook_graph.get_graph_dico(positions)
    json_path.write_text(
        # json.dumps : serialize obj to a JSON formatted str
        json.dumps(graph_dico, indent=4),
        encoding="utf-8",
    )

    # this replaces the command : dot -Tpng input.dot -o output.png
    graphviz.Source(dot_source).render(outfile=png_path, cleanup=True)

    return dot_path, json_path, png_path


def generate_expanded_graph_outputs(
    path,
    dot_dir=EXPANDED_DOT_DIR,
    json_dir=EXPANDED_JSON_DIR,
    png_dir=EXPANDED_PNG_DIR,
):
    path = Path(path)
    notebook_file = Notebook_File(str(path))
    notebook_graph = Notebook_Graph(notebook_file)

    graph = notebook_graph.get_expanded_dependency_graph_dico()

    dot_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    dot_path = dot_dir / f"{path.stem}.dot"
    json_path = json_dir / f"{path.stem}.json"
    png_path = png_dir / f"{path.stem}.png"

    dot_source = build_expanded_dot(graph)
    graphviz.Source(dot_source).render(format="dot", outfile=dot_path, cleanup=True)
    positioned_dot_source = dot_path.read_text(encoding="utf-8")
    positions = get_graphviz_positions(positioned_dot_source)
    graph_dico = notebook_graph.get_expanded_graph_dico(positions)
    json_path.write_text(json.dumps(graph_dico, indent=4), encoding="utf-8")

    graphviz.Source(dot_source).render(outfile=png_path, cleanup=True)

    return dot_path, json_path, png_path


write_graph_outputs = generate_graph_outputs

# clear out existing outputs
def clear_outputs(output_dir=OUTPUT_DIR):
    outputs = (
        ("dot", "*.dot"),
        ("json", "*.json"),
        ("png", "*.png"),
    )
    for subdir, pattern in outputs:
        dir = output_dir / subdir
        dir.mkdir(parents=True, exist_ok=True)
        for file in dir.glob(pattern):
            file.unlink()


def main():
    args = sys.argv[1:]
    expanded = "--expanded" in args
    notebook_paths = [arg for arg in args if arg != "--expanded"]
    notebook_paths = notebook_paths or [EXAMPLE_NOTEBOOKS_DIR / "example.ipynb"]

    for path in notebook_paths:
        if expanded:
            dot_path, json_path, png_path = generate_expanded_graph_outputs(path)
        else:
            dot_path, json_path, png_path = generate_graph_outputs(path)
        print(f"DOT:  {dot_path.relative_to(ROOT_DIR)}")
        print(f"JSON: {json_path.relative_to(ROOT_DIR)}")
        print(f"PNG:  {png_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()

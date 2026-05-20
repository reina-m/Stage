import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.notebook_file import Notebook_File
from src.notebook_graph import Notebook_Graph

TESTS_DIR = ROOT_DIR / "tests"
OUTPUT_DIR = ROOT_DIR / "output"
DOT_DIR = OUTPUT_DIR / "dot"
JSON_DIR = OUTPUT_DIR / "json"
PNG_DIR = OUTPUT_DIR / "png"


def quote_dot(value):
    return json.dumps(str(value))


def build_dot(graph_dico):
    lines = [
        "digraph Notebook {",
        '    rankdir="TB";',
        '    node [shape=circle, style=filled, fillcolor="#eeeeee", fontname="Helvetica"];',
        '    edge [fontname="Helvetica"];',
    ]

    for node in graph_dico["nodes"]:
        shape = node.get("shape", "circle")
        fillcolor = node.get("fillcolor", "#eeeeee")
        lines.append(
            f"    {quote_dot(node['id'])} "
            f"[label={quote_dot(node['name'])}, shape={quote_dot(shape)}, "
            f"fillcolor={quote_dot(fillcolor)}];"
        )

    for edge in graph_dico["edges"]:
        label = edge.get("label", "")
        if label != "":
            lines.append(
                f"    {quote_dot(edge['A'])} -> {quote_dot(edge['B'])} "
                f"[label={quote_dot(label)}];"
            )
        else:
            lines.append(f"    {quote_dot(edge['A'])} -> {quote_dot(edge['B'])};")

    lines.append("}")
    return "\n".join(lines)


def build_graph_output(notebook_path):
    notebook_file = Notebook_File(str(notebook_path))
    notebook_graph = Notebook_Graph(notebook_file)
    notebook_graph.initialise()

    return notebook_graph.get_dependency_graph_dico()


def write_graph_outputs(notebook_path, dot_dir=DOT_DIR, json_dir=JSON_DIR, png_dir=PNG_DIR):
    notebook_path = Path(notebook_path)
    output = build_graph_output(notebook_path)

    dot_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    dot_path = dot_dir / f"{notebook_path.stem}.dot"
    json_path = json_dir / f"{notebook_path.stem}.json"
    png_path = png_dir / f"{notebook_path.stem}.png"

    dot_path.write_text(build_dot(output), encoding="utf-8")
    json_path.write_text(json.dumps(output, indent=4), encoding="utf-8")
    subprocess.run(["dot", "-Tpng", str(dot_path), "-o", str(png_path)], check=True)

    return dot_path, json_path, png_path


def clear_outputs(output_dir=OUTPUT_DIR):
    for subdir, pattern in (("dot", "*.dot"), ("json", "*.json"), ("png", "*.png")):
        directory = output_dir / subdir
        directory.mkdir(parents=True, exist_ok=True)
        for output_file in directory.glob(pattern):
            output_file.unlink()


def main():
    notebook_paths = sys.argv[1:] or [ROOT_DIR / "tests" / "example.ipynb"]
    for notebook_path in notebook_paths:
        dot_path, json_path, png_path = write_graph_outputs(notebook_path)
        print(f"DOT:  {dot_path.relative_to(ROOT_DIR)}")
        print(f"JSON: {json_path.relative_to(ROOT_DIR)}")
        print(f"PNG:  {png_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()

# Notebook Graph Outputs

Generate dependency graph outputs from Jupyter notebooks.

## Setup

Install the Python dependencies in a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Install the Graphviz system package so the Python `graphviz` package can call the `dot` executable:

```bash
brew install graphviz
```

## Generate Outputs

Generate DOT, JSON, and PNG files for one notebook:

```bash
.venv/bin/python scripts/notebook_graph_outputs.py tests/example.ipynb
```

Generate DOT, JSON, and PNG files for every notebook in `tests/`:

```bash
.venv/bin/python scripts/generate_test_outputs.py
```

The shell wrapper runs the same all-test generation command:

```bash
scripts/generate_all_test_outputs.sh
```

Generated files are written to:

```text
output/dot/
output/json/
output/png/
```

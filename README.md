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
.venv/bin/python scripts/notebook_graph_outputs.py data/notebooks/examples/example.ipynb
```

Generate the expanded intra-cell workflow outputs:

```bash
.venv/bin/python scripts/notebook_graph_outputs.py --expanded data/notebooks/examples/intra_cell_bioinformatics_workflow.ipynb
```

Generate DOT, JSON, and PNG files for every example notebook:

```bash
for notebook in data/notebooks/examples/*.ipynb; do
    .venv/bin/python scripts/notebook_graph_outputs.py "$notebook"
done
```

Generate expanded outputs for every example notebook:

```bash
for notebook in data/notebooks/examples/*.ipynb; do
    .venv/bin/python scripts/notebook_graph_outputs.py --expanded "$notebook"
done
```

## Tests

Run the simple unit tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Generated files are written to:

```text
output/dot/
output/json/
output/png/
```

Expanded workflow files are written to:

```text
output_expanded/dot/
output_expanded/json/
output_expanded/png/
```

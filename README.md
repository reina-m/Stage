# Notebook Graph Outputs

Generate dependency graph outputs from Jupyter notebooks.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Generate Outputs

Generate DOT, JSON, and PNG files for one notebook:

```bash
.venv/bin/python scripts/notebook_graph_outputs.py data/notebooks/examples/example.ipynb
```

```bash
.venv/bin/python scripts/notebook_graph_outputs.py --expanded data/notebooks/examples/notebook10.ipynb
```


```bash
for notebook in data/notebooks/examples/*.ipynb; do
    .venv/bin/python scripts/notebook_graph_outputs.py "$notebook"
done
```

```bash
for notebook in data/notebooks/examples/*.ipynb; do
    .venv/bin/python scripts/notebook_graph_outputs.py --expanded "$notebook"
done
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

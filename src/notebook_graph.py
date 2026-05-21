class Notebook_Graph:
    # graph modelisation rules:
    # 1. one accepted notebook code cell becomes one node
    # 2. an edge A -> B means B uses data defined earlier in A
    # 3. calls do not create edges just because a function was defined before
    # 4. if a called function body uses an external variable, the dependency is
    #    propagated to the cell that calls the function

    def __init__(self, notebook_file):
        self.notebook_file = notebook_file
        # cells are already cleaned/analyzed by Notebook_File
        self.cells = notebook_file.get_cells()
        self.function_uses = notebook_file.get_function_uses()
        self.nodes = []
        self.edges = []

    def initialise(self):
        # build node list first then add dataflow edges between nodes
        self.add_nodes()
        self.add_data_edges()

    def add_nodes(self):
        # rule 1: one accepted code cell = one graph node
        for cell in self.cells:
            self.nodes.append(
                {
                    "id": cell.get_id(),
                    # example: code_index 0 -> A, 1 -> B
                    "name": self.get_cell_label(cell.get_code_index()),
                    "shape": "circle",
                    "fillcolor": "#eeeeee",
                    "type": "code_cell",
                    "notebook_index": cell.get_notebook_index(),
                    "code": cell.get_code(),
                    "imports": cell.get_imports(),
                    "defines": cell.get_defines(),
                    "callable_defines": cell.get_callable_defines(),
                    "uses": cell.get_uses(),
                    "calls": cell.get_calls(),
                }
            )

    def add_data_edges(self):
        # rule 2: edges represent data flow between cells
        # e.g. :
        # cell A: a = 1
        # cell B: b = a + 1
        # creates A -> B with label "a"
        last_def = {}
        labels = {}

        for c in self.cells:
            cell_id = c.get_id()

            # normal variable uses
            for var in c.get_uses():

                # rule 3: a function call/name alone does not create a dependency
                # example: def f() is skipped, then f() should not create def-cell -> call-cell
                if var in self.function_uses:
                    continue

                # if var was defined in an earlier cell, current cell depends on it
                if var in last_def:
                    self.add_edge_label(labels, last_def[var], cell_id, var)

            # function body dependencies propagated to the call cell
            for fun in c.get_calls():
                # rule 4:
                # cell A: threshold = 3
                # skipped cell: def f(x): return x > threshold
                # cell B: result = f(2)
                # creates A -> B with label "threshold"

                for var in self.function_uses.get(fun, []):
                    if var in last_def:
                        self.add_edge_label(labels, last_def[var], cell_id, var)

            # after uses are processed, this cell becomes latest definition source
            # e.g. if a is redefined here, later cells depend on this cell for a
            for var in c.get_defines():
                last_def[var] = cell_id

        # group several variable labels on the same (src -> tgt) edge
        for (src, tgt), edge_labels in labels.items():
            self.add_edge(src, tgt, ", ".join(edge_labels))

    def add_edge_label(self, labels, src, tgt, label):
        # temporary grouping before creating final edge dictionaries
        # e.g. A -> B may have labels ["a", "b"], then final label "a, b"
        key = (src, tgt)
        if key not in labels:
            labels[key] = []
        if label not in labels[key]:
            labels[key].append(label)

    def add_edge(self, src, tgt, label):
        # final edge format used by JSON/DOT exporters
        edge = {"A": src, "B": tgt, "label": label}
        if edge not in self.edges:
            self.edges.append(edge)

    def get_dependency_graph_dico(self):
        return {"nodes": self.nodes, "edges": self.edges}

    def get_graph_dico(self, positions=None):
        positions = positions or {}
        nodes = []
        for index, node in enumerate(self.nodes):
            nodes.append(
                {
                    "id": node["id"],
                    "name": node["name"],
                    "position": positions.get(
                        node["id"],
                        {
                            "x": str(80 + (index % 6) * 144),
                            "y": str(80 + (index // 6) * 112),
                        },
                    ),
                    "code": node["code"],
                }
            )

        edges = []
        for edge in self.edges:
            edges.append(
                {
                    "A": edge["A"],
                    "B": edge["B"],
                    "color": "",
                    "condition": "",
                    "id": f"{edge['A']} -> {edge['B']}",
                }
            )

        return {
            "nodes": nodes,
            "edges": edges,
            "subworkflows": {},
        }

    def get_callable_definitions(self):
        # helper: all functions/classes defined in accepted cells
        callable_defs = set()
        for cell in self.cells:
            for name in cell.get_callable_defines():
                callable_defs.add(name)
        return callable_defs

    # alphabetical order for temporary labels
    def get_cell_label(self, cell_index):
        label = ""
        cell_num = cell_index + 1
        while cell_num > 0:
            cell_num, r = divmod(cell_num - 1, 26)
            label = chr(ord("A") + r) + label
        return label

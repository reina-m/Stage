from .python_statement_parser import Python_Statement_Parser


class Notebook_Graph:
    # graph modelisation rules:
    # 1. one accepted notebook code cell becomes one node
    # 2. an edge A -> B means B uses data defined earlier in A
    # 3. calls do not create edges just because a function was defined before
    # 4. if a called function body uses an external variable, the dependency is
    #    propagated to the cell that calls the function
    CELL_SUBWORKFLOW_COLOR = "#fefefa"
    CONDITION_EDGE_COLORS = [
        "#4E79A7",
        "#E15759",
        "#EDC948",
        "#FF9DA7",
        "#F28E2B",
        "#76B7B2",
        "#B07AA1",
    ]
    POSITION_SCALE = 1.6

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
                    "output": cell.get_output(),
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

    def get_expanded_dependency_graph_dico(self):
        # to start working on sub workflows within cells
        # one accepted code cell is split into statement nodes
        # e.g. b = 1; f(b) becomes A.1 -> A.2 with label "b"
        nodes = []
        subflows = {}
        groups = []

        for c in self.cells:
            p = self.get_cell_statement_parser(c)
            stmts = p.get_statements()
            groups.append(p.get_items())
            nodes.extend([stmt.get_dico() for stmt in stmts])
            self.add_cell_subworkflow(subflows, c, stmts)
            subflows.update(p.get_subworkflows())

        edges = self.get_statement_edges(groups)
        return {"nodes": nodes, "edges": edges, "subworkflows": subflows}

    def add_cell_subworkflow(self, subflows, c, stmts):
        # each expanded cell becomes one subworkflow box
        # e.g. cell_0 contains ["cell_0_stmt_0", "cell_0_stmt_1"]
        if len(stmts) == 0:
            return

        cell_id = c.get_id()
        cell_lbl = self.get_cell_label(c.get_code_index())
        subflows[cell_id] = {
            "nodes": [stmt.get_id() for stmt in stmts],
            "label": f"Cell {cell_lbl}",
            "color": self.CELL_SUBWORKFLOW_COLOR,
        }

    def get_cell_statements(self, c):
        # parse one cell into ordered statements
        p = self.get_cell_statement_parser(c)
        return p.get_statements()

    def get_cell_statement_parser(self, c):
        p = Python_Statement_Parser(
            code=c.get_code(),
            cell_id=c.get_id(),
            cell_label=self.get_cell_label(c.get_code_index()),
        )
        p.analyse()
        return p

    def get_statement_edges(self, groups):
        # same idea as add_data_edges(), but at exact statement level
        # e.g.
        #   b = load_data()  -> last_defs["b"] = [{"node": "cell_0_stmt_0"}]
        #   next cell: f(b) -> edge cell_0_stmt_0 -> cell_1_stmt_0 label "b"
        last_defs = {}
        labels = {}
        cond_order = []

        for group in groups:
            last_defs = self.add_statement_item_edges(
                self.ensure_statement_items(group),
                last_defs,
                labels,
                cond_order,
            )

        condition_colors = self.get_condition_colors(cond_order)

        edges = []
        for (src, tgt, cond), edge_labels in labels.items():
            edges.append(
                {
                    "A": src,
                    "B": tgt,
                    "label": ", ".join(edge_labels),
                    "color": condition_colors.get(cond, ""),
                    "condition": cond,
                }
            )
        return edges

    def ensure_statement_items(self, group):
        if len(group) == 0:
            return []
        if isinstance(group[0], dict):
            return group
        return [{"kind": "stmt", "stmt": stmt} for stmt in group]

    def add_statement_item_edges(self, items, last_defs, labels, cond_order):
        env = self.copy_defs(last_defs)
        for item in items:
            if item["kind"] == "stmt":
                self.add_one_statement_edges(item["stmt"], env, labels, cond_order)
            elif item["kind"] == "if":
                env = self.add_if_statement_edges(item, env, labels, cond_order)
            elif item["kind"] == "loop":
                # e.g. for item in items: use(item) is traversed once as dataflow
                # zero or repeated iterations are not modeled by this graph
                env = self.add_statement_item_edges(
                    item["items"],
                    env,
                    labels,
                    cond_order,
                )
        return env

    def add_one_statement_edges(self, stmt, last_defs, labels, cond_order):
        stmt_id = stmt.get_id()
        stmt_cond = stmt.get_condition()

        # normal variable uses
        for var in stmt.get_uses():

            # a function call/name alone does not create a data dependency
            if var in self.function_uses:
                continue

            if self.is_ignored_name(var):
                continue

            if var in last_defs:
                for src in last_defs[var]:
                    cond = self.merge_condition(src["condition"], stmt_cond)
                    self.add_statement_edge_label(
                        labels, cond_order, src["node"], stmt_id, var, cond
                    )

        # function body external uses are propagated to the call statement
        # e.g. def f(x): return x + scale; f(b) depends on scale
        for fun in stmt.get_calls():
            for var in self.function_uses.get(fun, []):
                if self.is_ignored_name(var):
                    continue
                if var in last_defs:
                    for src in last_defs[var]:
                        cond = self.merge_condition(src["condition"], stmt_cond)
                        self.add_statement_edge_label(
                            labels, cond_order, src["node"], stmt_id, var, cond
                        )

        # definitions become available only after this statement's uses
        for var in stmt.get_defines():
            last_defs[var] = [{"node": stmt_id, "condition": stmt_cond}]

    def add_if_statement_edges(self, item, last_defs, labels, cond_order):
        before = self.copy_defs(last_defs)
        body_defs = self.add_statement_item_edges(
            item["body"],
            self.copy_defs(before),
            labels,
            cond_order,
        )
        else_defs = self.add_statement_item_edges(
            item["orelse"],
            self.copy_defs(before),
            labels,
            cond_order,
        )
        return self.merge_branch_defs(before, body_defs, else_defs, item)

    def merge_branch_defs(self, before, body_defs, else_defs, item):
        # e.g. x = 0; if flag: x = 1; y = x also keeps x = 0 when not (flag)
        merged = self.copy_defs(before)
        vars = set(before) | set(body_defs) | set(else_defs)
        for var in vars:
            prev = before.get(var, [])
            body = body_defs.get(var, [])
            other = else_defs.get(var, [])

            body_changed = not self.same_defs(prev, body)
            other_changed = not self.same_defs(prev, other)

            if body_changed and other_changed:
                merged[var] = self.unique_defs(body + other)
            elif body_changed:
                kept = self.mark_defs(other, item["else_condition"])
                merged[var] = self.unique_defs(body + kept)
            elif other_changed:
                kept = self.mark_defs(body, item["then_condition"])
                merged[var] = self.unique_defs(kept + other)
            else:
                merged[var] = prev
        return merged

    def copy_defs(self, defs):
        return {
            var: [{"node": d["node"], "condition": d["condition"]} for d in vals]
            for var, vals in defs.items()
        }

    def same_defs(self, left, right):
        return self.def_key(left) == self.def_key(right)

    def def_key(self, defs):
        return [(d["node"], d["condition"]) for d in defs]

    def unique_defs(self, defs):
        seen = set()
        res = []
        for d in defs:
            key = (d["node"], d["condition"])
            if key in seen:
                continue
            seen.add(key)
            res.append({"node": d["node"], "condition": d["condition"]})
        return res

    def mark_defs(self, defs, condition):
        return [
            {
                "node": d["node"],
                "condition": self.merge_condition(d["condition"], condition),
            }
            for d in defs
        ]

    def add_statement_edge_label(self, labels, cond_order, src, tgt, label, condition):
        key = (src, tgt, condition)
        if key not in labels:
            labels[key] = []
        if label not in labels[key]:
            labels[key].append(label)
        if condition != "" and condition not in cond_order:
            cond_order.append(condition)

    def merge_condition(self, base, extra):
        if base == "":
            return extra
        if extra == "":
            return base
        if base == extra:
            return base
        if extra.startswith(f"{base} and "):
            return extra
        return f"{base} and {extra}"

    def get_condition_colors(self, cond_order):
        colors = {}
        for idx, cond in enumerate(cond_order):
            colors[cond] = self.CONDITION_EDGE_COLORS[
                idx % len(self.CONDITION_EDGE_COLORS)
            ]
        return colors

    def get_intra_cell_edges(self, stmts):
        # helper for one-cell checks, now implemented with the notebook-wide logic
        return self.get_statement_edges([stmts])

    def is_ignored_name(self, name):
        if hasattr(self.notebook_file, "is_ignored_name"):
            return self.notebook_file.is_ignored_name(name)
        return False

    def get_expanded_graph_dico(self, positions):
        # MetroFlow-style output for statement nodes and cell subworkflow boxes
        # e.g. "subworkflows": {"cell_0": {"nodes": [...], "label": "Cell A"}}
        dico = self.get_expanded_dependency_graph_dico()
        sub_paths = self.get_subworkflow_paths(dico["subworkflows"])
        node_ids = self.get_expanded_node_ids(dico["nodes"], sub_paths)

        if not positions:
            raise ValueError("Graphviz positions are required to build graph JSON.")

        missing_positions = [
            node["id"] for node in dico["nodes"] if node["id"] not in positions
        ]
        if missing_positions:
            raise ValueError(
                f"Missing Graphviz positions for nodes: {', '.join(missing_positions)}"
            )

        nodes = []
        for node in dico["nodes"]:
            nodes.append(
                {
                    "id": node["id"],
                    "name": node["name"],
                    "position": self.scale_position(positions[node["id"]]),
                    "code": node["code"],
                }
            )
            nodes[-1]["id"] = node_ids[node["id"]]

        edges = []
        for edge in dico["edges"]:
            edges.append(
                {
                    "A": node_ids[edge["A"]],
                    "B": node_ids[edge["B"]],
                    "color": edge.get("color", ""),
                    "condition": edge.get("condition", ""),
                    "id": f"{node_ids[edge['A']]} -> {node_ids[edge['B']]}",
                }
            )

        return {
            "nodes": nodes,
            "edges": edges,
            "subworkflows": self.get_final_subworkflows(
                dico["subworkflows"],
                sub_paths,
                node_ids,
            ),
        }

    def get_subworkflow_paths(self, subflows):
        paths = {}

        def add_path(sub_id):
            if sub_id in paths:
                return paths[sub_id]

            sub = subflows[sub_id]
            parent = sub.get("parent", "")
            if parent in subflows:
                path = f"{add_path(parent)}.{sub_id}"
            else:
                path = sub_id

            paths[sub_id] = path
            return path

        for sub_id in subflows:
            add_path(sub_id)
        return paths

    def get_expanded_node_ids(self, nodes, sub_paths):
        node_ids = {}
        for node in nodes:
            parent = node.get("parent_subworkflow", "")
            if parent in sub_paths:
                node_ids[node["id"]] = f"{sub_paths[parent]}.{node['id']}"
            else:
                node_ids[node["id"]] = node["id"]
        return node_ids

    def get_final_subworkflows(self, subflows, sub_paths, node_ids):
        final = {}
        for sub_id in sorted(subflows, key=lambda sub: sub_paths[sub]):
            sub = subflows[sub_id]
            final[sub_paths[sub_id]] = {
                "nodes": [node_ids[node] for node in sub["nodes"]],
                "label": sub["label"],
                "color": sub["color"],
            }
        return final

    def scale_position(self, pos):
        # same idea as BioFlow metro maps: add space between visual nodes
        return {
            "x": str(float(pos["x"]) * self.POSITION_SCALE),
            "y": str(float(pos["y"]) * self.POSITION_SCALE),
        }

    def get_graph_dico(self, positions):
        if not positions:
            raise ValueError("Graphviz positions are required to build graph JSON.")

        missing_positions = [
            node["id"] for node in self.nodes if node["id"] not in positions
        ]
        if missing_positions:
            raise ValueError(
                f"Missing Graphviz positions for nodes: {', '.join(missing_positions)}"
            )

        nodes = []
        for node in self.nodes:
            nodes.append(
                {
                    "id": node["id"],
                    "name": node["name"],
                    "position": self.scale_position(positions[node["id"]]),
                    "code": node["code"],
                    "output": node["output"],
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

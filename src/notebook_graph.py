from .notebook_graph_output import NotebookGraphOutput
from .python_statement_parser import Python_Statement_Parser


class Notebook_Graph:
    # graph modelisation rules :
    # 1. one accepted notebook code cell becomes one node
    # 2. an edge A -> B means B uses data defined earlier in A
    # 3. calls do not create edges just because a function was defined before
    # 4. if a called function body uses an external variable, the dependency is
    #    propagated to the cell that calls the function
    subworkflow_colours = [
        "#fefefa",
        "#eefde6",
        "#e7e6fd",
        "#fefafa",
        "#e6fdfc",
        "#fdf4e6",
    ]
    colours = [
        "#4E79A7",
        "#E15759",
        "#EDC948",
        "#FF9DA7",
        "#F28E2B",
        "#76B7B2",
        "#B07AA1",
    ]

    def __init__(self, notebook_file):
        self.notebook_file = notebook_file
        # cells are already cleaned / analyzed by Notebook_File
        self.cells = notebook_file.get_cells()
        self.function_uses = notebook_file.get_function_uses()
        self.nodes = []
        self.edges = []

    def initialise(self):
        self.add_nodes()
        self.add_data_edges()

    # cell graph
    def add_nodes(self):
        # one accepted code cell = one graph node
        for cell in self.cells:
            self.nodes.append(
                {
                    "id": cell.get_id(),
                    # e.g. code_index 0 -> A, 1 -> B
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
        # edges represent dataflow between cells
        # e.g.:
        # cell A: a = 1
        # cell B: b = a + 1
        # creates A -> B with label "a"
        last_def = {}
        labels = {}

        for c in self.cells:
            cell_id = c.get_id()

            # normal variable uses :
            for var in c.get_uses():

                # a function name alone doesn't create an edge
                # e.g. def f() is skipped, then f() doesn't link to its call
                if var in self.function_uses:
                    continue

                # the current cell uses the latest definition of var
                if var in last_def:
                    self.add_edge_label(labels, last_def[var], cell_id, var)

            # external variables used in a function body belong to its call
            for fun in c.get_calls():
                # cell A: a = 3
                # skipped cell: def f(x): return x > a
                # cell B: result = f(2)
                # creates A -> B with label "a"

                for var in self.function_uses.get(fun, []):
                    if var in last_def:
                        self.add_edge_label(labels, last_def[var], cell_id, var)

            # definitions are available after the cell has been read
            # e.g. if a is redefined here, later cells depend on *this* cell for a
            for var in c.get_defines():
                last_def[var] = cell_id

        # grouping several variables on the same edge
        for (src, tgt), edge_labels in labels.items():
            self.add_edge(src, tgt, ", ".join(edge_labels))

    def add_edge_label(self, labels, src, tgt, label):
        # group the labels before creating the final edge dicos
        # e.g. A -> B may have labels ["a", "b"], then final label "a, b"
        key = (src, tgt)
        if key not in labels:
            labels[key] = []
        if label not in labels[key]:
            labels[key].append(label)

    def add_edge(self, src, tgt, label):
        # final edge dico used for JSON / DOT outputs
        edge = {"A": src, "B": tgt, "label": label}
        if edge not in self.edges:
            self.edges.append(edge)

    # statement graph
    def get_expanded_dependency_graph_dico(self):
        # split every accepted cell into statement nodes
        # e.g. b = 1; f(b) becomes A.1 -> A.2 with label "b"
        nodes = []
        subflows = {}
        groups = []

        for c in self.cells:
            p = self.get_cell_statement_parser(c)
            stmts = p.get_statements()
            groups.append(p.get_items())
            for stmt in stmts:
                node = stmt.get_dico()
                nodes.append(node)
            self.add_cell_subworkflow(subflows, c, stmts)

        edges = self.get_statement_edges(groups)
        nodes, subflows = self.remove_isolated_definitions(nodes, edges, subflows)
        return {"nodes": nodes, "edges": edges, "subworkflows": subflows}

    def remove_isolated_definitions(self, nodes, edges, subflows):
        # TODO : this doesnt really work??? i still get isolated edges sometimes (to see)
        linked_nodes = {
            node_id
            for edge in edges
            for node_id in (edge["A"], edge["B"])
        }
        kept_nodes = [
            node
            for node in nodes
            if (
                node["id"] in linked_nodes
                or len(node.get("defines", [])) == 0
                or len(node.get("calls", [])) != 0
            )
        ]
        kept_ids = {node["id"] for node in kept_nodes}
        kept_subflows = {}
        for subflow_id, subflow in subflows.items():
            subflow_nodes = [
                node_id for node_id in subflow["nodes"] if node_id in kept_ids
            ]
            if len(subflow_nodes) != 0:
                kept_subflows[subflow_id] = {
                    **subflow,
                    "nodes": subflow_nodes,
                }

        return kept_nodes, kept_subflows

    def add_cell_subworkflow(self, subflows, c, stmts):
        # each cell is one displayed box
        # e.g. cell_0 contains ["cell_0_stmt_0", "cell_0_stmt_1"]
        if len(stmts) == 0:
            return

        cell_id = c.get_id()
        cell_lbl = self.get_cell_label(c.get_code_index())
        subflows[cell_id] = {
            "nodes": [stmt.get_id() for stmt in stmts],
            "label": f"Cell {cell_lbl}",
            "color": self.subworkflow_colours[
                len(subflows) % len(self.subworkflow_colours)
            ],
        }

    # NEW FOR STATEMENTS
    def get_cell_statement_parser(self, c):
        # parse one cell into ordered statements / if structures
        p = Python_Statement_Parser(
            code=c.get_code(),
            cell_id=c.get_id(),
            cell_label=self.get_cell_label(c.get_code_index()),
        )
        p.analyse()
        return p

    def get_statement_edges(self, groups):
        # same idea as add_data_edges() BUT at statement level
        # e.g.:
        #   b = 1 -> last_defs["b"] = [{"node": "cell_0_stmt_0"}]
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

    def add_statement_item_edges(self, items, last_defs, labels, cond_order):
        # a group can contain normal statements or if branches
        env = self.copy_defs(last_defs)
        for item in items:
            if item["kind"] == "stmt":
                self.add_one_statement_edges(item["stmt"], env, labels, cond_order)
            elif item["kind"] == "if":
                env = self.add_if_statement_edges(item, env, labels, cond_order)
        return env

    def ensure_statement_items(self, group):
        # helper for callers giving only a flat list of statements
        if len(group) == 0:
            return []
        if isinstance(group[0], dict):
            return group
        return [{"kind": "stmt", "stmt": stmt} for stmt in group]

    def add_one_statement_edges(self, stmt, last_defs, labels, cond_order):
        stmt_id = stmt.get_id()
        stmt_cond = stmt.get_condition()

        # normal variable uses :
        for var in stmt.get_uses():

            # a function name alone doesn't create an edge
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

        # external variables used in a function body belong to its call
        # e.g. def f(x): return x + a; f(b) depends on a
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

        # definitions are available after the statement has been read
        for var in stmt.get_defines():
            last_defs[var] = [{"node": stmt_id, "condition": stmt_cond}]

    # if branches
    def add_if_statement_edges(self, item, last_defs, labels, cond_order):
        # parse both branches starting with the same definitions
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
        # definitions after an if can come from either branch
        # e.g. x = 0; if flag: x = 1; y = x also keeps x = 0 if not flag
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
        # add the branch condition to definitions kept from before the if
        return [
            {
                "node": d["node"],
                "condition": self.merge_condition(d["condition"], condition),
            }
            for d in defs
        ]

    def add_statement_edge_label(self, labels, cond_order, src, tgt, label, condition):
        # edges with different conditions stay separated
        key = (src, tgt, condition)
        if key not in labels:
            labels[key] = []
        if label not in labels[key]:
            labels[key].append(label)
        if condition != "" and condition not in cond_order:
            cond_order.append(condition)

    def merge_condition(self, c1, c2):
        if c1 == "":
            return c2
        if c2 == "":
            return c1
        if c1 == c2:
            return c1
        if c2.startswith(f"{c1} and "):
            return c2
        return f"{c1} and {c2}"

    def get_condition_colors(self, cond_order):
        # each condition gets one edge color, in discovery order
        colors = {}
        for idx, cond in enumerate(cond_order):
            colors[cond] = self.colours[
                idx % len(self.colours)
            ]
        return colors

    # helpers
    def is_ignored_name(self, name):
        # builtins / imported names aren't notebook data dependencies
        if hasattr(self.notebook_file, "is_ignored_name"):
            return self.notebook_file.is_ignored_name(name)
        return False

    # alphabetical order for temporary labels
    def get_cell_label(self, cell_index):
        label = ""
        cell_num = cell_index + 1
        while cell_num > 0:
            cell_num, r = divmod(cell_num - 1, 26)
            label = chr(ord("A") + r) + label
        return label

    # getters / outputs
    def get_dependency_graph_dico(self):
        return {"nodes": self.nodes, "edges": self.edges}

    def get_cell_statements(self, c):
        # parse one cell into ordered statements
        p = self.get_cell_statement_parser(c)
        return p.get_statements()

    def get_intra_cell_edges(self, stmts):
        # helper for one-cell checks
        return self.get_statement_edges([stmts])

    def get_expanded_graph_dico(self, positions):
        return NotebookGraphOutput(self).get_expanded_graph_dico(positions)

    def scale_position(self, pos):
        return NotebookGraphOutput(self).scale_position(pos)

    def get_graph_dico(self, positions):
        return NotebookGraphOutput(self).get_graph_dico(positions)

    def get_callable_definitions(self):
        # all functions / classes defined in accepted cells
        callable_defs = set()
        for cell in self.cells:
            for name in cell.get_callable_defines():
                callable_defs.add(name)
        return callable_defs

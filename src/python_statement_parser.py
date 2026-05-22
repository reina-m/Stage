import ast

from .notebook_statement import Notebook_Statement
from .python_ast_parser import Python_AST_Parser


class Python_Statement_Parser:
    # splits one Python notebook code cell into ordered top-level statements
    SUPPORTED_STMTS = (
        ast.Assign,
        ast.AnnAssign,
        ast.AugAssign,
        ast.Expr,
        ast.Import,
        ast.ImportFrom,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.For,
        ast.While,
    )

    IMPORT_STMTS = (ast.Import, ast.ImportFrom)
    SUBWORKFLOW_HUES = [58, 100, 241, 0, 177, 37, 281]
    SUBWORKFLOW_SATURATION = 90
    SUBWORKFLOW_LIGHTNESS_MIN = 85
    SUBWORKFLOW_LIGHTNESS_MAX = 99

    def __init__(self, code, cell_id, cell_label):
        self.code = code
        self.cell_id = cell_id
        self.cell_lbl = cell_label
        self.stmts = []
        self.items = []
        self.subflows = {}
        self.subflow_infos = {}
        self.stmt_idx = 0
        self.if_idx = 0
        self.for_idx = 0
        self.while_idx = 0
        self.sub_idx = 0
        self.max_depth = 0
        self.syntax_error = None

    def analyse(self):
        try:
            # ast.parse could return SyntaxError
            tree = ast.parse(self.code)
        except SyntaxError as error:
            self.syntax_error = error
            return

        self.items = self.parse_nodes(tree.body, self.cell_id, "", 0)
        self.add_subflow_colors()

    def parse_nodes(self, nodes, parent_subflow, condition, depth):
        items = []
        for node in nodes:
            if isinstance(node, ast.If):
                items.append(self.parse_if(node, parent_subflow, condition, depth + 1))
                continue
            if isinstance(node, ast.For):
                items.append(self.parse_for(node, parent_subflow, condition, depth + 1))
                continue
            if isinstance(node, ast.While):
                items.append(self.parse_while(node, parent_subflow, condition, depth + 1))
                continue

            # only the first implementation's top level statement types
            if not isinstance(node, self.SUPPORTED_STMTS):
                continue

            # import only statements do not become expanded graph nodes
            if isinstance(node, self.IMPORT_STMTS):
                continue

            stmt = self.get_statement(node, condition, parent_subflow)
            if stmt is not None:
                items.append({"kind": "stmt", "stmt": stmt})

        return items

    def parse_if(self, node, parent_subflow, condition, depth):
        sub_id = f"{self.cell_id}_if_{self.if_idx}"
        color_idx = self.sub_idx
        self.if_idx += 1
        self.sub_idx += 1
        self.max_depth = max(self.max_depth, depth)

        then_cond = ast.unparse(node.test)
        else_cond = f"not ({then_cond})"

        body = self.parse_nodes(
            node.body,
            sub_id,
            self.merge_condition(condition, then_cond),
            depth,
        )
        other = self.parse_nodes(
            node.orelse,
            sub_id,
            self.merge_condition(condition, else_cond),
            depth,
        )

        stmt_ids = self.get_item_statement_ids(body + other)
        if len(stmt_ids) > 0:
            self.subflow_infos[sub_id] = {
                "nodes": stmt_ids,
                "label": f"if {then_cond}",
                "depth": depth,
                "color_index": color_idx,
                "parent": parent_subflow,
            }

        return {
            "kind": "if",
            "id": sub_id,
            "body": body,
            "orelse": other,
            "then_condition": self.merge_condition(condition, then_cond),
            "else_condition": self.merge_condition(condition, else_cond),
        }

    def parse_for(self, node, parent_subflow, condition, depth):
        sub_id = f"{self.cell_id}_for_{self.for_idx}"
        color_idx = self.sub_idx
        self.for_idx += 1
        self.sub_idx += 1
        self.max_depth = max(self.max_depth, depth)

        target = ast.unparse(node.target)
        iterable = ast.unparse(node.iter)
        header = self.get_loop_statement(
            code=f"for {target} in {iterable}",
            defines=self.get_target_names(node.target),
            expr=node.iter,
            condition=condition,
            parent_subflow=sub_id,
        )
        body = self.parse_nodes(node.body, sub_id, condition, depth)
        items = [{"kind": "stmt", "stmt": header}] + body

        self.add_block_subflow(
            sub_id,
            items,
            f"for {target} in {iterable}",
            depth,
            color_idx,
            parent_subflow,
        )
        return {"kind": "loop", "id": sub_id, "items": items}

    def parse_while(self, node, parent_subflow, condition, depth):
        sub_id = f"{self.cell_id}_while_{self.while_idx}"
        color_idx = self.sub_idx
        self.while_idx += 1
        self.sub_idx += 1
        self.max_depth = max(self.max_depth, depth)

        test = ast.unparse(node.test)
        header = self.get_loop_statement(
            code=f"while {test}",
            defines=[],
            expr=node.test,
            condition=condition,
            parent_subflow=sub_id,
        )
        body = self.parse_nodes(node.body, sub_id, condition, depth)
        items = [{"kind": "stmt", "stmt": header}] + body

        self.add_block_subflow(
            sub_id,
            items,
            f"while {test}",
            depth,
            color_idx,
            parent_subflow,
        )
        return {"kind": "loop", "id": sub_id, "items": items}

    def add_block_subflow(self, sub_id, items, label, depth, color_idx, parent):
        stmt_ids = self.get_item_statement_ids(items)
        if len(stmt_ids) == 0:
            return

        self.subflow_infos[sub_id] = {
            "nodes": stmt_ids,
            "label": label,
            "depth": depth,
            "color_index": color_idx,
            "parent": parent,
        }

    def get_loop_statement(self, code, defines, expr, condition, parent_subflow):
        p = Python_AST_Parser(ast.unparse(expr))
        p.analyse()

        stmt = Notebook_Statement(
            cell_id=self.cell_id,
            statement_index=self.stmt_idx,
            cell_label=self.cell_lbl,
            code=code,
            defines=defines,
            uses=p.get_uses(),
            calls=p.get_calls(),
            condition=condition,
            parent_subworkflow=parent_subflow,
        )
        self.stmt_idx += 1
        self.stmts.append(stmt)
        return stmt

    def get_target_names(self, target):
        names = []
        self.add_target_names(target, names)
        return names

    def add_target_names(self, target, names):
        if isinstance(target, ast.Name):
            if target.id not in names:
                names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self.add_target_names(elt, names)

    def get_statement(self, node, condition, parent_subflow):
        stmt_code = self.get_statement_code(node)

        # reuse the cell parser on one statement to get defines/uses/calls
        p = Python_AST_Parser(stmt_code)
        p.analyse()
        if p.get_syntax_error() is not None:
            return None

        stmt = Notebook_Statement(
            cell_id=self.cell_id,
            statement_index=self.stmt_idx,
            cell_label=self.cell_lbl,
            code=stmt_code,
            defines=p.get_defines(),
            uses=p.get_uses(),
            calls=p.get_calls(),
            condition=condition,
            parent_subworkflow=parent_subflow,
        )
        self.stmt_idx += 1
        self.stmts.append(stmt)
        return stmt

    def get_item_statement_ids(self, items):
        stmt_ids = []
        for item in items:
            if item["kind"] == "stmt":
                stmt_ids.append(item["stmt"].get_id())
            elif item["kind"] == "if":
                stmt_ids.extend(self.get_item_statement_ids(item["body"]))
                stmt_ids.extend(self.get_item_statement_ids(item["orelse"]))
            elif item["kind"] == "loop":
                stmt_ids.extend(self.get_item_statement_ids(item["items"]))
        return stmt_ids

    def add_subflow_colors(self):
        self.subflows = {}
        for sub_id, sub in self.subflow_infos.items():
            self.subflows[sub_id] = {
                "nodes": sub["nodes"],
                "label": sub["label"],
                "color": self.get_subflow_color(sub["color_index"], sub["depth"]),
                "parent": sub["parent"],
            }

    def get_statement_code(self, node):
        # keeps the exact notebook source for this statement when possible
        src = ast.get_source_segment(self.code, node)
        if src is not None:
            return src.strip()

        # in case Python cannot recover the original segment
        return ast.unparse(node).strip()

    def merge_condition(self, base, extra):
        if base == "":
            return extra
        if extra == "":
            return base
        if base == extra:
            return base
        return f"{base} and {extra}"

    def get_subflow_color(self, color_idx, depth):
        l_min = self.SUBWORKFLOW_LIGHTNESS_MIN
        l_max = self.SUBWORKFLOW_LIGHTNESS_MAX
        if self.max_depth == 0:
            lightness = l_min
        else:
            norm = l_max - l_min
            lightness = l_max - (depth / self.max_depth) ** 3 * norm
            lightness = max(lightness, 99 - depth * 4)

        rgb = self.hsl_to_rgb(
            h=self.SUBWORKFLOW_HUES[color_idx % len(self.SUBWORKFLOW_HUES)],
            s=self.SUBWORKFLOW_SATURATION,
            l=lightness,
        )
        return "#%02x%02x%02x" % rgb

    def hsl_to_rgb(self, h, s, l):
        h, s, l = h / 360, s / 100, l / 100
        r, g, b = self.hue_to_rgb(h)
        c = (1.0 - abs(2.0 * l - 1.0)) * s
        r = (r - 0.5) * c + l
        g = (g - 0.5) * c + l
        b = (b - 0.5) * c + l
        return int(r * 255), int(g * 255), int(b * 255)

    def hue_to_rgb(self, h):
        r = abs(h * 6.0 - 3.0) - 1.0
        g = 2.0 - abs(h * 6.0 - 2.0)
        b = 2.0 - abs(h * 6.0 - 4.0)
        return self.saturate(r), self.saturate(g), self.saturate(b)

    def saturate(self, value):
        return max(0.0, min(1.0, value))

    # GETTERS
    def get_statements(self):
        return list(self.stmts)

    def get_items(self):
        return list(self.items)

    def get_subworkflows(self):
        return dict(self.subflows)

    def get_statement_dicos(self):
        return [stmt.get_dico() for stmt in self.stmts]

    def get_syntax_error(self):
        return self.syntax_error

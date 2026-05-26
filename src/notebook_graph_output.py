CELL_SUBWORKFLOW_COLOR = "#fefefa"
POSITION_SCALE = 1.6
SUBWORKFLOW_HUES = [58, 100, 241, 0, 177, 37, 281]
SUBWORKFLOW_SATURATION = 90
SUBWORKFLOW_LIGHTNESS_MIN = 85
SUBWORKFLOW_LIGHTNESS_MAX = 99


def style_subworkflows(subflows, max_depth):
    return {
        sub_id: {
            "nodes": subflow["nodes"],
            "label": subflow["label"],
            "color": get_subworkflow_color(
                subflow["color_index"],
                subflow["depth"],
                max_depth,
            ),
            "parent": subflow["parent"],
        }
        for sub_id, subflow in subflows.items()
    }


def get_subworkflow_color(color_index, depth, max_depth):
    if max_depth == 0:
        lightness = SUBWORKFLOW_LIGHTNESS_MIN
    else:
        spread = SUBWORKFLOW_LIGHTNESS_MAX - SUBWORKFLOW_LIGHTNESS_MIN
        lightness = SUBWORKFLOW_LIGHTNESS_MAX - (depth / max_depth) ** 3 * spread
        lightness = max(lightness, 99 - depth * 4)

    rgb = hsl_to_rgb(
        h=SUBWORKFLOW_HUES[color_index % len(SUBWORKFLOW_HUES)],
        s=SUBWORKFLOW_SATURATION,
        l=lightness,
    )
    return "#%02x%02x%02x" % rgb


def hsl_to_rgb(h, s, l):
    h, s, l = h / 360, s / 100, l / 100
    r, g, b = hue_to_rgb(h)
    chroma = (1.0 - abs(2.0 * l - 1.0)) * s
    r = (r - 0.5) * chroma + l
    g = (g - 0.5) * chroma + l
    b = (b - 0.5) * chroma + l
    return int(r * 255), int(g * 255), int(b * 255)


def hue_to_rgb(h):
    r = abs(h * 6.0 - 3.0) - 1.0
    g = 2.0 - abs(h * 6.0 - 2.0)
    b = 2.0 - abs(h * 6.0 - 4.0)
    return saturate(r), saturate(g), saturate(b)


def saturate(value):
    return max(0.0, min(1.0, value))


class NotebookGraphOutput:
    def __init__(self, graph):
        self.graph = graph

    def get_expanded_graph_dico(self, positions):
        dico = self.graph.get_expanded_dependency_graph_dico()
        sub_paths = self.get_subworkflow_paths(dico["subworkflows"])
        node_ids = self.get_expanded_node_ids(dico["nodes"], sub_paths)
        self._require_positions(dico["nodes"], positions)

        nodes = []
        for node in dico["nodes"]:
            nodes.append(
                {
                    "id": node_ids[node["id"]],
                    "name": node["name"],
                    "position": self.scale_position(positions[node["id"]]),
                    "code": node["code"],
                }
            )

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

    def get_graph_dico(self, positions):
        self._require_positions(self.graph.nodes, positions)

        nodes = []
        for node in self.graph.nodes:
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
        for edge in self.graph.edges:
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

    def _require_positions(self, nodes, positions):
        if not positions:
            raise ValueError("Graphviz positions are required to build graph JSON.")

        missing_positions = [
            node["id"] for node in nodes if node["id"] not in positions
        ]
        if missing_positions:
            raise ValueError(
                f"Missing Graphviz positions for nodes: {', '.join(missing_positions)}"
            )

    def get_subworkflow_paths(self, subflows):
        paths = {}

        def add_path(sub_id):
            if sub_id in paths:
                return paths[sub_id]

            subflow = subflows[sub_id]
            parent = subflow.get("parent", "")
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
            subflow = subflows[sub_id]
            final[sub_paths[sub_id]] = {
                "nodes": [node_ids[node] for node in subflow["nodes"]],
                "label": subflow["label"],
                "color": subflow["color"],
            }
        return final

    def scale_position(self, position):
        # same idea as BioFlow metro maps: add space between visual nodes
        return {
            "x": str(float(position["x"]) * self.graph.POSITION_SCALE),
            "y": str(float(position["y"]) * self.graph.POSITION_SCALE),
        }

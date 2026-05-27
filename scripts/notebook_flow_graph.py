# file made to generate dot files from graph dictionnaries (see src/notebook_graph.py)
import graphviz
import re

NODE_RE = re.compile(r'^\s*"?(?P<id>[^"\s\[]+)"?\s+\[(?P<attrs>.*?)\];', re.MULTILINE | re.DOTALL)
POS_RE = re.compile(r'pos="(?P<x>[^,"]+),(?P<y>[^"]+)"')

# to get positions computed by graphiz
def get_graphviz_positions(dot_source):
    positions = {}
    for node_match in NODE_RE.finditer(dot_source):
        pos_match = POS_RE.search(node_match.group("attrs"))
        if pos_match:
            positions[node_match.group("id")] = {
                "x": pos_match.group("x"),
                "y": pos_match.group("y"),
            }
    return positions


def build_dot(dico, include_subworkflows=False):
    dot = graphviz.Digraph(name="Notebook")
    dot.attr(rankdir="LR")
    dot.attr(
        "node",
        shape="circle",
        style="filled",
        fillcolor="#eeeeee"
    )
    dot.attr("edge")

    if include_subworkflows:
        add_subworkflow_nodes(dot, dico)
    else:
        add_nodes(dot, dico["nodes"])

    add_edges(dot, dico["edges"])

    return dot.source


def build_expanded_dot(dico, include_subworkflows=True):
    # helper for expanded notebook graphs
    # e.g. one cell subworkflow becomes a Graphviz cluster box
    return build_dot(dico, include_subworkflows=include_subworkflows)


def add_nodes(dot, nodes):
    for node in nodes:
        add_node(dot, node)


def add_node(dot, node):
    dot.node(
        node["id"],
        node["name"],
        shape=node.get("shape", "circle"),
        fillcolor=node.get("fillcolor", "#eeeeee"),
    )


def add_subworkflow_nodes(dot, dico):
    grouped = set()
    subs = dico.get("subworkflows", {})
    children = {}

    for sub_id, sub in subs.items():
        parent = get_sub_parent(sub_id, sub, subs)
        if parent in subs:
            if parent not in children:
                children[parent] = []
            children[parent].append(sub_id)

    def add_sub(dot_obj, sub_id):
        sub = subs[sub_id]
        child_ids = children.get(sub_id, [])
        child_nodes = set()
        for child_id in child_ids:
            child_nodes.update(subs[child_id].get("nodes", []))

        # Graphviz clusters draw the visual box around statement nodes.
        with dot_obj.subgraph(name=get_cluster_name(sub_id)) as c:
            c.attr(
                label=sub.get("label", sub_id),
                color="black",
            )
            for node in dico["nodes"]:
                if node["id"] in sub.get("nodes", []) and node["id"] not in child_nodes:
                    add_node(c, node)
                    grouped.add(node["id"])

            for child_id in child_ids:
                add_sub(c, child_id)

    for sub_id, sub in subs.items():
        parent = get_sub_parent(sub_id, sub, subs)
        if parent not in subs:
            add_sub(dot, sub_id)

    # nodes outside a subworkflow still have to be rendered normally.
    for node in dico["nodes"]:
        if node["id"] not in grouped:
            add_node(dot, node)


def get_sub_parent(sub_id, sub, subs):
    if "parent" in sub:
        return sub["parent"]

    parts = sub_id.split(".")
    for i in range(len(parts) - 1, 0, -1):
        parent = ".".join(parts[:i])
        if parent in subs:
            return parent
    return ""


def get_cluster_name(sub_id):
    # Graphviz cluster ids cannot safely use dots from final metro-map ids.
    return "cluster_" + re.sub(r"[^A-Za-z0-9_]", "_", sub_id)


def add_edges(dot, edges):
    for edge in edges:
        # edge endpoints already exist as normal nodes or cluster nodes
        label = edge.get("label", "")
        condition = edge.get("condition", "")
        if condition:
            condition_label = f"if {condition}"
            label = f"{label}\n{condition_label}" if label else condition_label
        dot.edge(edge["A"], edge["B"], label=label)

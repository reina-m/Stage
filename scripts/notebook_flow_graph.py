# file made to generate dot files from graph dictionnaries (see src/notebook_graph.py)
import graphviz
import re

NODE_RE = re.compile(r'^\s*"?(?P<id>[^"\s\[]+)"?\s+\[(?P<attrs>.*?)\];', re.MULTILINE | re.DOTALL)
POS_RE = re.compile(r'pos="(?P<x>[^,"]+),(?P<y>[^"]+)"')


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


def build_dot(dico):
    dot = graphviz.Digraph(name="Notebook")
    dot.attr(rankdir="LR")
    dot.attr(
        "node",
        shape="circle",
        style="filled",
        fillcolor="#eeeeee"
    )
    dot.attr("edge")

    for node in dico["nodes"]:
        dot.node(
            node["id"],
            node["name"],
            shape=node.get("shape", "circle"),
            fillcolor=node.get("fillcolor", "#eeeeee"),
        )

    for edge in dico["edges"]:
        dot.edge(edge["A"], edge["B"], label=edge.get("label", ""))

    return dot.source

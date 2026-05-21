# file made to generate dot files from graph dictionnaries (see src/notebook_graph.py)
import graphviz

def build_dot(dico):
    dot = graphviz.Digraph(name="Notebook")
    dot.attr(rankdir="TB")
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

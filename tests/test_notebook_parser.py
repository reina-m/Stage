import unittest

from src.notebook_file import Notebook_File
from src.notebook_graph import Notebook_Graph


class TestNotebookParser(unittest.TestCase):
    def get_notebook_graph(self, notebook_address):
        notebook_file = Notebook_File(notebook_address)
        notebook_graph = Notebook_Graph(notebook_file)
        notebook_graph.initialise()
        return notebook_graph

    def get_edge_keys(self, graph_dico):
        return {(edge["A"], edge["B"], edge["label"]) for edge in graph_dico["edges"]}

    def test_json_output_matches_metro_map_schema(self):
        notebook_graph = self.get_notebook_graph("tests/example.ipynb")
        graph_dico = notebook_graph.get_graph_dico()

        self.assertEqual(list(graph_dico.keys()), ["nodes", "edges", "subworkflows"])
        self.assertEqual(
            [list(node.keys()) for node in graph_dico["nodes"]],
            [["id", "name", "position", "code"]] * len(graph_dico["nodes"]),
        )
        self.assertEqual(
            [list(node["position"].keys()) for node in graph_dico["nodes"]],
            [["x", "y"]] * len(graph_dico["nodes"]),
        )
        self.assertEqual(
            [list(edge.keys()) for edge in graph_dico["edges"]],
            [["A", "B", "color", "condition", "id"]] * len(graph_dico["edges"]),
        )
        self.assertEqual(graph_dico["subworkflows"], {})

    def test_notebook1_dependency_graph(self):
        notebook_graph = self.get_notebook_graph("tests/notebook1.ipynb")
        graph_dico = notebook_graph.get_dependency_graph_dico()

        self.assertEqual([node["name"] for node in graph_dico["nodes"]], ["A", "B", "C", "D"])
        self.assertEqual(
            self.get_edge_keys(graph_dico),
            {
                ("cell_0", "cell_1", "a, b"),
                ("cell_0", "cell_3", "c"),
                ("cell_1", "cell_3", "d"),
                ("cell_2", "cell_3", "f"),
            },
        )

    def test_notebook2_dependency_graph(self):
        notebook_graph = self.get_notebook_graph("tests/notebook2.ipynb")
        graph_dico = notebook_graph.get_dependency_graph_dico()

        self.assertEqual([node["name"] for node in graph_dico["nodes"]], ["B", "C", "D", "E"])
        self.assertEqual(
            self.get_edge_keys(graph_dico),
            {
                ("cell_0", "cell_1", "a"),
                ("cell_1", "cell_3", "b"),
                ("cell_2", "cell_3", "c"),
            },
        )

    def test_notebook4_import_only_cell_is_not_relabelled(self):
        notebook_graph = self.get_notebook_graph("tests/notebook4.ipynb")
        graph_dico = notebook_graph.get_dependency_graph_dico()

        self.assertEqual([node["name"] for node in graph_dico["nodes"]], ["B", "C", "D"])
        self.assertEqual(
            self.get_edge_keys(graph_dico),
            {
                ("cell_0", "cell_2", "a"),
                ("cell_1", "cell_2", "b"),
            },
        )

    def test_notebook5_labels_without_cell_comments(self):
        notebook_graph = self.get_notebook_graph("tests/notebook5.ipynb")
        graph_dico = notebook_graph.get_dependency_graph_dico()

        self.assertEqual([node["name"] for node in graph_dico["nodes"]], ["A", "C"])
        self.assertEqual(
            self.get_edge_keys(graph_dico),
            {
                ("cell_0", "cell_1", "a, b, c"),
            },
        )

    def test_function_body_uses_are_propagated_to_call_cell(self):
        notebook_graph = self.get_notebook_graph("tests/notebook6.ipynb")
        graph_dico = notebook_graph.get_dependency_graph_dico()

        self.assertEqual([node["name"] for node in graph_dico["nodes"]], ["A", "C"])
        self.assertEqual(
            self.get_edge_keys(graph_dico),
            {
                ("cell_0", "cell_1", "a"),
            },
        )


if __name__ == "__main__":
    unittest.main()

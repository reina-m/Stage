import unittest

from src.notebook_cell import Notebook_Cell
from src.notebook_graph import Notebook_Graph


class SmallNotebook:
    def __init__(self, codes):
        self.cells = []
        self.function_uses = {}

        for index, code in enumerate(codes):
            cell = Notebook_Cell(
                id=f"cell_{index}",
                idx=index,
                code_idx=index,
                code=code.strip(),
            )
            cell.analyse()
            self.cells.append(cell)
            self.function_uses.update(cell.get_function_uses())

    def get_cells(self):
        return self.cells

    def get_function_uses(self):
        return self.function_uses

    def is_ignored_name(self, name):
        return False


def graph_from(codes):
    graph = Notebook_Graph(SmallNotebook(codes))
    graph.initialise()
    return graph


class NotebookGraphRulesTest(unittest.TestCase):
    def test_one_accepted_code_cell_becomes_one_node(self):
        graph = graph_from([
            "a = 1",
            "b = a",
        ])

        self.assertEqual([node["id"] for node in graph.nodes], ["cell_0", "cell_1"])
        self.assertEqual([node["name"] for node in graph.nodes], ["A", "B"])

    def test_edge_means_later_cell_uses_data_defined_earlier(self):
        graph = graph_from([
            "a = 1",
            "b = a",
        ])

        self.assertEqual(
            graph.edges,
            [{"A": "cell_0", "B": "cell_1", "label": "a"}],
        )

    def test_function_call_name_alone_does_not_create_an_edge(self):
        graph = graph_from([
            "def make_value(x):\n    return x + 1",
            "result = make_value(2)",
        ])

        self.assertEqual(graph.edges, [])

    def test_called_function_external_variable_links_to_call_cell(self):
        graph = graph_from([
            "scale = 10",
            "def make_value(x):\n    return x + scale",
            "result = make_value(2)",
        ])

        self.assertEqual(
            graph.edges,
            [{"A": "cell_0", "B": "cell_2", "label": "scale"}],
        )


if __name__ == "__main__":
    unittest.main()

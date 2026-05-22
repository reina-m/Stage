class Notebook_Statement:
    # stores one executable statement extracted from a notebook code cell
    def __init__(
        self,
        cell_id,
        statement_index,
        cell_label,
        code,
        defines=None,
        uses=None,
        calls=None,
        condition="",
        parent_subworkflow=None,
    ):
        self.id = f"{cell_id}_stmt_{statement_index}"
        self.cell_id = cell_id
        self.name = f"{cell_label}.{statement_index + 1}"
        self.kind = "statement"
        self.code = code
        self.defines = list(defines or [])
        self.uses = list(uses or [])
        self.calls = list(calls or [])
        self.condition = condition
        self.parent_subworkflow = parent_subworkflow or cell_id

    def get_id(self):
        return self.id

    def get_cell_id(self):
        return self.cell_id

    def get_name(self):
        return self.name

    def get_kind(self):
        return self.kind

    def get_code(self):
        return self.code

    def get_defines(self):
        return list(self.defines)

    def get_uses(self):
        return list(self.uses)

    def get_calls(self):
        return list(self.calls)

    def get_condition(self):
        return self.condition

    def get_parent_subworkflow(self):
        return self.parent_subworkflow

    def get_dico(self):
        return {
            "id": self.id,
            "cell_id": self.cell_id,
            "name": self.name,
            "kind": self.kind,
            "code": self.code,
            "defines": self.get_defines(),
            "uses": self.get_uses(),
            "calls": self.get_calls(),
            "condition": self.condition,
            "parent_subworkflow": self.parent_subworkflow,
        }

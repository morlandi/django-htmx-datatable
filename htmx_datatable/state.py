"""
The state of a table: what the user asked for (D5), already parsed from the
GET parameters (#4).
"""


class TableState:
    """
    search: the global search value ("" for none)
    ordering: (column name, descending) pairs, in priority order
    filters: column name -> raw filter value, as typed or selected
    """

    def __init__(self, search="", ordering=None, filters=None):
        self.search = search
        self.ordering = list(ordering) if ordering is not None else []
        self.filters = dict(filters) if filters is not None else {}

    def __repr__(self):
        return f"<TableState search={self.search!r} ordering={self.ordering!r} filters={self.filters!r}>"

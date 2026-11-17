"""
The state of a table: what the user asked for (D5), already parsed from the
GET parameters (see protocol.py).
"""


class TableState:
    """
    search: the global search value ("" for none)
    ordering: (column name, descending) pairs, in priority order; empty for
        the view's default ordering
    filters: column name -> raw filter value, as typed or selected
    page: the page number, from 1
    page_size: rows per page; None for the view's default
    """

    def __init__(self, search="", ordering=None, filters=None, page=1, page_size=None):
        self.search = search
        self.ordering = list(ordering) if ordering is not None else []
        self.filters = dict(filters) if filters is not None else {}
        self.page = page
        self.page_size = page_size

    def __repr__(self):
        return (
            f"<TableState search={self.search!r} ordering={self.ordering!r} "
            f"filters={self.filters!r} page={self.page} page_size={self.page_size}>"
        )

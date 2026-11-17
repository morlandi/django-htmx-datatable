"""
What the templates render (R3, D8): header cells with their sort button and
filter widget, rows of cells, and the table around them. Plain attributes
only, so the templates can be overridden without knowing the view.
"""
from django.utils.safestring import SafeData

from .columns import DateColumn, NumberColumn


class HeaderCell:
    """
    A visible column, in the header row and in the filter row.

    sort: "ascending", "descending" or None; sort_value: the ordering after a
    click on its sort button (E). widget: "text", "select", "date", "number",
    or None when the column has no filter; filter_name / filter_value: the
    filter parameter and its current value; choices: the (value, label) pairs
    of a select, set only when the filter row is rendered (R2).
    """

    def __init__(self, column, *, sort, widget, filter_name, filter_value):
        self.column = column
        self.sort = sort
        self.sort_value = f"-{column.name}" if sort == "ascending" else column.name
        self.widget = widget
        self.filter_name = filter_name
        self.filter_value = filter_value
        self.choices = None

    @property
    def aria_sort(self):
        return self.sort or "none"


class Cell:
    """
    One cell. `content` is plain text (escaped by the template) or safe HTML
    from a render hook. Plain text longer than the column's max_length is
    clipped, and `title` keeps the full text; HTML is never clipped (R3).
    """

    def __init__(self, column, value, content):
        self.column = column
        self.value = value
        self.title = ""
        if column.max_length and not isinstance(content, SafeData) and len(content) > column.max_length:
            self.title = content
            content = content[: column.max_length - 1] + "…"
        self.content = content


class Row:
    def __init__(self, obj, cells):
        self.obj = obj
        self.pk = obj.pk
        self.cells = cells


class Table:
    """Everything the templates need (D8)."""

    def __init__(self, *, id, url, names, state, header, rows, page, total_count, errors,
                 page_sizes, search_delay):
        self.id = id                          # base of the element ids
        self.url = url                        # where the form sends its requests
        self.names = names                    # "q", "o", "page", "page_size" -> parameter name
        self.state = state
        self.header = header                  # HeaderCell, one per visible column
        self.rows = rows
        self.page = page                      # django.core.paginator.Page
        self.total_count = total_count        # unfiltered count; None when nothing is filtered (H)
        self.errors = errors                  # (column, message) pairs (I)
        self.page_sizes = page_sizes
        self.search_delay = search_delay      # ms (J)
        self.ordering_value = ",".join(
            ("-" if descending else "") + name for name, descending in state.ordering
        )
        self.page_range = list(page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1))
        self.ellipsis = page.paginator.ELLIPSIS

    @property
    def has_filters(self):
        return any(cell.widget for cell in self.header)


def effective_ordering(columns, requested, default):
    """
    The (name, descending) pair the header shows as sorted: the first
    orderable one among the requested, else among the view's default; None
    when the model's ordering applies.
    """
    orderable = {c.name for c in columns if c.orderable}
    for pairs in (requested, default):
        for name, descending in pairs:
            if name in orderable:
                return (name, descending)
    return None


def filter_widget(view, column):
    """The widget of a column filter (K), or None when it has no filter."""
    if not (column.searchable or hasattr(view, f"filter_{column.name}")):
        return None
    if column.autofilter or column.static_choices() is not None:
        return "select"
    if isinstance(column, DateColumn):
        return "date"
    if isinstance(column, NumberColumn):
        return "number"
    return "text"


def make_header(view, columns, state, names, ordering):
    """HeaderCells for the visible columns; `ordering` from effective_ordering()."""
    cells = []
    for column in columns:
        if not column.visible:
            continue
        sort = None
        if ordering and ordering[0] == column.name:
            sort = "descending" if ordering[1] else "ascending"
        cells.append(HeaderCell(
            column,
            sort=sort,
            widget=filter_widget(view, column),
            filter_name=names.filter(column.name),
            filter_value=state.filters.get(column.name, ""),
        ))
    return cells


def make_rows(view, columns, objects):
    """Rows of cells for the visible columns; render_<name>() hooks first (R3)."""
    visible = [c for c in columns if c.visible]
    hooks = {c.name: getattr(view, f"render_{c.name}", None) for c in visible}
    rows = []
    for obj in objects:
        cells = []
        for column in visible:
            value = column_value(column, obj)
            hook = hooks[column.name]
            content = hook(obj, value) if hook else column.format(value)
            if not isinstance(content, SafeData):
                content = "" if content is None else str(content)
            cells.append(Cell(column, value, content))
        rows.append(Row(obj, cells))
    return rows


def column_value(column, obj):
    """The raw value of a column for `obj`: from its path, its annotation, or None (computed)."""
    if column.path is not None:
        return column.path.value_from(obj)
    if column.annotation:
        return getattr(obj, column.name, None)
    return None

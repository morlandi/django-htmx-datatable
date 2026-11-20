"""
The GET protocol (D5): from the query string to a TableState, and from a
TableState back to the canonical URL.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .state import TableState

RESERVED = ("q", "o", "page", "page_size")
FILTER_PREFIX = "f_"
# The hidden input that tells the endpoint the prefix of the table that sent
# the request (#7); never part of the canonical URL
PREFIX_PARAM = "_dt"


class ParamNames:
    """The GET parameter names of one table, with its optional prefix (D5)."""

    def __init__(self, prefix=""):
        if prefix and not (prefix.isascii() and prefix.isalnum()):
            # "-" and "_" would let the names of two tables overlap: "a-b-q"
            # looks like a parameter of table "a", "f_x-q" like a filter of
            # the table without prefix (#7)
            raise ValueError(f"invalid table prefix {prefix!r}: use ASCII letters and digits only")
        self.prefix = prefix

    def name(self, name):
        """"q" -> "q", or "orders-q" with prefix "orders"."""
        return f"{self.prefix}-{name}" if self.prefix else name

    def filter(self, column_name):
        """The parameter of a column filter: "f_genre" or "orders-f_genre"."""
        return self.name(FILTER_PREFIX + column_name)

    def owns(self, key):
        """True if `key` is a parameter of this table."""
        if self.prefix:
            return key.startswith(f"{self.prefix}-")
        return key in RESERVED or key.startswith(FILTER_PREFIX)


def parse_state(query, names, column_names, page_sizes):
    """
    A TableState from a QueryDict. Invalid values fall back to the defaults;
    filters of unknown columns are dropped. When a parameter is repeated the
    last value wins: a clicked sort button comes after the hidden ordering
    input (D4).
    """
    ordering = []
    for entry in query.get(names.name("o"), "").split(","):
        entry = entry.strip()
        # not removeprefix(): Python 3.8 (README)
        name = entry[1:] if entry.startswith("-") else entry
        if name:
            ordering.append((name, entry.startswith("-")))
    filters = {
        name: query[names.filter(name)]
        for name in column_names
        if query.get(names.filter(name), "").strip()
    }
    page = _positive_int(query.get(names.name("page")), 1)
    page_size = _positive_int(query.get(names.name("page_size")), None)
    if page_size not in page_sizes:
        page_size = page_sizes[0]
    return TableState(
        search=query.get(names.name("q"), "").strip(),
        ordering=ordering,
        filters=filters,
        page=page,
        page_size=page_size,
    )


def canonical_params(state, names, page_sizes):
    """The parameters of `state`, without empty and default values (D5)."""
    params = []
    if state.search:
        params.append((names.name("q"), state.search))
    if state.ordering:
        o = ",".join(("-" if descending else "") + name for name, descending in state.ordering)
        params.append((names.name("o"), o))
    if state.page != 1:
        params.append((names.name("page"), str(state.page)))
    if state.page_size != page_sizes[0]:
        params.append((names.name("page_size"), str(state.page_size)))
    for name, value in state.filters.items():
        if value:
            params.append((names.filter(name), value))
    return params


def canonical_url(current_url, params, names):
    """
    `current_url` (path and query, or absolute) with this table's parameters
    replaced by `params`; the parameters of other tables and of the page are
    kept (D5), the prefix input is dropped (#7). Returns a path with its
    query string.
    """
    parts = urlsplit(current_url)
    # kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not names.owns(k)]
    kept = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not names.owns(k) and k != PREFIX_PARAM
    ]
    return urlunsplit(("", "", parts.path, urlencode(kept + params), ""))


def _positive_int(text, default):
    try:
        value = int(text)
    except (TypeError, ValueError):
        return default
    return value if value >= 1 else default

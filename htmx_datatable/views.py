"""
The table view: column declarations and their validation (#2), the query
engine (#3), the HTTP side and the templates (#4).
"""
import logging

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.paginator import Paginator
from django.db.models import F
from django.db.models.constants import LOOKUP_SEP
from django.http import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.utils.cache import patch_vary_headers
from django.views.generic import View
# from django.views.generic.base import ContextMixin, TemplateResponseMixin

from .columns import ComputedColumn, words_q
from .paths import accessor_name
# from .protocol import ParamNames, canonical_params, canonical_url, parse_state
from .protocol import PREFIX_PARAM, ParamNames, canonical_params, canonical_url, parse_state
from .table import Table, effective_ordering, make_header, make_rows

logger = logging.getLogger(__name__)

# Class attributes removed in 0.2, with the way to replace them (#7)
REMOVED_ATTRIBUTES = {
    "template_name": "embed the table in a page with {% htmx_datatable %} or embed()",
    "prefix": "pass prefix= to {% htmx_datatable %} or to embed()",
}


# class HtmxDatatableView(TemplateResponseMixin, ContextMixin, View):
class HtmxDatatableView(View):
    """
    A table: its definition (model, columns, queryset) and its htmx endpoint.
    Pages show it with {% htmx_datatable %} or embed() (#7).
    """
    model = None
    columns = []
    # Default ordering, in the syntax of the "o" parameter: ["-published"] (D5)
    ordering = None
    # OR separator in search and filter values, e.g. "+" (R5); None: disabled
    search_values_separator = None
    # # GET parameter prefix, to host several tables on one page (D5)
    # prefix = ""
    page_sizes = [10, 25, 50, 100]
    # Delay before the search or a text filter sends a request, in ms (J)
    search_delay = 300
    # # template_name: the consumer's page, which includes "htmx_datatable/table.html"
    # The whole table: the plain GET, and {% htmx_datatable %} without template= (#6)
    table_template_name = "htmx_datatable/table.html"
    fragment_template_name = "htmx_datatable/fragment.html"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for name, hint in REMOVED_ATTRIBUTES.items():
            if name in cls.__dict__:
                raise ImproperlyConfigured(f"{cls.__name__}.{name} was removed in 0.2: {hint}")
        # A base class without a model is abstract: nothing to check yet
        if cls.model is not None:
            cls._bound_columns = cls.bind_columns(cls.columns)
            cls._check_ordering()

    @classmethod
    def bind_columns(cls, columns):
        """
        Bind column declarations to the model and validate them (R2).

        Raises ImproperlyConfigured, naming the view and the column.
        """
        annotations = {c.name: c for c in columns if c.annotation}
        names = set()
        bound = []
        for column in columns:
            prefix = f"{cls.__name__}, column {column.name!r}"
            if column.name in names:
                raise ImproperlyConfigured(f"{prefix}: duplicate name")
            names.add(column.name)
            if isinstance(column, ComputedColumn) and not callable(
                getattr(cls, f"render_{column.name}", None)
            ):
                raise ImproperlyConfigured(
                    f"{prefix}: a computed column needs a render_{column.name}() method"
                )
            # The value chosen in the select would go nowhere (#8)
            if isinstance(column, ComputedColumn) and column.autofilter and not callable(
                getattr(cls, f"filter_{column.name}", None)
            ):
                raise ImproperlyConfigured(
                    f"{prefix}: autofilter on a computed column needs a filter_{column.name}() method"
                )
            try:
                bound.append(column.bind(cls.model, annotations))
            except ImproperlyConfigured as e:
                raise ImproperlyConfigured(f"{prefix}: {e}") from None
        return bound

    @classmethod
    def _check_ordering(cls):
        orderable = {c.name for c in cls._bound_columns if c.orderable}
        for entry in cls.ordering or ():
            # not removeprefix(): Python 3.8 (README)
            if (entry[1:] if entry.startswith("-") else entry) not in orderable:
                raise ImproperlyConfigured(
                    f"{cls.__name__}: ordering {entry!r} is not an orderable column"
                )

    def get_columns(self, request):
        """The column declarations for `request`; override to change them per request."""
        return self.columns

    def get_bound_columns(self, request):
        """The columns for `request`, bound to the model and validated."""
        columns = self.get_columns(request)
        # The class declarations were already bound and checked at class definition
        if columns is self.columns:
            return self._bound_columns
        return self.bind_columns(columns)

    # def get(self, request, *args, **kwargs):
    #     """The full page for a plain GET, the fragment for an htmx request (D3, D5)."""
    #     table = self.get_table(request)
    #     if self.is_htmx(request):
    #         response = self.response_class(
    #             request=request, template=[self.fragment_template_name], context={"table": table}
    #         )
    #         names = ParamNames(self.prefix)
    #         current_url = request.headers.get("HX-Current-URL") or request.get_full_path()
    #         params = canonical_params(table.state, names, self.page_sizes)
    #         response["HX-Replace-Url"] = canonical_url(current_url, params, names)
    #     else:
    #         # Choices are computed only when the filter row is rendered (R2)
    #         for cell in table.header:
    #             if cell.widget == "select":
    #                 cell.choices = self.get_column_choices(request, cell.column)
    #         response = self.render_to_response(self.get_context_data(table=table))
    #     patch_vary_headers(response, ["HX-Request"])
    #     return response

    @classmethod
    def embed(cls, request, *, url, prefix="", kwargs=None):
        """
        The complete Table for a page that shows this table (#7). Its state
        comes from the page's query string; its htmx requests go to `url`,
        the endpoint of this view, and `kwargs` are the URL kwargs of that
        endpoint (self.kwargs, e.g. in get_initial_queryset()).

        Raises ImproperlyConfigured for an invalid prefix, or for one already
        used by another table on the same page.
        """
        try:
            ParamNames(prefix)
        except ValueError as e:
            raise ImproperlyConfigured(f"{cls.__name__}: {e}") from None
        used = getattr(request, "_htmx_datatable_prefixes", set())
        if prefix in used:
            raise ImproperlyConfigured(
                f"{cls.__name__}: prefix {prefix!r} is already used by another table "
                "on this page; give each table its own prefix"
            )
        request._htmx_datatable_prefixes = used | {prefix}
        view = cls()
        view.setup(request, **(kwargs or {}))
        return view.get_table(request, url=url, prefix=prefix, full=True)

    def get(self, request, *args, **kwargs):
        """
        The endpoint (#7): the fragment for an htmx request (D3, D5), the
        table alone for a plain GET. The prefix comes from the _dt input.
        """
        prefix = request.GET.get(PREFIX_PARAM, "")
        try:
            names = ParamNames(prefix)
        except ValueError:
            # A fixed text: the response is HTML, the value is not echoed
            return HttpResponseBadRequest("Invalid table prefix")
        if self.is_htmx(request):
            table = self.get_table(request, url=request.path, prefix=prefix)
            response = TemplateResponse(request, self.fragment_template_name, {"table": table})
            current_url = request.headers.get("HX-Current-URL") or request.get_full_path()
            params = canonical_params(table.state, names, self.page_sizes)
            response["HX-Replace-Url"] = canonical_url(current_url, params, names)
        else:
            table = self.get_table(request, url=request.path, prefix=prefix, full=True)
            response = TemplateResponse(request, self.table_template_name, {"table": table})
        patch_vary_headers(response, ["HX-Request"])
        return response

    def is_htmx(self, request):
        """An htmx request, but not a boosted navigation (which wants the full page)."""
        return request.headers.get("HX-Request") == "true" and request.headers.get("HX-Boosted") != "true"

    # def get_table(self, request):
    def get_table(self, request, *, url, prefix="", full=False):
        """
        The Table for this request: state, query, page, header and rows.
        `url`: the endpoint, where the htmx requests go. `full`: a complete
        table, with the choices of the filter row (R2), which an htmx
        fragment does not render.
        """
        # names = ParamNames(self.prefix)
        names = ParamNames(prefix)
        columns = self.get_bound_columns(request)
        state = parse_state(request.GET, names, [c.name for c in columns], self.page_sizes)
        qs, errors = self.get_table_queryset(request, state)
        page = Paginator(qs, state.page_size).get_page(state.page)
        # The page actually shown, for the canonical URL
        state.page = page.number
        filtered = bool(state.search or state.filters)
        ordering = effective_ordering(columns, state.ordering, self._default_ordering())
        # return Table(
        table = Table(
            # id=self.prefix or "dt",
            # prefix=self.prefix,
            # url=request.path,
            prefix=prefix,
            url=url,
            page_url=request.path,
            names={key: names.name(key) for key in ("q", "o", "page", "page_size")},
            state=state,
            header=make_header(self, columns, state, names, ordering),
            rows=make_rows(self, columns, page.object_list),
            page=page,
            total_count=self.get_initial_queryset(request).count() if filtered else None,
            errors=errors,
            page_sizes=self.page_sizes,
            search_delay=self.search_delay,
        )
        if full:
            # Choices are computed only when the filter row is rendered (R2)
            for cell in table.header:
                if cell.widget == "select":
                    cell.choices = self.get_column_choices(request, cell.column)
        return table

    def _default_ordering(self):
        """The view's `ordering` as (name, descending) pairs."""
        # not removeprefix(): Python 3.8 (README)
        return [(e[1:] if e.startswith("-") else e, e.startswith("-")) for e in self.ordering or ()]

    def get_initial_queryset(self, request):
        return self.model._default_manager.all()

    def get_table_queryset(self, request, state):
        """
        The queryset for `state` (a TableState): filtered, ordered and
        optimized, with the validation errors of the column filters as
        (column, message) pairs, for the status area (R5).
        """
        columns = self.get_bound_columns(request)
        qs = self.get_initial_queryset(request)
        self.check_annotations(qs, columns)
        qs, errors = self.filter_queryset(qs, columns, state)
        qs = self.order_queryset(qs, columns, state)
        qs = self.optimize_queryset(qs, columns)
        return qs, errors

    def check_annotations(self, qs, columns):
        """Annotation columns must exist on the queryset (R9)."""
        missing = [c.name for c in columns if c.annotation and c.name not in qs.query.annotations]
        if missing:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: get_initial_queryset() does not annotate "
                + ", ".join(repr(name) for name in missing)
            )

    def filter_queryset(self, qs, columns, state):
        """Global search and column filters (R5, R8)."""
        errors = []
        distinct = False
        separator = self.search_values_separator

        searchable = [c for c in columns if c.searchable]
        if state.search:
            targets = [(t, c.lookup) for c in searchable for t in c.search_targets]
            qs = qs.filter(words_q(state.search, targets, separator))
            distinct = any(t.many for t, lookup in targets)

        for column in columns:
            value = state.filters.get(column.name, "").strip()
            if not value:
                continue
            custom = getattr(self, f"filter_{column.name}", None)
            if custom is not None:
                qs = custom(qs, value)
                continue
            if not column.searchable:
                continue
            try:
                q = column.filter_q(value, separator)
            except ValidationError as e:
                errors.append((column, e.messages[0]))
                continue
            qs = qs.filter(q)
            distinct = distinct or column.needs_distinct

        if distinct:
            qs = qs.distinct()
        return qs, errors

    def order_queryset(self, qs, columns, state):
        """
        The requested ordering, else the view's, else the queryset's or the
        model's; pk always last, so pages are stable (R6).
        """
        keys = self._ordering_keys(columns, state.ordering)
        if not keys:
            default = self._default_ordering()
            keys = self._ordering_keys(columns, default)
        if not keys:
            keys = list(qs.query.order_by or self.model._meta.ordering)
        return qs.order_by(*keys, "pk")

    def _ordering_keys(self, columns, pairs):
        by_name = {c.name: c for c in columns}
        keys = []
        for name, descending in pairs:
            column = by_name.get(name)
            if column is None or not column.orderable:
                logger.debug("%s: ignoring ordering on %r", type(self).__name__, name)
                continue
            nulls = {"nulls_last": True} if column.nulls_last else {}
            for field in column.order_by:
                keys.append(F(field).desc(**nulls) if descending else F(field).asc(**nulls))
        return keys

    def optimize_queryset(self, qs, columns):
        """
        Load the relations shown by the visible columns: select_related for
        single-valued paths, prefetch_related for multi-valued ones. No only():
        render hooks may read fields no column declares (F).
        """
        select, prefetch = set(), set()
        for column in columns:
            if not column.visible or column.path is None:
                continue
            relations = [accessor_name(f) for f in column.path.fields if f.is_relation]
            if relations:
                (prefetch if column.many else select).add(LOOKUP_SEP.join(relations))
        if select:
            qs = qs.select_related(*sorted(select))
        if prefetch:
            qs = qs.prefetch_related(*sorted(prefetch))
        return qs

    def get_column_choices(self, request, column):
        """
        The choices of a column filter, computed only when the filter row is
        rendered (D, R2): static ones, or the distinct values for autofilter.
        """
        choices = column.static_choices()
        if choices is None and column.autofilter:
            # No field to read the distinct values from (#8)
            if isinstance(column, ComputedColumn):
                raise ImproperlyConfigured(
                    f"{type(self).__name__}, column {column.name!r}: autofilter on a computed "
                    "column needs get_column_choices() to return its choices"
                )
            values = (
                self.get_initial_queryset(request)
                .order_by(column.name)
                .values_list(column.name, flat=True)
                .distinct()
            )
            choices = [(value, column.format_value(value)) for value in values if value is not None]
        return choices

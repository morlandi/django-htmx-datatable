"""
The table view.

For now the column declarations and their validation (#2) and the query
engine (#3); the HTTP side comes with #4.
"""
import logging

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import F
from django.db.models.constants import LOOKUP_SEP
from django.views.generic import View

from .columns import ComputedColumn, words_q
from .paths import accessor_name

logger = logging.getLogger(__name__)


class HtmxDatatableView(View):
    model = None
    columns = []
    # Default ordering, in the syntax of the "o" parameter: ["-published"] (D5)
    ordering = None
    # OR separator in search and filter values, e.g. "+" (R5); None: disabled
    search_values_separator = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
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
            try:
                bound.append(column.bind(cls.model, annotations))
            except ImproperlyConfigured as e:
                raise ImproperlyConfigured(f"{prefix}: {e}") from None
        return bound

    @classmethod
    def _check_ordering(cls):
        orderable = {c.name for c in cls._bound_columns if c.orderable}
        for entry in cls.ordering or ():
            if entry.removeprefix("-") not in orderable:
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
            default = [(e.removeprefix("-"), e.startswith("-")) for e in self.ordering or ()]
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
            values = (
                self.get_initial_queryset(request)
                .order_by(column.name)
                .values_list(column.name, flat=True)
                .distinct()
            )
            choices = [(value, value) for value in values if value is not None]
        return choices

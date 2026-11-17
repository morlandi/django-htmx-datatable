"""
Column declarations (R1, R4).

A view declares its columns as `Column` objects. When the view class is
defined, every declaration is bound to the view's model with `bind()`: the
field path is resolved and a copy of the subclass matching the field is
returned (TextColumn, NumberColumn, ...). Declarations are never modified, so
they can be shared between views.
"""
import copy
import datetime

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.db.models import ForeignObjectRel, Q
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from .parsing import parse_date, parse_decimal, parse_integer, split_alternatives, split_terms
from .paths import FieldPath

# Matches no row: a search term that no field takes (R5)
NOTHING = Q(pk__in=[])


class Column:
    """
    A table column, declared on a view.

    `name` is a field path of the view's model ("author__last_name"), or the
    name of an annotation (`annotation=True`, typed subclasses only).
    """

    # A typed filter matches the converted value exactly; an untyped one
    # searches words over search_fields (R5)
    typed_filter = False

    def __init__(
        self,
        name,
        *,
        title=None,
        visible=True,
        searchable=None,
        orderable=None,
        choices=None,
        autofilter=False,
        lookup_field=None,
        max_length=None,
        css_class=None,
        initial_search_value=None,
        order_by=None,
        search_fields=None,
        nulls_last=False,
        annotation=False,
    ):
        self.name = name
        self.title = title
        self.visible = visible
        self.searchable = searchable
        self.orderable = orderable
        self.choices = choices
        self.autofilter = autofilter
        self.lookup_field = lookup_field
        self.max_length = max_length
        self.css_class = css_class
        self.initial_search_value = initial_search_value
        self.order_by = tuple(order_by) if order_by is not None else None
        self.search_fields = tuple(search_fields) if search_fields is not None else None
        self.nulls_last = nulls_last
        self.annotation = annotation
        # Set by bind()
        self.path = None
        self.many = False

    def __repr__(self):
        return f"<{type(self).__name__} {self.name!r}>"

    def bind(self, model, annotations=()):
        """
        A copy of this column bound to `model`, with the defaults filled in.

        A plain `Column` becomes the subclass matching its field; a subclass
        declared explicitly is kept. `annotations` are the names of the
        annotation columns of the same view, valid in `order_by` and
        `search_fields`.

        Raises ImproperlyConfigured.
        """
        if not isinstance(self.name, str) or not self.name:
            raise ImproperlyConfigured("the name must be a non-empty string")
        bound = copy.copy(self)
        if isinstance(self, ComputedColumn):
            default_title = capfirst(self.name.replace("_", " "))
            default_fields = ()
        elif self.annotation:
            if not isinstance(self, TYPED_COLUMNS):
                raise ImproperlyConfigured(
                    "an annotation needs a typed column (TextColumn, NumberColumn, "
                    "DateColumn, DateTimeColumn, BooleanColumn, ChoiceColumn)"
                )
            default_title = capfirst(self.name.replace("_", " "))
            default_fields = (self.name,)
        else:
            path = FieldPath(model, self.name)
            if type(self) is Column:
                # All subclasses share __init__, so changing the class of the
                # copy is safe.
                bound.__class__ = column_class_for(path)
            bound.path = path
            bound.many = path.many
            default_title = _verbose_name(path)
            default_fields = () if path.field.is_relation else (self.name,)

        if bound.title is None:
            bound.title = default_title
        if bound.order_by is None:
            # Ordering on a multi-valued path would duplicate the rows
            bound.order_by = () if bound.many else default_fields
        if bound.search_fields is None:
            bound.search_fields = default_fields
        for entry in bound.order_by + bound.search_fields:
            if entry not in annotations:
                FieldPath(model, entry)
        bound.search_targets = [
            bound._search_target(entry, model, annotations) for entry in bound.search_fields
        ]
        bound.orderable = bound._flag("orderable", bound.order_by, "order_by")
        bound.searchable = bound._flag("searchable", bound.search_fields, "search_fields")
        return bound

    def _flag(self, attr, fields, fields_attr):
        """`orderable` / `searchable`: default from `visible` and `fields`, checked if explicit."""
        value = getattr(self, attr)
        if value is None:
            return self.visible and bool(fields)
        if value and not fields:
            raise ImproperlyConfigured(f"{attr}=True needs {fields_attr}")
        return value

    @property
    def lookup(self):
        """The lookup of the text search (D: lookup_field applies to text only)."""
        return self.lookup_field or "icontains"

    @property
    def filter_path(self):
        """The path a typed filter matches on."""
        return self.name

    @property
    def has_typed_filter(self):
        return self.typed_filter or self.autofilter or self.static_choices() is not None

    @property
    def needs_distinct(self):
        """True if filtering on this column may duplicate rows (multi-valued relations)."""
        return self.many or any(t.many for t in self.search_targets)

    def _search_target(self, entry, model, annotations):
        """The bound column searched for one entry of search_fields."""
        if entry == self.name:
            return self
        if entry in annotations:
            return annotations[entry].bind(model, annotations)
        return Column(entry).bind(model)

    def static_choices(self):
        """(value, label) pairs known without a query, or None (D)."""
        if self.choices is None or self.choices is False:
            return None
        return list(self.choices)

    def to_filter_value(self, value):
        """Convert a raw typed-filter value; raises ValidationError (R5)."""
        return value

    def filter_q(self, value, separator=None):
        """
        The Q for a column filter value: exact match of the converted value(s)
        for a typed filter, word search over search_fields otherwise.
        Raises ValidationError when a typed value does not fit (R5).
        """
        if self.has_typed_filter:
            values = [self.to_filter_value(v) for v in split_alternatives(value, separator)]
            return Q(**{f"{self.filter_path}__in": values}) if values else Q()
        return words_q(value, [(t, self.lookup) for t in self.search_targets], separator)

    def term_q(self, term, lookup):
        """
        The Q matching one search term on this column's own field, or None
        when the term does not fit the field's type (R5).
        """
        choices = self.static_choices()
        if choices is not None:
            term = term.lower()
            values = [value for value, label in choices if term in str(label).lower()]
            return Q(**{f"{self.name}__in": values}) if values else None
        return Q(**{f"{self.name}__{lookup}": term})


class TextColumn(Column):
    """A text field."""


class NumberColumn(Column):
    """An integer, decimal or float field."""

    typed_filter = True

    def _parse(self, text):
        field = self.path.field if self.path else None
        if isinstance(field, models.IntegerField):
            return parse_integer(text)
        return parse_decimal(text)

    def to_filter_value(self, value):
        number = self._parse(value)
        if number is None:
            raise ValidationError(_("Enter a number."))
        return number

    def term_q(self, term, lookup):
        number = self._parse(term)
        return None if number is None else Q(**{self.name: number})


class DateColumn(Column):
    """A date field. Filter values are ISO dates (D5); search terms are read as the user sees them."""

    typed_filter = True

    def to_filter_value(self, value):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            raise ValidationError(_("Enter a valid date.")) from None

    def term_q(self, term, lookup):
        date = parse_date(term)
        return None if date is None else Q(**{self.filter_path: date})


class DateTimeColumn(DateColumn):
    """A datetime field, filtered and searched on its date."""

    @property
    def filter_path(self):
        return f"{self.name}__date"


class BooleanColumn(Column):
    """A boolean field: Yes / No filter, never in the global search (R5)."""

    typed_filter = True

    def static_choices(self):
        if self.choices is None:
            return [("1", _("Yes")), ("0", _("No"))]
        return super().static_choices()

    def to_filter_value(self, value):
        try:
            return {"1": True, "0": False}[value]
        except KeyError:
            raise ValidationError(_("Select Yes or No.")) from None

    def term_q(self, term, lookup):
        return None


class ChoiceColumn(Column):
    """A field with choices: filtered on the value, searched on the labels."""

    typed_filter = True

    def static_choices(self):
        if self.choices is None and self.path is not None:
            return list(self.path.field.flatchoices)
        return super().static_choices()

    def to_filter_value(self, value):
        return self.path.field.to_python(value) if self.path else value


class RelatedColumn(Column):
    """
    A path ending on a relation ("author"): shows str() of the related object.
    Neither orderable nor searchable without `order_by` / `search_fields`.
    """

    def term_q(self, term, lookup):
        return None


class ComputedColumn(Column):
    """
    A column with no field, rendered by the view's render_<name>(obj, value).
    Neither orderable nor searchable without `order_by` / `search_fields` (R4).
    """

    def term_q(self, term, lookup):
        return None


TYPED_COLUMNS = (TextColumn, NumberColumn, DateColumn, DateTimeColumn, BooleanColumn, ChoiceColumn)


def column_class_for(path):
    """The Column subclass matching the last field of `path`."""
    field = path.field
    if field.is_relation:
        return RelatedColumn
    if field.choices:
        return ChoiceColumn
    if isinstance(field, models.BooleanField):
        return BooleanColumn
    # DateTimeField is a subclass of DateField: check it first
    if isinstance(field, models.DateTimeField):
        return DateTimeColumn
    if isinstance(field, models.DateField):
        return DateColumn
    if isinstance(field, (models.IntegerField, models.DecimalField, models.FloatField)):
        return NumberColumn
    return TextColumn


def _verbose_name(path):
    """Default title: the verbose name of the last field, kept lazy."""
    field = path.field
    if isinstance(field, ForeignObjectRel):
        opts = field.related_model._meta
        return capfirst(opts.verbose_name_plural if path.many else opts.verbose_name)
    return capfirst(field.verbose_name)


def words_q(value, targets, separator=None):
    """
    Word search (R5, R8): every term must match at least one target; the
    alternatives split by `separator` are ORed. `targets` are (column, lookup)
    pairs. Q() when there is nothing to search, NOTHING when no alternative
    can match.
    """
    alternatives = [split_terms(a) for a in split_alternatives(value, separator)]
    alternatives = [terms for terms in alternatives if terms]
    if not alternatives:
        return Q()
    matched = [q for terms in alternatives if (q := _terms_q(terms, targets)) is not None]
    return Q.create(matched, connector=Q.OR) if matched else NOTHING


def _terms_q(terms, targets):
    """AND of the terms, each ORed over the targets; None if a term fits no target."""
    term_qs = []
    for term in terms:
        matches = [q for column, lookup in targets if (q := column.term_q(term, lookup)) is not None]
        if not matches:
            return None
        term_qs.append(Q.create(matches, connector=Q.OR))
    return Q.create(term_qs)

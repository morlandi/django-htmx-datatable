"""
Column declarations (R1, R4).

A view declares its columns as `Column` objects. When the view class is
defined, every declaration is bound to the view's model with `bind()`: the
field path is resolved and a copy of the subclass matching the field is
returned (TextColumn, NumberColumn, ...). Declarations are never modified, so
they can be shared between views.
"""
import copy

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import ForeignObjectRel
from django.utils.text import capfirst

from .paths import FieldPath


class Column:
    """
    A table column, declared on a view.

    `name` is a field path of the view's model ("author__last_name"), or the
    name of an annotation (`annotation=True`, typed subclasses only).
    """

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


class TextColumn(Column):
    """A text field."""


class NumberColumn(Column):
    """An integer, decimal or float field."""


class DateColumn(Column):
    """A date field."""


class DateTimeColumn(Column):
    """A datetime field."""


class BooleanColumn(Column):
    """A boolean field."""


class ChoiceColumn(Column):
    """A field with choices."""


class RelatedColumn(Column):
    """
    A path ending on a relation ("author"): shows str() of the related object.
    Neither orderable nor searchable without `order_by` / `search_fields`.
    """


class ComputedColumn(Column):
    """
    A column with no field, rendered by the view's render_<name>(obj, value).
    Neither orderable nor searchable without `order_by` / `search_fields` (R4).
    """


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

"""
Field paths: a Django lookup path ("author__last_name") resolved on a model.

One resolver serves display, sorting, search and queryset optimization (R9).
"""
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured, ObjectDoesNotExist
from django.db.models import ForeignObjectRel
from django.db.models.constants import LOOKUP_SEP


class FieldPath:
    """
    A lookup path resolved on a model.

    Attributes:
        model: the model the path starts from
        path: the path as written ("author__last_name")
        fields: the field (or reverse relation) of every segment
        field: the last of them
        many: True when the path crosses a multi-valued relation
            (many-to-many or reverse foreign key)

    Raises ImproperlyConfigured if the path does not resolve.
    """

    def __init__(self, model, path):
        self.model = model
        self.path = path
        self.fields = []
        self.many = False
        current = model
        for name in path.split(LOOKUP_SEP):
            if current is None:
                raise ImproperlyConfigured(
                    f'"{path}": "{self.fields[-1].name}" is not a relation, '
                    f'so "{name}" cannot follow it'
                )
            try:
                field = current._meta.pk if name == "pk" else current._meta.get_field(name)
            except FieldDoesNotExist:
                raise ImproperlyConfigured(
                    f'"{path}": {current.__name__} has no field "{name}"'
                ) from None
            if field.is_relation and field.related_model is None:
                raise ImproperlyConfigured(
                    f'"{path}": "{name}" is a GenericForeignKey, not supported'
                )
            self.fields.append(field)
            if field.many_to_many or field.one_to_many:
                self.many = True
            current = field.related_model if field.is_relation else None
        self.field = self.fields[-1]

    def __repr__(self):
        return f"<FieldPath {self.model.__name__}.{self.path}>"

    def value_from(self, obj):
        """
        The value of the path for `obj`.

        A NULL relation along the path gives None, as does a missing reverse
        one-to-one. A multi-valued path gives the list of non-NULL values.
        """
        values = [obj]
        for field in self.fields:
            values = [v for value in values for v in _step(field, value)]
        if self.many:
            return [v for v in values if v is not None]
        return values[0] if values else None


def _step(field, value):
    """The values reached from `value` through `field`, as a list."""
    if value is None:
        return []
    # A reverse relation is read through its accessor ("book_set" or the
    # related_name), not through its query name.
    attname = field.get_accessor_name() if isinstance(field, ForeignObjectRel) else field.name
    try:
        attr = getattr(value, attname)
    except ObjectDoesNotExist:
        # Reverse one-to-one without a related object
        return []
    if field.many_to_many or field.one_to_many:
        # .all() uses the prefetch cache when present
        return list(attr.all())
    return [attr]

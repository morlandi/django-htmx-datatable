"""
The table view.

For now (issue #2) only the column declarations and their validation; the
HTTP side comes with #4.
"""
from django.core.exceptions import ImproperlyConfigured
from django.views.generic import View

from .columns import ComputedColumn


class HtmxDatatableView(View):
    model = None
    columns = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # A base class without a model is abstract: nothing to check yet
        if cls.model is not None:
            cls._bound_columns = cls.bind_columns(cls.columns)

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

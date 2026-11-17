from django.db.models import Count
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from htmx_datatable.columns import Column, ComputedColumn, NumberColumn
from htmx_datatable.views import HtmxDatatableView

from .models import Book


class BookTableView(HtmxDatatableView):
    """The example table: one column of every kind."""

    model = Book
    template_name = "books/book_list.html"
    page_sizes = [5, 10, 25]
    columns = [
        Column("title", max_length=20),
        Column(
            "author",
            order_by=("author__last_name", "author__first_name"),
            search_fields=("author__first_name", "author__last_name"),
        ),
        Column("genre"),
        Column("published", nulls_last=True),
        Column("pages"),
        Column("price"),
        Column("available"),
        Column("tags__name", title=_("Tags"), autofilter=True),
        NumberColumn("n_tags", annotation=True, title=_("Number of tags")),
        ComputedColumn("price_per_page", title=_("Price / page")),
    ]

    def get_initial_queryset(self, request):
        return Book.objects.annotate(n_tags=Count("tags", distinct=True))

    def render_price_per_page(self, obj, value):
        return format_html("<small>{}</small>", round(obj.price / obj.pages, 3))

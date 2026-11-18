from django.db.models import Count
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from htmx_datatable.columns import Column, ComputedColumn, NumberColumn
from htmx_datatable.views import HtmxDatatableView

# from .models import Book
from .models import Author, Book


class BookTableView(HtmxDatatableView):
    """The example table: one column of every kind."""

    model = Book
    # template_name = "books/book_list.html"
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


class AuthorBookTableView(HtmxDatatableView):
    """The books of one author, from the URL: shown twice on one page (#7)."""

    model = Book
    ordering = ["published"]
    page_sizes = [5, 10]
    columns = [
        Column("title", max_length=30),
        Column("genre"),
        Column("published", nulls_last=True),
        Column("pages"),
        Column("available"),
    ]

    def get_initial_queryset(self, request):
        return Book.objects.filter(author_id=self.kwargs["pk"])


class CompareView(TemplateView):
    """Two tables of the same class on one page, with their own prefix (#7)."""

    template_name = "books/compare.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["calvino"] = Author.objects.get(last_name="Calvino")
        context["pavese"] = Author.objects.get(last_name="Pavese")
        return context

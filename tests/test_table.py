import datetime
from decimal import Decimal

from django.core.paginator import Paginator
from django.test import SimpleTestCase, TestCase
from django.utils import formats, timezone, translation
from django.utils.html import format_html

from example.books.models import Book
from htmx_datatable.columns import Column, ComputedColumn
from htmx_datatable.protocol import ParamNames
from htmx_datatable.state import TableState
from htmx_datatable.table import Cell, Table, effective_ordering, make_header, make_rows
from htmx_datatable.views import HtmxDatatableView


def bound(*columns, **attrs):
    view = type("BookView", (HtmxDatatableView,), {"model": Book, "columns": list(columns), **attrs})
    return view, {c.name: c for c in view._bound_columns}


class FormatTestCase(SimpleTestCase):

    def setUp(self):
        self.view, self.columns = bound(
            Column("title"), Column("genre"), Column("published"), Column("created"),
            Column("price"), Column("available"), Column("tags__name"),
        )

    def format(self, name, value):
        return self.columns[name].format(value)

    def test_none_is_empty(self):
        self.assertEqual(self.format("title", None), "")
        self.assertEqual(self.format("published", None), "")

    def test_date(self):
        date = datetime.date(1957, 6, 1)
        with translation.override("en"):
            self.assertEqual(self.format("published", date), "06/01/1957")
        with translation.override("it"):
            self.assertEqual(self.format("published", date), "01/06/1957")

    def test_datetime_in_local_time(self):
        value = datetime.datetime(2026, 1, 10, 9, 0, tzinfo=datetime.timezone.utc)
        expected = formats.date_format(timezone.localtime(value), "SHORT_DATETIME_FORMAT")
        self.assertEqual(self.format("created", value), expected)

    def test_number(self):
        with translation.override("it"):
            self.assertEqual(self.format("price", Decimal("12.50")), "12,50")

    def test_boolean(self):
        self.assertEqual(self.format("available", True), "Yes")
        self.assertEqual(self.format("available", False), "No")

    def test_choice_label(self):
        self.assertEqual(self.format("genre", "short_stories"), "Short stories")

    def test_many(self):
        self.assertEqual(self.format("tags__name", ["classic", "fantasy"]), "classic, fantasy")


class CellTestCase(SimpleTestCase):

    def setUp(self):
        view, columns = bound(Column("title", max_length=5))
        self.column = columns["title"]

    def test_clipped(self):
        cell = Cell(self.column, None, "Il barone")
        self.assertEqual((cell.content, cell.title), ("Il b…", "Il barone"))

    def test_short_text_is_kept(self):
        cell = Cell(self.column, None, "Il b")
        self.assertEqual((cell.content, cell.title), ("Il b", ""))

    def test_html_is_never_clipped(self):
        html = format_html("<b>{}</b>", "Il barone")
        self.assertEqual(Cell(self.column, None, html).content, html)


class RowsTestCase(TestCase):
    fixtures = ["books_test"]

    def test_values_hooks_and_escaping(self):
        def render_title(self, obj, value):
            return f"<i>{value}</i>"

        def render_cover(self, obj, value):
            return format_html("<img alt='{}'>", obj.title)

        view_class, columns = bound(
            Column("title"),
            Column("author"),
            Column("tags__name"),
            Column("pages", visible=False),
            ComputedColumn("cover"),
            render_title=render_title,
            render_cover=render_cover,
        )
        (row,) = make_rows(view_class(), list(columns.values()), [Book.objects.get(pk=1)])
        self.assertEqual(row.pk, 1)
        title, author, tags, cover = row.cells
        # A plain string from a hook stays plain: the template escapes it
        self.assertEqual(title.content, "<i>Il barone rampante</i>")
        self.assertNotIsInstance(title.content, type(cover.content))
        self.assertEqual(author.content, "Italo Calvino")
        self.assertEqual(tags.content, "classic, fantasy")
        self.assertEqual(cover.content, "<img alt='Il barone rampante'>")
        self.assertIsNone(cover.value)


class HeaderTestCase(SimpleTestCase):

    def setUp(self):
        def filter_cover(self, qs, value):
            return qs

        self.view_class, self.columns = bound(
            Column("title"),
            Column("genre"),
            Column("available"),
            Column("published"),
            Column("pages"),
            Column("author__last_name", autofilter=True),
            Column("price", searchable=False),
            Column("created", visible=False),
            ComputedColumn("cover"),
            render_cover=lambda self, obj, value: "",
            filter_cover=filter_cover,
        )

    def header(self, state, ordering=None):
        cells = make_header(self.view_class(), list(self.columns.values()), state, ParamNames(), ordering)
        return {cell.column.name: cell for cell in cells}

    def test_widgets(self):
        header = self.header(TableState())
        self.assertEqual(
            {name: cell.widget for name, cell in header.items()},
            {
                "title": "text",
                "genre": "select",
                "available": "select",
                "published": "date",
                "pages": "number",
                "author__last_name": "select",
                "price": None,
                "cover": "text",
            },
        )

    def test_filter_name_and_value(self):
        cell = self.header(TableState(filters={"genre": "essay"}))["genre"]
        self.assertEqual((cell.filter_name, cell.filter_value), ("f_genre", "essay"))

    def test_sort(self):
        header = self.header(TableState(), ordering=("title", False))
        self.assertEqual((header["title"].aria_sort, header["title"].sort_value), ("ascending", "-title"))
        self.assertEqual((header["pages"].aria_sort, header["pages"].sort_value), ("none", "pages"))
        header = self.header(TableState(), ordering=("title", True))
        self.assertEqual((header["title"].aria_sort, header["title"].sort_value), ("descending", "title"))

    def test_effective_ordering(self):
        columns = list(self.columns.values())
        self.assertEqual(effective_ordering(columns, [("nope", False), ("pages", True)], []), ("pages", True))
        self.assertEqual(effective_ordering(columns, [], [("title", False)]), ("title", False))
        self.assertIsNone(effective_ordering(columns, [], []))


class TableTestCase(SimpleTestCase):

    def test_page_range_and_ordering_value(self):
        page = Paginator(range(200), 10).get_page(10)
        table = Table(
            id="dt", url="/books/", names={}, state=TableState(ordering=[("pages", True), ("title", False)]),
            header=[], rows=[], page=page, total_count=None, errors=[], page_sizes=[10], search_delay=300,
        )
        self.assertEqual(table.ordering_value, "-pages,title")
        self.assertEqual(table.page_range, [1, table.ellipsis, 8, 9, 10, 11, 12, table.ellipsis, 20])
        self.assertFalse(table.has_filters)

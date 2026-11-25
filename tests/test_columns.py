from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, SimpleTestCase

from example.books.models import Book
from htmx_datatable.columns import (
    BooleanColumn,
    ChoiceColumn,
    Column,
    ComputedColumn,
    DateColumn,
    DateTimeColumn,
    NumberColumn,
    RelatedColumn,
    TextColumn,
)
from htmx_datatable.views import HtmxDatatableView


def define_view(*columns, **attrs):
    """Define a view on Book with `columns` (class definition runs the checks)."""
    return type("BookView", (HtmxDatatableView,), {"model": Book, "columns": list(columns), **attrs})


def bind(*columns, **attrs):
    """The bound columns of a view on Book, by name."""
    return {c.name: c for c in define_view(*columns, **attrs)._bound_columns}


def noop_render(self, obj, value):
    return ""


class KindTestCase(SimpleTestCase):

    def test_kind_from_field(self):
        columns = bind(
            Column("title"),
            Column("pages"),
            Column("price"),
            Column("pk"),
            Column("genre"),
            Column("available"),
            Column("published"),
            Column("created"),
            Column("author"),
            Column("tags__name"),
        )
        self.assertEqual(
            {name: type(c) for name, c in columns.items()},
            {
                "title": TextColumn,
                "pages": NumberColumn,
                "price": NumberColumn,
                "pk": NumberColumn,
                "genre": ChoiceColumn,
                "available": BooleanColumn,
                "published": DateColumn,
                "created": DateTimeColumn,
                "author": RelatedColumn,
                "tags__name": TextColumn,
            },
        )

    def test_declared_subclass_is_kept(self):
        self.assertIs(type(bind(TextColumn("pages"))["pages"]), TextColumn)

    def test_declaration_is_not_modified(self):
        column = Column("title")
        bind(column)
        self.assertIs(type(column), Column)
        self.assertIsNone(column.path)
        self.assertIsNone(column.orderable)

    def test_many(self):
        self.assertTrue(bind(Column("tags__name"))["tags__name"].many)
        self.assertFalse(bind(Column("title"))["title"].many)


class DefaultsTestCase(SimpleTestCase):

    def test_title_from_verbose_name(self):
        self.assertEqual(str(bind(Column("author__last_name"))["author__last_name"].title), "Last name")

    def test_explicit_title(self):
        self.assertEqual(bind(Column("title", title="Book"))["title"].title, "Book")

    def test_field_column(self):
        column = bind(Column("title"))["title"]
        self.assertEqual(column.order_by, ("title",))
        self.assertEqual(column.search_fields, ("title",))
        self.assertTrue(column.orderable)
        self.assertTrue(column.searchable)

    def test_hidden_column(self):
        column = bind(Column("title", visible=False))["title"]
        self.assertFalse(column.orderable)
        self.assertFalse(column.searchable)

    def test_many_column_is_not_orderable(self):
        column = bind(Column("tags__name"))["tags__name"]
        self.assertFalse(column.orderable)
        self.assertTrue(column.searchable)

    def test_related_column(self):
        column = bind(Column("author"))["author"]
        self.assertFalse(column.orderable)
        self.assertFalse(column.searchable)

    def test_related_column_with_fields(self):
        column = bind(
            Column(
                "author",
                order_by=("author__last_name", "author__first_name"),
                search_fields=("author__first_name", "author__last_name"),
            )
        )["author"]
        self.assertTrue(column.orderable)
        self.assertTrue(column.searchable)

    def test_computed_column(self):
        column = bind(ComputedColumn("full_title"), render_full_title=noop_render)["full_title"]
        self.assertEqual(column.title, "Full title")
        self.assertIsNone(column.path)
        self.assertFalse(column.orderable)
        self.assertFalse(column.searchable)

    def test_annotation_column(self):
        column = bind(NumberColumn("n_tags", annotation=True))["n_tags"]
        self.assertEqual(column.title, "N tags")
        self.assertIsNone(column.path)
        self.assertEqual(column.order_by, ("n_tags",))
        self.assertTrue(column.orderable)

    def test_order_by_annotation(self):
        columns = bind(
            Column("author", order_by=("n_tags",)),
            NumberColumn("n_tags", annotation=True),
        )
        self.assertTrue(columns["author"].orderable)


class ValidationTestCase(SimpleTestCase):

    def assertInvalid(self, message, *columns, **attrs):
        with self.assertRaisesMessage(ImproperlyConfigured, message):
            define_view(*columns, **attrs)

    def test_duplicate_name(self):
        self.assertInvalid("BookView, column 'title': duplicate name", Column("title"), Column("title"))

    def test_unknown_path(self):
        self.assertInvalid(
            "BookView, column 'author__nickname': \"author__nickname\": Author has no field \"nickname\"",
            Column("author__nickname"),
        )

    def test_unknown_order_by(self):
        self.assertInvalid('Book has no field "rank"', Column("title", order_by=("rank",)))

    def test_unknown_search_field(self):
        self.assertInvalid('Book has no field "subtitle"', Column("title", search_fields=("subtitle",)))

    def test_computed_without_render(self):
        self.assertInvalid("a computed column needs a render_cover() method", ComputedColumn("cover"))

    def test_computed_autofilter_without_filter(self):
        # The value chosen in the select would go nowhere (#8)
        self.assertInvalid(
            "BookView, column 'decade': autofilter on a computed column needs a filter_decade() method",
            ComputedColumn("decade", autofilter=True),
            render_decade=noop_render,
        )

    def test_searchable_without_fields(self):
        self.assertInvalid("searchable=True needs search_fields", Column("author", searchable=True))

    def test_orderable_without_fields(self):
        self.assertInvalid("orderable=True needs order_by", Column("author", orderable=True))

    def test_annotation_on_plain_column(self):
        self.assertInvalid("an annotation needs a typed column", Column("n_tags", annotation=True))

    def test_empty_name(self):
        self.assertInvalid("the name must be a non-empty string", Column(""))


class GetColumnsTestCase(SimpleTestCase):

    def setUp(self):
        self.request = RequestFactory().get("/")

    def test_class_columns_are_bound_once(self):
        view_class = define_view(Column("title"))
        self.assertIs(view_class().get_bound_columns(self.request), view_class._bound_columns)

    def test_override_is_bound_per_request(self):
        view_class = define_view(get_columns=lambda self, request: [Column("pages")])
        (column,) = view_class().get_bound_columns(self.request)
        self.assertIs(type(column), NumberColumn)

    def test_override_is_validated(self):
        view_class = define_view(get_columns=lambda self, request: [Column("nope")])
        with self.assertRaisesMessage(ImproperlyConfigured, 'Book has no field "nope"'):
            view_class().get_bound_columns(self.request)

    def test_base_without_model_is_not_checked(self):
        class Base(HtmxDatatableView):
            columns = [Column("anything")]
        self.assertFalse(hasattr(Base, "_bound_columns"))

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count
from django.test import RequestFactory, TestCase

from example.books.models import Book
from htmx_datatable.columns import Column, NumberColumn
from htmx_datatable.state import TableState
from htmx_datatable.views import HtmxDatatableView


class BookView(HtmxDatatableView):
    model = Book
    columns = [
        Column("title"),
        Column(
            "author",
            order_by=("author__last_name", "author__first_name"),
            search_fields=("author__first_name", "author__last_name"),
        ),
        Column("genre"),
        Column("published", nulls_last=True),
        Column("pages"),
        Column("available"),
        Column("tags__name"),
    ]


class TagCountView(HtmxDatatableView):
    model = Book
    columns = [Column("title"), NumberColumn("n_tags", annotation=True)]

    def get_initial_queryset(self, request):
        return Book.objects.annotate(n_tags=Count("tags"))


ALL_BY_TITLE = [9, 7, 1, 6, 5, 4, 2, 8, 3]


class QueryTestCase(TestCase):
    fixtures = ["books"]

    def query(self, view_class=BookView, **state):
        qs, errors = view_class().get_table_queryset(RequestFactory().get("/"), TableState(**state))
        return [book.pk for book in qs], errors

    def pks(self, view_class=BookView, **state):
        pks, errors = self.query(view_class, **state)
        self.assertEqual(errors, [])
        return pks


class SearchTestCase(QueryTestCase):

    def test_words_across_columns(self):
        self.assertEqual(self.pks(search="calvino barone"), [1])
        self.assertEqual(self.pks(search="italo"), [1, 2, 3])

    def test_many_valued_without_duplicates(self):
        pks = self.pks(search="a")
        self.assertEqual(len(pks), len(set(pks)))
        self.assertIn(1, pks)

    def test_typed_terms(self):
        self.assertEqual(self.pks(search="280"), [1])
        self.assertEqual(self.pks(search="06/01/1957"), [1])

    def test_no_match(self):
        self.assertEqual(self.pks(search="xyz"), [])

    def test_no_search(self):
        self.assertEqual(self.pks(), ALL_BY_TITLE)


class FilterTestCase(QueryTestCase):

    def test_column_filter(self):
        self.assertEqual(self.pks(filters={"genre": "essay"}), [7])

    def test_filters_and_search_combine(self):
        self.assertEqual(self.pks(search="calvino", filters={"available": "0"}), [3])

    def test_invalid_value_is_reported_and_ignored(self):
        pks, errors = self.query(filters={"pages": "abc", "genre": "essay"})
        self.assertEqual(pks, [7])
        self.assertEqual([(c.name, message) for c, message in errors], [("pages", "Enter a number.")])

    def test_unknown_column_is_ignored(self):
        self.assertEqual(self.pks(filters={"price": "12.50"}), ALL_BY_TITLE)

    def test_separator(self):
        class View(BookView):
            search_values_separator = "+"
        self.assertEqual(self.pks(View, filters={"genre": "essay+poetry"}), [9, 7])

    def test_custom_filter(self):
        class View(BookView):
            def filter_title(self, qs, value):
                return qs.filter(pages__gt=int(value))
        self.assertEqual(self.pks(View, filters={"title": "500"}), [6, 4])


class OrderingTestCase(QueryTestCase):

    def test_descending(self):
        self.assertEqual(self.pks(ordering=[("pages", True)]), [4, 6, 5, 1, 7, 8, 2, 3, 9])

    def test_ties_broken_by_pk(self):
        self.assertEqual(self.pks(ordering=[("genre", False)]), [7, 1, 2, 4, 5, 6, 8, 9, 3])

    def test_nulls_last_both_ways(self):
        self.assertEqual(self.pks(ordering=[("published", False)]), [5, 1, 8, 3, 2, 4, 7, 6, 9])
        self.assertEqual(self.pks(ordering=[("published", True)]), [6, 7, 4, 2, 3, 8, 1, 5, 9])

    def test_not_orderable_is_ignored(self):
        self.assertEqual(self.pks(ordering=[("tags__name", False)]), ALL_BY_TITLE)

    def test_view_ordering(self):
        class View(BookView):
            ordering = ["-pages"]
        self.assertEqual(self.pks(View), [4, 6, 5, 1, 7, 8, 2, 3, 9])

    def test_view_ordering_is_checked(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "'tags__name' is not an orderable column"):
            class View(BookView):
                ordering = ["tags__name"]


class AnnotationTestCase(QueryTestCase):

    def test_order_by_annotation(self):
        self.assertEqual(self.pks(TagCountView, ordering=[("n_tags", True)]), [4, 1, 2, 5, 6, 3, 8, 7, 9])

    def test_missing_annotation(self):
        class View(TagCountView):
            def get_initial_queryset(self, request):
                return Book.objects.all()
        with self.assertRaisesMessage(ImproperlyConfigured, "does not annotate 'n_tags'"):
            self.query(View)


class OptimizationTestCase(QueryTestCase):

    def test_relations_are_loaded_in_two_queries(self):
        view = BookView()
        request = RequestFactory().get("/")
        qs, errors = view.get_table_queryset(request, TableState())
        columns = view.get_bound_columns(request)
        with self.assertNumQueries(2):
            rows = [[c.path.value_from(book) for c in columns] for book in qs]
        self.assertEqual(rows[2][1].last_name, "Calvino")
        self.assertEqual(rows[2][6], ["classic", "fantasy"])


class ChoicesTestCase(QueryTestCase):

    def test_autofilter(self):
        class View(HtmxDatatableView):
            model = Book
            columns = [Column("author__last_name", autofilter=True)]
        view = View()
        (column,) = view.get_bound_columns(None)
        self.assertEqual(
            view.get_column_choices(None, column),
            [("Calvino", "Calvino"), ("Eco", "Eco"), ("Ginzburg", "Ginzburg"), ("Morante", "Morante")],
        )

    def test_static(self):
        view = BookView()
        genre = view.get_bound_columns(None)[2]
        self.assertEqual(view.get_column_choices(None, genre), list(Book.Genre.choices))

from django.core.exceptions import ValidationError
from django.db.models import Count
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from example.books.models import Book
from htmx_datatable.columns import Column, NumberColumn, TextColumn, words_q
from htmx_datatable.views import HtmxDatatableView


def bound(*columns):
    """The bound columns of a view on Book, by name."""
    view = type("BookView", (HtmxDatatableView,), {"model": Book, "columns": list(columns)})
    return {c.name: c for c in view._bound_columns}


def column(declaration):
    return bound(declaration)[declaration.name]


class QueryTestCase(TestCase):
    fixtures = ["books"]

    def pks(self, q, qs=None):
        qs = Book.objects.all() if qs is None else qs
        return sorted(qs.filter(q).distinct().values_list("pk", flat=True))


class TermTestCase(QueryTestCase):

    def test_text(self):
        self.assertEqual(self.pks(column(Column("title")).term_q("barone", "icontains")), [1])

    def test_integer(self):
        pages = column(Column("pages"))
        self.assertEqual(self.pks(pages.term_q("280", None)), [1])
        self.assertIsNone(pages.term_q("28.5", None))
        self.assertIsNone(pages.term_q("abc", None))

    def test_decimal(self):
        price = column(Column("price"))
        self.assertEqual(self.pks(price.term_q("12.50", None)), [1])
        with translation.override("it"):
            self.assertEqual(self.pks(price.term_q("12,50", None)), [1])

    def test_date_as_shown(self):
        published = column(Column("published"))
        with translation.override("en"):
            self.assertEqual(self.pks(published.term_q("06/01/1957", None)), [1])
        with translation.override("it"):
            self.assertEqual(self.pks(published.term_q("01/06/1957", None)), [1])
        self.assertIsNone(published.term_q("rossi", None))

    def test_datetime_on_date(self):
        self.assertEqual(self.pks(column(Column("created")).term_q("2026-01-10", None)), [1])

    def test_choice_labels(self):
        genre = column(Column("genre"))
        self.assertEqual(self.pks(genre.term_q("short", None)), [3])
        self.assertIsNone(genre.term_q("xyz", None))

    def test_boolean_and_related_never_match(self):
        self.assertIsNone(column(Column("available")).term_q("yes", None))
        self.assertIsNone(column(Column("author")).term_q("calvino", None))


class WordsTestCase(QueryTestCase):

    def setUp(self):
        columns = bound(Column("title"), Column("author__last_name"), Column("pages"))
        self.text_targets = [(columns["title"], "icontains"), (columns["author__last_name"], "icontains")]
        self.pages_target = [(columns["pages"], None)]

    def test_every_word_must_match(self):
        self.assertEqual(self.pks(words_q("calvino barone", self.text_targets)), [1])
        self.assertEqual(self.pks(words_q("calvino", self.text_targets)), [1, 2, 3])
        self.assertEqual(self.pks(words_q("calvino xyz", self.text_targets)), [])

    def test_quoted_phrase(self):
        self.assertEqual(self.pks(words_q('"nome della"', self.text_targets)), [6])

    def test_empty_value_matches_all(self):
        self.assertEqual(len(self.pks(words_q("  ", self.text_targets))), 9)

    def test_alternatives(self):
        self.assertEqual(self.pks(words_q("barone + storia", self.text_targets, "+")), [1, 4])

    def test_word_no_field_takes(self):
        self.assertEqual(self.pks(words_q("abc", self.pages_target)), [])
        self.assertEqual(self.pks(words_q("280", self.pages_target)), [1])

    def test_mixed_types(self):
        targets = self.text_targets + self.pages_target
        self.assertEqual(self.pks(words_q("280", targets)), [1])

    def test_annotation_target(self):
        columns = bound(
            Column("title", search_fields=("title", "n_tags")),
            NumberColumn("n_tags", annotation=True),
        )
        title = columns["title"]
        self.assertIs(type(title.search_targets[1]), NumberColumn)
        qs = Book.objects.annotate(n_tags=Count("tags"))
        self.assertEqual(self.pks(title.filter_q("3"), qs), [4])


class FilterTestCase(QueryTestCase):

    def test_number(self):
        pages = column(Column("pages"))
        self.assertEqual(self.pks(pages.filter_q("280")), [1])
        with self.assertRaises(ValidationError):
            pages.filter_q("abc")

    def test_date_is_iso(self):
        published = column(Column("published"))
        self.assertEqual(self.pks(published.filter_q("1957-06-01")), [1])
        with self.assertRaises(ValidationError):
            published.filter_q("01/06/1957")

    def test_datetime_on_date(self):
        self.assertEqual(self.pks(column(Column("created")).filter_q("2026-01-10")), [1])

    def test_boolean(self):
        available = column(Column("available"))
        self.assertEqual(self.pks(available.filter_q("0")), [3, 7])
        with self.assertRaises(ValidationError):
            available.filter_q("x")

    def test_choice(self):
        genre = column(Column("genre"))
        self.assertEqual(self.pks(genre.filter_q("essay")), [7])
        self.assertEqual(self.pks(genre.filter_q("essay+poetry", "+")), [7, 9])

    def test_autofilter_is_exact(self):
        last_name = column(Column("author__last_name", autofilter=True))
        self.assertEqual(self.pks(last_name.filter_q("Eco")), [6, 7])
        self.assertEqual(self.pks(last_name.filter_q("Ec")), [])

    def test_text_searches_words(self):
        self.assertEqual(self.pks(column(Column("title")).filter_q("rosa")), [6])

    def test_related_with_search_fields(self):
        author = column(Column("author", search_fields=("author__first_name", "author__last_name")))
        self.assertEqual(self.pks(author.filter_q("italo")), [1, 2, 3])

    def test_many(self):
        tags = column(Column("tags__name"))
        self.assertTrue(tags.needs_distinct)
        self.assertEqual(self.pks(tags.filter_q("fantasy")), [1, 2])


class StaticChoicesTestCase(SimpleTestCase):

    def test_boolean(self):
        choices = column(Column("available")).static_choices()
        self.assertEqual([(v, str(label)) for v, label in choices], [("1", "Yes"), ("0", "No")])

    def test_field_choices(self):
        self.assertEqual(column(Column("genre")).static_choices(), list(Book.Genre.choices))

    def test_no_choices(self):
        self.assertIsNone(column(Column("genre", choices=False)).static_choices())
        self.assertIsNone(column(Column("title")).static_choices())

    def test_explicit_choices(self):
        title = column(TextColumn("title", choices=[("a", "A")]))
        self.assertEqual(title.static_choices(), [("a", "A")])
        self.assertTrue(title.has_typed_filter)

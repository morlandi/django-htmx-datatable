from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from example.books.models import Author, AuthorProfile, Book, Tag
from htmx_datatable.paths import FieldPath


class ResolveTestCase(TestCase):

    def test_plain_field(self):
        path = FieldPath(Book, "title")
        self.assertEqual(path.field, Book._meta.get_field("title"))
        self.assertFalse(path.many)

    def test_pk(self):
        self.assertEqual(FieldPath(Book, "pk").field, Book._meta.pk)
        self.assertEqual(FieldPath(Book, "author__pk").field, Author._meta.pk)

    def test_foreign_key(self):
        path = FieldPath(Book, "author__last_name")
        self.assertEqual(path.field, Author._meta.get_field("last_name"))
        self.assertFalse(path.many)

    def test_path_ending_on_relation(self):
        path = FieldPath(Book, "author")
        self.assertTrue(path.field.is_relation)
        self.assertFalse(path.many)

    def test_many_to_many(self):
        self.assertTrue(FieldPath(Book, "tags__name").many)

    def test_reverse_many_to_many(self):
        self.assertTrue(FieldPath(Tag, "books__title").many)

    def test_reverse_foreign_key(self):
        self.assertTrue(FieldPath(Author, "books__title").many)

    def test_reverse_one_to_one(self):
        path = FieldPath(Author, "profile__website")
        self.assertEqual(path.field, AuthorProfile._meta.get_field("website"))
        self.assertFalse(path.many)

    def test_unknown_field(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'Author has no field "nickname"'):
            FieldPath(Book, "author__nickname")

    def test_segment_after_plain_field(self):
        with self.assertRaisesMessage(ImproperlyConfigured, '"title" is not a relation'):
            FieldPath(Book, "title__length")


class ValueTestCase(TestCase):
    fixtures = ["books"]

    def test_plain_field(self):
        book = Book.objects.get(pk=1)
        self.assertEqual(FieldPath(Book, "title").value_from(book), "Il barone rampante")

    def test_null_value(self):
        book = Book.objects.get(pk=9)
        self.assertIsNone(FieldPath(Book, "published").value_from(book))

    def test_foreign_key(self):
        book = Book.objects.get(pk=1)
        self.assertEqual(FieldPath(Book, "author__last_name").value_from(book), "Calvino")

    def test_null_relation_in_the_middle(self):
        book = Book.objects.get(pk=9)
        self.assertIsNone(FieldPath(Book, "author__last_name").value_from(book))

    def test_path_ending_on_relation(self):
        book = Book.objects.get(pk=1)
        self.assertEqual(FieldPath(Book, "author").value_from(book), Author.objects.get(pk=1))

    def test_many_to_many(self):
        book = Book.objects.get(pk=1)
        self.assertEqual(FieldPath(Book, "tags__name").value_from(book), ["classic", "fantasy"])

    def test_many_to_many_empty(self):
        book = Book.objects.get(pk=9)
        self.assertEqual(FieldPath(Book, "tags__name").value_from(book), [])

    def test_reverse_foreign_key(self):
        author = Author.objects.get(pk=1)
        self.assertEqual(
            FieldPath(Author, "books__title").value_from(author),
            ["Il barone rampante", "Le città invisibili", "Marcovaldo"],
        )

    def test_reverse_one_to_one(self):
        AuthorProfile.objects.create(author_id=1, website="https://example.com")
        path = FieldPath(Author, "profile__website")
        self.assertEqual(path.value_from(Author.objects.get(pk=1)), "https://example.com")
        self.assertIsNone(path.value_from(Author.objects.get(pk=2)))

    def test_prefetched_many_to_many(self):
        book = Book.objects.prefetch_related("tags").get(pk=1)
        with self.assertNumQueries(0):
            self.assertEqual(FieldPath(Book, "tags__name").value_from(book), ["classic", "fantasy"])

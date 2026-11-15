from django.apps import apps
from django.test import TestCase

from example.books.models import Book


class BootstrapTestCase(TestCase):
    fixtures = ["books"]

    def test_app_is_installed(self):
        self.assertTrue(apps.is_installed("htmx_datatable"))

    def test_example_fixture_loads(self):
        self.assertEqual(Book.objects.count(), 9)
        self.assertEqual(Book.objects.filter(author__isnull=True).count(), 1)

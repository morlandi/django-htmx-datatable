from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings


@override_settings(ROOT_URLCONF="tests.urls")
class TemplateTagTestCase(TestCase):
    fixtures = ["books_test"]

    def render(self, source, query=""):
        request = RequestFactory().get(f"/page/?{query}")
        return Template("{% load htmx_datatable %}" + source).render(Context({"request": request}))

    def test_one_table(self):
        html = self.render('{% htmx_datatable "books-table" %}', "q=calvino")
        self.assertIn('action="/page/"', html)
        self.assertIn('hx-get="/books/"', html)
        self.assertIn('id="dt-body"', html)
        self.assertIn('value="calvino"', html)
        self.assertNotIn('name="_dt"', html)

    def test_two_tables_with_prefix_and_url_kwargs(self):
        html = self.render(
            '{% htmx_datatable "books-table" prefix="a" %}'
            '{% htmx_datatable "genre-books-table" genre="essay" prefix="b" %}'
        )
        self.assertIn('<input type="hidden" name="_dt" value="a">', html)
        self.assertIn('<input type="hidden" name="_dt" value="b">', html)
        self.assertIn('hx-get="/books/essay/"', html)
        self.assertIn('id="dt-a-body"', html)
        self.assertIn('id="dt-b-body"', html)

    def test_custom_template(self):
        html = self.render('{% htmx_datatable "books-table" template="tests/book_table.html" %}')
        self.assertIn("Add a book", html)

    def test_without_request(self):
        template = Template('{% load htmx_datatable %}{% htmx_datatable "books-table" %}')
        with self.assertRaisesMessage(ImproperlyConfigured, "context_processors.request"):
            template.render(Context())

    def test_not_a_table(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "is not the URL of an HtmxDatatableView"):
            self.render('{% htmx_datatable "not-a-table" %}')

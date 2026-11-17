from django.test import RequestFactory, TestCase
from django.utils.html import format_html

from example.books.models import Book
from htmx_datatable.columns import Column
from htmx_datatable.views import HtmxDatatableView


class BookView(HtmxDatatableView):
    model = Book
    template_name = "tests/books.html"
    columns = [
        Column("title"),
        Column("author__last_name", autofilter=True),
        Column("genre"),
        Column("published"),
        Column("pages"),
        Column("available"),
    ]


class ViewTestCase(TestCase):
    fixtures = ["books"]

    def get(self, query="", view_class=BookView, **headers):
        request = RequestFactory().get(f"/books/?{query}", headers=headers)
        response = view_class.as_view()(request)
        response.render()
        return response

    def htmx(self, query="", view_class=BookView, current_url="http://testserver/books/"):
        return self.get(query, view_class, HX_Request="true", HX_Current_URL=current_url)


class FullPageTestCase(ViewTestCase):

    def test_full_page(self):
        response = self.get()
        self.assertContains(response, '<form class="htmx-datatable-form"')
        self.assertContains(response, 'id="dt-body"')
        self.assertContains(response, 'class="htmx-datatable-filters"')
        self.assertNotContains(response, "hx-swap-oob")
        self.assertNotIn("HX-Replace-Url", response)
        self.assertIn("HX-Request", response["Vary"])

    def test_filter_widgets_and_choices(self):
        response = self.get("f_genre=essay")
        self.assertContains(response, '<option value="essay" selected>Essay</option>', html=True)
        self.assertContains(response, '<option value="Calvino">Calvino</option>', html=True)
        self.assertContains(response, 'type="date" name="f_published"')
        self.assertContains(response, 'inputmode="decimal" name="f_pages"')

    def test_boosted_request_gets_the_full_page(self):
        response = self.get(HX_Request="true", HX_Boosted="true")
        self.assertContains(response, '<form class="htmx-datatable-form"')


class FragmentTestCase(ViewTestCase):

    def test_fragment_is_all_out_of_band(self):
        response = self.htmx()
        content = response.content.decode()
        self.assertNotIn("htmx-datatable-filters", content)
        self.assertNotIn("<form", content)
        for element_id in ("dt-body", "dt-head", "dt-o", "dt-status", "dt-pager"):
            self.assertIn(f'id="{element_id}"', content)
        self.assertEqual(content.count('hx-swap-oob="true"'), 5)
        self.assertIn("HX-Request", response["Vary"])

    def test_canonical_url(self):
        response = self.htmx(
            "q=calvino&page_size=10&f_genre=&o=",
            current_url="http://testserver/books/?tab=1&q=old",
        )
        self.assertEqual(response["HX-Replace-Url"], "/books/?tab=1&q=calvino")

    def test_page_beyond_the_last(self):
        response = self.htmx("page=99")
        self.assertEqual(response["HX-Replace-Url"], "/books/")


class ContentTestCase(ViewTestCase):

    def test_counter(self):
        self.assertContains(self.htmx(), "1–9 of 9")
        response = self.htmx("q=calvino")
        self.assertContains(response, "1–3 of 3")
        self.assertContains(response, "(filtered from 9)")

    def test_filter_error_in_status(self):
        self.assertContains(self.htmx("f_pages=abc"), "Pages: Enter a number.")

    def test_sort_header(self):
        response = self.htmx("o=-pages")
        self.assertContains(response, 'aria-sort="descending"')
        self.assertContains(response, 'name="o" value="pages"')
        self.assertContains(response, 'id="dt-o" name="o" value="-pages"')

    def test_pager(self):
        response = self.htmx("page_size=10")
        self.assertNotContains(response, 'name="page"')

    def test_escaping(self):
        class View(BookView):
            def render_title(self, obj, value):
                return f"<script>{value}</script>"

            def render_genre(self, obj, value):
                return format_html("<b>{}</b>", value)

        response = self.htmx(view_class=View)
        self.assertContains(response, "&lt;script&gt;Il barone rampante&lt;/script&gt;")
        self.assertContains(response, "<b>novel</b>")

    def test_empty(self):
        self.assertContains(self.htmx("q=xyz"), "No matching rows")

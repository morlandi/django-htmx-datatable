from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase
from django.utils.html import format_html

from example.books.models import Book
from htmx_datatable.columns import Column
from htmx_datatable.views import HtmxDatatableView


class BookView(HtmxDatatableView):
    model = Book
    # template_name = "tests/books.html"
    columns = [
        Column("title"),
        Column("author__last_name", autofilter=True),
        Column("genre"),
        Column("published"),
        Column("pages"),
        Column("available"),
    ]


class CustomTemplateBookView(BookView):
    table_template_name = "tests/book_table.html"


class ViewTestCase(TestCase):
    fixtures = ["books_test"]

    def get(self, query="", view_class=BookView, **headers):
        request = RequestFactory().get(f"/books/?{query}", headers=headers)
        response = view_class.as_view()(request)
        # response.render()
        # A 400 for an invalid prefix is a plain HttpResponse
        if hasattr(response, "render"):
            response.render()
        return response

    def htmx(self, query="", view_class=BookView, current_url="http://testserver/books/"):
        return self.get(query, view_class, HX_Request="true", HX_Current_URL=current_url)


class FullPageTestCase(ViewTestCase):

    # def test_full_page(self):
    def test_plain_get(self):
        response = self.get()
        # The table alone, without a page around it (#7)
        self.assertNotContains(response, "<html")
        self.assertContains(response, '<form class="htmx-datatable-form"')
        self.assertContains(response, 'id="dt-body"')
        self.assertContains(response, 'class="htmx-datatable-filters"')
        self.assertContains(response, '<div class="htmx-datatable-scroll">')
        self.assertNotContains(response, "hx-swap-oob")
        self.assertNotIn("HX-Replace-Url", response)
        self.assertIn("HX-Request", response["Vary"])

    def test_filter_widgets_and_choices(self):
        response = self.get("f_genre=essay")
        self.assertContains(response, '<option value="essay" selected>Essay</option>', html=True)
        self.assertContains(response, '<option value="Calvino">Calvino</option>', html=True)
        self.assertContains(response, 'type="date" name="f_published"')
        self.assertContains(response, 'inputmode="decimal" name="f_pages"')

    def test_default_button_is_neutral(self):
        # Enter in a text field clicks the first submit button of the form:
        # it must not be a sort button (#1)
        content = self.get().content.decode()
        first_submit = content.index('type="submit"')
        self.assertEqual(content[first_submit:].split(">")[0], 'type="submit" hidden tabindex="-1"')

    def test_boosted_request_gets_the_full_page(self):
        response = self.get(HX_Request="true", HX_Boosted="true")
        self.assertContains(response, '<form class="htmx-datatable-form"')

    def test_table_template_name(self):
        # The plain GET renders the view's template (#6)
        self.assertContains(self.get(view_class=CustomTemplateBookView), "Add a book")
        self.assertNotContains(self.get(), "Add a book")
        # The htmx response is still the fragment
        self.assertNotContains(self.htmx(view_class=CustomTemplateBookView), "Add a book")


class FragmentTestCase(ViewTestCase):

    def test_fragment_is_all_out_of_band(self):
        response = self.htmx()
        content = response.content.decode()
        self.assertNotIn("htmx-datatable-filters", content)
        self.assertNotIn("<form", content)
        self.assertNotIn("htmx-datatable-scroll", content)
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


class EndpointPrefixTestCase(ViewTestCase):

    def test_prefix_from_the_hidden_input(self):
        response = self.htmx("_dt=b&b-q=calvino", current_url="http://testserver/page/?a-q=x&_dt=b")
        self.assertEqual(response["HX-Replace-Url"], "/page/?a-q=x&b-q=calvino")
        self.assertContains(response, 'id="dt-b-body"')

    def test_invalid_prefix(self):
        response = self.htmx("_dt=<b>")
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "<b>", status_code=400)


class EmbedTestCase(ViewTestCase):

    def page_request(self, query=""):
        return RequestFactory().get(f"/page/?{query}")

    def test_embed(self):
        table = BookView.embed(self.page_request("b-q=calvino&q=other"), url="/books/", prefix="b")
        self.assertEqual((table.url, table.page_url, table.id), ("/books/", "/page/", "dt-b"))
        self.assertEqual(table.state.search, "calvino")
        author = next(cell for cell in table.header if cell.column.name == "author__last_name")
        self.assertIn(("Calvino", "Calvino"), author.choices)

    def test_url_kwargs(self):
        class GenreView(BookView):
            def get_initial_queryset(self, request):
                return super().get_initial_queryset(request).filter(genre=self.kwargs["genre"])

        table = GenreView.embed(self.page_request(), url="/books/essay/", kwargs={"genre": "essay"})
        self.assertTrue(table.rows)
        self.assertEqual({row.obj.genre for row in table.rows}, {"essay"})

    def test_two_tables_of_the_same_class(self):
        request = self.page_request("a-q=calvino")
        a = BookView.embed(request, url="/books/", prefix="a")
        b = BookView.embed(request, url="/books/", prefix="b")
        self.assertEqual((a.state.search, b.state.search), ("calvino", ""))
        self.assertLess(len(a.rows), len(b.rows))

    def test_duplicate_prefix(self):
        for prefix in ("a", ""):
            request = self.page_request()
            BookView.embed(request, url="/books/", prefix=prefix)
            with self.subTest(prefix=prefix), self.assertRaisesMessage(ImproperlyConfigured, "already used"):
                BookView.embed(request, url="/books/", prefix=prefix)

    def test_invalid_prefix(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "ASCII letters and digits"):
            BookView.embed(self.page_request(), url="/books/", prefix="a-b")


class RemovedAttributesTestCase(TestCase):

    def test_removed_attributes(self):
        for name in ("template_name", "prefix"):
            with self.subTest(name=name), self.assertRaisesMessage(ImproperlyConfigured, "removed in 0.2"):
                type("View", (HtmxDatatableView,), {name: "x"})

from django.utils import translation

from tests.test_views import ViewTestCase


class TranslationTestCase(ViewTestCase):
    """The catalogs shipped in htmx_datatable/locale (issue #5)."""

    def test_template_texts(self):
        with translation.override("it"):
            response = self.get("f_genre=essay")
        self.assertContains(response, 'placeholder="Cerca"')
        self.assertContains(response, "Righe per pagina")
        self.assertContains(response, '<option value="">Tutti</option>', html=True)
        self.assertContains(response, 'aria-label="Pagine"')
        self.assertContains(response, "(filtrate da ")
        self.assertNotContains(response, "Search")
        self.assertNotContains(response, "Rows per page")

    def test_python_texts(self):
        with translation.override("it"):
            response = self.get("f_available=x")
        self.assertContains(response, "Seleziona Sì o No.")
        self.assertNotContains(response, "Select Yes or No.")

    def test_english_is_the_default(self):
        response = self.get()
        self.assertContains(response, 'placeholder="Search"')
        self.assertContains(response, "Rows per page")

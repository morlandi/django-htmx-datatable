from django.http import QueryDict
from django.test import SimpleTestCase

from htmx_datatable.protocol import ParamNames, canonical_params, canonical_url, parse_state
from htmx_datatable.state import TableState

COLUMNS = ["title", "genre", "pages"]
PAGE_SIZES = [10, 25, 50]


def parse(query, prefix=""):
    return parse_state(QueryDict(query), ParamNames(prefix), COLUMNS, PAGE_SIZES)


class ParseTestCase(SimpleTestCase):

    def test_defaults(self):
        state = parse("")
        self.assertEqual(
            (state.search, state.ordering, state.filters, state.page, state.page_size),
            ("", [], {}, 1, 10),
        )

    def test_all_parameters(self):
        state = parse("q=rossi+mar&o=-published,title&page=3&page_size=25&f_genre=novel")
        self.assertEqual(state.search, "rossi mar")
        self.assertEqual(state.ordering, [("published", True), ("title", False)])
        self.assertEqual(state.filters, {"genre": "novel"})
        self.assertEqual((state.page, state.page_size), (3, 25))

    def test_unknown_and_empty_filters_are_dropped(self):
        self.assertEqual(parse("f_genre=&f_nope=x&f_pages=280").filters, {"pages": "280"})

    def test_last_ordering_wins(self):
        self.assertEqual(parse("o=title&o=-pages").ordering, [("pages", True)])

    def test_invalid_values(self):
        for query in ("page=abc", "page=0", "page=-2"):
            self.assertEqual(parse(query).page, 1, query)
        self.assertEqual(parse("page_size=7").page_size, 10)
        self.assertEqual(parse("o=,-,").ordering, [])

    def test_prefix(self):
        state = parse("orders-q=x&q=y&orders-f_genre=essay&f_genre=novel", prefix="orders")
        self.assertEqual(state.search, "x")
        self.assertEqual(state.filters, {"genre": "essay"})


class CanonicalTestCase(SimpleTestCase):

    def test_defaults_are_left_out(self):
        state = TableState(filters={"genre": ""}, page=1, page_size=10)
        self.assertEqual(canonical_params(state, ParamNames(), PAGE_SIZES), [])

    def test_all_parameters(self):
        state = TableState(
            search="rossi mar",
            ordering=[("published", True), ("title", False)],
            filters={"genre": "novel"},
            page=3,
            page_size=25,
        )
        self.assertEqual(
            canonical_params(state, ParamNames("orders"), PAGE_SIZES),
            [
                ("orders-q", "rossi mar"),
                ("orders-o", "-published,title"),
                ("orders-page", "3"),
                ("orders-page_size", "25"),
                ("orders-f_genre", "novel"),
            ],
        )

    def test_other_parameters_are_kept(self):
        url = canonical_url(
            "http://testserver/books/?tab=2&q=old&f_genre=x&orders-q=z",
            [("q", "new")],
            ParamNames(),
        )
        self.assertEqual(url, "/books/?tab=2&orders-q=z&q=new")

    def test_prefixed_table_keeps_the_others(self):
        url = canonical_url("/books/?q=a&orders-q=old", [("orders-q", "new")], ParamNames("orders"))
        self.assertEqual(url, "/books/?q=a&orders-q=new")

    def test_no_parameters(self):
        self.assertEqual(canonical_url("/books/?q=old", [], ParamNames()), "/books/")

    def test_prefix_param_is_dropped(self):
        url = canonical_url("/books/?_dt=orders&tab=1", [("orders-q", "new")], ParamNames("orders"))
        self.assertEqual(url, "/books/?tab=1&orders-q=new")


class PrefixTestCase(SimpleTestCase):

    def test_valid(self):
        for prefix in ("", "orders", "B2", "dt"):
            self.assertEqual(ParamNames(prefix).prefix, prefix)

    def test_invalid(self):
        for prefix in ("a-b", "f_x", "a b", "a.b", "città"):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                ParamNames(prefix)

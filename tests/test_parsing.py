import datetime
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import formats, translation

from htmx_datatable.parsing import (
    date_format_to_strptime,
    parse_date,
    parse_decimal,
    parse_integer,
    split_alternatives,
    split_terms,
)


class SplitTestCase(SimpleTestCase):

    def test_words(self):
        self.assertEqual(split_terms("  rossi   mar "), ["rossi", "mar"])

    def test_quoted_phrase(self):
        self.assertEqual(split_terms('"Mario Rossi" milano'), ["Mario Rossi", "milano"])
        self.assertEqual(split_terms("'Mario Rossi'"), ["Mario Rossi"])

    def test_empty(self):
        self.assertEqual(split_terms(""), [])
        self.assertEqual(split_terms('""'), [])

    def test_alternatives(self):
        self.assertEqual(split_alternatives("novel + essay", "+"), ["novel", "essay"])
        self.assertEqual(split_alternatives("novel + ", "+"), ["novel"])
        self.assertEqual(split_alternatives("novel+essay", None), ["novel+essay"])


class NumberTestCase(SimpleTestCase):

    def test_integer(self):
        self.assertEqual(parse_integer("42"), 42)
        self.assertIsNone(parse_integer("4.2"))
        self.assertIsNone(parse_integer("abc"))

    def test_decimal(self):
        self.assertEqual(parse_decimal("12.50"), Decimal("12.50"))
        self.assertIsNone(parse_decimal("abc"))
        self.assertIsNone(parse_decimal("NaN"))
        self.assertIsNone(parse_decimal("Infinity"))

    def test_decimal_localized(self):
        with translation.override("it"):
            self.assertEqual(parse_decimal("12,50"), Decimal("12.50"))


class DateFormatToStrptimeTestCase(SimpleTestCase):

    def test_numeric_formats_are_converted(self):
        self.assertEqual(date_format_to_strptime("m/d/Y"), "%m/%d/%Y")
        self.assertEqual(date_format_to_strptime("d.m.Y"), "%d.%m.%Y")
        # 'j' and 'n' drop the leading zero when rendering, but strptime
        # accepts both padded and unpadded values
        self.assertEqual(date_format_to_strptime("j-n-Y"), "%d-%m-%Y")
        # Anything which is not a specifier stays literal, CJK included
        self.assertEqual(date_format_to_strptime("Y年n月j日"), "%Y年%m月%d日")

    def test_month_names_cannot_be_converted(self):
        self.assertIsNone(date_format_to_strptime("d M Y"))
        self.assertIsNone(date_format_to_strptime("j F Y"))

    def test_escaped_formats_are_declined(self):
        self.assertIsNone(date_format_to_strptime(r"d \d\i m"))


class ParseDateTestCase(SimpleTestCase):
    """What the table renders (SHORT_DATE_FORMAT), parse_date() reads back."""

    LANGUAGES = ["en", "it", "fr", "es", "de", "pt", "ja", "pl", "nl", "zh-hans"]
    DATE = datetime.date(2026, 3, 7)

    def test_round_trip(self):
        for language in self.LANGUAGES:
            with self.subTest(language=language), translation.override(language):
                rendered = formats.date_format(self.DATE, "SHORT_DATE_FORMAT")
                self.assertEqual(parse_date(rendered), self.DATE, rendered)

    def test_month_name_languages_fall_back_to_input_formats(self):
        # 'tr' renders "07 Mar 2026", which cannot be read back; the input
        # formats of the language still work
        with translation.override("tr"):
            self.assertEqual(formats.date_format(self.DATE, "SHORT_DATE_FORMAT"), "07 Mar 2026")
            self.assertEqual(parse_date("07/03/2026"), self.DATE)
            self.assertIsNone(parse_date("07 Mar 2026"))

    def test_iso_always_works(self):
        with translation.override("it"):
            self.assertEqual(parse_date("2026-03-07"), self.DATE)

    def test_not_a_date(self):
        self.assertIsNone(parse_date("rossi"))
        self.assertIsNone(parse_date("2026-02-30"))

"""
Reading what the user types: search terms, numbers and dates (R5).

Every parse_* function returns None when the text does not fit the type,
so the caller can skip a field instead of failing.
"""
import datetime
from decimal import Decimal, InvalidOperation

from django.utils import formats
from django.utils.text import smart_split, unescape_string_literal


def split_alternatives(value, separator):
    """Split a value on the OR separator (R5); without a separator, one alternative."""
    if not separator:
        return [value]
    return [part.strip() for part in value.split(separator) if part.strip()]


def split_terms(value):
    """
    Split a search value into terms, as the Django admin does: words separated
    by spaces, or phrases in quotes ("Mario Rossi").
    """
    terms = []
    for bit in smart_split(value):
        if bit.startswith(('"', "'")) and bit[0] == bit[-1]:
            bit = unescape_string_literal(bit)
        if bit:
            terms.append(bit)
    return terms


def parse_integer(text):
    """An int, or None. Separators follow the active language."""
    try:
        return int(formats.sanitize_separators(text))
    except ValueError:
        return None


def parse_decimal(text):
    """A finite Decimal, or None. Separators follow the active language ("12,50" in Italian)."""
    try:
        value = Decimal(formats.sanitize_separators(text))
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


# Django date format specifiers which have a strptime equivalent; anything
# else (a translated month name, for instance) cannot be read back.
DATE_FORMAT_SPECIFIERS = "aAbcdDeEfFgGhHiIjlLmMnNoOPrsStTUuwWyYzZ"
STRPTIME_EQUIVALENTS = {
    "d": "%d", "j": "%d",
    "m": "%m", "n": "%m",
    "Y": "%Y", "y": "%y",
}


def date_format_to_strptime(date_format):
    """
    Convert a Django date format ("d/m/Y") into the equivalent strptime
    pattern ("%d/%m/%Y"), so a date the table rendered can be read back.

    Returns None when the format holds something strptime cannot match
    (e.g. a translated month name).
    """
    if "\\" in date_format:
        # Escaped literals: don't attempt the conversion
        return None
    pattern = ""
    for ch in date_format:
        if ch in STRPTIME_EQUIVALENTS:
            pattern += STRPTIME_EQUIVALENTS[ch]
        elif ch in DATE_FORMAT_SPECIFIERS:
            return None
        elif ch == "%":
            pattern += "%%"
        else:
            pattern += ch
    return pattern


def parse_date(text):
    """
    A date typed by the user, or None.

    The format the table renders dates with (SHORT_DATE_FORMAT) is tried
    first, since that is what the user sees and copies; DATE_INPUT_FORMATS
    of the active language follow.
    """
    date_formats = []
    rendering_format = date_format_to_strptime(formats.get_format("SHORT_DATE_FORMAT"))
    if rendering_format:
        date_formats.append(rendering_format)
    date_formats += formats.get_format("DATE_INPUT_FORMATS")
    for date_format in date_formats:
        try:
            return datetime.datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None

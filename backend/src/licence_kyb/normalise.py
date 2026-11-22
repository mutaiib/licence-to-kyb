"""Writing variants that do not change a value: digits and dashes as printed on licences."""

from __future__ import annotations

import re
import unicodedata

# Arabic-Indic (U+0660-U+0669) and Eastern Arabic-Indic (U+06F0-U+06F9) digits, as printed on
# many licences.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def ascii_digits(text: str) -> str:
    return text.translate(_DIGITS)


def normalise_number(number: str) -> str:
    """A licence number as written in its pattern: ASCII digits, upper case, one kind of
    dash, no spaces ("cn-1002016" with an en dash and "CN-1002016" are the same number)."""
    value = ascii_digits(unicodedata.normalize("NFKC", number)).upper()
    value = re.sub("[\\u2010-\\u2015\\u2212]", "-", value)
    return re.sub(r"\s+", "", value)

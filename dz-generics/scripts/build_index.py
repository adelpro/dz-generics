"""Build the SQLite index from the ministry nomenclature workbook.

This module owns the fragile part of the build: turning the ministry's header
row into column indices. The workbooks are laid out by hand, so the same
logical column sits at a different index on every sheet -- `Retraits` has no
`OBS` column, which puts its `TYPE` and `STATUT` at 14 and 15 instead of the
16 and 17 they occupy on the other two sheets. Columns are therefore resolved
by matching header text and never by position.

`references/schema.md` records the inspected layout of all three sheets, the
row counts, and the value sets of the `TYPE` and `STATUT` columns. Read it
before changing anything here.
"""

from __future__ import annotations

import unicodedata


def _fold(text: str) -> str:
    """Uppercase and drop accents so `DÉNOMINATION` matches `DENOMINATION`."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def find_header(headers: list[str | None], prefix: str) -> int | None:
    """Index of the first header starting with `prefix`, or `None` if absent.

    Matching is case- and accent-insensitive, so a ministry edit confined to a
    suffix -- `DENOMINATION COMMUNE INTERNATIONALE` becoming
    `DENOMINATION COMMUNE INTERNATIONALE (DCI)` -- cannot break the build.

    Punctuation is *not* folded: a prefix has to reproduce the header's
    punctuation exactly, so match `N°` and not `N`. Prefixes can be ambiguous,
    since `DATE D'ENREGISTREMENT INITIAL` and `DATE D'ENREGISTREMENT  FINAL`
    share a prefix; the first match wins, and a caller that needs the second
    column must pass a longer prefix.

    `headers` is a raw row from openpyxl's `iter_rows`, so the unnamed trailing
    columns arrive as `None`; those are skipped rather than raising.
    """
    wanted = _fold(prefix)
    for index, header in enumerate(headers):
        if header is None:
            continue
        if _fold(str(header)).startswith(wanted):
            return index
    return None

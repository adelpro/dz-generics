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

The index is the **union of the three sheets** (9595 rows), not a join.
`Nomenclature`, `Non Renouveles` and `Retraits` are disjoint lists -- a product
leaves one when it fails to renew or is withdrawn -- so `availability` is
recorded from the sheet a row was read from, never by joining by registration
number. A join produces exactly one row out of 9595.
"""

from __future__ import annotations

import datetime as _datetime
import os
import re
import sqlite3
import tempfile
import unicodedata

import openpyxl

from normalize import dci_keys, dose_key, fold, form_key


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


class BuildError(RuntimeError):
    """The workbook could not be turned into an index we trust.

    Raised rather than writing a partial index: a lookup reading a truncated
    SQLite file would answer "not in the nomenclature" for a product that is
    in it, which is a wrong answer, not a missing one.
    """


SOURCE_URL = (
    "https://www.miph.gov.dz/fr/nomenclature-nationale-des-produits-pharmaceutiques/"
)

# (product column, header prefix). The prefix is resolved with `find_header`
# *per sheet*; a field whose column is absent on a sheet resolves to `None`.
COLUMNS = (
    ("reg_no", "N°ENREGISTREMENT"),
    ("code", "CODE"),
    ("dci", "DENOMINATION COMMUNE INTERNATIONALE"),
    ("brand", "NOM DE MARQUE"),
    ("form", "FORME"),
    ("dosage", "DOSAGE"),
    ("packaging", "CONDITIONNEMENT"),
    ("liste", "LISTE"),
    ("p1", "P1"),
    ("p2", "P2"),
    ("obs", "OBS"),
    ("lab", "LABORATOIRES DETENTEUR"),
    ("country", "PAYS DU LABORATOIRE"),
    ("date_start", "DATE D'ENREGISTREMENT INITIAL"),
    ("date_end", "DATE D'ENREGISTREMENT  FINAL"),
    ("type", "TYPE"),
    ("statut", "STATUT"),
    ("shelf_life", "DUREE DE STABILITE"),
    ("withdrawn_at", "DATE DE RETRAIT"),
    ("withdrawn_reason", "MOTIF DE RETRAIT"),
)
_PREFIX = dict(COLUMNS)

# Columns present on every sheet. `obs`/`date_end`/`shelf_life` and the two
# withdrawal columns are per-sheet and declared below instead.
_COMMON_REQUIRED = (
    "reg_no", "code", "dci", "brand", "form", "dosage", "packaging",
    "liste", "p1", "p2", "lab", "country", "date_start", "type", "statut",
)

# `match` is a prefix of the sheet name -- never an exact string, because
# `Non Renouvelés ` carries a trailing space and a future release may change it.
_SHEET_SPECS = (
    {
        "key": "main",
        "match": "Nomenclature",
        "availability": "active",
        "required": _COMMON_REQUIRED + ("obs", "date_end", "shelf_life"),
    },
    {
        "key": "not_renewed",
        "match": "Non Renouvel",
        "availability": "not_renewed",
        "required": _COMMON_REQUIRED + ("obs", "date_end"),
    },
    {
        "key": "withdrawn",
        "match": "Retraits",
        "availability": "withdrawn",
        "required": _COMMON_REQUIRED + ("withdrawn_at", "withdrawn_reason"),
    },
)

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE product (
  id INTEGER PRIMARY KEY,
  reg_no TEXT, code TEXT,
  dci TEXT, dci_key TEXT, dci_base_key TEXT,
  brand TEXT, brand_key TEXT,
  form TEXT, form_key TEXT,
  dosage TEXT, dose_key TEXT,
  packaging TEXT, liste TEXT, p1 TEXT, p2 TEXT, obs TEXT,
  lab TEXT, country TEXT,
  date_start TEXT, date_end TEXT,
  type TEXT, statut TEXT, shelf_life TEXT,
  availability TEXT,
  withdrawn_at TEXT, withdrawn_reason TEXT
);
CREATE INDEX idx_brand ON product(brand_key);
CREATE INDEX idx_dci   ON product(dci_base_key);
CREATE INDEX idx_code  ON product(code);
CREATE INDEX idx_reg   ON product(reg_no);
"""

_INSERT = """
INSERT INTO product (
  reg_no, code, dci, dci_key, dci_base_key,
  brand, brand_key, form, form_key, dosage, dose_key,
  packaging, liste, p1, p2, obs, lab, country,
  date_start, date_end, type, statut, shelf_life,
  availability, withdrawn_at, withdrawn_reason
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# A header row carries at least this many of the prefixes above. The real rows
# carry 17-18; the institutional banner above them carries none. A threshold
# rather than an exact count, because the exact count moves between releases.
_HEADER_MIN_MATCHES = 8

# `( 5425 DE )` in the title row above each header.
_DECLARED_RE = re.compile(r"\(\s*(\d+)\s+DE\s*\)")
_VERSION_RE = re.compile(r"([^\d\s]+)\s+(\d{4})")

# A build with fewer than this fraction of the previous build's rows is a
# collapse, not an editorial shrink. It is deliberately conservative: normal
# ministry revisions add and drop rows every release, so a strict "any
# decrease" guard would block a legitimate refresh. Exact per-sheet truncation
# is caught separately by the declared-count check; this backstop catches a
# total that moves for a reason the per-sheet check cannot see (union logic, a
# sheet silently disappearing, the workbook being swapped for a fragment).
_ROW_COUNT_FLOOR = 0.8

# The sheet name spells `Aout` without the accent; the label must carry it.
_MONTHS = {
    "JANVIER": "Janvier", "FEVRIER": "Février", "MARS": "Mars", "AVRIL": "Avril",
    "MAI": "Mai", "JUIN": "Juin", "JUILLET": "Juillet", "AOUT": "Août",
    "SEPTEMBRE": "Septembre", "OCTOBRE": "Octobre", "NOVEMBRE": "Novembre",
    "DECEMBRE": "Décembre",
}


def _clean(value: object) -> str:
    """Every cell as stripped text; `None` and blank both become `""`."""
    if value is None:
        return ""
    return str(value).strip()


def _cell(row: tuple, index: int | None) -> object:
    """Cell at `index`, or `None` when the column is absent or the row short."""
    if index is None or index >= len(row):
        return None
    return row[index]


def _date_text(value: object) -> str:
    """A date cell as ISO text; strings and blanks pass through.

    `DATE DE RETRAIT` holds 1132 strings among its datetimes, so a date cell
    cannot be assumed to be a `datetime`.
    """
    if value is None:
        return ""
    if isinstance(value, _datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, _datetime.date):
        return value.isoformat()
    return str(value).strip()


def _header_index(all_rows: list[tuple]) -> int | None:
    """First row carrying at least `_HEADER_MIN_MATCHES` known prefixes."""
    for index, row in enumerate(all_rows):
        matches = sum(1 for _, prefix in COLUMNS
                      if find_header(row, prefix) is not None)
        if matches >= _HEADER_MIN_MATCHES:
            return index
    return None


def _declared_count(title_rows: list[tuple]) -> int | None:
    """Last `( N DE )` declaration in the rows above the header."""
    declared = None
    for row in title_rows:
        for cell in row:
            if cell is None:
                continue
            for match in _DECLARED_RE.finditer(str(cell)):
                declared = int(match.group(1))
    return declared


def _version_label(sheet_name: str) -> str:
    match = _VERSION_RE.search(sheet_name)
    if match is None:
        raise BuildError(f"no version in sheet name {sheet_name!r}")
    month = _MONTHS.get(_fold(match.group(1)))
    if month is None:
        raise BuildError(f"unknown month {match.group(1)!r} in {sheet_name!r}")
    return f"{month} {match.group(2)}"


def _sheet_names(sheetnames: list[str]) -> dict[str, str]:
    """The three working sheets, matched by name prefix."""
    found = {}
    for spec in _SHEET_SPECS:
        matches = [name for name in sheetnames if name.startswith(spec["match"])]
        if not matches:
            raise BuildError(
                f"no sheet whose name starts with {spec['match']!r}")
        found[spec["key"]] = matches[0]
    return found


def _read_sheet(ws, spec: dict) -> tuple[list[tuple], int]:
    """Parse one sheet into insert-ready rows; returns `(rows, unparsed)`.

    Columns are resolved on this sheet's own header, so `OBS` resolving to
    `None` on `Retraits` is a fact about `Retraits` and not about the caller.
    """
    all_rows = list(ws.iter_rows(values_only=True))
    sheet_name = getattr(ws, "title", spec["key"])
    header_index = _header_index(all_rows)
    if header_index is None:
        raise BuildError(f"{sheet_name!r}: no header row found")
    header = all_rows[header_index]
    resolved = {field: find_header(header, prefix) for field, prefix in COLUMNS}
    for field in spec["required"]:
        if resolved.get(field) is None:
            raise BuildError(
                f"{sheet_name!r}: required column {_PREFIX[field]!r} is missing")

    declared = _declared_count(all_rows[:header_index])
    if declared is None:
        raise BuildError(
            f"{sheet_name!r}: no '( N DE )' row count above the header")

    records = []
    unparsed = 0
    for row in all_rows[header_index + 1:]:
        if not any(_clean(cell) for cell in row):
            continue
        raw = {field: _cell(row, index) for field, index in resolved.items()}
        dci = _clean(raw["dci"])
        exact, base = dci_keys(dci)
        dosage = _clean(raw["dosage"])
        strength = dose_key(dosage)
        if strength is None:
            unparsed += 1
        records.append((
            _clean(raw["reg_no"]), _clean(raw["code"]),
            dci, exact, base,
            _clean(raw["brand"]), fold(raw["brand"]),
            _clean(raw["form"]), form_key(raw["form"]),
            dosage, strength,
            _clean(raw["packaging"]), _clean(raw["liste"]),
            _clean(raw["p1"]), _clean(raw["p2"]), _clean(raw["obs"]),
            _clean(raw["lab"]), _clean(raw["country"]),
            _date_text(raw["date_start"]), _date_text(raw["date_end"]),
            _clean(raw["type"]).upper(), _clean(raw["statut"]).upper(),
            _clean(raw["shelf_life"]),
            spec["availability"],
            _date_text(raw["withdrawn_at"]), _clean(raw["withdrawn_reason"]),
        ))

    if len(records) != declared:
        raise BuildError(
            f"{sheet_name!r}: parsed {len(records)} data rows but the sheet "
            f"declares {declared}")
    return records, unparsed


def _write_index(out_sqlite: str, records: list[tuple], meta: dict) -> None:
    """Write to a sibling temp file, then replace the target atomically."""
    out_sqlite = os.path.abspath(out_sqlite)
    directory = os.path.dirname(out_sqlite) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=directory, prefix=".nomenclature-", suffix=".sqlite.tmp")
    os.close(fd)
    connection = None
    try:
        connection = sqlite3.connect(tmp_path)
        connection.executescript(_SCHEMA)
        connection.executemany(_INSERT, records)
        connection.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)", meta.items())
        connection.commit()
        connection.close()
        connection = None
        os.replace(tmp_path, out_sqlite)
    except BaseException:
        if connection is not None:
            connection.close()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def build(source_xlsx: str, out_sqlite: str,
          previous_row_count: int | None = None) -> dict:
    """Build the index at `out_sqlite` from `source_xlsx`.

    Returns `{"row_count", "withdrawn", "not_renewed", "version_label"}`.
    `previous_row_count`, when given, is the row count of the index being
    replaced; a build that loses more than `_ROW_COUNT_FLOOR` of it raises
    `BuildError` instead of overwriting a good index with a truncated one.

    The workbook is closed before the SQLite file is written, so a workbook
    failure cannot strand a half-written index.
    """
    wb = openpyxl.load_workbook(source_xlsx, read_only=True, data_only=True)
    try:
        names = _sheet_names(wb.sheetnames)
        records: list[tuple] = []
        availability_counts = {"active": 0, "not_renewed": 0, "withdrawn": 0}
        unparsed_total = 0
        for spec in _SHEET_SPECS:
            sheet_records, unparsed = _read_sheet(wb[names[spec["key"]]], spec)
            records.extend(sheet_records)
            availability_counts[spec["availability"]] = len(sheet_records)
            unparsed_total += unparsed
    finally:
        wb.close()

    row_count = len(records)
    if previous_row_count is not None \
            and row_count < previous_row_count * _ROW_COUNT_FLOOR:
        raise BuildError(
            f"built {row_count} rows against a previous {previous_row_count}; "
            f"below the {_ROW_COUNT_FLOOR:.0%} floor, so the index was not "
            f"written")

    meta = {
        "version_label": _version_label(names["main"]),
        "source_url": SOURCE_URL,
        "source_filename": os.path.basename(source_xlsx),
        "built_at": _datetime.datetime.now().isoformat(timespec="seconds"),
        "row_count": str(row_count),
        "main_sheet": names["main"],
        "unparsed_doses": str(unparsed_total),
    }
    _write_index(out_sqlite, records, meta)

    return {
        "row_count": row_count,
        "withdrawn": availability_counts["withdrawn"],
        "not_renewed": availability_counts["not_renewed"],
        "version_label": meta["version_label"],
    }


def _previous_row_count(out_sqlite: str) -> int | None:
    """`meta.row_count` of an existing index, or `None` if unreadable."""
    if not os.path.exists(out_sqlite):
        return None
    try:
        connection = sqlite3.connect(out_sqlite)
        try:
            row = connection.execute(
                "SELECT value FROM meta WHERE key='row_count'").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return None


def _main(argv: list[str] | None = None) -> int:
    import sys

    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: build_index.py SOURCE.xlsx [OUT.sqlite]")
        return 2
    source = argv[0]
    out = argv[1] if len(argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "nomenclature.sqlite")

    stats = build(source, out, previous_row_count=_previous_row_count(out))
    active = (stats["row_count"] - stats["not_renewed"] - stats["withdrawn"])
    unparsed = None
    connection = sqlite3.connect(out)
    try:
        row = connection.execute(
            "SELECT value FROM meta WHERE key='unparsed_doses'").fetchone()
        unparsed = row[0] if row else "?"
    finally:
        connection.close()

    print(f"wrote {out}")
    print(f"  version_label  : {stats['version_label']}")
    print(f"  row_count      : {stats['row_count']}")
    print(f"  active         : {active}")
    print(f"  not_renewed    : {stats['not_renewed']}")
    print(f"  withdrawn      : {stats['withdrawn']}")
    print(f"  unparsed_doses : {unparsed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

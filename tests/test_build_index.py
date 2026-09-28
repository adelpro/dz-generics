import os

import pytest

from conftest import SOURCE_XLSX


# The ministry workbook is gitignored, so a fresh clone has no source to build
# from. Only the tests that actually open it are skipped; the `find_header`
# tests exercise a pure function and must keep running.
requires_workbook = pytest.mark.skipif(
    not os.path.exists(SOURCE_XLSX),
    reason=f"ministry workbook not downloaded: {SOURCE_XLSX}",
)


def test_headers_resolve_by_prefix():
    """Header lookup must survive the full-string being longer than expected."""
    from build_index import find_header
    headers = ["N°", "N°ENREGISTREMENT", "CODE",
               "DENOMINATION COMMUNE INTERNATIONALE (DCI)", "NOM DE MARQUE"]
    assert find_header(headers, "DENOMINATION COMMUNE") == 3
    assert find_header(headers, "NOM DE MARQUE") == 4
    assert find_header(headers, "DOSAGE") is None


def test_find_header_ignores_case_and_accents():
    """A ministry rename to different casing or accents must not break the build."""
    from build_index import find_header
    headers = ["DÉNOMINATION COMMUNE INTERNATIONALE", "pays du laboratoire"]
    assert find_header(headers, "denomination commune") == 0
    assert find_header(headers, "PAYS DU LABORATOIRE") == 1


def test_find_header_skips_blank_cells_and_takes_the_first_match():
    """Blank cells arrive from openpyxl as None, and prefixes can be ambiguous.

    `DATE D'ENREGISTREMENT INITIAL` and `DATE D'ENREGISTREMENT  FINAL` both
    start with `DATE D'ENREGISTREMENT`, so a caller wanting the second one
    has to pass a longer prefix. That is the caller's job; this pins the
    contract so the ambiguity is a documented choice, not a surprise.
    """
    from build_index import find_header
    headers = [None, "CODE", None, "DATE D'ENREGISTREMENT INITIAL ",
               "DATE D'ENREGISTREMENT  FINAL "]
    assert find_header(headers, "CODE") == 1
    assert find_header(headers, "DATE D'ENREGISTREMENT") == 3
    assert find_header(headers, "DATE D'ENREGISTREMENT  FINAL") == 4
    assert find_header(headers, "INEXISTANT") is None
    # Without the None guard the blank cell would fold to the string "NONE"
    # and a broad prefix could match it.
    assert find_header([None, "CODE"], "No") is None


@requires_workbook
def test_build_reads_real_workbook(tmp_path):
    """Exact, not 'roughly': a truncated sheet must fail this, and the three
    sheets sum to 9595 (5425 + 1491 + 2679)."""
    from build_index import build
    out = tmp_path / "n.sqlite"
    stats = build(SOURCE_XLSX, str(out))
    assert stats["row_count"] == 9595
    assert stats["version_label"] == "Ao\u00fbt 2026"
    assert out.exists()


@requires_workbook
def test_build_fails_loudly_when_row_count_collapses(tmp_path):
    """A silently-truncated index is worse than no index."""
    from build_index import BuildError, build
    with pytest.raises(BuildError):
        build(SOURCE_XLSX, str(tmp_path / "n.sqlite"), previous_row_count=50000)


@requires_workbook
def test_row_count_floor_allows_the_same_count_but_not_a_thirty_percent_drop(
        tmp_path):
    """`_ROW_COUNT_FLOOR = 0.8` is the implementer's interpretation, so pin it.

    `test_build_fails_loudly_when_row_count_collapses` passes for any floor
    above 0.19 (`previous_row_count=50000`), so it says nothing about the
    threshold's meaning. Here the current workbook's own count must not raise,
    while a previous count a ~30% drop below it must.
    """
    from build_index import BuildError, build
    stats = build(SOURCE_XLSX, str(tmp_path / "same.sqlite"),
                  previous_row_count=9595)
    assert stats["row_count"] == 9595
    with pytest.raises(BuildError):
        # 9595 is ~70% of 13700: a 30% drop, well below the 0.8 floor.
        build(SOURCE_XLSX, str(tmp_path / "dropped.sqlite"),
              previous_row_count=13700)


@requires_workbook
def test_availability_comes_from_the_source_sheet(tmp_path):
    """Review Focus #5. The three sheets are disjoint, so a join yields
    nothing and a main-sheet-only build would report POLARAMINE as
    'not in the nomenclature'."""
    import sqlite3
    from build_index import build
    out = tmp_path / "n.sqlite"
    stats = build(SOURCE_XLSX, str(out))
    con = sqlite3.connect(out)
    counts = dict(con.execute(
        "SELECT availability, COUNT(*) FROM product GROUP BY availability"))
    assert counts["withdrawn"] > 2000
    assert counts["not_renewed"] > 1000
    assert counts["active"] > 5000
    # POLARAMINE's brand appears in *both* off-main sheets -- one not-renewed
    # row and three withdrawn rows -- so the assertion is over the set, not a
    # positional `fetchall()[0]` that depends on insertion order.
    avails = {row[0] for row in con.execute(
        "SELECT availability FROM product WHERE brand_key='POLARAMINE'")}
    assert avails == {"not_renewed", "withdrawn"}, (
        "POLARAMINE must stay findable even though it is off the main list")


@requires_workbook
def test_type_and_statut_columns_hold_only_domain_values(tmp_path):
    """The brief's highest-value behaviour: the per-sheet TYPE/STATUT columns.

    `Retraits` has no `OBS` column, so its TYPE/STATUT sit two columns to the
    left of the other sheets'. Resolving them once from the main sheet and
    reusing those indices silently writes withdrawal dates into `type` and the
    withdrawal-motif paragraphs into `statut`, and every positional or
    main-sheet-only test still passes. Pinning the whole table's domain --
    not one sheet's -- makes any such regression fail immediately.
    """
    import sqlite3
    from build_index import build
    out = tmp_path / "n.sqlite"
    build(SOURCE_XLSX, str(out))
    con = sqlite3.connect(out)

    types = {row[0] for row in con.execute("SELECT DISTINCT type FROM product")}
    statuts = {row[0] for row in
               con.execute("SELECT DISTINCT statut FROM product")}
    assert types <= {"GE", "RE", "BIO", ""}, types
    assert statuts <= {"F", "I", ""}, statuts

    # A domain check alone also passes if the columns are empty everywhere, so
    # pin that the values are actually carried, including on the sheet whose
    # columns sit at different indices.
    assert con.execute(
        "SELECT COUNT(*) FROM product WHERE type<>''").fetchone()[0] > 9000
    assert con.execute(
        "SELECT COUNT(*) FROM product WHERE statut<>''").fetchone()[0] > 9000
    assert con.execute(
        "SELECT COUNT(*) FROM product WHERE availability='withdrawn' "
        "AND type<>''").fetchone()[0] > 2000


@requires_workbook
def test_type_keeps_bio_distinct_from_ge(tmp_path):
    """A biosimilar is not interchangeable with a chemical generic."""
    import sqlite3
    from build_index import build
    out = tmp_path / "n.sqlite"
    build(SOURCE_XLSX, str(out))
    con = sqlite3.connect(out)
    bio = con.execute("SELECT COUNT(*) FROM product WHERE type='BIO'").fetchone()[0]
    assert bio > 10

import pytest

from conftest import SOURCE_XLSX


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


def test_build_reads_real_workbook(tmp_path):
    """Exact, not 'roughly': a truncated sheet must fail this, and the three
    sheets sum to 9595 (5425 + 1491 + 2679)."""
    from build_index import build
    out = tmp_path / "n.sqlite"
    stats = build(SOURCE_XLSX, str(out))
    assert stats["row_count"] == 9595
    assert stats["version_label"] == "Ao\u00fbt 2026"
    assert out.exists()


def test_build_fails_loudly_when_row_count_collapses(tmp_path):
    """A silently-truncated index is worse than no index."""
    from build_index import BuildError, build
    with pytest.raises(BuildError):
        build(SOURCE_XLSX, str(tmp_path / "n.sqlite"), previous_row_count=50000)


def test_availability_comes_from_the_source_sheet(tmp_path):
    """Review Focus #5. The three sheets are disjoint, so a join yields
    nothing and a main-sheet-only build would report POLARAMINE — which sits
    only in the not-renewed list — as 'not in the nomenclature'."""
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
    polaramine = con.execute(
        "SELECT availability FROM product WHERE brand_key='POLARAMINE'"
    ).fetchall()
    assert polaramine, "POLARAMINE must be findable even though it is off the main list"
    assert polaramine[0][0] == "not_renewed"


def test_type_keeps_bio_distinct_from_ge(tmp_path):
    """A biosimilar is not interchangeable with a chemical generic."""
    import sqlite3
    from build_index import build
    out = tmp_path / "n.sqlite"
    build(SOURCE_XLSX, str(out))
    con = sqlite3.connect(out)
    bio = con.execute("SELECT COUNT(*) FROM product WHERE type='BIO'").fetchone()[0]
    assert bio > 10

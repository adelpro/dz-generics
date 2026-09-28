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

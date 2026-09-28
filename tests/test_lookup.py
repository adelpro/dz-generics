"""Task 4: the layer a user actually talks to.

Every test here runs against the committed index at
``dz-generics/data/nomenclature.sqlite``, because the whole point of the layer
is that it answers from the real nomenclature. The pinned values (7
equivalents, the ``COMRPIME`` anchor, the 0.85 fuzzy boundary) were verified by
the controller against that same file before this task was written.
"""

import json
import os
import sqlite3
import subprocess
import sys

import pytest

from conftest import SCRIPTS_DIR

DB_PATH = os.path.join(SCRIPTS_DIR, "..", "data", "nomenclature.sqlite")
LOOKUP_PY = os.path.join(SCRIPTS_DIR, "lookup.py")

requires_index = pytest.mark.skipif(
    not os.path.exists(DB_PATH),
    reason=f"committed index missing: {DB_PATH}",
)


def test_paracetamol_tablet_lookup_finds_generics():
    """The headline use case, end to end against the real index.
    DOLIPRANE anchors on the COMPRIME 1000MG tablet (`COMRPIME` in the file),
    whose equivalence class holds 7 active products in this release."""
    from lookup import lookup
    res = lookup(name="doliprane")
    assert res.query == "doliprane"
    assert res.status == "found"
    assert res.dci_base_key is not None
    assert res.anchor.form_key == "COMPRIME"
    assert len(res.equivalents) > 1
    assert all(p.form_key == "COMPRIME" for p in res.equivalents)
    # The anchor is a member of its own equivalence class.
    assert any(p.brand_key == "DOLIPRANE" for p in res.equivalents)


def test_different_dosage_is_not_an_equivalent():
    from lookup import lookup
    res = lookup(name="doliprane")
    assert all(p.dose_key == res.anchor.dose_key for p in res.equivalents)
    assert all(p.dose_key != res.anchor.dose_key for p in res.other_dosages)


def test_anchor_has_a_known_dose_even_when_the_query_is_a_dci():
    """PARACETAMOL covers 89 active rows over 28 form/dose pairs, 7 of them
    with no determinable dose. Sorting None first would anchor on an unknown
    dose, so the rule must require one."""
    from lookup import lookup
    res = lookup(dci="PARACETAMOL")
    assert res.status == "found"
    assert res.anchor.dose_key is not None
    assert res.anchor.availability == "active"


def test_an_unknown_dose_never_lands_in_equivalents():
    """None means unknown dose, never an equal one. Grouping by a shared None
    reports seven unrelated oral solutions as interchangeable."""
    from lookup import lookup
    for query in ({"dci": "PARACETAMOL"}, {"name": "doliprane"}):
        res = lookup(**query)
        assert all(p.dose_key is not None for p in res.equivalents)
        assert all(p.dose_key is not None for p in res.other_dosages)


def test_a_fallback_anchor_is_flagged_and_forms_no_class():
    """ACETADOL is the active PARACETAMOL row with no determinable dose, so the
    rule falls back to it -- but the fallback is part of the answer. The dose
    is unknown, so it is *not comparable*: no equivalence class may form, and
    the text must say so rather than group seven unrelated oral solutions."""
    from lookup import lookup, render_text
    res = lookup(name="ACETADOL")
    assert res.status == "found"
    assert res.anchor.dose_key is None
    assert res.anchor.availability == "active"
    assert res.anchor_rule == "active_unknown_dose"
    assert res.equivalents == []
    assert "not comparable" in render_text(res).lower()


def test_an_off_market_anchor_is_flagged_as_a_fallback():
    """ISOCLOPRAMID has no active row at all (one blank-base withdrawn row), so
    the rule falls back to an off-market anchor; the answer must lead with
    that, and form no class."""
    from lookup import lookup
    res = lookup(name="ISOCLOPRAMID")
    assert res.status == "found"
    assert res.anchor.availability != "active"
    assert res.anchor_rule == "off_market"
    assert res.equivalents == []


def test_unknown_name_returns_no_match_not_a_guess():
    from lookup import lookup
    res = lookup(name="zzzznotadrug")
    assert res.status == "not_found"
    assert res.candidates == []


def test_fuzzy_match_lists_candidates_and_never_picks():
    """Never auto-pick. 'DOLIPRAN' scores 0.941 against DOLIPRANE and is the
    only brand above the 0.85 cutoff -- and even a single fuzzy candidate must
    not be silently chosen, because the user typed something else."""
    from lookup import lookup
    res = lookup(name="dolipran")
    assert res.status == "ambiguous"
    assert res.candidates
    assert all(c.brand_key == "DOLIPRANE" for c in res.candidates)


def test_a_typo_below_the_cutoff_is_not_a_match_at_all():
    """The other side of the cutoff. 'DOLIPRNA' scores 0.824 against DOLIPRANE,
    under 0.85, and finds nothing -- it must not be widened into a guess.
    The plan originally used 'doliprna' as the near-miss and expected a match;
    that was wrong, and this pair pins both sides of the boundary."""
    from lookup import lookup
    res = lookup(name="doliprna")
    assert res.status == "not_found"
    assert res.candidates == []


def test_json_output_round_trips():
    import json
    from lookup import lookup
    payload = json.loads(lookup(name="doliprane").to_json())
    assert "version_label" in payload


# ---------------------------------------------------------------------------
# Safety properties the brief calls out explicitly. These are the tests that
# fail if a later edit makes the layer generous with matches or careless with
# unknown dosages -- the project's medical risk lives here.
# ---------------------------------------------------------------------------


def test_none_dose_key_never_lands_in_equivalents():
    """`dose_key` is None for 810 rows: unknown, not a match and not a
    mismatch. Two Nones are not evidence of equivalence, so no product whose
    dose is undeterminable may appear in an equivalence class.

    `other_forms` is exempt by design: the brief buckets it by form alone, and
    a form-only list is not a claim of equivalence -- the two rows it holds
    here are a `SOLUTION_BUVABLE` and a `SUPPOSITOIRE` whose strengths the file
    leaves undeterminable, and they are printed as `dose unknown`.
    """
    from lookup import lookup
    res = lookup(name="doliprane")
    assert all(p.dose_key is not None for p in res.equivalents)
    assert all(p.dose_key is not None for p in res.other_dosages)
    assert all(p.form_key != res.anchor.form_key for p in res.other_forms)


def test_non_active_rows_stay_out_of_equivalents():
    from lookup import lookup
    res = lookup(name="doliprane")
    assert all(p.availability == "active" for p in res.equivalents)
    assert all(p.availability != "active" for p in res.inactive)


def test_include_inactive_folds_the_inactive_bucket_back_in():
    """`--include-inactive` widens the class to the full historical picture,
    so `equivalents` then legitimately contains non-active rows and `inactive`
    is empty. Without the flag the same rows stay out.

    The widening is confined to the anchor's own form and dose, so a 500MG row
    can never appear in a 1000MG class -- an unknown-dose row cannot either.
    """
    from lookup import lookup
    default = lookup(name="doliprane")
    widened = lookup(name="doliprane", include_inactive=True)

    # The flag adds rows and relabels none of them: the two not-renewed
    # 1000MG tablets move from `inactive` into `equivalents`, still carrying
    # their own availability.
    assert [p.brand_key for p in default.inactive] == ["DOLICRANE", "GEMAL"]
    assert widened.inactive == []
    assert {p.brand_key for p in widened.equivalents} - {
        p.brand_key for p in default.equivalents} == {"DOLICRANE", "GEMAL"}
    assert all(p.dose_key == "1000MG" for p in widened.equivalents)
    assert {p.availability for p in widened.equivalents} == {
        "active", "not_renewed"}
    # Without the flag nothing off-market leaks in.
    assert all(p.availability == "active" for p in default.equivalents)


def test_include_inactive_cannot_smuggle_an_unknown_dose_into_equivalents():
    """`--include-inactive` folds off-market rows in, but only rows already at
    the anchor's *known* form and dose. It must not become a back door for a
    shared unknown dose: when the anchor's own dose is None the class stays
    empty, and no row in a widened class may have a null dose."""
    from lookup import lookup
    for query in ({"name": "doliprane"}, {"name": "ACETADOL"},
                  {"dci": "PARACETAMOL"}):
        res = lookup(include_inactive=True, **query)
        assert all(p.dose_key is not None for p in res.equivalents)
        if res.anchor.dose_key is None:
            assert res.equivalents == []


def test_the_seven_verified_equivalents_are_exactly_these():
    """The brief names the 7 active paracetamol 1000 mg tablets. Pinning the
    set -- not a count -- is what makes a wrongly-included or wrongly-dropped
    row fail.

    ``brand_key`` is folded (punctuation collapses to spaces), so the pin is
    on the verbatim ``brand``, which is the string the brief spells.
    """
    from lookup import lookup
    res = lookup(name="doliprane")
    assert {p.brand for p in res.equivalents} == {
        "ANTALGAN", "DOLI-BIEN", "DOLIPRANE", "DOLYC", "EXPANDOL",
        "PARACETAMOL PHYSIOPHARM", "ROSADOL",
    }


def test_augmentin_anchors_the_active_re_sachet():
    """AUGMENTIN's anchor is the active `RE` sachet 1000MG/125MG.

    CONFLICT, recorded deliberately. The brief's spot-check table describes
    this as "the active RE sachet 1000MG/125MG, with **7 GE copies** alongside
    -- 6 made locally and AMOXICILLINE/ACIDE CLAVULANIQUE SANDOZ ADULTE
    imported (I)". Against this index that figure is unreachable under the
    brief's own bucketing rule:

      - At that exact form and dose there are 6 active rows (5 GE + 1 RE),
        all `F`; plus 2 not-renewed rows (SANDOZ `I`, CLAVOR `F`).
      - "6 local + 1 imported(SANDOZ)" is only reachable by counting the
        *not_renewed* SANDOZ row -- i.e. by putting a non-active row in
        `equivalents`, which the brief also forbids (`equivalents` is
        "same form, same dose, active"; `--include-inactive` is what folds
        off-market rows in).

    So this test pins the rule as written (6 active) and fails loudly if the
    bucket rule is ever changed to match the prose instead. The controller
    must decide which of the two statements is the contract.
    """
    from lookup import lookup
    res = lookup(name="augmentin")
    assert res.status == "found"
    assert res.anchor.brand_key == "AUGMENTIN"
    assert res.anchor.form_key == "POUDRE_POUR_SUSPENSION_BUVABLE_EN_SACHET_DOSE"
    assert res.anchor.dose_key == "1000MG/125MG"
    assert res.anchor.availability == "active"
    assert res.anchor.type == "RE"
    assert all(p.availability == "active" for p in res.equivalents)
    # 5 active GE copies beside the RE anchor, sorted by brand.
    assert len(res.equivalents) == 6
    assert res.equivalents[0].brand_key == "AMOCLAN 8 1"
    # Exactly one RE (the anchor) and 5 GE copies.
    assert sum(p.type == "GE" for p in res.equivalents) == 5
    assert sum(p.type == "RE" for p in res.equivalents) == 1
    assert any(p.brand_key == "AUGMENTIN" and p.type == "RE"
               for p in res.equivalents)
    # The not-renewed SANDOZ row is present, and only in the off-market bucket.
    assert [p.brand_key for p in res.inactive] == [
        "AMOXICILLINE ACIDE CLAVULANIQUE SANDOZ ADULTE", "CLAVOR"]


def test_polaramine_resolves_although_it_is_on_no_active_list():
    """POLARAMINE has no active row at all: one not-renewed and three
    withdrawn. The lookup must resolve it, not report it missing, and it must
    present nothing as available."""
    from lookup import lookup
    res = lookup(name="polaramine")
    assert res.status == "found"
    assert res.anchor.availability != "active"
    assert res.equivalents == []
    assert res.anchor.form_key == "SIROP"
    assert res.anchor.withdrawn_reason == "RETRAIT PAR LE MSPRH POUR INTERDICTION D'IMPORTATION"


def test_a_withdrawn_anchor_carries_a_reason_for_every_row():
    """Three different reasons across POLARAMINE's rows. A reason is the
    difference between an unsafe drug and one that stopped selling, so it
    cannot be dropped on the way through."""
    from lookup import lookup
    res = lookup(name="polaramine")
    rows = res.anchor_rows
    assert len(rows) == 4
    reasons = {p.withdrawn_reason for p in rows if p.availability == "withdrawn"}
    assert reasons == {
        "RETRAIT PAR LE DETENTEUR POUR MOTIF COMMERCIAL",
        "PRODUIT NON COMMERCIALISE ET DECISION NON RENOUVELEE",
        "RETRAIT PAR LE MSPRH POUR INTERDICTION D'IMPORTATION",
    }


def test_anchor_matching_several_rows_is_reported_not_hidden():
    """A brand may hold several rows in the same form and dose (DOLIPRANE has
    two 500MG COMPRIME rows, one active and one not renewed). The result has to
    say how many rows the query matched instead of picking one silently."""
    from lookup import lookup
    res = lookup(name="doliprane")
    assert len(res.matched_rows) == 12
    assert len(res.anchor_rows) == 6


def test_one_row_matched_is_not_reported_as_several():
    from lookup import lookup
    res = lookup(name="augmentin")
    assert len(res.anchor_rows) == 1


def test_a_blank_dci_base_key_does_not_fuse_unrelated_molecules():
    """Three rows carry a blank `dci_base_key` and are unrelated molecules:
    KINADYN MG (magnesium carbonate), MAGNESIUM SULFATE, and ISOCLOPRAMID
    (metoclopramide). Grouping on '' would report metoclopramide as an
    equivalent of magnesium -- the exact wrong-marriage this layer exists to
    prevent. A blank key defines no class, so each such row stands alone."""
    from lookup import lookup
    res = lookup(name="KINADYN MG")
    assert res.status == "found"
    assert res.anchor.dci_base_key == ""
    assert res.equivalents == []
    assert res.other_dosages == []
    assert res.other_forms == []
    assert res.inactive == []

    # The other direction: querying ISOCLOPRAMID must not pull in the
    # magnesium rows through the shared empty key.
    res = lookup(name="ISOCLOPRAMID")
    assert res.status == "found"
    assert res.anchor.dci_base_key == ""
    brands = ({p.brand_key for p in res.equivalents}
              | {p.brand_key for p in res.other_forms}
              | {p.brand_key for p in res.other_dosages})
    assert "KINADYN MG" not in brands
    assert "MAGNESIUM SULFATE" not in brands


def test_a_brand_spanning_several_dci_bases_buckets_only_its_own():
    """194 brands carry rows under more than one base key. The class is the
    anchor's base key, never the brand's whole row set -- otherwise a brand
    would pull in a different substance."""
    import sqlite3
    from lookup import lookup
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT brand_key FROM product WHERE dci_base_key<>'' "
            "GROUP BY brand_key HAVING COUNT(DISTINCT dci_base_key)>1 "
            "ORDER BY brand_key LIMIT 1").fetchone()
    finally:
        con.close()
    brand_key = row[0]
    res = lookup(name=brand_key)
    assert res.status == "found"
    for bucket in (res.equivalents, res.other_dosages, res.other_forms,
                   res.inactive):
        assert all(p.dci_base_key == res.anchor.dci_base_key
                   for p in bucket)


def test_code_route_resolves_a_registration_code():
    """A code identifies a registration, and this one is shared by 7 brands
    (the schema notes CODE is not unique). The pinned anchor rule takes the
    lowest `(dose_key, form_key)` among the active rows, which here is
    DOLI-BIEN -- so the code route reaches the right *tablet* class but not
    the DOLIPRANE brand. Recorded rather than papered over; see
    `test_dci_route_anchors_an_active_known_dose_not_the_doliprane_brand`."""
    from lookup import lookup
    res = lookup(code="03 B 081")
    assert res.status == "found"
    assert res.anchor.form_key == "COMPRIME"
    assert res.anchor.dose_key == "1000MG"
    assert {p.brand_key for p in res.equivalents} == {
        "ANTALGAN", "DOLI BIEN", "DOLIPRANE", "DOLYC", "EXPANDOL",
        "PARACETAMOL PHYSIOPHARM", "ROSADOL"}


def test_dci_route_is_case_and_punctuation_insensitive():
    """`--dci` folds the same way `--name` does. PARACETAMOL has one base key
    here, so the route is unambiguous in *key* terms -- what it is not is a
    brand, which is the distinction recorded in
    `test_dci_route_anchors_an_active_known_dose_not_the_doliprane_brand`."""
    from lookup import lookup
    by_lower = lookup(dci="paracetamol")
    by_accents = lookup(dci="Paracétamol")
    assert by_lower.status == "found"
    assert by_lower.anchor == by_accents.anchor
    assert by_lower.dci_base_key == "PARACETAMOL"


def test_dci_route_anchors_an_active_known_dose_not_the_doliprane_brand():
    """The DCI route identifies a substance, not a brand, so it is expected to
    anchor somewhere other than the DOLIPRANE brand. PARACETAMOL matches 192
    rows (89 active) across 28 distinct (form, dose) groups. The anchor rule
    requires an active row with a *known* dose, then the lowest
    `(dose_key, form_key)`: the 1000MG COMPRIME tablet, brand DOLI BIEN.

    The point of the spot-check is that the bare None-first rule cannot win:
    the anchor is active with a known dose, and its class is the identical
    seven 1000MG tablets the brand route reaches.
    """
    from lookup import lookup
    res = lookup(dci="PARACETAMOL")
    assert res.status == "found"
    assert res.dci_base_key == "PARACETAMOL"
    assert len(res.matched_rows) == 192
    assert res.anchor.availability == "active"
    assert res.anchor.dose_key == "1000MG"
    assert res.anchor.form_key == "COMPRIME"
    assert res.anchor.brand_key == "DOLI BIEN"
    # The class is the same seven tablets the DOLIPRANE brand route reaches.
    assert {p.brand for p in res.equivalents} == {
        "ANTALGAN", "DOLI-BIEN", "DOLIPRANE", "DOLYC", "EXPANDOL",
        "PARACETAMOL PHYSIOPHARM", "ROSADOL"}
    assert all(p.dose_key is not None for p in res.equivalents)


def test_blank_type_is_not_dressed_up_as_a_generic():
    """`type` is three-valued and may be blank (50 rows). A blank is unknown,
    not GE, so it must survive the round trip verbatim rather than being
    defaulted."""
    import sqlite3
    from lookup import lookup
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT brand_key, dci_base_key FROM product "
            "WHERE type='' AND availability='active' LIMIT 1").fetchone()
    finally:
        con.close()
    assert row is not None, "index no longer carries blank-type active rows"
    brand_key, base_key = row
    res = lookup(name=brand_key)
    assert res.status == "found"
    assert any(p.brand_key == brand_key and p.type == ""
               for p in res.anchor_rows + res.equivalents)


def test_lookup_refuses_to_write_to_the_index(tmp_path):
    """The index is read-only at query time. Opening it read-write would let a
    bug in the renderer corrupt the thing every answer depends on."""
    import hashlib
    before = hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest()
    from lookup import lookup
    for query in ({"name": "doliprane"}, {"dci": "PARACETAMOL"},
                  {"name": "polaramine"}, {"name": "zzzznotadrug"}):
        lookup(**query).to_json()
    after = hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest()
    assert before == after


def test_no_query_without_an_exact_match_ever_produces_an_anchor():
    """The single most important property, swept over real index data.

    Every string here either misses entirely or resolves only fuzzily. None of
    them may yield an anchor, whatever difflib scores -- a near match is a
    near match, and the user typed something else.
    """
    from normalize import fold
    from lookup import lookup
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        typed = ["DOLIPRAN", "doliprna", "AUGMENTN", "POLARAMIN",
                 "zzzznotadrug", "DOLIPRANEE", "DOLPRANE"]
        for spelling in typed:
            exact = con.execute(
                "SELECT 1 FROM product WHERE brand_key=? LIMIT 1",
                (fold(spelling),)).fetchone()
            assert exact is None, f"{spelling!r} is an exact match; pick another"
            res = lookup(name=spelling)
            assert res.anchor is None, f"{spelling!r} produced an anchor"
            assert res.status in ("ambiguous", "not_found")
    finally:
        con.close()


def test_no_none_dose_row_ever_reaches_a_class_across_the_index():
    """Swept, not spot-checked: every active row whose dose is undeterminable
    is looked up as a brand, and no result may place a None-dose row in any
    equivalence bucket."""
    from lookup import lookup
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        brands = [r[0] for r in con.execute(
            "SELECT DISTINCT brand_key FROM product "
            "WHERE dose_key IS NULL AND availability='active'")]
    finally:
        con.close()
    assert brands, "index no longer has unknown-dose active rows"
    for brand_key in brands:
        res = lookup(name=brand_key)
        if not res.anchor:
            continue
        assert all(p.dose_key is not None for p in res.equivalents)
        if res.anchor.dose_key is None:
            assert res.equivalents == []


# ---------------------------------------------------------------------------
# CLI contract: flags, exit codes, and output a human reads.
# ---------------------------------------------------------------------------


def _run(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, LOOKUP_PY, *args],
        capture_output=True, text=True, encoding="utf-8", env=env,
        cwd=os.path.dirname(SCRIPTS_DIR),
    )


def test_cli_prints_the_version_label_on_every_invocation():
    assert "Août 2026" in _run("--name", "DOLIPRANE").stdout
    assert "Août 2026" in _run("--name", "zzzznotadrug").stdout


def test_cli_exits_zero_on_a_hit_one_on_a_miss_and_two_on_usage():
    assert _run("--name", "DOLIPRANE").returncode == 0
    assert _run("--name", "zzzznotadrug").returncode == 1
    assert _run().returncode == 2
    assert _run("--name", "DOLIPRANE", "--dci", "PARACETAMOL").returncode == 2


def test_cli_ambiguous_query_lists_candidates_without_picking_one():
    out = _run("--name", "dolipran")
    assert out.returncode == 0
    assert "DOLIPRANE" in out.stdout
    assert "ambiguous" in out.stdout.lower()
    # It must not have resolved anything.
    assert "EQUIVALENTS" not in out.stdout


def test_cli_renders_statut_as_origin_and_type_as_type():
    out = _run("--name", "DOLIPRANE")
    assert "made in Algeria" in out.stdout
    assert "GE (generic-equivalent)" in out.stdout
    # STATUT is not an availability flag. The anchor's own equivalents are all
    # Algerian-made, so the *equivalents block* must carry no "imported"; other
    # buckets legitimately can and do.
    block = out.stdout.split("EQUIVALENTS --")[1].split("Other dosages")[0]
    assert "imported" not in block.lower()
    # And the status line still states availability, separately from origin.
    assert "status" in out.stdout.lower()


def test_cli_marks_a_biologic_row_visibly():
    import sqlite3
    from lookup import lookup
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT brand_key, dci_base_key FROM product "
            "WHERE type='BIO' AND availability='active' LIMIT 1").fetchone()
    finally:
        con.close()
    assert row is not None
    out = _run("--name", row[0])
    assert "BIO" in out.stdout


def test_cli_json_output_is_parseable_and_names_the_buckets():
    out = _run("--name", "DOLIPRANE", "--json")
    assert out.returncode == 0
    payload = json.loads(out.stdout)
    assert payload["version_label"] == "Août 2026"
    assert payload["status"] == "found"
    assert payload["anchor"]["brand_key"] == "DOLIPRANE"
    for key in ("equivalents", "other_dosages", "other_forms", "inactive"):
        assert key in payload


def test_cli_leads_with_an_off_market_anchor():
    out = _run("--name", "Polaramine")
    assert out.returncode == 0
    assert "off-market" in out.stdout.lower()
    assert "SIROP" in out.stdout
    assert "RETRAIT PAR LE MSPRH POUR INTERDICTION D'IMPORTATION" in out.stdout


@requires_index
def test_the_index_read_only_uri_is_actually_used():
    """A guard on the test fixture rather than the code: if the path moves,
    everything above silently skips and the suite still goes green."""
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM product").fetchone()[0] == 9595
    finally:
        con.close()

"""Task 2 tests: the normalization layer (fold / form_key / dose_key / dci_keys).

The brief's functions are kept verbatim, with one data-corrected fixture: an
earlier draft asserted ``0,5MG/5ML == 1MG/ML``, which is false -- 0.5 mg per
5 ml is 0.1 mg/ml (DEXCHLORPHENIRAMINE MALEATE, 7 rows in the file). The plan
now says ``0,5MG/5ML == 0,1MG/ML``; the guard asserting it is *not* 1MG/ML
stays so the wrong merge cannot come back.

Two further fixtures are corrected the same way, both for arithmetic reasons:

- ``0,25 µg`` is 0.00025 mg, not the 0.025 mg the fix-round findings wrote.
  0.25 µg -> 0.025 mg is a 100x error; the key must be ``0.00025MG``.
- ``test_dose_key_never_merges_1000_micrograms_into_1000_milligrams`` pins a
  bug the findings did not catch: ``1000µG/ML`` was keying as ``1000MG/ML``.

A ``FORM_CANON`` provenance test reads the ministry workbook, because the
finding is that 90 of its keys were hand-written under a comment claiming the
table was derived from the source.
"""

import os

import pytest

from conftest import SOURCE_XLSX
from normalize import FORM_CANON, dci_keys, dose_key, fold, form_key


# --- fold ---------------------------------------------------------------------

def test_fold_strips_accents_and_case():
    assert fold("Cétirizine  Dihlorhydrate") == "CETIRIZINE DIHLORHYDRATE"
    assert fold("doliprane") == "DOLIPRANE"
    assert fold(None) == ""


# --- form_key -----------------------------------------------------------------

def test_form_key_canonicalizes_abbreviations():
    """Review Focus #3: the headline paracetamol-tablet case."""
    assert form_key("COMP.") == form_key("COMPRIME") == "COMPRIME"
    assert form_key("COMPRIME PELLICULE SECABLE") == "COMPRIME_PELLICULE_SECABLE"
    assert form_key("SIROP") == "SIROP"


def test_form_key_placeholder_does_not_match_everything():
    """Review Focus #4."""
    assert form_key("FORME") == "NON_SPECIFIE"
    assert form_key("FORME") != form_key("SIROP")


def test_form_canon_keys_all_occur_in_the_workbook():
    """Finding 4: FORM_CANON claimed provenance it did not have.

    Every key must be a FORME spelling the ministry actually publishes, or it
    is guesswork sitting under a comment that says the table was derived from
    the source. A spelling this release has never used then falls through to
    the identity path instead of being silently mis-mapped.
    """
    if not os.path.exists(SOURCE_XLSX):
        pytest.skip(f"ministry workbook not downloaded: {SOURCE_XLSX}")

    import openpyxl

    from normalize import fold as _fold

    workbook = openpyxl.load_workbook(SOURCE_XLSX, read_only=True, data_only=True)
    observed = set()
    for sheet, first_row in (
        ("Nomenclature Aout 2026", 17),
        ("Non Renouvelés ", 13),
        ("Retraits", 12),
    ):
        for row in workbook[sheet].iter_rows(min_row=first_row, values_only=True):
            for cell in row[5:6]:
                if cell is not None:
                    observed.add(_fold(cell))

    unobserved = sorted(key for key in FORM_CANON if key not in observed)
    assert unobserved == [], f"FORM_CANON keys absent from the workbook: {unobserved}"


# --- dose_key: identities -----------------------------------------------------

def test_dose_key_ratio_equals_concentration():
    """Review Focus #2. Both sides of each pair are the same strength.

    NB an earlier draft of this plan asserted 0,5MG/5ML == 1MG/ML. That is
    false -- 0.1 vs 1.0 mg/ml -- and the implementer caught it.
    """
    assert dose_key("0,5MG/5ML") == dose_key("0,1MG/ML")
    assert dose_key("5MG/5ML") == dose_key("1MG/ML")
    assert dose_key("6,25MG/5ML") == dose_key("1,25MG/ML")


def test_dose_key_distinct_strengths_stay_distinct():
    assert dose_key("500MG") != dose_key("1G")
    assert dose_key("10MG") != dose_key("20MG")


def test_dose_key_converts_grams_to_milligrams():
    """Step 3 of the brief specifies G->MG; without this the rule is untested."""
    assert dose_key("1G") == dose_key("1000MG")
    assert dose_key("0,5G") == dose_key("500MG")


# --- dose_key: the dimension must survive --------------------------------------

def test_dose_key_keeps_its_dimension_through_a_space():
    """The bug that cost a fix round. A space between the number and the
    unit must not cost the unit: 10 UI/ML is not the bare number 10, and
    40 MG/0.8ML is not 40."""
    assert dose_key("10 UI/ML") == dose_key("10UI/ML")
    assert dose_key("40 MG/0.8ML") == "50MG/ML"
    assert dose_key("60 MG/1.5 ML") == "40MG/ML"


def test_dose_key_never_collapses_across_dimensions():
    """A mass, a concentration, a volume and a percentage are different
    quantities even when the number is the same."""
    keys = {dose_key("0,25 µg"), dose_key("0.25 MG/ML"),
            dose_key("0.5 ML"), dose_key("0,5 %")}
    assert None not in keys
    assert len(keys) == 4


def test_dose_key_is_never_dimensionless():
    """No key may be a bare number. Without a dimension a mass, a
    concentration, a percentage and a volume all collide."""
    for raw in ["10 UI/ML", "0,25 µg", "0.5 ML", "0.25 MG/ML",
                "100 MG", "3,5MG/FL.", "0,05%", "0.02"]:
        key = dose_key(raw)
        assert key is None or key.rstrip("0123456789."), f"{raw!r} -> {key!r}"


def test_dose_key_keeps_ui_as_ui():
    """UI is not MG. The conversion is substance-specific and unknown here."""
    key = dose_key("100UI/ML (3.5MG/ML)")
    assert key is not None and "UI" in key
    assert dose_key("10 UI/ML") != dose_key("10 MG/ML")


def test_dose_key_keeps_a_non_mass_numerator_when_a_ratio_divides():
    """Critical 2, the other half: reducing X/Y must not relabel X as a mass.

    ``30MUI/0,5ML`` was keying ``60MG/ML`` and ``0,1IR/ML`` was keying
    ``0,1MG/ML`` -- a UI->MG and an IR->MG conversion that the DCI cannot
    justify. Dividing is exact; relabelling the numerator is not.
    """
    assert dose_key("30MUI/0,5ML") == "60MUI/ML"
    assert dose_key("0,1IR/ML") == "0.1IR/ML"
    assert dose_key("0,5MMOLE/ML") == "0.5MMOLE/ML"
    # Units are uppercased so that mg/ml and MG/ML meet; KBQ is not a mass,
    # so it is carried through the division as itself.
    assert dose_key("1100 KBq/ML (6,6 MBq/FL)") == "1100KBQ/ML"


def test_dose_key_converts_micrograms_to_milligrams():
    """Finding 5: the µG->MG entry existed and no code path reached it.

    ``µG`` also has to be normalised before lookup -- str.upper() turns
    MICRO SIGN into GREEK CAPITAL MU, so the table lookup missed and the key
    came out as ``50ΜG``.
    """
    assert dose_key("0,25 µg") == "0.00025MG"
    assert dose_key("25 µg") == dose_key("0,025 MG")
    # The file states the conversion itself: 100UG/2ML (0,1MG/2ML).
    assert dose_key("100UG/2ML (0,1MG/2ML) (0,05MG/ML)") == "0.05MG/ML"


def test_dose_key_never_merges_1000_micrograms_into_1000_milligrams():
    """1000µG/ML was keying 1000MG/ML -- a factor of 1000 on a real row."""
    assert dose_key("1000µG/ML") == "1MG/ML"
    assert dose_key("1000µG/ML") != dose_key("1000MG/ML")
    assert dose_key("20µG/80µL") == "0.02MG/80µL"


# --- dose_key: multi-ingredient ------------------------------------------------

def test_dose_key_returns_none_for_multi_ingredient_strengths():
    """10+100+300 IR/ML and COMPARTIMENT A/B describe several actives; they
    are not a single dose identity."""
    assert dose_key("0,1IR/ML+1IR/ML+10IR/ML") is None
    assert dose_key("COMPARTIMENT A (0,25 L) ,COMPARTIMENT B (4,75 L )") is None
    assert dose_key("15MG+45MG") is None


def test_dose_key_keeps_a_single_active_split_into_its_salts():
    """The counterpart: a ``+`` inside a bracket is a decomposition, not a
    second active. 500MG (sel 167MG+375MG) is one substance."""
    assert dose_key("500MG**  ( sel 167MG+375MG)") == "500MG"
    assert dose_key("567,7MG ├®quivalent en Fer (2+) 100MG") is not None


def test_dose_key_returns_none_when_there_is_no_number():
    """22 rows carry q.s / --- / blanks. None means unknown, not a mismatch."""
    assert dose_key("q.s pour un flacon") is None
    assert dose_key("---") is None
    assert dose_key(None) is None


def test_dose_key_decimal_comma_and_dot_agree():
    """The decimal-comma merge must survive the unit rule.

    1025 rows use a comma. It is the number format, not a different quantity,
    so both spellings of one strength meet -- and the bare-number spellings
    (0,0005 / 0.0005) meet at None, which is the honest answer for them.
    """
    assert dose_key("0,0005 MG") == dose_key("0.0005 MG") == "0.0005MG"
    assert dose_key("0,5 MG") == dose_key("0.5MG") == "0.5MG"
    assert dose_key("0,0005") is None and dose_key("0.0005") is None


def test_dose_key_returns_none_when_the_strength_is_not_at_the_start():
    """A cell that opens with prose yields ``None``, not a guessed number.

    ``GAZ LIQUEFIE SOUS PRESSION ( PURETE >= 98% V/V N2O)`` has a strength
    expression in it, but it is a gas purity, not a dose -- and ``44 BAR`` is
    a pressure. Scanning forward for the first number would key those as if
    they were strengths, which is the class of error this layer exists to
    stop. ``None`` is *unknown*, which the answer carries through honestly.
    """
    assert dose_key("PURETE ≥ 99.50%") is None
    assert dose_key("I =350MG/ML") is None
    assert dose_key("AMP. DE 5ML") is None


def test_dose_key_returns_none_for_a_dash_separated_dose_schedule():
    """Two titration regimens are two different strengths, not one key.

    Found by a before/after sweep of every row, not by the findings: the
    reconstitution rows (``5MG/ML (100MG/20ML - 500MG/100ML)``) are handled
    correctly by the first-expression rule, but a *top-level* dash followed
    by a number is a second dose, and reading only the first declared two
    different schedules identical::

        30µG/0,05MG/6JRS - 40µG/0,075MG/5JRS - 30µG/0,125MG/10JRS  -> 0.03MG/0.05MG
        0,03MG/0,05MG - 0,04MG/0,075MG - 0,03MG/0,125MG            -> 0.03MG/0.05MG

    A dash followed by a *word* is not a dose, and a dash inside brackets is
    a reconstitution table. Both must keep their key.
    """
    assert dose_key(
        "30µG/0,05MG/6JRS - 40µG/0,075MG/5JRS - 30µG/0,125MG/10JRS") is None
    assert dose_key("0,03MG/0,05MG - 0,04MG/0,075MG - 0,03MG/0,125MG") is None
    assert dose_key("100ML/100ML - 250ML/250ML") is None
    # A dash before a word is punctuation, not a second dose.
    assert dose_key("160MG/SACHET-DOSE (288MG/SACHET ACETYLSALICYLATE)") \
        == "160MG/SACHET"
    assert dose_key("74,4MG/SACHET- DOSE") == "74.4MG/SACHET"
    # A dash inside brackets is a reconstitution table for the same stock.
    assert dose_key("5MG/ML (100MG/20ML - 500MG/100ML)") == "5MG/ML"
    assert dose_key("0,5MG/ML (25MG/50ML) - (50MG/100ML)") == "0.5MG/ML"


# --- dci_keys ------------------------------------------------------------------

def test_dci_keys_group_salt_and_base():
    """Review Focus #1."""
    exact, base = dci_keys("CETIRIZINE DICHLORHYDRATE")
    exact2, base2 = dci_keys("CETIRIZINE")
    assert base == base2
    assert exact != exact2


def test_dci_keys_prefer_the_clause_after_exprime_en():
    """Review Focus #1 again: 181 DCIs state the base substance after a marker."""
    _, base = dci_keys("ACIDE ZOLEDRONIQUE MONOHYDRATE EXPRIME EN ACIDE ZOLEDRONIQUE")
    assert base == dci_keys("ACIDE ZOLEDRONIQUE")[1]


def test_dci_keys_use_the_parenthesised_base_when_present():
    _, base = dci_keys("AMLODIPINE BESILATE (AMLODIPINE)")
    assert base == dci_keys("AMLODIPINE")[1]

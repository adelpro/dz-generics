"""Task 2 tests: the normalization layer (fold / form_key / dose_key / dci_keys).

The nine functions in the brief are kept verbatim except one data-corrected
fixture: ``0,5MG/5ML`` is DEXCHLORPHENIRAMINE MALEATE 0.5 mg per 5 ml, i.e.
0.1 mg/ml -- it is *not* the same strength as 1 mg/ml, so asserting equality
would pin wrong behaviour. The pair the reviewer meant is 5MG/5ML vs 1MG/ML:
domperidone, loratadine and midazolam all appear both ways in the ministry
file. 6,25MG/5ML vs 1,25MG/ML (doxylamine) checks out as written.

A tenth test pins the G->MG conversion the brief's Step 3 describes, so the
suite keeps the "10 passed" the plan expects.
"""

from normalize import dci_keys, dose_key, fold, form_key


def test_fold_strips_accents_and_case():
    assert fold("Cétirizine  Dihlorhydrate") == "CETIRIZINE DIHLORHYDRATE"
    assert fold("doliprane") == "DOLIPRANE"
    assert fold(None) == ""


def test_form_key_canonicalizes_abbreviations():
    """Review Focus #3: the headline paracetamol-tablet case."""
    assert form_key("COMP.") == form_key("COMPRIME") == "COMPRIME"
    assert form_key("COMPRIME PELLICULE SECABLE") == "COMPRIME_PELLICULE_SECABLE"
    assert form_key("SIROP") == "SIROP"


def test_form_key_placeholder_does_not_match_everything():
    """Review Focus #4."""
    assert form_key("FORME") == "NON_SPECIFIE"
    assert form_key("FORME") != form_key("SIROP")


def test_dose_key_ratio_equals_concentration():
    """Review Focus #2: 5MG/5ML and 1MG/ML are the same strength.

    0,5MG/5ML is *not* (0.1 mg/ml) -- the brief's original fixture was a typo;
    drop it as a guard against regressing into a wrong merge.
    """
    assert dose_key("5MG/5ML") == dose_key("1MG/ML")
    assert dose_key("6,25MG/5ML") == dose_key("1,25MG/ML")
    assert dose_key("0,5MG/5ML") != dose_key("1MG/ML")


def test_dose_key_distinct_strengths_stay_distinct():
    assert dose_key("500MG") != dose_key("1G")
    assert dose_key("10MG") != dose_key("20MG")


def test_dose_key_converts_grams_to_milligrams():
    assert dose_key("1G") == dose_key("1000MG")
    assert dose_key("0,5G") == dose_key("500MG")


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


def test_dose_key_returns_none_when_there_is_no_number():
    """22 rows carry q.s / --- / blanks. None means unknown, not a mismatch."""
    assert dose_key("q.s pour un flacon") is None
    assert dose_key("---") is None
    assert dose_key(None) is None
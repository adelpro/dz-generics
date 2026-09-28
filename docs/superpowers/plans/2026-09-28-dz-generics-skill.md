# Algerian Drug Generics Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a skill that answers "what is the generic equivalent of X in Algeria?" from either a brand name or a DCI, using the Ministry of Industry's national nomenclature, and publish it to the user's synced opencode config repo.

**Architecture:** Two standalone Python scripts with no Claude-specific logic — `build_index.py` converts the ministry `.xlsx` into a SQLite index with normalized search keys; `lookup.py` queries that index and prints equivalence classes. A thin `SKILL.md` instructs the model how to run the lookup and how to phrase the answer. The same two scripts later wrap in an MCP adapter without modification.

**Tech Stack:** Python 3.12 (already installed), `openpyxl` (build-time only), `sqlite3` stdlib (query-time, no install), `pytest` (dev only).

**Spec:** This document. The design decisions from the earlier conversation are folded into Global Constraints and Review Focus below.

---

## Global Constraints

- **Source of truth is the ministry file, nothing else.** Never invent a product, laboratory, or DCI. If a drug is not in the index, say it is not in the nomenclature.
- **A "generic equivalent" means same DCI (salt-insensitive), same pharmaceutical form, same normalized dosage.** Any other combination is reported separately and explicitly labelled *not equivalent*.
- **A dose key must carry its dimension** — mass, mass per volume, percent, volume, or units. A dimensionless number is not a dose identity: `0.25 µg` (a mass), `0.25 MG/ML` (a concentration) and `0.25 L` (a volume) all reduce to `0.25`, and a key that lets them collide reports a wrong strength as an equivalent. When `dose_key` cannot determine the dimension, it returns `None`. `None` means *unknown dosage* and must never be read as a mismatch, and never as a match.
- **A multi-ingredient strength is not a single dose identity.** Rows like `0,1IR/ML+1IR/ML+10IR/ML` or `COMPARTIMENT A (0,25 L),COMPARTIMENT B (4,75 L)` describe a product with several actives; they key to `None` rather than to whichever number happened to parse first.
- **`TYPE` is three-valued — `GE`, `RE`, and `BIO` (biologics, 58 rows).** It is stored verbatim. Never reduce it to a boolean, and never bucket a blank or unrecognised value as `GE`. A biosimilar is not interchangeable with a chemical generic the way a `GE` is, so the distinction has to survive to the answer.
- **`STATUT` is locally-made vs imported (`F`/`I`), not an availability flag.** It tracks the holder's country at 94.6% / 3.9%. Use it to say *made in Algeria* or *imported from X* — never to decide whether a product is on the market.
- **Availability comes from which sheet a record was read from**, never from a join and never from `STATUT`. The three sheets are disjoint (main ∩ not-renewed = 0, main ∩ withdrawn = 1), so the index is their union: 5425 active + 1491 not renewed + 2679 withdrawn.
- **Never auto-pick a brand on fuzzy match.** Ambiguous input lists candidates and stops. The source file misspells the same substance several ways, so an exact-match miss must say "not found" rather than guess.
- **Every answer states the nomenclature version** (e.g. `Nomenclature Août 2026`) and closes with a note that substitution is the pharmacist's or prescriber's decision, since the nomenclature records no bioequivalence or excipient data.
- **Withdrawn and not-renewed products are flagged, never presented as available.** A withdrawn product is a safety issue, not a formatting detail.
- **The index is read-only at query time.** `lookup.py` must never write to the SQLite file.
- **Scripts contain no model-specific logic** — no prompt text, no skill references, no assumptions about who calls them.
- **Answer in the language the user asked in.** Default to French for French queries, Arabic for Arabic queries, English for English. French drug terms must not be translated into English output when the user wrote French.

## Review Focus

These are the five input classes most likely to break this and not yet pinned by any stated requirement. Each gets a test in the owning task.

1. **The same substance written two ways — and sometimes three.** `CETIRIZINE DICHLORHYDRATE` in the main sheet against bare `CETIRIZINE` in the Retraits sheet. On top of the salt suffix, 181 DCI values state the base substance after a marker (`ACIDE ZOLEDRONIQUE MONOHYDRATE EXPRIME EN ACIDE ZOLEDRONIQUE`), and some use parentheses instead (`AMLODIPINE BESILATE (AMLODIPINE)`). The salt list must be the **French** forms this file prefers — `SODIQUE` (31 rows) and `ANHYDRE` (26) are the two largest gaps in the English list. Grouping must work, and a match must still show the real DCI string, never a synthesized one.
2. **Dosage written as a ratio vs a concentration.** `0,5MG/5ML` and `0,1MG/ML` are the same strength written two ways, as are `5MG/5ML` and `1MG/ML`; 1025 rows use a decimal **comma**, which a naive float parse reads as `0`. Getting this wrong silently returns zero generics for syrups — the most common failure mode. The trap is the opposite one, though: a key that drops the unit and keeps only the number makes a mass, a concentration, a percentage and a volume collide on the same key, which reports a wrong strength as an equivalent. 22 rows carry no digit at all (`q.s pour un flacon`, `---`, `n`); `dose_key` returns `None` and that must read as *unknown*, never as a mismatch.
3. **Form written as an abbreviation vs the full word.** 683 distinct raw values over 5425 rows, including misspellings (`COMRPIME`, `COMRIME`) and values that are not forms at all (`FLACON`, `LAIT EN POUDRE`, `---`). Without canonicalization, a paracetamol tablet lookup misses the generic tablets, which is the headline use case.
4. **The placeholder form `FORME`.** Two rows in 9595 carry the literal string `FORME` in the form column, meaning unspecified. It must not match every form — that would report a syrup as a tablet equivalent. It gets its own canonical value and a flag. It is rare enough that a 5% threshold gate passes trivially; the gate exists to catch a *different* value going missing, not this one.
5. **A product that is off the main list, sometimes for two different reasons.** `POLARAMINE` appears nowhere in the main sheet — but it appears in **both** `Non Renouvelés ` *and* `Retraits`, giving it 4 rows across the two: not renewed *and* withdrawn. The two non-main sheets overlap on 40 registration numbers. So availability is not a single value per brand, and a lookup has to decide what to lead with (withdrawn is the more serious state, and the one that matters to a patient). A build that reads only the main list reports `POLARAMINE` as "not in the nomenclature" when it is really off-market for a reason the user needs to be told.

---

## File Structure

| Path | Responsibility |
|---|---|
| `dz-generics/scripts/normalize.py` | Pure functions: text folding, form canonicalization, dose parsing, DCI keying. No I/O, no database. |
| `dz-generics/scripts/build_index.py` | Reads the `.xlsx`, resolves sheets and headers, writes `data/nomenclature.sqlite`. |
| `dz-generics/scripts/lookup.py` | Read-only CLI over the SQLite file. Resolves input to a DCI, emits equivalence classes. |
| `dz-generics/scripts/profile_source.py` | Prints row counts, form/dosage distributions and unparsed-value counts from a source file. The tool for re-checking assumptions when the ministry changes a column. |
| `dz-generics/scripts/fetch_source.py` | Downloads the newest ministry `.xlsx`. Optional; never on the query path. |
| `dz-generics/data/nomenclature.sqlite` | The built index. ~5.4k rows, expected under 5 MB. |
| `dz-generics/references/schema.md` | Exact source columns, sheet names and quirks, `TYPE`/`STATUT` semantics. Written from real inspection, not assumption. |
| `dz-generics/references/answering.md` | How to phrase results, the safety note, multilingual output. |
| `dz-generics/SKILL.md` | Trigger description and the operating instructions. |
| `tests/conftest.py` | Puts `dz-generics/scripts` on `sys.path` and exports `SOURCE_XLSX`. Without it no test can import the modules. |
| `tests/test_normalize.py` | Unit tests for the normalization layer. |
| `tests/test_build_index.py` | Header resolution, sheet handling, row-count guard. |
| `tests/test_lookup.py` | End-to-end against the real built index. |
| `README.md` | Public repo front door: what it does, install, refresh, data provenance, disclaimer. |

Tests live at the repo root; the installable skill is the `dz-generics/`
directory alone, so no test file ever reaches `~/.config/opencode/skills/`.

---

## Phase 0 — Ground Truth (verified in Task 1)

Task 1 inspected the live file and wrote the full result to
`dz-generics/references/schema.md`. **That file, not this section, is the
authority on the source layout** — read it before touching `build_index.py`.
The short version:

- Source page: `https://www.miph.gov.dz/fr/nomenclature-nationale-des-produits-pharmaceutiques/`
- Current file: `.../2026/09/clean_NOMENCLATURE.VERSION.AOUT_.2026-.xlsx` (1,252,820 bytes)
- `data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx` — **gitignored**, never redistributed
- Sheets and data rows: `Nomenclature Aout 2026` 5425, `Non Renouvelés ` 1491 (**trailing space in the name**), `Retraits` 2679. 9595 total.
- Header rows are 16 / 12 / 11 — each sheet has an institutional banner above it, and its title row states its own row count, which makes a free integrity check.
- Main sheet declares 36 columns and fills 19. **`Retraits` has a different layout from the other two** — no `OBS`, no `DATE D'ENREGISTREMENT FINAL`, two extra columns, and `TYPE`/`STATUT` two positions to the left. Resolve columns by name, per sheet.
- `TYPE` = `GE` / `RE` / `BIO`. `STATUT` = `F` (locally made) / `I` (imported).
- **The three sheets are disjoint** (main ∩ not-renewed = 0, main ∩ withdrawn = 1). Availability is a property of the source sheet, not a join result.
- Filename patterns are inconsistent (`clean_` prefix appears and disappears; upload month ≠ version month). The version label must come from the **sheet name**, which is stable.

---

## Task 1: Pin the source schema

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_build_index.py`
- Create: `dz-generics/scripts/build_index.py`
- Create: `dz-generics/references/schema.md`

**Interfaces:**
- Consumes: `data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx`
- Produces: `find_header(headers: list[str], prefix: str) -> int | None` in `build_index.py`; `references/schema.md` with the exact header strings, sheet names, and `TYPE`/`STATUT` value sets, which Task 2 and Task 3 hardcode; and `tests/conftest.py` exporting `SOURCE_XLSX`.

- [ ] **Step 1: Write `tests/conftest.py`**

Every test in this project does a bare `from normalize import fold` or
`from build_index import find_header`, but those modules live in
`dz-generics/scripts/` while the tests live in `tests/`. pytest puts the
*test* directory on `sys.path`, not the script directory, so without this
file no test can ever pass. Insert the script directory and define
`SOURCE_XLSX`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dz-generics", "scripts"))

SOURCE_XLSX = os.path.join(
    os.path.dirname(__file__), "..", "data", "source",
    "NOMENCLATURE.VERSION.AOUT_.2026-.xlsx",
)
```

- [ ] **Step 2: Write the failing test**

```python
def test_headers_resolve_by_prefix():
    """Header lookup must survive the full-string being longer than expected."""
    from build_index import find_header
    headers = ["N°", "N°ENREGISTREMENT", "CODE",
               "DENOMINATION COMMUNE INTERNATIONALE (DCI)", "NOM DE MARQUE"]
    assert find_header(headers, "DENOMINATION COMMUNE") == 3
    assert find_header(headers, "NOM DE MARQUE") == 4
    assert find_header(headers, "DOSAGE") is None
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m pytest tests/test_build_index.py::test_headers_resolve_by_prefix -v`
Expected: FAIL with `ImportError: cannot import name 'find_header' from 'build_index'`
(the module does not exist yet — `conftest.py` is what puts it on the path)

- [ ] **Step 4: Dump the real headers and value sets**

```bash
python -c "import openpyxl,sys;wb=openpyxl.load_workbook(r'data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx',read_only=True,data_only=True);ws=wb['Nomenclature Aout 2026'];rows=list(ws.iter_rows(min_row=16,max_row=16,values_only=True))[0];[print(i,repr(c)) for i,c in enumerate(rows) if c is not None]"
```

Also dump `SELECT`-equivalent frequency counts of `FORME`, `TYPE`, `STATUT` over column 6, 17, 18 of the data rows. Write both into `references/schema.md` verbatim, including the exact trailing space in `Non Renouvelés `.

- [ ] **Step 5: Implement `find_header(headers: list[str], prefix: str) -> int | None` in `dz-generics/scripts/build_index.py`**

Case-insensitive, accent-insensitive `startswith` over the header list; returns the index of the first match or `None`. This is why a truncated or renamed suffix like `(DCI)` cannot break the build.

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest tests/test_build_index.py::test_headers_resolve_by_prefix -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_build_index.py dz-generics/scripts/build_index.py dz-generics/references/schema.md
git commit -m "feat: pin ministry source schema and header resolution"
```

---

## Task 2: Normalization layer

**Files:**
- Create: `dz-generics/scripts/normalize.py`
- Create: `tests/test_normalize.py`

**Interfaces:**
- Consumes: nothing
- Produces: `fold(text: str | None) -> str`, `form_key(form: str | None) -> str`, `dose_key(dosage: str | None) -> str | None`, `dci_keys(dci: str | None) -> tuple[str, str]`, and the constant `FORM_CANON`.

Later tasks call these by these names. `dose_key` returns `None` for an unparseable dosage, and callers must treat `None` as *unknown* rather than as a mismatch.

- [ ] **Step 1: Write the failing tests**

```python
def test_fold_strips_accents_and_case():
    from normalize import fold
    assert fold("Cétirizine  Dihlorhydrate") == "CETIRIZINE DIHLORHYDRATE"
    assert fold("doliprane") == "DOLIPRANE"
    assert fold(None) == ""


def test_form_key_canonicalizes_abbreviations():
    """Review Focus #3: the headline paracetamol-tablet case."""
    from normalize import form_key
    assert form_key("COMP.") == form_key("COMPRIME") == "COMPRIME"
    assert form_key("COMPRIME PELLICULE SECABLE") == "COMPRIME_PELLICULE_SECABLE"
    assert form_key("SIROP") == "SIROP"


def test_form_key_placeholder_does_not_match_everything():
    """Review Focus #4."""
    from normalize import form_key
    assert form_key("FORME") == "NON_SPECIFIE"
    assert form_key("FORME") != form_key("SIROP")


def test_dose_key_ratio_equals_concentration():
    """Review Focus #2. Both sides of each pair are the same strength.
    NB an earlier draft of this plan asserted 0,5MG/5ML == 1MG/ML. That is
    false -- 0.1 vs 1.0 mg/ml -- and the implementer caught it."""
    from normalize import dose_key
    assert dose_key("0,5MG/5ML") == dose_key("0,1MG/ML")
    assert dose_key("5MG/5ML") == dose_key("1MG/ML")
    assert dose_key("6,25MG/5ML") == dose_key("1,25MG/ML")


def test_dose_key_distinct_strengths_stay_distinct():
    from normalize import dose_key
    assert dose_key("500MG") != dose_key("1G")
    assert dose_key("10MG") != dose_key("20MG")


def test_dose_key_keeps_its_dimension_through_a_space():
    """The bug that cost a fix round. A space between the number and the
    unit must not cost the unit: 10 UI/ML is not the bare number 10, and
    40 MG/0.8ML is not 40."""
    from normalize import dose_key
    assert dose_key("10 UI/ML") == dose_key("10UI/ML")
    assert dose_key("40 MG/0.8ML") == "50MG/ML"
    assert dose_key("60 MG/1.5 ML") == "40MG/ML"


def test_dose_key_never_collapses_across_dimensions():
    """A mass, a concentration, a volume and a percentage are different
    quantities even when the number is the same."""
    from normalize import dose_key
    keys = {dose_key("0,25 \u00b5G"), dose_key("0.25 MG/ML"),
            dose_key("0.5 ML"), dose_key("0,5 %")}
    assert None not in keys
    assert len(keys) == 4


def test_dose_key_is_never_dimensionless():
    """No key may be a bare number. Without a dimension a mass, a
    concentration, a percentage and a volume all collide."""
    from normalize import dose_key
    for raw in ["10 UI/ML", "0,25 \u00b5G", "0.5 ML", "0.25 MG/ML",
                "100 MG", "3,5MG/FL.", "0,05%", "0.02"]:
        key = dose_key(raw)
        assert key is None or key.rstrip("0123456789."), f"{raw!r} -> {key!r}"


def test_dose_key_keeps_ui_as_ui():
    """UI is not MG. The conversion is substance-specific and unknown here."""
    from normalize import dose_key
    key = dose_key("100UI/ML (3.5MG/ML)")
    assert key is not None and "UI" in key
    assert dose_key("10 UI/ML") != dose_key("10 MG/ML")


def test_dose_key_returns_none_for_multi_ingredient_strengths():
    """10+100+300 IR/ML and COMPARTIMENT A/B describe several actives; they
    are not a single dose identity."""
    from normalize import dose_key
    assert dose_key("0,1IR/ML+1IR/ML+10IR/ML") is None
    assert dose_key("COMPARTIMENT A (0,25 L) ,COMPARTIMENT B (4,75 L )") is None
    assert dose_key("15MG+45MG") is None


def test_dci_keys_group_salt_and_base():
    """Review Focus #1."""
    from normalize import dci_keys
    exact, base = dci_keys("CETIRIZINE DICHLORHYDRATE")
    exact2, base2 = dci_keys("CETIRIZINE")
    assert base == base2
    assert exact != exact2


def test_dci_keys_prefer_the_clause_after_exprime_en():
    """Review Focus #1 again: 181 DCIs state the base substance after a marker."""
    from normalize import dci_keys
    _, base = dci_keys("ACIDE ZOLEDRONIQUE MONOHYDRATE EXPRIME EN ACIDE ZOLEDRONIQUE")
    assert base == dci_keys("ACIDE ZOLEDRONIQUE")[1]


def test_dci_keys_use_the_parenthesised_base_when_present():
    from normalize import dci_keys
    _, base = dci_keys("AMLODIPINE BESILATE (AMLODIPINE)")
    assert base == dci_keys("AMLODIPINE")[1]


def test_dose_key_returns_none_when_there_is_no_number():
    """22 rows carry q.s / --- / blanks. None means unknown, not a mismatch."""
    from normalize import dose_key
    assert dose_key("q.s pour un flacon") is None
    assert dose_key("---") is None
    assert dose_key(None) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normalize'`

- [ ] **Step 3: Implement `normalize.py`**

`fold`: NFKD normalize, drop combining marks, uppercase, replace every non-alphanumeric run with a single space, strip.

`FORM_CANON`: build a dict from the distinct `FORME` values listed in
`references/schema.md`, mapping each observed spelling to a canonical token.
It must be derived from the observed data — the file has 683 distinct values
including misspellings and non-forms — not from a guessed list. The full
distribution is what `profile_source.py` prints, so use that to build it.
Map the literal `FORME` to `NON_SPECIFIE`, and give non-form values
(`FLACON`, `---`, `LAIT EN POUDRE`) their own keys rather than collapsing
them into a form.

**Every key in `FORM_CANON` must be a string that actually occurs in the
workbook.** The first implementation shipped 90 hand-written entries
alongside the observed ones, under a comment claiming the table was derived
from the source — so a reader could not tell which mappings were evidence and
which were guesswork. That is exactly what the "source of truth is the
ministry file, nothing else" constraint forbids. Either the entry is observed,
or it is not in the table. Add a test that reads the workbook, collects the
distinct `FORME` values, and asserts every `FORM_CANON` key is among them; a
new ministry release with a spelling you have not seen then falls through to
the identity path rather than being silently mis-mapped.

`dose_key`, and the rules are ordered because they interact:

1. Take the **first** strength expression in the string and ignore the rest.
   A string may restate the same strength in a second notation — `100UI/ML
   (3.5MG/ML)`, `0,1% (0,1G/100G)` — and picking up a unit from a *different*
   expression relabels the dose. `100UI/ML (3.5MG/ML)` keyed as `100MG/ML` was
   a real output of the first implementation.
2. A **space between the number and the unit is not significant.** `10 UI/ML`
   and `10UI/ML` are the same; `40 MG/0.8ML` is `50MG/ML`. The first
   implementation matched the unit against the raw remainder of the string
   with no `\s*` tolerance, so every spaced value silently lost its unit.
3. The **unit is mandatory.** If no unit is found, return `None`. A bare
   number is not a dose identity: it is why `0,25 µg`, `0.25 MG/ML` and
   `0.5 ML` all collided on `0.25` and `0.5`.
4. **Never convert between units that are not dimensionally safe.** `G`→`MG`
   and `µG`→`MG` are exact. `UI`→`MG` is *substance-specific* — for insulin
   1 UI ≈ 0.034 mg, for others it differs — so UI is carried as its own
   dimension and never converted. Percentage stays percentage; it is not
   interchangeable with a mass fraction without knowing the basis.
5. Reduce a ratio by dividing (`40 MG/0.8ML` → `50MG/ML`) so ratio and
   concentration forms meet on one key.
6. Return `None` for a **multi-ingredient** strength — one containing a `+`
   between strengths, or a `COMPARTIMENT A / B` structure. Check this against
   the observed rows before applying it, so a harmless `+` does not
   over-trigger.

Decimal comma becomes a period — 1025 rows, not an edge case. Return `None`
when no number is found, and let the caller treat that as *unknown*, which is
different from *mismatched*.

`dci_keys`, in order: fold; if the string contains `EXPRIME EN`, take only
what follows it as the substance; else if it contains a parenthesised group,
take that; else use the whole string. Then produce the exact key by sorting
the tokens alphabetically, and the base key by dropping salt/hydrate
suffixes. **The suffix list must be the French forms this file prefers** —
the English-only list in an earlier draft of this plan was wrong, and
`SODIQUE` (31 rows) and `ANHYDRE` (26) are its two largest omissions. The
observed list, with row counts, is the table in `references/schema.md`:
CHLORHYDRATE, SODIUM, SODIQUE, MONOSODIQUE, SULFATE, FUMARATE,
DICHLORHYDRATE, MALEATE, TRIHYDRATE, MONOHYDRATE, DIHYDRATE, ANHYDRE,
ANHYDROUS, POTASSIUM, POTASSIQUE, CALCIUM, MAGNESIUM, ACETATE, NITRATE,
BROMURE, CITRATE, PHOSPHATE, MESYLATE, TOSYLATE. Treat an unrecognised
suffix as part of the substance rather than dropping it — dropping a token
that is not a salt merges two genuinely different drugs, which is the worse
error.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: 16 passed

- [ ] **Step 5: Write `dz-generics/scripts/profile_source.py` and run it against the real file**

Unit tests only prove the normalizer handles the cases you already thought
of. This script is how you find the ones you did not — and it is the tool to
re-run whenever the ministry changes a column, so it ships as a real
artifact rather than a throwaway command. It reads the main sheet, skips to row 17, and prints: row count, a descending
frequency count of `form_key`, how many dosages `dose_key` returned `None`
for **together with the raw values of those rows**, and the full descending
distribution of raw `FORME` strings — not just the top 25, because
`FORM_CANON` is built from it and a truncated tail means unmapped forms.
Give it a `main()`, an `argparse` path argument, and an
`if __name__ == "__main__":` guard.

Then run it:

```bash
python dz-generics/scripts/profile_source.py data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx
```

Expected: **`unparsed dosages` on the main sheet is a few hundred, not 22.**
The 22 numberless rows are the floor, not the target — every dosage whose
dimension cannot be determined is correctly `None` too. Verified against the
real file, that is **416 on the main sheet** (810 across all three sheets):
660 with no unit, 70 blank, 58 where the strength is not at the start of the
string, 18 multi-ingredient, 4 with no number.

An earlier draft of this plan said "roughly 240-280", derived from a probe
figure of "217 rows". That figure was mislabeled: 217 was the number of
distinct *spellings*, which cover **462 rows**. The row count is what matters
here, so the correct expectation is 400-480. A return to 22, or a zero, means
the unit is being dropped again.

**The gate is not the count — it is the shape:**

- **Zero** dose keys may be dimensionless. If `profile_source.py` reports any
  key made only of digits and dots, the unit was dropped somewhere.
- **Zero** keys may gather together raw strings of different dimensions. The
  probe in `.superpowers/sdd/2026-09-28-dz-generics-skill/probe_task2.py`
  prints exactly this; re-run it and read the "dimensionless keys with >1 raw"
  line, which must be 0.
- `None` means *unknown dosage*, different from *mismatched dosage*, and must
  stay that way all the way to the answer.

**Gate:** `NON_SPECIFIE` must be under 5% of rows — the literal `FORME`
placeholder is only 2 rows in 9595, so this passes easily, and the gate
exists to catch a *different* form value going missing. Also confirm the raw
FORME list contains nothing you would be embarrassed to leave unmapped.

- [ ] **Step 6: Commit**

```bash
git add dz-generics/scripts/profile_source.py dz-generics/scripts/normalize.py tests/test_normalize.py
git commit -m "feat: normalization layer for form, dosage and DCI keys"
```

---

## Task 3: Build the index

**Files:**
- Modify: `dz-generics/scripts/build_index.py`
- Modify: `tests/test_build_index.py`

**Interfaces:**
- Consumes: `find_header` (Task 1), `fold`, `form_key`, `dose_key`, `dci_keys` (Task 2)
- Produces: `build(source_xlsx: str, out_sqlite: str, previous_row_count: int | None = None) -> dict` returning `{"row_count": int, "withdrawn": int, "not_renewed": int, "version_label": str}`, plus the `BuildError` exception. Writes the schema below.

Schema — pinned, because Task 4 and Task 5 both query it by these exact names:

```sql
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
  availability TEXT,     -- 'active' | 'not_renewed' | 'withdrawn'
  withdrawn_at TEXT, withdrawn_reason TEXT
);
CREATE INDEX idx_brand ON product(brand_key);
CREATE INDEX idx_dci   ON product(dci_base_key);
CREATE INDEX idx_code  ON product(code);
CREATE INDEX idx_reg   ON product(reg_no);
```

The table holds the **union of all three sheets** (9595 rows), not just the
main list. `reg_no` is not unique — 8 duplicates in the main sheet — so
`id` is the primary key and `reg_no` is an index only. `withdrawn_at` and
`withdrawn_reason` come from the `Retraits` sheet, which is the only one
that has them, and they are the reason a lookup can say *why* a product is
off-market rather than just that it is.

`meta` keys: `version_label`, `source_url`, `source_filename`, `built_at`,
`row_count`, `main_sheet`, `unparsed_doses`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_build_index.py -v`
Expected: FAIL with `ImportError: cannot import name 'build'`

- [ ] **Step 3: Implement `build()`**

Open with `read_only=True, data_only=True`. Read the main sheet by the name
that starts with `Nomenclature` rather than by exact match. Locate each
sheet's header row as the first row carrying at least 8 of the required
header prefixes — not by hardcoding 16/12/11, since those move between
releases. **Resolve columns separately per sheet with `find_header`**, because
`Retraits` has a different layout: no `OBS`, no `DATE D'ENREGISTREMENT FINAL`,
and `TYPE`/`STATUT` two positions to the left of the other two sheets. A
prefix that resolves on one sheet returns a different index — or `None` — on
another, which is exactly how a caller detects an absent column. If a
required column is missing from a sheet that should have it, raise
`BuildError` naming the sheet and the header.

Read all three sheets and insert every row, setting `availability` from
**which sheet the row came from** — `active`, `not_renewed`, `withdrawn`.
Do not join the other two sheets onto the main rows: they are disjoint, so
that produces one row out of 9595. Capture `DATE DE RETRAIT` and
`MOTIF DE RETRAIT` from `Retraits` into `withdrawn_at` / `withdrawn_reason`.

Every cell gets `.strip()`. `type` and `statut` additionally get `.upper()` —
the file contains `'RE '`, `' RE'`, `'I '` and a lowercase `'i'`. Store `type`
verbatim otherwise: `BIO` is its own value, and a blank stays blank rather
than becoming `GE`.

Insert every data row that has any content, not only rows with a brand: the
main sheet has 5425 data rows and one of them carries no `FORME`, which is
still a product. Emptying the brand column is not a filter condition.

Cross-check each sheet's parsed row count against the number the sheet
declares for itself, and raise `BuildError` on a mismatch. The declaration is
real and parseable — it sits in the title row above the header, as
`( N DE )`:

```
r12: NOMENCLATURE NATIONALE DES PRODUITS ... AU 31 AOUT 2026  ( 5425 DE )
r9:  LISTE DES PRODUITS ... QUI N'ONT PAS FAIT L'OBJET DE RENOUVELLEMENT ... ( 1491 DE )
r9:  LISTE DES PRODUITS ... FAISANT L'OBJET DE RETRAIT ... ( 2679 DE )
```

Match it with `\(\s*(\d+)\s+DE\s*\)` against the rows above the header, and
take the last numeric declaration found. This is the cheapest way to catch a
silently-misparsed sheet, and it is the only check that fires when a future
release moves the header row or drops a column in a way `find_header` still
tolerates. It is also the check whose absence lets a truncated index ship.

Write `version_label` parsed from the main sheet name — `Nomenclature Aout 2026`
→ `Août 2026` — via a small French-to-UTF-8 month map, never from the
filename. Note the sheet name carries `Aout` without the accent. Write
`built_at` as an ISO timestamp. Write to a temp file and `os.replace` it over
the target so a crashed build cannot leave a half-written index.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_build_index.py -v`
Expected: 4 passed

- [ ] **Step 5: Build the real index and sanity-check it**

```bash
python dz-generics/scripts/build_index.py data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx
```

Expected output, all verified against the real file beforehand:

| figure | expected |
|---|---|
| `row_count` | **9595** — exactly 5425 + 1491 + 2679 |
| `active` | 5425 |
| `not_renewed` | 1491 |
| `withdrawn` | 2679 |
| `unparsed_doses` | **810** — 416 main + 150 not-renewed + 244 withdrawn |

`unparsed_doses` counts rows whose `DOSAGE` has no determinable dimension, and
they are carried through as *unknown*. It is **not** zero, and zero would be a
bug: it would mean `dose_key` is inventing numbers out of `q.s` rows. An
earlier draft of this plan said "roughly 22", which was the pre-fix figure
before the mandatory-unit rule landed; 810 is the current, correct value.

`meta` must record `row_count` and `unparsed_doses` **across all three
sheets**, since all three are indexed.

- [ ] **Step 6: Commit**

```bash
git add dz-generics/scripts/build_index.py tests/test_build_index.py dz-generics/data/nomenclature.sqlite
git commit -m "feat: build SQLite index from ministry nomenclature"
```

---

## Task 4: Lookup and equivalence

**Files:**
- Create: `dz-generics/scripts/lookup.py`
- Create: `tests/test_lookup.py`

**Interfaces:**
- Consumes: `data/nomenclature.sqlite` (Task 3), `fold` (Task 2)
- Produces:
  - `LookupResult` — a dataclass with fields `query: str`, `status: str`
    (one of `"found"`, `"ambiguous"`, `"not_found"`), `dci_base_key: str | None`,
    `anchor: Product | None`, `candidates: list[Product]`, `version_label: str`,
    and four **properties**: `equivalents`, `other_dosages`, `other_forms`,
    `inactive`. Properties, not methods — the anchor is already on the result,
    so passing it back in is redundant.
  - `Product` — a dataclass mirroring one `product` row, exposing `brand`,
    `dci`, `form`, `form_key`, `dosage`, `dose_key`, `lab`, `country`,
    `type`, `availability`.
  - `lookup(name: str | None = None, dci: str | None = None, code: str | None = None) -> LookupResult`
  - `LookupResult.to_json() -> str`
  - CLI `lookup.py --name <str> | --dci <str> | --code <str>`, optional
    `--json`, optional `--include-inactive`. Exit 0 on a hit, 1 on no hit,
    2 on a usage error.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lookup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lookup'`

- [ ] **Step 3: Implement `lookup.py`**

Resolution order: exact `brand_key` match, then exact `dci_key` or
`dci_base_key` match, then `code` match, then
`difflib.get_close_matches(cutoff=0.85)` against distinct `brand_key` values.
Fuzzy results become `candidates`; if the user did not disambiguate, status
is `ambiguous` and the script prints candidates without picking one. The
source file misspells the same substance several ways, so a miss must report
`not_found` rather than widen the net.

Pick the **anchor**. A brand is not one product — `DOLIPRANE` is twelve rows
across tablets, suppositories and sachets — so the rule has to be pinned or
the answer is arbitrary. Verified against the index:

1. Consider the rows the query matched.
2. Prefer rows with `availability = 'active'`. If none are active, use all of
   them — the anchor is then itself off-market and must be flagged as such.
3. Among those, take the row whose `(dose_key, form_key)` sorts first
   lexicographically. This is arbitrary but deterministic, which is what a
   test needs; every alternative lands in the other buckets anyway.

For `DOLIPRANE` that yields the `COMPRIME` / `1000MG` tablet, whose raw form in
the file is the misspelling `COMRPIME` — a useful confirmation that `form_key`
canonicalization is on the path. Its `equivalents` are the **7** active
paracetamol 1000 mg tablets: `ANTALGAN`, `DOLI-BIEN`, `DOLIPRANE`, `DOLYC`,
`EXPANDOL`, `PARACETAMOL PHYSIOPHARM`, `ROSADOL`.

Then group every product sharing the anchor's `dci_base_key` into four buckets
by `(form_key, dose_key)` and `availability`: `equivalents` (same form, same
dose, `active`), `other_dosages`, `other_forms`, and `inactive` (everything
whose `availability` is not `active`). `--include-inactive` folds `inactive`
back into `equivalents` for the rare user who wants the full historical
picture, and says so in the output.

**The anchor itself may be off-market.** `POLARAMINE` is in **both** the
not-renewed and the withdrawn lists — 4 rows, 1 and 3 — and has **no active
row at all**, so its anchor is a withdrawn \`SIROP\` and the answer must lead
with that rather than presenting anything as available. Carry
`withdrawn_reason` through for withdrawn records: POLARAMINE's rows carry
three different ones, and "retrait par le détenteur pour motif commercial" is
the difference between a drug that was unsafe and one that simply stopped
selling. The user cannot tell without being told.

Note that a brand can also appear under several registration numbers in the
*same* form and dose, and the two off-main sheets overlap on 40 registration
numbers, so availability is not a single value per brand. When the anchor
matches several rows, say so rather than picking one silently.

Render `statut` as *made in Algeria* (`F`) or *imported* (`I`), never as an
availability statement, and render `type` as generic-equivalent (`GE`),
reference product (`RE`) or biologic (`BIO`). A `BIO` row in the equivalents
list must be visibly marked, because a biosimilar is not interchangeable with
a chemical generic the way a `GE` is.

Print `version_label` on every invocation. If `built_at` is older than 90
days, print a staleness warning. Use compact aligned text by default and
`--json` for structured output.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lookup.py -v`
Expected: 6 passed

- [ ] **Step 5: Manual spot-check against names a pharmacist would recognize**

```bash
python dz-generics/scripts/lookup.py --name "DOLIPRANE"
python dz-generics/scripts/lookup.py --dci "PARACETAMOL"
python dz-generics/scripts/lookup.py --name "Augmentin"
python dz-generics/scripts/lookup.py --name "Polaramine"
```

Expected, against the verified data:

| command | what to verify |
|---|---|
| `--name "DOLIPRANE"` | anchor is the `COMPRIME` 1000 mg tablet (`COMRPIME` in the file, canonicalized); **7** active equivalents listed with laboratories, all `made in Algeria` (`F`) |
| `--dci "PARACETAMOL"` | the same anchor by the DCI route, and that `other_dosages` / `other_forms` separate 500 mg tablets, effervescent and orodispersible forms rather than merging them |
| `--name "Augmentin"` | resolves to the active `RE` sachet 1000MG/125MG, with **7 `GE` copies** alongside — 6 made locally and `AMOXICILLINE/ACIDE CLAVULANIQUE SANDOZ ADULTE` imported (`I`) |
| `--name "Polaramine"` | resolves although it is on no active list; leads with its off-market status and carries a withdrawal reason; must present nothing as available |
| `--name "dolipran"` | `ambiguous` with DOLIPRANE as a candidate, **not** silently resolved |
| `--name "zzzznotadrug"` | exits 1 with a clear message, no guess |

Then check the rendering rules by eye: `statut` shown as *made in Algeria* / *imported* and never as availability; `type` shown as `GE` / `RE` / `BIO` with any `BIO` row visibly marked; and the version label printed on every invocation.

- [ ] **Step 6: Commit**

```bash
git add dz-generics/scripts/lookup.py tests/test_lookup.py
git commit -m "feat: lookup with equivalence classes and ambiguity handling"
```

---

## Task 5: Write the skill

**Files:**
- Create: `dz-generics/SKILL.md`
- Create: `dz-generics/references/answering.md`

**Interfaces:**
- Consumes: `lookup.py` CLI (Task 4)
- Produces: the packaged skill directory

- [ ] **Step 1: Draft `SKILL.md`**

Frontmatter `name: dz-generics`. The `description` is the only thing that decides whether this fires, so it must be pushy and cover all three input routes — brand name, DCI, and the natural phrasings a user actually types. Write it in English; name the French, Arabic and Darija phrasings explicitly, since a user asking "بديل دوليبران" should still match.

The body covers: run `lookup.py` first and never answer from memory; report the anchor's DCI, form and dosage; list equivalents grouped by laboratory with the country of origin; state the version label; state that substitution is the pharmacist's decision; flag inactive products. Point to `references/answering.md` for phrasing and to `scripts/build_index.py` for refreshing. Keep under 120 lines.

- [ ] **Step 2: Write `references/answering.md`**

One worked example per language. Show the distinction between "same DCI, same form, same dosage" and "same DCI, different dosage" in the output itself, since that is where a careless answer becomes a medical error. Include the exact closing sentence about the pharmacist.

- [ ] **Step 3: Verify the skill is self-contained**

```bash
python -c "import os,shutil,tempfile;p=os.path.join(tempfile.gettempdir(),'skilltest');shutil.rmtree(p,ignore_errors=True);shutil.copytree('dz-generics',p);print(sorted(os.listdir(p)))"
python "%TEMP%/skilltest/scripts/lookup.py" --name "DOLIPRANE"
```

Expected: the lookup runs from a copy in the system temp directory with no
reference to the repo, proving the skill carries its own data. On PowerShell
use `$env:TEMP` in place of `%TEMP%`.

- [ ] **Step 4: Commit**

```bash
git add dz-generics/SKILL.md dz-generics/references/answering.md
git commit -m "docs: author dz-generics skill and answering guidance"
```

---

## Phase 4 — Evaluation

**Skill:** `superpowers:skill-creator`

- [ ] **Step 1: Write 3 realistic test prompts to `dz-generics-workspace/evals/evals.json`** — one brand lookup in French, one DCI lookup in Arabic, one deliberately unanswerable drug that must produce an honest "not in the nomenclature" instead of a plausible invention. That third one is the most important of the three.

- [ ] **Step 2: Spawn all six runs in one turn** — three with the skill, three without it as baseline — per the skill-creator procedure.

- [ ] **Step 3: Draft assertions while they run.** The one that matters: on the unanswerable drug, the with-skill run must not name a specific generic, and the baseline almost certainly will.

- [ ] **Step 4: Grade, aggregate, run `eval-viewer/generate_review.py` with `--static`, and hand it to the user.** Use `--static` — there is no display here, so it writes a standalone HTML file to open manually.

- [ ] **Step 5: Iterate on the feedback.** The most likely finding is that the model over-explains or omits the version label.

## Phase 5 — Publish and Maintain

Public repo `adelpro/dz-generics`, MIT licensed.

**Redistribution line, and it is a real one:** the derived SQLite index ships, the ministry's `.xlsx` does not. The index is a factual list of registrations — names, forms, dosages, labs — published by a government ministry as public information. The `.xlsx` is the ministry's own document. Committing a 1.2 MB government file into a public repo invites a takedown and gives you nothing, because `fetch_source.py` can fetch it in one request. So `data/source/` is gitignored, and the README states plainly that the source file is not redistributed and must be downloaded from the ministry.

- [ ] **Step 1: Write `scripts/fetch_source.py`** — fetch the ministry page, regex the first `.xlsx` URL whose anchor text matches `Version`, download to `data/source/`. Print the URL and the byte count. Keep it out of the query path entirely; the filename pattern is inconsistent and this will break at some point. When it does, the manual download still works, so a failure here must never block a lookup.

- [ ] **Step 2: Test the fetcher against the live site**

```bash
python dz-generics/scripts/fetch_source.py
```

Expected: downloads a file whose size is within 10% of the known 1,252,820 bytes. A much smaller file means the regex grabbed the wrong link.

- [ ] **Step 3: Write `.gitignore`** with `data/source/`, `__pycache__/`, `*.pyc`, and `dz-generics-workspace/`.

- [ ] **Step 4: Write the README** — what it does, one worked example, the install line, how to refresh, and an explicit data-provenance section: source URL, version label, build date, the statement that the ministry file is not redistributed, and a line that this is a lookup aid and not a source of prescribing advice.

- [ ] **Step 5: Add a medical disclaimer to `SKILL.md`** and mirror it in the README. It must say the tool lists registrations and does not assess bioequivalence, excipients, or clinical suitability, and that a pharmacist or prescriber decides on substitution. This is the kind of thing that must be present before strangers install it, not after.

- [ ] **Step 6: Create the repo, commit, push**

```bash
gh repo create adelpro/dz-generics --public --description "Find generic equivalents of Algerian medicines by brand name or DCI" --license MIT
```

- [ ] **Step 7: Install locally** to `~/.config/opencode/skills/dz-generics/` and confirm it appears in the skills list on next start.

- [ ] **Step 8: Mirror into the private config repo** so your own agents keep receiving updates. Check the mapping in the opencode-synced clone at `~/.local/share/opencode/opencode-synced/repo` — read `buildSyncPlan` in `dist/sync/paths.js` for the skills path. Then copy by hand: the opencode-synced plugin is known broken on this machine, because `shellQuote()` in `dist/shell-node.js` single-quotes arguments that `child_process.exec` hands to `cmd.exe`, which does not strip them, so every `git -C` call fails. Do not fix the plugin as part of this task; run `git add`/`commit`/`push` in the clone directly.

- [ ] **Step 9: Set the refresh cadence.** The ministry publishes every one to two months. Check the page monthly; rebuild only when the version label in `meta` differs from the live page, and push a commit titled with the new version so users can see the data is current.

---

## Open Decisions

Three choices the plan pins a default for. Each is one word from you to change.

1. **Answer language** — default is to mirror the user's language. If you would rather always get French, that is a one-line change in `SKILL.md`.
2. **Publish scope** — default is your private `my-opencode-config` repo only. Making it public means the bundled 1.2 MB source file and the index go public; that is fine, but the ministry's terms on redistribution are worth a look first.
3. **Withdrawn handling** — default excludes withdrawn products from the equivalents list entirely and mentions them in a footnote. If you would rather see them inline marked struck-through, that changes `lookup.py` and the tests.

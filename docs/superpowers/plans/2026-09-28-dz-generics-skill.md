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
- **Never auto-pick a brand on fuzzy match.** Ambiguous input lists candidates and stops.
- **Every answer states the nomenclature version** (e.g. `Nomenclature Août 2026`) and closes with a note that substitution is the pharmacist's or prescriber's decision, since the nomenclature records no bioequivalence or excipient data.
- **Withdrawn and not-renewed products are flagged, never presented as available.** A withdrawn product is a safety issue, not a formatting detail.
- **The index is read-only at query time.** `lookup.py` must never write to the SQLite file.
- **Scripts contain no model-specific logic** — no prompt text, no skill references, no assumptions about who calls them.
- **Answer in the language the user asked in.** Default to French for French queries, Arabic for Arabic queries, English for English. French drug terms must not be translated into English output when the user wrote French.

## Review Focus

These are the five input classes most likely to break this and not yet pinned by any stated requirement. Each gets a test in the owning task.

1. **The same substance written two ways.** The main sheet has `CETIRIZINE DICHLORHYDRATE`; the Retraits sheet has bare `CETIRIZINE`. Salt-suffix stripping must group them, and a match across the two spellings must still show the real DCI string, not a synthesized one.
2. **Dosage written as a ratio vs a concentration.** `0,5MG/5ML` and `1MG/ML` are the same strength but are different strings; `0,5` uses a decimal comma. A naive string compare silently returns zero generics for syrups — the single most common failure mode.
3. **Form written as an abbreviation vs the full word.** `COMP.`, `COMP.PELLI.SEC`, `COMPRIME`, `COMPRIME PELLICULE`. Without canonicalization, a paracetamol tablet lookup misses the generic tablets, which is the headline use case.
4. **The placeholder form `FORME`.** Some rows carry the literal string `FORME` in the form column, meaning unspecified. It must not match every form — that would report a syrup as a tablet equivalent. It gets its own canonical value and a flag.
5. **A product present in both the main sheet and the Retraits sheet.** Withdrawn wins over not-renewed, and the record still resolves to its DCI so the user learns the drug exists but is off-market.

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

## Phase 0 — Ground Truth (done during planning; re-verify in Task 1)

Already established against the live file, so tasks do not re-discover it:

- Source page: `https://www.miph.gov.dz/fr/nomenclature-nationale-des-produits-pharmaceutiques/`
- Current file: `https://www.miph.gov.dz/fr/wp-content/uploads/2026/09/clean_NOMENCLATURE.VERSION.AOUT_.2026-.xlsx` (1,252,820 bytes)
- Downloaded to `data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx`
- Sheets: `Nomenclature Aout 2026` (5441 rows, header row 16, data from 17), `Non Renouvelés ` (1503 rows, header row 12 — **trailing space in the name**), `Retraits` (2690 rows, header row 11)
- Main sheet declares 36 columns but names only ~20. Columns are **not** contiguous — the build must match by header text, never by index.
- `TYPE` holds `GE` / `RE`. `STATUT` holds `F` / `I`. Their exact meanings are **not yet confirmed** and Task 2 settles it from the data.

Filename patterns are inconsistent across releases (`clean_` prefix appears and disappears; upload month does not match version month). The version label must come from the **sheet name**, which is stable, not the filename.

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
    """Review Focus #2: 0,5MG/5ML and 1MG/ML are the same strength."""
    from normalize import dose_key
    assert dose_key("0,5MG/5ML") == dose_key("1MG/ML")
    assert dose_key("6,25MG/5ML") == dose_key("1,25MG/ML")


def test_dose_key_distinct_strengths_stay_distinct():
    from normalize import dose_key
    assert dose_key("500MG") != dose_key("1G")
    assert dose_key("10MG") != dose_key("20MG")


def test_dci_keys_group_salt_and_base():
    """Review Focus #1."""
    from normalize import dci_keys
    exact, base = dci_keys("CETIRIZINE DICHLORHYDRATE")
    exact2, base2 = dci_keys("CETIRIZINE")
    assert base == base2
    assert exact != exact2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normalize'`

- [ ] **Step 3: Implement `normalize.py`**

`fold`: NFKD normalize, drop combining marks, uppercase, replace every non-alphanumeric run with a single space, strip.

`FORM_CANON`: build a dict from the distinct `FORME` values dumped in Task 1 Step 3, mapping each observed abbreviation to a canonical token. It must be derived from observed data, not from a guessed list — add a comment naming the source sheet and row count. Map the literal `FORME` to `NON_SPECIFIE`.

`dose_key`: extract number, unit, and optional `/per` amount. Decimal comma becomes a period. A `X per Y` ratio is reduced to a base ratio by dividing, so the key is comparable across ratio and concentration forms. Convert `G`→`MG`, `µG`→`MG` at a factor of 1000, `ML`→ per-mL denominator preserved as a number. Return `None` when no number is found.

`dci_keys`: fold the DCI, sort its tokens alphabetically into the exact key, then drop salt and hydrate suffixes (DICHLORHYDRATE, CHLORHYDRATE, SULFATE, MALEATE, FUMARATE, MESYLATE, TOSYLATE, SODIUM, POTASSIUM, CALCIUM, TRIHYDRATE, ANHYDROUS) to produce the base key. The suffix list must also be checked against the distinct DCI values from Task 1 Step 3 and extended if the data contains suffixes not listed here.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: 6 passed

- [ ] **Step 5: Write `dz-generics/scripts/profile_source.py` and run it against the real file**

Unit tests only prove the normalizer handles the cases you already thought
of. This script is how you find the ones you did not — and it is the tool to
re-run whenever the ministry changes a column, so it ships as a real
artifact rather than a throwaway command. It reads the main sheet, skips to
row 17, and prints: row count, a descending frequency count of `form_key`,
how many dosages `dose_key` returned `None` for, and the 25 most common raw
`FORME` strings. Give it a `main()`, an `argparse` path argument, and a
`if __name__ == "__main__":` guard.

Then run it:

```bash
python dz-generics/scripts/profile_source.py data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx
```

Expected: `unparsed dosages: 0`, and `NON_SPECIFIE` under 5% of rows.

**Gate:** if `NON_SPECIFIE` is 5% or more, the `FORME` placeholder is common
enough that Step 3's `FORM_CANON` is missing real values. Go back, extend it,
and comment the `FORM_CANON` dict with which observed values map to
`NON_SPECIFIE` and why. Do not proceed to Task 3 with an unexplained gap —
Task 3 writes these keys into the index and Task 4 reports on them.

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
  availability TEXT   -- 'active' | 'not_renewed' | 'withdrawn'
);
CREATE INDEX idx_brand ON product(brand_key);
CREATE INDEX idx_dci   ON product(dci_base_key);
CREATE INDEX idx_code  ON product(code);
CREATE INDEX idx_reg   ON product(reg_no);
```

`meta` keys: `version_label`, `source_url`, `source_filename`, `built_at`, `row_count`, `main_sheet`, `unparsed_doses`.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_reads_real_workbook(tmp_path):
    from build_index import build
    out = tmp_path / "n.sqlite"
    stats = build(SOURCE_XLSX, str(out))
    assert stats["row_count"] > 5000
    assert out.exists()


def test_build_fails_loudly_when_row_count_collapses(tmp_path):
    """A silently-truncated index is worse than no index."""
    from build_index import BuildError, build
    with pytest.raises(BuildError):
        build(SOURCE_XLSX, str(tmp_path / "n.sqlite"), previous_row_count=50000)


def test_withdrawn_product_is_flagged(tmp_path):
    """Review Focus #5."""
    import sqlite3
    from build_index import build
    out = tmp_path / "n.sqlite"
    build(SOURCE_XLSX, str(out))
    con = sqlite3.connect(out)
    n = con.execute("SELECT COUNT(*) FROM product WHERE availability='withdrawn'").fetchone()[0]
    assert n > 100
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_build_index.py -v`
Expected: FAIL with `ImportError: cannot import name 'build'`

- [ ] **Step 3: Implement `build()`**

Open with `read_only=True, data_only=True`. Read the main sheet by the name that starts with `Nomenclature` rather than by exact match. Locate the header row as the first row where at least 8 of the required header prefixes are present. Resolve every column by `find_header`. If any required column is missing, raise `BuildError` naming the missing header.

Read `Non Renouvelés ` and `Retraits` by prefix match too. Join them onto the main rows by `reg_no`. Availability precedence: `withdrawn` beats `not_renewed` beats `active`.

Write `version_label` parsed from the main sheet name — `Nomenclature Aout 2026` → `Août 2026` — via a small French-to-UTF-8 month map, never from the filename. Write `built_at` as an ISO timestamp. Write the script to a temp file and `os.replace` it over the target so a crashed build cannot leave a half-written index.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_build_index.py -v`
Expected: 3 passed

- [ ] **Step 5: Build the real index and sanity-check it**

```bash
python dz-generics/scripts/build_index.py data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx
```

Expected output includes a row count near 5425, a `withdrawn` count near 2690, and `unparsed_doses 0`.

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
    """The headline use case, end to end against the real index."""
    from lookup import lookup
    res = lookup(name="doliprane")
    assert res.query == "doliprane"
    assert res.status == "found"
    assert res.dci_base_key is not None
    assert len(res.equivalents) > 1
    assert all(p.form_key == "COMPRIME" for p in res.equivalents)


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


def test_close_but_wrong_name_returns_candidates_not_a_pick():
    from lookup import lookup
    res = lookup(name="doliprna")
    assert res.status == "ambiguous" or res.status == "found"
    if res.status == "ambiguous":
        assert len(res.candidates) >= 1


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

Resolution order: exact `brand_key` match, then exact `dci_key` or `dci_base_key` match, then `code` match, then `difflib.get_close_matches(cutoff=0.85)` against distinct `brand_key` values. Fuzzy results become `candidates`; if the user did not disambiguate, status is `ambiguous` and the script prints candidates without picking one.

Pick the **anchor**: the best match for the query, preferring an exact brand hit. Group every product sharing the anchor's `dci_base_key` into three buckets by `(form_key, dose_key)`: `equivalents`, `other_dosages`, `other_forms`. Withdrawn and not-renewed records are excluded from `equivalents` by default and surfaced in a separate `inactive` list so the model can flag them without presenting them as available.

Print `version_label` on every invocation. If `built_at` is older than 90 days, print a staleness warning. Use compact aligned text by default and `--json` for structured output.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lookup.py -v`
Expected: 5 passed

- [ ] **Step 5: Manual spot-check against names a pharmacist would recognize**

```bash
python dz-generics/scripts/lookup.py --name "DOLIPRANE"
python dz-generics/scripts/lookup.py --dci "PARACETAMOL"
python dz-generics/scripts/lookup.py --name "Augmentin"
python dz-generics/scripts/lookup.py --name "Polaramine"
```

Expected: paracetamol and amoxicillin return multiple local laboratories; Polaramine shows as a `RE` reference product with its own equivalents; a genuinely absent name exits 1 with a clear message rather than a guess.

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

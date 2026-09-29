---
name: dz-generics
description: Find the generic equivalent, alternative, or substitute of a medicine in Algeria, or check whether a brand is registered or still on the Algerian market, from the Ministry of Industry's national nomenclature. Use whenever a medicine, brand, or active substance is named with Algeria, its availability, its laboratories, or its local-vs-imported origin. Fires on French ("le générique du Doliprane", "l'équivalent du paracétamol", "disponible en Algérie", "médicament remboursé"), Arabic ("بديل دوليبران", "البدائل المتوفرة في الجزائر للباراسيتامول", "هل هذا الدواء متوفر في الجزائر", "مثيل الدواء"), English ("generic alternative in Algeria", "is Tylenol available in Algeria", "which lab makes X in Algeria"), and Darija or transliterated spellings of brand and DCI names (dolipran, doliprane, paracetamol, الباراسيتامول). Always answers by running the bundled scripts/lookup.py against the committed ministry index — never from its own knowledge.
license: MIT
metadata:
  author: Adel Ben Yahia (adelpro)
  version: 1.0.0
  hermes:
    tags: [pharmacy, algeria, medicine, generics, availability]
    related_skills: [skill-creator, skill-validator-omni]
---

# dz-generics — Algerian generic equivalents

Answers "what is the generic equivalent of this medicine in Algeria?" from the
Ministry of Industry and Pharmaceutical Production's *Nomenclature nationale*,
shipped as a committed SQLite index (9,595 registration rows).

It reports what the registry **lists**: registrations, forms, dosages,
laboratories, and whether each product is active, not renewed, or withdrawn. It
does **not** assess bioequivalence, excipients, stability, or clinical
suitability, and it is not prescribing advice.

Paths below are relative to the folder holding this `SKILL.md` (default install:
`~/.config/opencode/skills/dz-generics`). The index travels with the script, so
the working directory does not matter.

## When to Use

- A medicine, brand, or active substance is named together with Algeria.
- The user asks whether a brand is available, registered, sold, or still on the
  market in Algeria.
- The user asks for a generic, equivalent, alternative, substitute, or
  "مثيل" / "بديل" for an Algerian medicine.
- The user asks which laboratory makes a product, or whether it is made in
  Algeria or imported.
- Any of these in French, Arabic, English, or Darija, including transliterated
  brand and DCI spellings.

## Don't Use For

- Bioequivalence, therapeutic substitution decisions, dosing, or interactions —
  this tool lists registrations and nothing else.
- Medicines outside Algeria. The nomenclature covers only products registered
  for the Algerian market.
- Pricing, reimbursement, or stock availability — none of that is in the index.

## Prerequisites

- `python3` on PATH. Query time uses only the Python standard library
  (`sqlite3`); nothing to install.
- `scripts/lookup.py` and `data/nomenclature.sqlite` must travel together. The
  index is committed, so no build step is needed for a lookup.
- On Windows, set `$env:PYTHONIOENCODING="utf-8"` first, or accented and Arabic
  output is mangled by the console codepage.

## Procedure

### 1. Never answer from your own knowledge

**This is the non-negotiable step.** The nomenclature is the only authority on
what is registered in Algeria. Model memory of French and Algerian brand names
is confidently wrong exactly here — a product can be off-market, made by a
different laboratory, or absent altogether. If you have not run the command in
step 2 during this turn, you do not have an answer.

Never invent a product, a laboratory, or a registration number. If the tool did
not return it, it is not in the answer.

### 2. Run the lookup

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts/lookup.py --name "DOLIPRANE"    # brand as printed
python scripts/lookup.py --dci "PARACETAMOL"   # by active substance
python scripts/lookup.py --code "03 B 081"     # by registration code
python scripts/lookup.py --name "PARACETAMOL" --json   # full structured output
```

- `--name` is accent- and case-insensitive; use the Latin spelling printed in
  the registry. `--dci` takes the substance, never a brand. `--code` takes a
  registration code. Exactly one of the three is required.
- Add `--json` when you need the complete list: text mode truncates long
  sections at 20 items with `... and N more`.
- `--include-inactive` folds not-renewed and withdrawn rows into the
  equivalents list. Do **not** use it for a normal answer; it is for a
  deliberate historical or market-exit question.
- Exit codes: `0` answered (found or ambiguous), `1` not found, `2` usage error.

### 3. Read the output

1. The **first line is the version label**. Every answer states it.
2. The **Anchor** block names the product the tool chose: brand, DCI, form,
   dosage, its own status (`active` / `not renewed` / `withdrawn`), origin
   (`made in Algeria` / `imported`), type, and registration number.
3. Then five sections, and their difference is the whole safety story:
   - **EQUIVALENTS** — same DCI, same form, same dose. The only genuinely
     equivalent class.
   - **Other dosages** — same form, *different* dose. **Not equivalent.**
   - **Unknown dose** — same form, dose not determinable. **Not evidence of a
     difference** — do not describe it as a difference and do not offer it as
     equivalent.
   - **Other forms** — different form. **Not equivalent.**
   - **Off-market** — withdrawn or not renewed at the anchor's form and dose.
     **Not available. Do not present as an option.**
4. Each line carries the laboratory, `made in Algeria` or `imported`, and the
   type `GE` (generic), `RE` (reference), or `BIO` (biologic). An off-market row
   is marked `[withdrawn]` or `[not renewed]` **wherever it appears**, in every
   section; a line with no marker is an active one. Never drop the marker when
   you reformat a line.
5. **A sixth section may appear: "Other products under this name".** Some names
   cover more than one medicine. NOBAC is a chewable tablet
   (alginate/bicarbonate/**calcium carbonate**) and a suspension
   (alginate/bicarbonate) — two different DCIs under one brand. MANTIXA carries
   terbinafine and molsidomine, which share no ingredient at all. When this
   section is present you **must** show it: those products are **not**
   equivalents, and the tool is telling you the name is ambiguous. Say plainly
   which one the answer is about, and if the user asked about a different form,
   tell them the other product exists and how to ask for it (by its own DCI or
   code). When the tool flags them as unrelated, say that too — it is a fact
   about the registry, not a suggestion of equivalence.

### 4. Answer

1. State the version label and the anchor's DCI, form and dosage.
2. **Check the anchor's own status first.** If it is `withdrawn` or
   `not renewed`, lead with that: the brand is not obtainable, never present it
   as available, and never label another brand's products as its "generics".
   You may then present the **active** class of the same DCI/form/dose,
   explicitly as *the substance's* class.
3. If the anchor is active, list the equivalents **grouped by laboratory**, each
   with made-in-Algeria vs imported and its type.
4. Keep the three "not equivalent" reasons separate and named: **different
   dose**, **different form**, **unknown dose**. Never collapse them and never
   present an unknown dose as a difference.
5. Off-market products go in their own clearly labelled block, with `withdrawn`
   or `not renewed` shown, and are never offered as an alternative. Keep the
   `[withdrawn]` / `[not renewed]` marker on **any** off-market row you list,
   whatever section it came from.
6. Close with the disclaimer sentence in step 6.

### 5. Match the user's language

Mirror the user's language: French query, French answer; Arabic, Arabic;
English, English. Drug names stay in the nomenclature's own Latin/French form,
because that is what is printed on the box and what a pharmacist reads.

The registry contains no Arabic. If the user asks in Arabic or Darija, or uses a
transliterated spelling, resolve the name to its Latin registry form first
(دوليبران → DOLIPRANE, الباراسيتامول → PARACETAMOL, بنادول → the substance
PARACETAMOL), then run the tool.

### 6. Always close with the disclaimer

> Equivalence here means same DCI, same form, same dose. It is not a statement
> of bioequivalence, and substitution is the pharmacist's or prescriber's
> decision.

## Common Edge Cases

- **The user named a specific dose or form.** The tool picks its own anchor
  (lowest active known dose). If that is not what the user asked for, say which
  row you are answering for. To answer for the requested form and dose, take a
  row at that form and dose from `--json`, re-anchor on it with
  `--code "<its code>"`, then re-check the new anchor's form and dosage. Never
  promote a different-dose or different-form row into the equivalent list.
- **`ambiguous`** — a near match is not a match. Present the candidates and ask
  the user to pick one. Do not choose for them.
- **`not found`** — say plainly that nothing in the nomenclature matches. Do not
  guess. If the user named a foreign brand that is not in the registry, say so;
  you may offer to look up its substance by DCI, but never relabel another
  brand's products as "generics of X".
- **A brand that exists only with a suffix.** Some brands appear in the registry
  only as `NAME <variant>` (for example `RIFEX 120`, `RIFEX 180`). If a bare
  name misses, try the suffixed forms before concluding it is absent.
- **A foreign brand with no Algerian registration.** State that it is not
  registered here. The substance mapping you offer is general knowledge; the
  products you list must come from the registry, and say which is which.

## Pitfalls

- **The three "not equivalent" reasons are not interchangeable.** "Different
  dose", "different form", and "unknown dose" are different claims. An unknown
  dose is *not* evidence of a difference — presenting it as one is a false
  statement about a medicine, on the safe side but still false.
- **Off-market is not a footnote.** A `withdrawn` or `not renewed` product must
  never sit in a list of options. Every off-market line keeps its marker.
- **`GE` is not a quality grade.** It means the registry classifies the product
  as a generic equivalent of the same DCI/form/dose. It says nothing about
  bioequivalence. `BIO` (biologic) is not interchangeable with a chemical `GE`
  the way another `GE` is, and a blank type is not `GE`.
- **`made in Algeria` / `imported` is not availability.** It is the origin of
  the marketing-authorisation holder. Never read it as "obtainable".
- **The text output truncates at 20 items per section.** If a section ends with
  `... and N more`, re-run with `--json` before claiming the list is complete.
- **The index is a snapshot.** It carries a version label and a build date. If
  the tool warns the index is stale, pass that warning on.

## Verification

- The answer names the nomenclature version, and it matches the tool's first
  line.
- Every product, laboratory, and registration number in the answer appears in
  the tool's output. Nothing was supplied from memory.
- Every equivalent listed shares the anchor's DCI, form, and dosage; anything at
  a different dose or form is labelled *not equivalent* with its stated reason.
- Every off-market product carries `[withdrawn]` or `[not renewed]`, and none is
  presented as available.
- The answer closes with the disclaimer sentence, in the user's language.
- If the lookup missed, the answer says so and offers no invented product.

## Files

- [references/answering.md](references/answering.md) — worked examples (FR, AR,
  EN) and the phrasing/trigger table.
- [references/schema.md](references/schema.md) — the verified source schema.
- `scripts/build_index.py` — rebuild the index after a ministry refresh;
  `scripts/fetch_source.py` downloads the source workbook from the ministry.

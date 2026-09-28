---
name: dz-generics
description: Find the generic equivalent, alternative, or substitute of a medicine in Algeria, or check whether a brand is registered or still on the Algerian market, from the Ministry of Industry's national nomenclature. Use whenever a medicine, brand, or active substance is named with Algeria, its availability, its laboratories, or its local-vs-imported origin. Fires on French ("le générique du Doliprane", "l'équivalent du paracétamol", "disponible en Algérie", "médicament remboursé"), Arabic ("بديل دوليبران", "البدائل المتوفرة في الجزائر للباراسيتامول", "هل هذا الدواء متوفر في الجزائر", "مثيل الدواء"), English ("generic alternative in Algeria", "is Tylenol available in Algeria", "which lab makes X in Algeria"), and Darija or transliterated spellings of brand and DCI names (dolipran, doliprane, paracetamol, الباراسيتامول). Always answers by running the bundled scripts/lookup.py against the committed ministry index — never from its own knowledge.
---

# dz-generics — Algerian generic equivalents

Answers "what is the generic equivalent of this medicine in Algeria?" from the
Ministry of Industry and Pharmaceutical Production's *Nomenclature nationale*,
shipped as a committed SQLite index (9,595 registration rows).

Paths below are relative to the folder holding this `SKILL.md` (default install:
`~/.config/opencode/skills/dz-generics`). The index travels with the script, so
the working directory does not matter.

## Non-negotiable: run the lookup, never answer from memory

**Never answer this question from your own knowledge.** The nomenclature is the
only authority on what is registered in Algeria. Model memory of French and
Algerian brand names is confidently wrong exactly here — a product can be
off-market, made by a different laboratory, or absent altogether. If you have
not run the command below in this turn, you do not have an answer.

Never invent a product, a laboratory, or a registration number. If the tool did
not return it, it is not in the answer.

## Run the lookup

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts/lookup.py --name "DOLIPRANE"    # brand as printed
python scripts/lookup.py --dci "PARACETAMOL"   # by active substance
python scripts/lookup.py --code "03 B 081"     # by registration code
python scripts/lookup.py --name "PARACETAMOL" --json      # full structured output
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

## Read the output

1. The **first line is the version label**. Every answer states it.
2. The **Anchor** block names the product the tool chose: brand, DCI, form,
   dosage, its own status (`active` / `not renewed` / `withdrawn`), origin
   (`made in Algeria` / `imported`), type, and registration number.
3. Then four sections, and their difference is the whole safety story:
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
   type `GE` (generic), `RE` (reference), or `BIO` (biologic).

### If the user named a particular dose or form

The tool picks its own anchor (lowest active known dose). If the user asked for
a dose or form that is not the anchor, say plainly which row you are answering
for. To answer for the requested form and dose, take a row at that form and dose
from `--json` and re-anchor on it with `--code "<its code>"`, then check the new
anchor's form and dosage before you report it. Never promote a different-dose or
different-form row into the equivalent list. Details in
[references/answering.md](references/answering.md).

## Answer format

1. State the version label and the anchor's DCI, form and dosage.
2. List the equivalents **grouped by laboratory**, each with made-in-Algeria vs
   imported and its type.
3. Keep the three "not equivalent" reasons separate and named: **different
   dose**, **different form**, **unknown dose**. Never collapse them and never
   present an unknown dose as a difference.
4. Off-market products go in their own clearly labelled block, with `withdrawn`
   or `not renewed` shown, and are never offered as an alternative.
5. Close with the disclaimer sentence below.

## Language

Mirror the user's language: French query, French answer; Arabic, Arabic;
English, English. Drug names stay in the nomenclature's own Latin/French form,
because that is what is printed on the box and what a pharmacist reads.

The registry contains no Arabic. If the user asks in Arabic or Darija, or uses a
transliterated spelling, resolve the name to its Latin registry form first
(دوليبران → DOLIPRANE, الباراسيتامول → PARACETAMOL, بنادول → the substance
PARACETAMOL), then run the tool.

## When the tool is ambiguous or misses

- **ambiguous** — a near match is not a match. Present the candidates and ask
  the user to pick one. Do not choose for them.
- **not found** — say plainly that nothing in the nomenclature matches. Do not
  guess. If the user named a foreign brand that is not in the registry, say so;
  you may offer to look up its substance by DCI, but never relabel another
  brand's products as "generics of X".

## Disclaimer — include in every answer, in the user's language

> Equivalence here means same DCI, same form, same dose. It is not a statement
> of bioequivalence, and substitution is the pharmacist's or prescriber's
> decision.

## Files

- [references/answering.md](references/answering.md) — worked examples (FR, AR,
  EN) and the phrasing/trigger table.
- [references/schema.md](references/schema.md) — the verified source schema.
- `scripts/build_index.py` — rebuild `data/nomenclature.sqlite` after a
  ministry refresh; `scripts/fetch_source.py` downloads the source workbook.

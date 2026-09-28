# dz-generics

Find the generic equivalents of an Algerian medicine from a brand name, a DCI,
or a registration code — using the Ministry of Industry and Pharmaceutical
Production's *Nomenclature nationale des produits pharmaceutiques à usage de la
médecine humaine*.

An agent skill, a CLI, and a committed SQLite index of the registry.

```console
$ python skills/dz-generics/scripts/lookup.py --name "DOLIPRANE"
Nomenclature nationale -- version Août 2026

Anchor: DOLIPRANE -- PARACETAMOL
  form         : COMRPIME
  dosage       : 1000MG  [key 1000MG]
  status       : active
  origin       : made in Algeria (ALGERIE)
  type         : GE (generic-equivalent)

EQUIVALENTS -- same DCI, same form (COMPRIME), same dose (1000MG):

   1. ANTALGAN -- 1000MG -- GE (generic-equivalent)
      made in Algeria -- SARL ALPHACARE
   2. DOLI-BIEN -- 1000MG -- GE (generic-equivalent)
      made in Algeria -- PHARMIDAL NS
   3. DOLIPRANE -- 1000MG -- GE (generic-equivalent)
      made in Algeria -- PROPHARMAL
   ...
```

## What it does and does not do

It reports what the registry **lists**: which products share an active
substance, form and dosage, which laboratory holds each one, whether it is made
in Algeria or imported, and whether it is active, not renewed, or withdrawn.

It does **not** assess bioequivalence, excipients, stability, or clinical
suitability. Equivalence here means *same DCI, same form, same dose* — nothing
more. **Substitution is the pharmacist's or prescriber's decision.** This is a
lookup aid, not a source of prescribing advice.

## Install

```bash
# any agent, via the skills.sh CLI
npx skills add adelpro/dz-generics -l                 # preview
npx skills add adelpro/dz-generics -a claude-code --copy -y

# or just clone it
git clone https://github.com/adelpro/dz-generics
```

The repo is also an Agent Plugins 1.0.0 package (`plugin.json`), so compatible
clients can load `skills/` directly.

Query time needs only Python 3 and the standard library. Nothing to install.

## Use

```bash
python skills/dz-generics/scripts/lookup.py --name "DOLIPRANE"   # brand
python skills/dz-generics/scripts/lookup.py --dci "PARACETAMOL"  # substance
python skills/dz-generics/scripts/lookup.py --code "03 B 081"    # reg. code
python skills/dz-generics/scripts/lookup.py --name "RIFEX 120" --json
```

On Windows, set `$env:PYTHONIOENCODING="utf-8"` first so accented and Arabic
output is not mangled by the console codepage.

Exit codes: `0` answered (found or ambiguous), `1` not found, `2` usage error.

### How a result is grouped

Five sections, and the difference between them is the point:

| section | meaning |
|---|---|
| **Equivalents** | same DCI, same form, same dose. The only genuinely equivalent class. |
| **Other dosages** | same DCI and form, *different* dose. **Not equivalent.** |
| **Unknown dose** | same DCI and form, dose not determinable. **Not evidence of a difference.** |
| **Other forms** | same DCI, different form. **Not equivalent.** |
| **Off-market** | withdrawn or not renewed at the anchor's form and dose. **Not available.** |

Every off-market row carries `[withdrawn]` or `[not renewed]` **wherever it
appears**; a row with no marker is active.

Three things the output is careful about, because each is a way to be
confidently wrong about a medicine:

- **An unknown dose is not a different dose.** `q.s` and multi-ingredient
  dosages have no determinable strength, so they get their own section instead
  of being reported as a different strength.
- **Off-market is never presented as an option.** A withdrawn product is a
  safety fact, not a formatting detail.
- **A near match is not a match.** A fuzzy hit lists candidates and stops; it
  never picks one for you.

## Data provenance

- **Source:** Ministère de l'Industrie Pharmaceutique,
  [Nomenclature nationale](https://www.miph.gov.dz/fr/nomenclature-nationale-des-produits-pharmaceutiques/).
- **Current index:** version *Août 2026*, 9,595 registration rows
  (5,425 active / 1,491 not renewed / 2,679 withdrawn), built from
  `clean_NOMENCLATURE.VERSION.AOUT_.2026-.xlsx`.
- **The ministry's spreadsheet is not redistributed here.** `data/source/` is
  gitignored. `scripts/fetch_source.py` downloads it in one request, or fetch it
  by hand from the page above. What ships is the derived index: a factual list
  of registrations, with attribution.
- The index records a version label and build date, and the tool warns when it
  is more than 90 days old. **Check the version before relying on an answer.**

## Refreshing the data

The ministry publishes every one to two months.

```bash
python skills/dz-generics/scripts/fetch_source.py        # newest release
python skills/dz-generics/scripts/build_index.py <the .xlsx>
```

`build_index.py` fails loudly rather than indexing garbage: it resolves columns
by header name per sheet, cross-checks each sheet against the row count the
sheet declares for itself, and refuses to write when the row count collapses.
`scripts/profile_source.py` prints the distributions it uses, for when the
ministry renames something.

## Development

```bash
python -m pytest -q -W error
```

80 tests. The suite skips narrowly when the gitignored source workbook is
absent, so a fresh clone runs green.

The normalization layer is the riskiest part of this project: it decides when
two spreadsheet rows describe the same medicine, and a wrong answer there is
invisible. Its rules are derived from the observed data, not assumed, and
`references/schema.md` documents the source layout they are built on.

## License

MIT. See [LICENSE](LICENSE).

The MIT licence covers this project's code and derived index. It does not grant
rights to the ministry's spreadsheet, which is not included.

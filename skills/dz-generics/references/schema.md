# Source schema — Algerian national nomenclature

Everything below was read out of the ministry workbook, not assumed. If you
change `scripts/build_index.py`, this is the document that has to stay true.

**Inspected:** 2026-09-28, from `data/source/NOMENCLATURE.VERSION.AOUT_.2026-.xlsx`
(1,252,820 bytes) with `openpyxl.load_workbook(read_only=True, data_only=True)`.

**Published by:** Ministère de l'Industrie Pharmaceutique,
`https://www.miph.gov.dz/fr/nomenclature-nationale-des-produits-pharmaceutiques/`

The `.xlsx` is not redistributed with this project; download it from the
ministry. Re-verify everything in this file after every refresh — see
[Re-verifying](#re-verifying-after-a-ministry-refresh).

Notation: `␠` marks a significant space inside a string (leading, trailing, or
doubled). Those spaces are real and will break an exact string comparison.

---

## The three sheets

Sheet names are `repr()`-exact. **The trailing space in `Non Renouvelés ` is
part of the name** — `wb["Non Renouvelés"]` raises `KeyError`.

| Sheet name (verbatim) | Header row | First data row | Data rows | `max_column` | Columns carrying data |
|---|---|---|---|---|---|
| `Nomenclature Aout 2026` | 16 | 17 | **5425** | 36 | 0–18 (+ one stray at 35) |
| `Non Renouvelés ` | 12 | 13 | **1491** | 19 | 0–17 |
| `Retraits` | 11 | 12 | **2679** | 21 | 0–17 |

`max_column` is declared, not used. The main sheet claims 36 columns and
fills 19; `Retraits` claims 21 and fills 18. Do not size anything from
`max_column`, and do not use `ws.max_row` as a row count — it is the header
row plus the data rows (5441 / 1503 / 2690).

`Aout` in the main sheet name is **not** accented. Parse the version label from
this name (`Aout` → `Août`), never from the filename — filename patterns
change between releases (`clean_` prefix appears and disappears, and the
upload month does not match the version month).

### Rows above the header

All three sheets open with an institutional banner, so the header row is not
row 1. These are title rows holding the sheet's own row count, which makes
them a free integrity check:

| Sheet | Row | Verbatim |
|---|---|---|
| `Nomenclature Aout 2026` | 6 | `REPUBLIQUE ALGERIENNE DEMOCRATIQUE ET POPULAIRE` |
| | 7 | `                     MINISTERE DE L'INDUSTRIE PHARMACEUTIQUE ` (leading spaces) |
| | 8 | `DIRECTION DE LA PHARMACO-ECONOMIE, DES ACTIVITES PHARMACEUTIQUES ET DE LA REGULATION` |
| | 12 | `NOMENCLATURE NATIONALE DES PRODUITS PHARMACEUTIQUES A USAGE DE LA MEDECINE HUMAINE AU 31 AOUT 2026  ( 5425 DE )` |
| `Non Renouvelés ` | 5, 6, 7 | same banner as above |
| | 9 | `LISTE DES PRODUITS PHARMACEUTIQUES A USAGE DE LA MEDECINE HUMAINE QUI N'ONT PAS FAIT L'OBJET DE RENOUVELLEMENT AU 31 AOUT 2026 ( 1491 DE ) ` (trailing space) |
| `Retraits` | 5, 6, 7 | same banner as above |
| | 9 | `LISTE DES PRODUITS PHARMACEUTIQUES A USAGE DE LA MEDECINE HUMAINE FAISANT L'OBJET DE RETRAIT AU 31 AOUT 2026  ( 2679 DE )` |

Each declared count (5425 / 1491 / 2679) matches the number of data rows
exactly. Assert on it.

---

## Column layout, verbatim

### `Nomenclature Aout 2026` — 19 named columns

| Idx | Header (verbatim) | Notes |
|---|---|---|
| 0 | `N°` | `°` is U+00B0 DEGREE SIGN. Row ordinal, `int`, 1…5425 |
| 1 | `N°ENREGISTREMENT` | registration number; **not unique** (8 duplicates) |
| 2 | `CODE` | short form, 2075 distinct; **not unique per DCI** |
| 3 | `DENOMINATION COMMUNE INTERNATIONALE` | the DCI. No `(DCI)` suffix |
| 4 | `NOM DE MARQUE` | brand |
| 5 | `FORME` | dosage form, free text |
| 6 | `DOSAGE` | strength, free text |
| 7 | `CONDITIONNEMENT` | packaging, 1 blank |
| 8 | `LISTE` | 798 blank |
| 9 | `P1` | `HOP` for 5420 of 5425 |
| 10 | `P2` | `OFF` or blank |
| 11 | `OBS` | 5360 of 5425 blank |
| 12 | `LABORATOIRES DETENTEUR DE LA DECISION D'ENREGISTREMENT` | note `LABORATOIRES` |
| 13 | `PAYS DU LABORATOIRE DETENTEUR DE LA DECISION D'ENREGISTREMENT` | |
| 14 | `DATE D'ENREGISTREMENT INITIAL␠` | trailing space |
| 15 | `DATE D'ENREGISTREMENT␠␠FINAL␠` | **two** spaces before `FINAL`, plus a trailing one |
| 16 | `TYPE` | see [TYPE](#type--originator-versus-copy) |
| 17 | `STATUT` | see [STATUT](#statut--locally-made-versus-imported) |
| 18 | `DUREE DE STABILITE` | 33 distinct, e.g. `24 MOIS`, `36 MOIS␠` |
| 19–35 | *(unnamed)* | empty. Index 35 holds a single stray `' '` (row 4570) |

### `Non Renouvelés ` — 18 named columns

Identical to the main sheet for indices 0–17, **including `OBS` at 11, both
date columns, `TYPE` at 16 and `STATUT` at 17**. There is no
`DUREE DE STABILITE`. Index 18 is unnamed and empty.

### `Retraits` — 18 named columns, laid out differently

| Idx | Header (verbatim) | Main-sheet equivalent |
|---|---|---|
| 0–10 | `N°` … `P2` | same |
| 11 | `LABORATOIRES DETENTEUR DE LA DECISION D'ENREGISTREMENT` | was 12 |
| 12 | `PAYS DU LABORATOIRE DETENTEUR DE LA DECISION D'ENREGISTREMENT` | was 13 |
| 13 | `DATE D'ENREGISTREMENT INITIAL␠` | was 14 |
| 14 | `TYPE` | **was 16** |
| 15 | `STATUT` | **was 17** |
| 16 | `DATE DE RETRAIT` | *new* |
| 17 | `MOTIF DE RETRAIT` | *new* |
| 18–20 | *(unnamed)* | empty |

`Retraits` has **no `OBS` column**, **no `DATE D'ENREGISTREMENT FINAL`**, and
**no `DUREE DE STABILITE`**. Two extra columns, three missing, and `TYPE` /
`STATUT` land two positions to the left. (The sheet's XML carries a stale
`spans="1:19"`; the cells are `A11`–`R11`.)

### Why columns are resolved by name, never by index

Reading `Retraits` column 16 by index yields `datetime(2009, 3, 7)` — the
withdrawal date — where the caller asked for `TYPE`. Verified against the real
file: `find_header(retraits_headers, "TYPE")` returns 14 and the first data
value is `'GE'`. The same prefix returns 16 on the other two sheets. This is
why `build_index.find_header` exists and why Task 3 must call it per sheet.

The `Retraits` data rows *are* correctly aligned with its own header (the
shift comes from the absent `OBS` column, not from a malformed row) — the
earlier claim in the plan that all sheets share one layout is simply wrong.

`find_header` folds case and accents but **not punctuation**, so a prefix has
to reproduce the header's punctuation: pass `N°`, not `N`. Prefixes are
ambiguous where headers share a stem — `DATE D'ENREGISTREMENT INITIAL` and
`DATE D'ENREGISTREMENT␠␠FINAL` both start with `DATE D'ENREGISTREMENT`, the
first match wins, and the caller must pass a longer prefix to reach the second.
`OBS` correctly resolves to `None` on `Retraits`, which is how a caller
detects that the column is not there.

---

## TYPE — originator versus copy

`TYPE` holds **`GE`, `RE`, and `BIO`**. The plan assumed two values; there are
three, plus blanks and whitespace-padded duplicates.

| Value | Reading | Evidence |
|---|---|---|
| `RE` | **Référence** — the originator / reference product | 704 distinct brands carry it. `AUGMENTIN`, `CLAMOXYL`, `VOLTARENE`, `MOTILIUM`, `SINTROM`, `FLAGYL`, `ASPEGIC`, `ATARAX`, `ACTEMRA`, `NEXVIAZYME`, `XENPOZYME`, `SAIZEN` are all `RE`. For `AMOXICILLINE` (61 rows) the 6 `RE` rows are exactly `CLAMOXYL` ×3 and `AUGMENTIN` ×3 (the last three being `AUGMENTIN`, `AUGMENTIN ENFANT`, `AUGMENTIN ENFANT ET AUGMENTIN NOURRISSON`); the other 55 are `GE` from BIOCARE, CONTINENTAL PHARM, HIKMA PHARMA ALGERIA, GROUPE SAIDAL, HUPP PHARMA |
| `GE` | **Générique équivalent** — a generic copy | 4362 rows, the bulk of the list |
| `BIO` | **biologic** — neither of the above | 58 rows: trastuzumab, infliximab, pertuzumab, somatropine, enoxaparine, epoetine alfa, factor VII, daratumumab. Mixes originators (`SAIZEN`, `CANMAB 150`) with biosimilars (`INFLIXIMAB-SAIDAL`, `OMNITROPE`, `PECTUNA`, `REMSIMA SC`) |

`BIO` matters for answering: a biologic copy is not interchangeable with a
chemical generic the way `GE` is, so `TYPE` must not be reduced to a boolean.
Store it verbatim.

Raw value sets (unstripped, so padding is visible):

| Sheet | Values |
|---|---|
| `Nomenclature Aout 2026` | `GE` 4362, `RE` 954, `BIO` 58, `None` 47, `'RE '` 3, `' RE'` 1 |
| `Non Renouvelés ` | `GE` 1113, `RE` 377, `None` 1 — **no `BIO`** |
| `Retraits` | `GE` 1920, `RE` 757, `None` 2 — **no `BIO`** |

Always `.strip()`, and treat empty as *unknown* rather than as `GE`.

### TYPE is per registration, not per brand

19 brands appear as both `RE` and `GE` — `DOLIPRANE`, `EFFERALGAN`, `PROFENID`,
`PERIACTINE`, `ZYDENA`, `SALBUTAMOL` and 13 others. `DOLIPRANE` has five `RE`
rows (suppositories 100/150/200/300 mg and powder) and one `GE` row
(`COMRPIME` 1000 mg — note the ministry typo). Never infer a brand's `TYPE`;
read it per row.

---

## STATUT — locally made versus imported

`STATUT` holds **`F` and `I`**. The plan could not confirm these; from the data
they track the country of the marketing-authorisation holder almost perfectly:

| `STATUT` | Rows | Country = `ALGERIE` | Top countries |
|---|---|---|---|
| `F` | 4027 | **3811 (94.6%)** | ALGERIE, FRANCE 70, JORDANIE 55, TURQUIE 23 |
| `I` | 1398 | **54 (3.9%)** | FRANCE 375, INDE 145, ALLEMAGNE 100, JORDANIE 81, ROYAUME-UNI 69 |

The same split holds on the other two sheets, which is what makes it a property
of the product rather than of one list:

| Sheet | `F` → % Algerian | `I` → % Algerian |
|---|---|---|
| `Nomenclature Aout 2026` | 94.6% | 3.9% |
| `Non Renouvelés ` | 87.7% | 5.2% |
| `Retraits` | 77.6% | 2.6% |

**Reading: `F` = locally made, `I` = imported.** The workbook ships no legend,
so the letter expansions are an inference from this pattern; what is *measured*
is the behaviour above. Do not build anything on the expansion, only on the
distinction.

Residual exceptions, for reference when a record looks wrong: 216 `F` rows name
a non-Algerian holder (e.g. `SCANDONEST` / `SEPTODENT` / FRANCE) and 54 `I`
rows name an Algerian one (e.g. `TRUXIMA` / `HIKMA PHARMA ALGERIA`).

**`STATUT` is not a market-availability flag.** 1398 `I` rows sit in the main
nomenclature, and it does not track `DATE D'ENREGISTREMENT FINAL` — `I` rows
carry 2025 and 2026 end dates. Availability comes from which sheet a record is
on, not from this column. See below.

Raw value sets:

| Sheet | Values |
|---|---|
| `Nomenclature Aout 2026` | `F` 4027, `I` 1396, `'I '` 2 |
| `Non Renouvelés ` | `I` 828, `F` 658, `'i'` 5 — **lowercase `i`** |
| `Retraits` | `I` 1971, `F` 706, `None` 2 |

Normalise with `.strip().upper()`: the file contains `'I '`, `'i'`, `'RE '` and
`' RE'`.

Cross-tabulated with `TYPE`, `STATUT` is independent of it — `(GE, F)` 3781,
`(RE, I)` 756, `(GE, I)` 581, `(RE, F)` 202, `(BIO, F)` 40, `(BIO, I)` 18,
`(null, I)` 43, `(null, F)` 4.

---

## The three sheets are disjoint — a join on `N°ENREGISTREMENT` finds nothing

This is the finding most likely to break a build, and it contradicts the plan.

| Pair | Shared registration numbers |
|---|---|
| main ∩ `Non Renouvelés ` | **0** |
| main ∩ `Retraits` | **1** |
| `Non Renouvelés ` ∩ `Retraits` | 40 |

The sheets are three separate lists — currently valid, not renewed, withdrawn —
each with its own row numbering restarting at 1. A product leaves one list
when it is withdrawn or fails to renew; it does not also sit in the main list.
9595 rows in total (5425 + 1491 + 2679).

`POLARAMINE` demonstrates it: it appears **nowhere** in the main sheet, only in
`Non Renouvelés ` (row 1, `RE`, `I`, holder `SCHERING PLOUGH`). A lookup that
only reads the main list will report it as "not in the nomenclature" when it is
really off-market for a different reason.

**Consequence for the build:** availability must be derived from *which sheet a
record was read from*, not by joining the other two sheets onto the main rows
by `N°ENREGISTREMENT`. Such a join yields one row. If Task 3's test expects
more than 100 withdrawn products, this is why it would fail.

Note also that `N°ENREGISTREMENT` is not a unique key: 8 duplicates in the main
sheet, 1 in `Retraits`. It is a lookup key, not a primary key.

---

## What makes a row an equivalence class

`CODE` alone does not work: 175 of 2075 codes span more than one DCI, mostly
typos (`'02 C 030'` covers both `MEPIVACAINE HYDROCHLORIDE` and
`MEPIVACAINE CHLORHYDRATE`). Grouping on
`(CODE, DCI, FORME, DOSAGE)` gives 2963 groups over 5425 rows, and the groups
are real:

```
('03 B 007', 'PARACETAMOL', 'SUPPOSITOIRE', '100MG')
  -> DOLIPRANE, DOLYMEX, PARACETAMOL DBF, PAROL, SUPPFADOL 100
```

That is the headline use case working off real data. 2150 of the 2963 groups
hold a single product, which is expected — most molecules have no local
generic.

---

## FORME — 683 distinct strings for 5425 rows

The dirtiest column in the file, and the reason `form_key` canonicalises
instead of comparing. 696 distinct raw values collapse to 683 once stripped.
One row is an empty string, one is `---`.

**The literal placeholder `FORME` does not appear in the main sheet at all**
(0 rows). It appears once in `Non Renouvelés ` (`LORATADINE` / `GELARTINE`) and
once in `Retraits` (`ASTEMIZOLE` / `HISTANAL`) — 2 rows out of 9595. Handle
it, but do not expect it to be a measurable share; the plan's 5% gate is
trivially satisfied.

Top values, verbatim, for building `FORM_CANON`:

| Count | Value | | Count | Value |
|---|---|---|---|---|
| 1173 | `COMPRIME PELLICULE` | | 51 | `SOLUTION BUVABLE EN GOUTTES` |
| 480 | `COMPRIME` | | 50 | `CREME DERMIQUE` |
| 409 | `GELULE` | | 42 | `POMMADE DERMIQUE` |
| 235 | `COMPRIME SECABLE` | | 39 | `POUDRE POUR SOLUTION BUVABLE EN SACHET DOSE` |
| 190 | `COMPRIME PELLICULE SECABLE` | | 35 | `GEL DERMIQUE` |
| 141 | `COLLYRE EN SOLUTION` | | 34 | `COMPRIME ENROBE` |
| 118 | `SIROP` | | 28 | `SOLUTION INJECTABLE IM/IV` |
| 118 | `COMPRIME ORODISPERSIBLE` | | 26 | `CREME` |
| 115 | `SOLUTION BUVABLE` | | 25 | `COMPRIME A CROQUER` |
| 109 | `SOLUTION INJECTABLE` | | 24 | `SOLUTION INJECTABLE IV` |
| 70 | `SUPPOSITOIRE` | | 24 | `MICROGRANULE EN GELLULE LIBERATION PROLONGEE` |
| 69 | `SUSPENSION BUVABLE` | | 23 | `CAPSULE MOLLE` |
| 53 | `COMPRIME PELLICULE A LIBERATION PROLONGEE` | | 23 | `SUSPENSION POUR PULVERISATION NASALE` |
| | | | 22 | `COMPRIME EFFERVESSANT` |

The top 45 cover 74.3% of rows. The long tail is free-text: misspellings
(`COMRPIME` 5, `COMRIME` 6, `COMRPIMPE` 3), abbreviations (`SOL. P. PERF. IV`,
`PDRE. LYOPH.`, `DRG.`, `AMP.BUV.`), casing (`Gel ORAL`, `Solution
concentrEe pour HEmodialyse`), and values that are not forms at all
(`FLACON`, `LIQUID.1L.`, `LAIT EN POUDRE`, `---`). Read the full distribution
with `scripts/profile_source.py` (Task 2) rather than guessing a canonical
list.

---

## DCI — 1414 distinct values, 0 blank

Salt and hydrate suffixes observed as the last token of the folded DCI, with
their row counts. The plan's list covers the first nine; the rest are not in it
and **must be added** by `dci_keys` (Task 2):

| In the plan's list | | Not in the plan's list | |
|---|---|---|---|
| `CHLORHYDRATE` | 69 | `SODIQUE` | 31 |
| `SODIUM` | 24 | `ANHYDRE` | 26 |
| `SULFATE` | 16 | `MONOHYDRATE` | 15 |
| `FUMARATE` | 10 | `DIHYDRATE` | 7 |
| `DICHLORHYDRATE` | 8 | `MAGNESIUM` | 7 |
| `MALEATE` | 8 | `ACETATE` | 6 |
| `TRIHYDRATE` | 6 | `NITRATE` | 6 |
| `POTASSIUM` | 4 | `BROMURE` | 5 |
| `CALCIUM` | 3 | `CITRATE` | 4 |
| | | `PHOSPHATE` | 4 |
| | | `POTASSIQUE` | 4 |
| | | `MONOSODIQUE` | 3 |

`SODIQUE` (31) is the largest gap: the plan's list has the English `SODIUM`
but not the French `SODIQUE`, which this file prefers. Next is `ANHYDRE` (26),
the French form of the `ANHYDROUS` the plan does list.

**181 of the 1414 DCIs contain `EXPRIME`** — a salt stated one way and the
expressed active substance another:

```
ACIDE ZOLEDRONIQUE MONOHYDRATE EXPRIME EN ACIDE ZOLEDRONIQUE
AMOXICILLINE ... EXPRIME EN ...
ACETYLSALICYLATE DE DL LYSINE EXPRIME EN ACIDE ACETYLSALICYLIQUE
```

Some use parentheses instead: `AMLODIPINE BESILATE (AMLODIPINE)`, and some
appear both ways for the same product. Sorting tokens alphabetically (as
`dci_keys` does) will not equate `ACIDE ZOLEDRONIQUE MONOHYDRATE` with
`ACIDE ZOLEDRONIQUE`; the `EXPRIME EN` clause is the part that carries the
base substance.

### A DCI can name SEVERAL actives, and that broke the key

`/` separates actives: 500 distinct DCIs use it, 349 of them with exactly two.
The `EXPRIME EN` and parenthetical rules above are correct **per substance**,
but they were applied to the whole DCI, so a combination kept only its first
parenthetical:

```
AMLODIPINE BESILATE (AMLODIPINE)/PERINDOPRIL ARGININE (PERINDOPRIL)
  -> dci_base_key = "AMLODIPINE"        <-- perindopril deleted
```

`COVERAM`, `PRATIMA AM` and `TORVAPINE` — real two-drug combinations — were
therefore filed under `AMLODIPINE` and reported as the same medicine as a
single-ingredient amlodipine tablet. **28 rows, latent from the first build**,
missed by four reviews and 87 tests because every test asked about a
one-ingredient drug.

`dci_keys` now resolves each slash-separated component on its own, strips salts
per component, and joins the results order-insensitively (the file writes one
combination both ways round). A multi-active key carries the **`COMBINATION`**
marker:

```
COMBINATION AMLODIPINE PERINDOPRIL
```

The marker is load-bearing, not cosmetic: without it a combination key could
equal one of its own ingredients and the tool would call a two-drug product
equivalent to a one-drug one. No token in the registry starts with `COMB`, so
it cannot collide — an earlier apparent collision was a substring match against
`RECOMBINANTE`.

**A slash is not always a combination.** 92 of the 500 slash-bearing DCIs use
it for a dosage (`APRPITANT 80MG / 125MG`) or a multi-component biologic
(`COMPOSANT 1 : FIBRINOGENE HUMAIN (PROTEINE COAGULABLE)/...`). A piece only
counts as an active when it looks like one — no digits, at least three
characters, not a structural label. Splitting those would invent actives that
do not exist.

**The same substance is written with the components in either order.** Combine
on the *sorted set of resolved components*, never on the raw string, or
`PRATIMA AM` looks like two different products.

### Spelling variants that defeat exact matching

The same substance is spelled several ways *within this one file*. Confirmed
examples:

- `ACIDE ACETYLSALICYLIQUE` and `ACIDE ACETYLSALICYTIQUE`
- `EXTRAITS ALLERGENIQUES DERMATOPHAGOIDES` and `EXTRAITS ALLERGENIQUS
  DERMATOPHAGOIDES` and `EXTRAITS ALLERGENIQUES DERMARTOPHAGOIDES`
- `CANDESARTAN CILEXETIL` and `CANDESSARTAN CILEXETIL`
- `LIDOCAINE CHLORHYDRATE ANHYDRE` and `LIDOCAINE  CHLORHYDRATE` (double space)
- `DICHLORBYDRATE DE LEVOCETIRIZINE` and `LEVOCETIRIZINE DICHLORHYDRATE`
- `ROCURONIUM BROMIDE` and `ROCURONIUM BROMURE`
- `ACIDE RISEDRONIQUE` and `ACIDE RIDEDRONIQUE` (inside an `EXPRIME` string)
- `DOXORUBICINE HYDROCHLORIDE LIPOSOM` — English amid French
- `CHLORIDRATO` (Spanish) appears in the brand column against French DCIs

This is the argument for grouping on salt-insensitive keys and for never
promising a fuzzy match as a fact. It is also why an exact-match lookup must
say "not found" rather than guess.

### Salt and hydrate suffixes: what is stripped, what is kept, and why

`dci_base_key` reduces a DCI to its **active moiety** by dropping salt and
hydrate suffixes. That is a deliberate decision with a regulatory basis and a
known limit, and a future maintainer should not "fix" it without reading this.

**The authorities disagree by axis, so the rule is per-axis:**

| suffix class | examples | stripped? | basis |
|---|---|---|---|
| hydrate / polymorph | `ANHYDRE`, `MONOHYDRATE`, `DIHYDRATE`, `HEMIHYDRATE`, `TRIHYDRATE` | **yes** | FDA (Orange Book): "Anhydrous and hydrated entities, as well as different polymorphs, are considered to be the same active ingredient." |
| salt / ester | `DICHLORHYDRATE`, `CHLORHYDRATE`, `MALEATE`, `BESYLATE`, `SULFATE`, `CITRATE`, `SODIQUE`, `POTASSIQUE`, `CALCIUM`, `MAGNESIUM` | **yes, here** | see below — a deliberate divergence from the letter of the FDA rule |

**The FDA says a different salt IS a different active ingredient:**

> "Different salts, esters or other noncovalent derivatives … of the same
> active moiety are regarded as different active ingredients … considered
> pharmaceutical alternatives and, thus, not therapeutically equivalent."

**We strip them anyway, for two reasons, and both are checkable:**

1. *The registry normalises salts itself.* 181 DCI values carry an
   `EXPRIME EN <base>` clause (`AMLODIPINE BESILATE EXPRIME EN AMLODIPINE`),
   which is the ministry stating the salt is expressed as the base. Stripping
   elsewhere is consistent with the ministry's own convention, not contrary
   to it.
2. *Splitting would wreck the answers.* The FDA rule governs **therapeutic
   equivalence claims** — substituting a besylate for a maleate. This tool
   makes no such claim: every answer closes by saying equivalence here means
   same DCI, same form, same dose, and that bioequivalence is not asserted and
   substitution is the pharmacist's decision. Splitting on salt would move
   `CETIRIZINE` from 33 grouped products to 2, and would separate
   `ESOMEPRAZOLE` from `ESOMEPRAZOLE MAGNESIUM`, a distinction no clinician
   acts on.

**Measured, so nobody re-derives it:**

- 97 base keys are reached from more than one exact DCI spelling.
- In **28** of those, the spellings co-occur under a *single brand* — the
  registry plainly means one substance (`AMIOCARDONE` carries both
  `AMIODARONE` and `AMIODARONE CHLORHYDRATE`). Merging is unambiguously right
  there.
- In **69**, the spellings sit under different brands (`CETIRIZINE` vs
  `CETIRIZINE DICHLORHYDRATE`; `DICLOFENAC` / `SODIQUE` / `POTASSIQUE`). These
  are the debatable ones, and they are merged on purpose.

**The mitigation is presentation, not grouping.** Every rendered row carries
its raw DCI string, so a salt difference is always *visible* even when the rows
share a class. If a future release ever needs the strict reading, the change is
to stop stripping the salt vocabulary and rebuild — but expect it to shatter
most classes in the file, because 41% of rows carry a salt token.

**Do not strip a token that is not in the vocabulary**, and never bundle a
*combination* into a base: `PARACETAMOL/TRAMADOL CHLORHYDRATE` is two actives,
and ATC is explicit that "products containing two or more active ingredients
are regarded as combinations and given different ATC codes from the product
with a single component". The ingredient-count difference is the one merge
that is always wrong — it is the NOBAC case (`ALGINATE/BICARBONATE` vs
`ALGINATE/BICARBONATE/CARBONATE DE CALCIUM`), and it must never be collapsed.

---

## DOSAGE — 1178 distinct values, 19 blank

`10MG` (262), `100MG` (194), `500MG` (191), `5MG` (189), `50MG` (183).

- **1025 rows use a decimal comma** (`0,5MG/5ML`), not a period. A naive float
  parse reads `0` for all of them.
- 224 rows are percentages (`2%`, `POUDRE 2%`).
- 22 rows contain **no digit at all**: 19 blanks, plus `'n'`, `'---'`, and
  `'q.s pour un flacon'` (quantum satis). `dose_key` returns `None` for these;
  callers must read `None` as *unknown*, never as a mismatch.

---

## Data-hygiene rules for the build

1. **`.strip()` every cell.** Rows with padded values in the main sheet:
   `FORME` 70, `DCI` 23, `NOM DE MARQUE` 18, `TYPE` 4, `STATUT` 2. Padding also
   appears inside values (`LISTE I␠`, `36 MOIS␠`, `' RE'`, `'I '`).
2. **`.strip().upper()` for `TYPE` and `STATUT` specifically.** `Non
   Renouvelés ` contains lowercase `'i'`; both sheets contain `'RE '` and
   `' RE'`.
3. **Treat blanks as unknown, never as a value.** `TYPE` 47 null, `LISTE` 798
   null, `P2` 992 null, `OBS` 5360 of 5425 null, `DOSAGE` 19 blank, `DUREE DE
   STABILITE` 605 null.
4. **Dates are `datetime` except for a few strings.** `DATE D'ENREGISTREMENT
   INITIAL` is `datetime` for 5406 rows, null for 18, and the string
   `'00/00/2019'` for one (`268/13 P 475/19/25`). `DATE D'ENREGISTREMENT FINAL`
   is `datetime` or null only. `DATE DE RETRAIT` is messier still: 1545
   `datetime`, **1132 strings**, 2 null.
5. **`LISTE`, `P1`, `P2` are near-free text.** `P1` is `HOP` for 5420 of 5425
   main rows; `Retraits` also has `HOP*`, `HOP.`, `*HOP`, and even `OFF`. One
   `P2` cell holds a sentence: `MEDICAMENT SOUMIS A PRESCRIPTION
   RESTREINTE: PRESCRIPTION SPECIALISEE`. Do not build enums on these.
6. **`RETRAITS` has a free-text `MOTIF DE RETRAIT`** — 96 distinct values over
   2679 rows, some full paragraphs. Top: `RETRAIT PAR LE MSPRH POUR
   INTERDICTION D'IMPORTATION` 824, `RETRAIT PAR LE DETENTEUR POUR MOTIF
   COMMERCIAL` 803, `PRODUIT NON COMMERCIALISE ET DECISION NON RENOUVELEE` 501.
   Useful for *why* a product is off-market; never for a decision.
7. **Load with `read_only=True, data_only=True`.** The workbook contains no
   formulas worth evaluating, and `read_only` keeps the memory footprint down.

---

## Re-verifying after a ministry refresh

The ministry publishes every one to two months, and the file has already been
seen changing shape (`clean_` prefix, column count). After every download,
re-run these checks and update this file if any of them move:

- Sheet names via `wb.sheetnames` — especially the trailing space in
  `Non Renouvelés␠` and the absence of an accent in `Nomenclature Aout 2026`.
- The row count in each title row against the number of data rows.
- The header row index per sheet, by locating the row that carries the header
  strings, not by hardcoding 16/12/11.
- The full header string list per sheet, and the index of every column the
  build reads. `Retraits` is the one that has already shifted.
- The `TYPE` and `STATUT` value sets, including any new value — an unrecognised
  `TYPE` must not be silently bucketed as a generic.
- The main-list intersection with each of the other two sheets (0 and 1 here).
  If it is no longer ~0, the availability logic in the build needs revisiting.
- `FORME` distinct count, and whether the literal placeholder has reappeared in
  the main sheet.

`scripts/profile_source.py` (Task 2) automates most of this once it exists.

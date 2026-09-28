# Answering with dz-generics

Worked examples and phrasing detail. `SKILL.md` is the rulebook; this file is
where the format is shown on real tool output. Every product, laboratory and
registration number below came out of the committed index — copy nothing from
here as a fact without re-running the tool, because the ministry re-publishes
every one to two months.

The canonical disclaimer, in the three languages:

> **EN** — Equivalence here means same DCI, same form, same dose. It is not a
> statement of bioequivalence, and substitution is the pharmacist's or
> prescriber's decision.
>
> **FR** — L'équivalence signifie ici même DCI, même forme et même dosage. Ce
> n'est pas une preuve de bioéquivalence, et la substitution relève de la
> décision du pharmacien ou du prescripteur.
>
> **AR** — يعني التكافؤ هنا تطابق المادة الفعالة والشكل الصيدلاني والجرعة. وهو
> ليس إثباتًا للتكافؤ الحيوي، ويبقى قرار الاستبدال بيد الصيدلي أو الطبيب
> الواصف.

---

## Trigger phrasings

| Route | What the user types | Command |
|---|---|---|
| Brand, FR | "le générique du Doliprane", "Doliprane 500 mg" | `--name "DOLIPRANE"` |
| DCI, FR | "l'équivalent du paracétamol" | `--dci "PARACETAMOL"` |
| Brand, AR | "بديل دوليبران" | `--name "DOLIPRANE"` |
| DCI, AR | "البدائل المتوفرة للباراسيتامول" | `--dci "PARACETAMOL"` |
| Transliterated | "dolipran", "paracetamol", "amoxicilin" | the Latin registry spelling |
| Brand, EN | "generic alternative for Augmentin in Algeria" | `--name "AUGMENTIN"` |
| Availability | "is X available / still on the market in Algeria?" | `--name "X"`, read `status` |
| Code | "03 B 081" or a registration number | `--code "03 B 081"` |

The registry has **no Arabic text**. Always resolve an Arabic or Darija name to
its Latin form before calling the tool. `--name` needs the brand exactly as the
registry prints it (accents and case aside); `--dci` needs the substance.

## The tool's anchor is not the user's request

`--name` and `--dci` pick an anchor on their own: the active row with a known
dose, lowest `(dose, form)`. So `--name "DOLIPRANE"` anchors on the 1000 mg
tablet even when the user asked about 500 mg. Never let that slide.

To answer for a specific form and dose:

1. Run `--json` and find the row the user actually named, by `dosage` and
   `form`.
2. Note its `code`.
3. Re-run with `--code "<that code>"` and confirm the new anchor's `dosage`
   and `form` are the ones the user asked about.
4. If no row at that form and dose exists, say so — do not answer for a nearby
   one.

---

## Worked example — French (brand + dose)

> **User:** Je cherche les génériques du Doliprane 500 mg disponibles en
> Algérie. Quels laboratoires les fabriquent et où sont-ils produits ?

Commands: `--name "DOLIPRANE" --json` (shows the 500 mg row), then
`--code "03 B 005"` (re-anchors on the 500 mg tablet class).

**Réponse**

Nomenclature nationale — version **Août 2026**.

Substance active (DCI) : **PARACETAMOL**. Forme : comprimé. Dosage : **500 mg**.

Équivalents enregistrés — même DCI, même forme, même dosage :

- **PARALGAN** 500 mg — GE — fabriqué en Algérie — GROUPE SAIDAL
- **PARACETAL** 500 mg — GE — fabriqué en Algérie — SOCIETE PHARMACEUTIQUE
  ALGERIENNE SOPHAL
- **PARACETAMOL PHYSIOPHARM** 500 mg — GE — fabriqué en Algérie — PHYSIOPHARM
  LABORATOIRES
- **DOLYC** 500 mg — GE — fabriqué en Algérie — LABORATOIRES MERINAL
- **DOLI-BIEN** 500 mg — GE — fabriqué en Algérie — PHARMIDAL NS
- **ROSADOL** 500 mg — GE — fabriqué en Algérie — ROSASPHARMA
- **ANTALGAN** 500 mg — GE — fabriqué en Algérie — SARL ALPHACARE

Dosages différents — PARACETAMOL, comprimé, **NON équivalents** : 1000 mg, par
exemple DOLIPRANE, DOLI-BIEN, DOLYC, ROSADOL (liste complète avec `--json`).

Autres formes — **NON équivalentes** : sirop, suspension buvable, suppositoire,
sachet.

Hors marché — à ne pas présenter comme disponible : **DOLIPRANE 500 mg**
(référence, SANOFI AVENTIS SPA) — enregistrement non renouvelé.

L'équivalence signifie ici même DCI, même forme et même dosage. Ce n'est pas une
preuve de bioéquivalence, et la substitution relève de la décision du pharmacien
ou du prescripteur.

**What the example shows:** the requested 500 mg row is answered from a
500 mg anchor; 1000 mg is named and explicitly *not* equivalent; the branded
Doliprane 500 itself is off-market and is surfaced as such, never as an option.

---

## Worked example — Arabic (DCI + form)

> **المستخدم:** أريد قائمة البدائل المتوفرة في الجزائر للباراسيتامول على شكل
> شراب، مع ذكر المختبرات المصنعة.

Commands: `--dci "PARACETAMOL"` (whole substance), then
`--code "03 B 117"` (suspension buvable, 24 mg/ml) and
`--code "03 B 061"` (solution buvable, dose non déterminable).

**الجواب**

التسمية الوطنية للمنتجات الصيدلانية — نسخة **أوت 2026**.

المادة الفعالة: **PARACETAMOL** (الباراسيتامول). الشكل الدوائي: سائل للشرب.

البدائل المسجَّلة في الجزائر — نفس الشكل ونفس الجرعة (24 ملغ/مل، معلّق للشرب):

- **DOLIBON** — GE — مصنّع في الجزائر — GEOPHARM
- **DOLIPRANE 2,4%** — GE — مصنّع في الجزائر — PROPHARMAL
- **DOLYMEX** — GE — مصنّع في الجزائر — KPMA BIOTIC
- **MIGRAMOL PEDIATRIQUE** — GE — مصنّع في الجزائر — LAD PHARMA
- **PARALGAN** — GE — مصنّع في الجزائر — GROUPE SAIDAL

جرعات مختلفة — **غير مكافئة**: 50 ملغ/مل (DOLOMOL)، 25 ملغ/مل (TYLENOL JEUNE
ENFANT).

جرعة غير محدَّدة — **لا تُقارَن، وليست دليلًا على اختلاف** (محاليل للشرب بدون
جرعة قابلة للتحديد): ACETADOL، DOLI-BIEN، DOLPRIV، EFFERALGAN PEDIATRIQUE،
ISOMOL، PEDIAMOL. لا تُقدَّم كبدائل مكافئة، ولا تُقدَّم كجرعة مختلفة.

يعني التكافؤ هنا تطابق المادة الفعالة والشكل الصيدلاني والجرعة. وهو ليس إثباتًا
للتكافؤ الحيوي، ويبقى قرار الاستبدال بيد الصيدلي أو الطبيب الواصف.

**What the example shows:** the answer is in Arabic while the names stay Latin;
the exact `SIROP` form has no active rows, so the agent says which oral-liquid
form it answered for instead of silently stretching "شراب"; and the unknown-dose
group is its **own** section — neither equivalent nor "different dose".

---

## Worked example — English (a miss, and an off-market foreign brand)

> **User:** What are the Algerian generics for zzzznotadrug?

```
Nomenclature nationale -- version Août 2026

No product in this nomenclature matches 'zzzznotadrug'.
Nothing close enough to offer was found either -- this is a miss,
not a guess. Check the spelling, or search by DCI or code.
```

**Answer:** Nothing in the Algerian nomenclature (version Août 2026) matches
"zzzznotadrug", and no near match was found. I will not guess a product. If you
have the active substance (DCI) or the registration code, I can look it up that
way.

> **User:** Is Tylenol available in Algeria?

`--name "TYLENOL"` returns TYLENOL 3% syrup, **not renewed** — in the registry,
but off-market. **Answer:** Tylenol is in the nomenclature but its registration
was not renewed, so it is not presented as available. Its active substance is
paracetamol (PARACETAMOL); the Algerian registry lists products by DCI, so I can
look up paracetamol products — but those are not "Tylenol generics" and I will
not label them that way. Then the disclaimer.

**What the example shows:** a miss produces an honest "not found" with no
invented product; and a foreign brand that *is* listed but off-market is
reported as off-market, not as available and not silently swapped for another
brand's products.

---

## Cautions

- The version label is on **every** invocation, including a miss. Put it in
  every answer.
- `statut` (`F`/`I`) is origin — *made in Algeria* vs *imported* — **not**
  availability. Availability is `active` / `not renewed` / `withdrawn`.
- `BIO` is a biologic; it is not interchangeable with a chemical `GE`. Repeat
  the tool's `***BIOLOGIC***` warning when one appears.
- An unknown dose (`dose_key` null) is never an equivalent and never a stated
  difference.
- Never present a withdrawn or not-renewed row as an option, even when it is the
  only row for a substance.

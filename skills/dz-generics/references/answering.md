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

## The anchor's own status governs the answer

Look at the anchor's `status` **before** you present any class. It decides the
shape of the answer, not just a footnote:

- **The anchor is `active`.** Present the equivalent class normally, and put any
  off-market rows in their own clearly labelled block.
- **The anchor is `not renewed` or `withdrawn`.** The brand the user asked about
  is **not obtainable**. Lead with that, do not present the brand as available,
  and do not offer the off-market rows as options. You may then present the
  **active** class of the same DCI/form/dose — but label it as *the substance's*
  class, **not** as "the generics of «brand»". The registry answers by DCI; the
  brand is not the substance.

This is the same rule in every language, and it is what makes the Tylenol and
the Doliprane 500 answers below read the same way: both brands are off-market,
so both answers say so first, neither offers the brand, and both may then name
the active class of the substance explicitly under the substance's name.

---

## Worked example — French (brand + dose)

> **User:** Je cherche les génériques du Doliprane 500 mg disponibles en
> Algérie. Quels laboratoires les fabriquent et où sont-ils produits ?

Commands: `--name "DOLIPRANE" --json` (shows the 500 mg row), then
`--code "03 B 005"` (re-anchors on the 500 mg tablet class).

**Réponse**

Nomenclature nationale — version **Août 2026**.

Substance active (DCI) : **PARACETAMOL**. Forme : comprimé. Dosage : **500 mg**.

⚠️ Le **Doliprane 500 mg** lui-même est **hors marché** (référence, SANOFI
AVENTIS SPA — enregistrement non renouvelé). Il n'est donc pas disponible, et
je ne le présente pas comme une option. Ce qui suit est la classe de la
**substance PARACETAMOL** en comprimé 500 mg — ce ne sont pas « les génériques
du Doliprane ».

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

L'équivalence signifie ici même DCI, même forme et même dosage. Ce n'est pas une
preuve de bioéquivalence, et la substitution relève de la décision du pharmacien
ou du prescripteur.

**What the example shows:** the queried brand, Doliprane 500, is off-market, so
the answer leads with that and never offers it; the requested 500 mg class is
then presented on a 500 mg anchor, **explicitly as the substance's class, not as
"les génériques du Doliprane"** (exactly as the Tylenol example below does); and
1000 mg is named and explicitly *not* equivalent.

---

## Worked example — Arabic (DCI + form)

> **المستخدم:** أريد قائمة البدائل المتوفرة في الجزائر للباراسيتامول على شكل
> شراب، مع ذكر المختبرات المصنعة.

Commands: `--dci "PARACETAMOL"` (whole substance), `--name "TYLENOL"` (the
`SIROP` the user actually named), then `--code "03 B 117"` (suspension buvable,
24 mg/ml). The `SIROP` form has **no active row** — both its rows are off-market
(TYLENOL 3% *not renewed*, PARACETAMOL ELEXIR SAD 120 mg *withdrawn*) — so the
answer names the nearest **active** oral-liquid form, `SUSPENSION BUVABLE`
24 mg/ml, and answers for that explicitly.

**الجواب**

التسمية الوطنية للمنتجات الصيدلانية — نسخة **أوت 2026**.

المادة الفعالة: **PARACETAMOL** (الباراسيتامول).

**الشكل الذي طلبته — الشراب (SIROP) — لا توجد له أي تسجيلة سارية**: سطران
فقط، وكلاهما خارج السوق — **TYLENOL** 3% (150 مغ/5 مل) لم تُجدَّد تسجيلته،
و**PARACETAMOL ELEXIR SAD** 120 مغ مسحوب. لا يُعرض أيٌّ منهما كبديل متوفر.

أقرب شكل سائل للشرب مسجَّل وساري هو **المعلّق للشرب (SUSPENSION BUVABLE)
120 مغ/5 مل (2,4 غ/100 مل)، أي 24 ملغ/مل**، وكلّه مصنَّع في الجزائر:

- **DOLIBON** — GE — GEOPHARM
- **DOLIPRANE 2,4%** — GE — PROPHARMAL
- **DOLYMEX** — GE — KPMA BIOTIC
- **MIGRAMOL PEDIATRIQUE** — GE — LAD PHARMA
- **PARALGAN** — GE — GROUPE SAIDAL

⚠️ هذه أسماء فئة المادة **PARACETAMOL** في شكل المعلّق للشرب، وليست «بدائل
TYLENOL»؛ فعلامة TYLENOL نفسها خارج السوق.

جرعات مختلفة في نفس الشكل — **غير مكافئة**: **DOLOMOL** 50 ملغ/مل (لم تُجدَّد
تسجيلته)، و**TYLENOL JEUNE ENFANT GOÛT BANANE** 25 ملغ/مل (مسحوب).

⚠️ لا توجد أي جرعة «غير محدَّدة» في شكل **المعلّق للشرب**: هذا القسم فارغ هنا،
فلا يُستشهد بأحد. أما **المحلول للشرب (SOLUTION BUVABLE)** — وهو شكل *مختلف*،
لا بديل — فيحمل سبعة أسطر بجرعة غير قابلة للتحديد (ACETADOL، DOLI-BIEN،
DOLPRIV، EFFERALGAN PEDIATRIQUE، ISOMOL، PEDIAMOL) وسطرًا واحدًا بجرعة
*معروفة* (ISOMOL 20 ملغ/مل، ساري)، لذا لا تُقارَن جرعاته بجرعات المعلّق.
الجرعة المجهولة ليست جرعة مختلفة.

يعني التكافؤ هنا تطابق المادة الفعالة والشكل الصيدلاني والجرعة. وهو ليس إثباتًا
للتكافؤ الحيوي، ويبقى قرار الاستبدال بيد الصيدلي أو الطبيب الواصف.

**What the example shows:** the answer stays in Arabic while names stay Latin;
the exact form the user named (`SIROP`) has **no active registration**, so the
answer says that first instead of silently stretching «شراب» to cover another
form; it then answers for `SUSPENSION BUVABLE` 24 mg/ml as the *substance's*
registered class, explicitly not as "alternatives to Tylenol". The
`SOLUTION BUVABLE` nuance is stated because the tool treats it as a **different
form** — that form holds both unknown-dose rows and one known-dose row
(ISOMOL 20 mg/ml) — so lumping it in with the suspension would assert a
comparison the data does not support. The different-dose rows are named and
their off-market status is shown.

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
was not renewed, so it is not available and I do not present it as an option.
Its active substance is paracetamol (PARACETAMOL); the Algerian registry lists
products by DCI, so I can show you the **registered paracetamol** products — but
these are the substance's class, not "Tylenol generics", and I will not label
them that way. Then the disclaimer.

**What the example shows:** the same rule as the Doliprane 500 answer above —
the queried brand is off-market, so the answer leads with that, never offers the
brand, and may then name the active class **as the substance's class, explicitly
not as the brand's generics**. The first question shows a miss producing an
honest "not found" with no invented product.

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
- **Label what is sourced and what is not.** Every product, laboratory and
  registration detail must come from the registry. When you add something the
  registry does not hold — for example, that a foreign brand not listed in
  Algeria (Nurofen) contains ibuprofen — say plainly that the **substance
  mapping is general knowledge** while **the products come from the registry**.
  The reader must be able to tell which part is sourced and which is not.

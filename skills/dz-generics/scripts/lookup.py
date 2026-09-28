"""Lookup and equivalence over the ministry nomenclature index.

This is the layer a user actually talks to: it turns the name a person typed
-- a brand, a DCI, or a registration code -- into one *anchor* product, then
reports that anchor's equivalence class from the committed SQLite index built
in Task 3.

The project's medical risk lives here. A wrong answer tells someone two
medicines are interchangeable when they are not, so the rules below are
deliberately ungenerous:

- **A fuzzy match never auto-picks.** ``DOLIPRAN`` is one edit from
  ``DOLIPRANE`` and the only candidate above the cutoff; it still comes back
  ``ambiguous`` with the candidate listed, because the user typed something
  else. Below the cutoff (``DOLIPRNA`` at 0.824) the answer is ``not_found``.
- **An unknown dosage is never a match.** ``dose_key`` is ``None`` for 810
  rows. Two ``None``s are not evidence of equivalence, so a row with an
  undeterminable dose can never land in ``equivalents``.
- **The anchor needs a known dose.** The rule prefers an ``active`` row with
  a non-null ``dose_key``; if none exists it falls back to an active row, then
  to any row, and reports that fallback. If the anchor's own dose is unknown,
  ``equivalents`` is empty: equivalence is undefined without a dosage.
- **A non-active row is never an equivalent** unless ``include_inactive`` is
  asked for, and then the output says so.
- **A blank ``type`` is unknown, not ``GE``.** ``GE`` / ``RE`` / ``BIO`` are
  carried verbatim and rendered verbatim; a ``BIO`` row is visibly flagged
  because a biosimilar is not interchangeable with a chemical generic.
- **``statut`` is origin, not availability.** ``F`` is *made in Algeria*,
  ``I`` is *imported*; neither says whether the product is on the market.

Resolution (`lookup`, `Product`, `LookupResult`, the SQL) is kept separate
from rendering (`render_text`, `staleness_note`), because Task 5 asks for the
same answer in Arabic and French and must not have to re-derive it.

Query time uses only the standard library -- ``sqlite3``, ``difflib``,
``json``, ``argparse`` -- and opens the index read-only. The index is a
contract: query it by the column names Task 3 pinned, never write to it.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import difflib
import json
import os
import sqlite3
import sys

from normalize import fold

# The committed index, addressed relative to this file so the CLI works from
# any working directory. Never opened read-write.
DB_FILENAME = os.path.join("..", "data", "nomenclature.sqlite")

# Above this ratio a brand is *shown to the user*, never chosen for them.
FUZZY_CUTOFF = 0.85
# Enough to disambiguate a typo without turning the answer into a list.
MAX_CANDIDATES = 5

# How the anchor was chosen. The first is the only happy path; the other two
# are fallbacks that are themselves part of the answer and must be reported.
ANCHOR_RULE_KNOWN_DOSE = "active_known_dose"
ANCHOR_RULE_UNKNOWN_DOSE = "active_unknown_dose"
ANCHOR_RULE_OFF_MARKET = "off_market"

# A stale index answers from an old release silently, which is the failure
# mode a dated nomenclature makes most dangerous.
STALE_AFTER = datetime.timedelta(days=90)

AVAILABILITY_LABELS = {
    "active": "active",
    "not_renewed": "not renewed",
    "withdrawn": "withdrawn",
}
TYPE_LABELS = {
    "GE": "GE (generic-equivalent)",
    "RE": "RE (reference product)",
    "BIO": "BIO (biologic -- NOT interchangeable with a chemical generic)",
    "": "type unknown",
}
STATUT_LABELS = {"F": "made in Algeria", "I": "imported", "": "origin unknown"}

# Every column a Product carries. One row of `product` maps straight onto it.
_PRODUCT_COLUMNS = (
    "id", "reg_no", "code", "dci", "dci_key", "dci_base_key", "brand",
    "brand_key", "form", "form_key", "dosage", "dose_key", "lab", "country",
    "type", "statut", "availability", "withdrawn_at", "withdrawn_reason",
)


@dataclasses.dataclass(frozen=True)
class Product:
    """One ``product`` row.

    The raw strings are kept verbatim -- ``date_start`` / ``date_end`` /
    ``withdrawn_at`` are opaque text, not parsed dates, and ``type`` may be
    blank, which is not ``GE``.
    """

    id: int | None = None
    reg_no: str = ""
    code: str = ""
    dci: str = ""
    dci_key: str = ""
    dci_base_key: str = ""
    brand: str = ""
    brand_key: str = ""
    form: str = ""
    form_key: str = ""
    dosage: str = ""
    dose_key: str | None = None
    lab: str = ""
    country: str = ""
    type: str = ""
    statut: str = ""
    availability: str = ""
    withdrawn_at: str = ""
    withdrawn_reason: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Product":
        return cls(**{name: row[name] for name in _PRODUCT_COLUMNS})

    def to_dict(self) -> dict:
        payload = dataclasses.asdict(self)
        payload["origin"] = origin_label(self.statut)
        payload["type_label"] = TYPE_LABELS.get(self.type, self.type)
        payload["availability_label"] = availability_label(self.availability)
        return payload


@dataclasses.dataclass
class LookupResult:
    """The answer: the anchor, its class, and how the query resolved.

    ``status`` is one of ``found`` / ``ambiguous`` / ``not_found``. The five
    class buckets are properties because the anchor is already here; passing
    it back in would be redundant. They are only populated when
    ``anchor`` is set -- an ambiguous or missed query resolves nothing, and
    inventing a class for it would be a guess.
    """

    query: str
    status: str
    dci_base_key: str | None = None
    anchor: Product | None = None
    candidates: list[Product] = dataclasses.field(default_factory=list)
    version_label: str = ""
    built_at: str = ""
    include_inactive: bool = False
    # Which branch of the anchor rule won: a known-dose active row (the only
    # happy path), or a fallback to an active row with an unknown dose, or to
    # an off-market row. A fallback is part of the answer, not a detail.
    anchor_rule: str = ""
    # Every row the query matched and the subset the anchor was chosen from.
    # A brand can hold several rows in the same form and dose, and availability
    # is not a single value per brand, so both are reported rather than hidden.
    matched_rows: list[Product] = dataclasses.field(default_factory=list)
    anchor_rows: list[Product] = dataclasses.field(default_factory=list)
    # The whole DCI base group, bucketed. Populated only when there is an
    # anchor; the grouping is decided once, at resolution time.
    _equivalents: list[Product] = dataclasses.field(
        default_factory=list, repr=False)
    _other_dosages: list[Product] = dataclasses.field(
        default_factory=list, repr=False)
    _unknown_dose: list[Product] = dataclasses.field(
        default_factory=list, repr=False)
    _other_forms: list[Product] = dataclasses.field(
        default_factory=list, repr=False)
    _inactive: list[Product] = dataclasses.field(
        default_factory=list, repr=False)

    @property
    def equivalents(self) -> list[Product]:
        """Same DCI base, same form, same dose, active (unless widened)."""
        return self._equivalents

    @property
    def other_dosages(self) -> list[Product]:
        """Same DCI base and form, a *different* known dose."""
        return self._other_dosages

    @property
    def unknown_dose(self) -> list[Product]:
        """Same DCI base and form, dose undeterminable.

        An unknown dose is not a *different* dose: it cannot be compared with
        the anchor's, so it is not evidence of a difference. Reported here
        rather than under ``other_dosages`` so the answer never asserts a
        dosage difference the data does not support.
        """
        return self._unknown_dose

    @property
    def other_forms(self) -> list[Product]:
        """Same DCI base, a different form (any dose)."""
        return self._other_forms

    @property
    def inactive(self) -> list[Product]:
        """Not renewed or withdrawn, at the anchor's form and dose."""
        return self._inactive

    @property
    def anchor_is_active(self) -> bool:
        return self.anchor is not None and self.anchor.availability == "active"

    def to_json(self) -> str:
        payload = {
            "query": self.query,
            "status": self.status,
            "dci_base_key": self.dci_base_key,
            "version_label": self.version_label,
            "built_at": self.built_at,
            "include_inactive": self.include_inactive,
            "anchor_rule": self.anchor_rule,
            "anchor_is_active": self.anchor_is_active,
            "anchor": self.anchor.to_dict() if self.anchor else None,
            "anchor_rows": [p.to_dict() for p in self.anchor_rows],
            "matched_rows": [p.to_dict() for p in self.matched_rows],
            "candidates": [p.to_dict() for p in self.candidates],
            "equivalents": [p.to_dict() for p in self.equivalents],
            "other_dosages": [p.to_dict() for p in self.other_dosages],
            "unknown_dose": [p.to_dict() for p in self.unknown_dose],
            "other_forms": [p.to_dict() for p in self.other_forms],
            "inactive": [p.to_dict() for p in self.inactive],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Rendering vocabulary -- one place that decides what statut / type / status
# mean in words, so the text renderer and the JSON agree.
# ---------------------------------------------------------------------------


def availability_label(availability: str) -> str:
    return AVAILABILITY_LABELS.get(availability, availability or "unknown")


def type_label(type_: str) -> str:
    return TYPE_LABELS.get(type_, type_)


def origin_label(statut: str) -> str:
    return STATUT_LABELS.get(statut, statut or "origin unknown")


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def default_index_path() -> str:
    """Absolute path of the committed index, next to this module's data dir."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, DB_FILENAME))


def _connect(index_path: str) -> sqlite3.Connection:
    """Open the index read-only.

    ``mode=ro`` is load-bearing: a query-time bug must not be able to corrupt
    the file every answer depends on.
    """
    uri = "file:{}?mode=ro".format(index_path.replace("\\", "/"))
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _meta(connection: sqlite3.Connection) -> dict[str, str]:
    return {key: value for key, value in
            connection.execute("SELECT key, value FROM meta")}


def _rows_for_brand(connection, brand_key: str) -> list[Product]:
    return [Product.from_row(r) for r in connection.execute(
        "SELECT * FROM product WHERE brand_key=?", (brand_key,))]


def _resolve_exact(connection, name=None, dci=None, code=None):
    """The rows an exact route matches, in the brief's resolution order.

    Returns ``(matched, route)``; ``route`` is ``""`` when nothing matched, so
    a caller can tell "the brand hit nothing but the DCI did" from a total
    miss. Fuzzy is *not* here -- it belongs to the caller, because it must
    never produce an anchor.
    """
    if name:
        rows = _rows_for_brand(connection, fold(name))
        if rows:
            return rows, "brand"
        return [], ""

    if dci:
        key = fold(dci)
        rows = [Product.from_row(r) for r in connection.execute(
            "SELECT * FROM product WHERE dci_key=? OR dci_base_key=? "
            "ORDER BY brand_key", (key, key))]
        if rows:
            return rows, "dci"
        return [], ""

    if code:
        text = str(code).strip()
        rows = [Product.from_row(r) for r in connection.execute(
            "SELECT * FROM product WHERE code=? ORDER BY brand_key", (text,))]
        if rows:
            return rows, "code"
        return [], ""

    return [], ""


def _fuzzy_candidates(connection, typed: str) -> list[Product]:
    """Brands close to ``typed``, for the user to choose between. Never an
    anchor. ``get_close_matches`` returns at most one row per brand, so the
    rows are fetched back explicitly."""
    brands = [row[0] for row in connection.execute(
        "SELECT DISTINCT brand_key FROM product")]
    close = difflib.get_close_matches(
        fold(typed), brands, n=MAX_CANDIDATES, cutoff=FUZZY_CUTOFF)
    candidates: list[Product] = []
    for brand_key in close:
        candidates.extend(_rows_for_brand(connection, brand_key))
    return candidates


def _anchor_sort_key(product: Product):
    """Lowest ``(dose_key, form_key)`` wins, with the row id as the final
    tie-break. Several rows can share a form and dose, and picking between
    them arbitrarily would make the anchor jump between releases."""
    return (product.dose_key or "", product.form_key, product.id or 0)


def _pick_anchor(rows: list[Product]) -> tuple[Product, str]:
    """The pinned anchor rule, and which branch of it won.

    1. Prefer rows that are ``active`` **and** have a known ``dose_key``; among
       those take the lowest ``(dose_key, form_key)``.
    2. Only if none qualifies, fall back -- first to any active row, then to
       any row at all. A ``None`` dose_key sorts as ``""``, so without step 1
       the fallback would anchor on an unknown dose purely because ``None``
       sorts first. The fallback is itself part of the answer, which is why
       the rule name travels back with the anchor.
    """
    with_known_dose = [row for row in rows
                       if row.availability == "active"
                       and row.dose_key is not None]
    if with_known_dose:
        return (min(with_known_dose, key=_anchor_sort_key),
                ANCHOR_RULE_KNOWN_DOSE)
    active = [row for row in rows if row.availability == "active"]
    if active:
        return min(active, key=_anchor_sort_key), ANCHOR_RULE_UNKNOWN_DOSE
    return min(rows, key=_anchor_sort_key), ANCHOR_RULE_OFF_MARKET


def _anchor_rows(anchor: Product, matched: list[Product]) -> list[Product]:
    """The rows the anchor was chosen from: the active ones, or all of them
    when nothing is active. Reported so a multi-row brand says so."""
    active = [row for row in matched if row.availability == "active"]
    return active or matched


def _bucket(anchor: Product, group: list[Product],
            include_inactive: bool) -> tuple[list, list, list, list, list]:
    """Split the anchor's DCI base group the way the brief defines it.

    ``equivalents`` is same form *and* same known dose. A ``None`` dose_key is
    never equal to the anchor's dose, so an unknown dose can only ever leave
    the class -- and when the anchor's own dose is ``None`` nothing can match
    it, so the class is empty.

    A same-form row with an unknown dose goes to ``unknown_dose``, never to
    ``other_dosages``: an unknown dose is not a *different* dose, so calling it
    one would assert a difference the data does not support. That holds whether
    the row is active or not -- ``include_inactive`` only folds off-market rows
    at a *known* dose back in, so it can never smuggle an unknown dose into
    ``equivalents``.
    """
    same_dose = anchor.dose_key is not None
    equivalents, other_dosages, unknown_dose = [], [], []
    other_forms, inactive = [], []
    for row in group:
        if row.form_key != anchor.form_key:
            other_forms.append(row)
        elif row.dose_key is None:
            unknown_dose.append(row)
        elif same_dose and row.dose_key == anchor.dose_key:
            (equivalents if row.availability == "active"
             else inactive).append(row)
        else:
            # Same form, a *different known* dose. Two Nones are not evidence
            # of equivalence, and a null dose never reaches this branch.
            other_dosages.append(row)

    if include_inactive:
        # The rare request for the full historical picture: the off-market
        # rows already at the anchor's known form and dose fold back in.
        # ``unknown_dose`` is not touched -- the flag is about availability,
        # not about dose.
        equivalents = sorted(equivalents + inactive, key=_sort_key)
        inactive = []

    return (sorted(equivalents, key=_sort_key),
            sorted(other_dosages, key=_sort_key),
            sorted(unknown_dose, key=_sort_key),
            sorted(other_forms, key=_sort_key),
            sorted(inactive, key=_sort_key))


def _sort_key(product: Product):
    """Stable, human-sensible order: brand, then dose, then id."""
    return (product.brand_key, product.dose_key or "", product.form_key,
            product.id or 0)


def lookup(name: str | None = None, dci: str | None = None,
           code: str | None = None, *, include_inactive: bool = False,
           index_path: str | None = None) -> LookupResult:
    """Resolve a brand, DCI or code to a product and its equivalence class.

    Only one route should be given; the CLI enforces that, and if more than
    one is passed the first in the brief's order wins. ``index_path`` is for
    tests and for pointing at a rebuilt index -- it defaults to the committed
    one and is always opened read-only.
    """
    typed = name if name is not None else (dci if dci is not None else code)
    query = "" if typed is None else str(typed)

    connection = _connect(index_path or default_index_path())
    try:
        meta = _meta(connection)
        matched, _route = _resolve_exact(connection, name, dci, code)

        if not matched and name:
            # Fuzzy is a *display* route, never a resolution route.
            candidates = _fuzzy_candidates(connection, name)
            return LookupResult(
                query=query, status="ambiguous" if candidates else "not_found",
                candidates=candidates,
                version_label=meta.get("version_label", ""),
                built_at=meta.get("built_at", ""),
                include_inactive=include_inactive)

        if not matched:
            return LookupResult(
                query=query, status="not_found",
                version_label=meta.get("version_label", ""),
                built_at=meta.get("built_at", ""),
                include_inactive=include_inactive)

        anchor, anchor_rule = _pick_anchor(matched)
        # A third of the DCI gradings are not clean: 3 rows carry an EMPTY
        # `dci_base_key` ('CARONATE DE MAGNESIUM...', 'MAGNESIUM SULFATE',
        # 'METOCLOPRAMIDE...'), and 194 brands span more than one base key.
        # Grouping on an empty key would marry three unrelated molecules into
        # one equivalence class, so an unknown base key defines no class: the
        # anchor stands alone and the class is empty.
        group = []
        if anchor.dci_base_key:
            group = [Product.from_row(r) for r in connection.execute(
                "SELECT * FROM product WHERE dci_base_key=?",
                (anchor.dci_base_key,))]
        buckets = _bucket(anchor, group, include_inactive)

        result = LookupResult(
            query=query, status="found", dci_base_key=anchor.dci_base_key,
            anchor=anchor, version_label=meta.get("version_label", ""),
            built_at=meta.get("built_at", ""),
            include_inactive=include_inactive, anchor_rule=anchor_rule,
            matched_rows=sorted(matched, key=_sort_key),
            anchor_rows=_anchor_rows(anchor, matched))
        (result._equivalents, result._other_dosages, result._unknown_dose,
         result._other_forms, result._inactive) = buckets
        return result
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# Rendering -- decides only how the answer looks, never what it is.
# ---------------------------------------------------------------------------


def staleness_note(built_at: str, now: datetime.datetime | None = None) -> str:
    """A warning when the index is older than the brief's 90 days.

    ``built_at`` is Task 3's ISO timestamp; an unparseable one returns a
    warning rather than pretending the index is fresh.
    """
    if not built_at:
        return "WARNING: the index has no build date; its freshness is unknown."
    try:
        built = datetime.datetime.fromisoformat(built_at)
    except ValueError:
        return f"WARNING: unreadable build date {built_at!r}; freshness unknown."
    now = now or datetime.datetime.now()
    if now - built > STALE_AFTER:
        days = (now - built).days
        return (f"WARNING: this index is {days} days old (built {built_at}); "
                f"the ministry publishes a new release every one to two "
                f"months, so re-download before relying on it.")
    return ""


def _header(result: LookupResult) -> list[str]:
    lines = [f"Nomenclature nationale -- version {result.version_label or '?'}"]
    note = staleness_note(result.built_at)
    if note:
        lines.append(note)
    return lines


def _product_line(index: int, product: Product, *, tag: str = "") -> list[str]:
    """One product as two short lines.

    A single wide line folded unreadably at any realistic terminal width: the
    laboratory name is long and free text, so the origin and type columns
    vanished off the right edge. Two lines keep brand/dose/type together and
    put origin and laboratory underneath, which is what a reader on a phone
    needs.
    """
    dose = product.dose_key or "dose unknown"
    flag = "" if product.type != "BIO" else "  ***BIOLOGIC***"
    first = (f"  {index:>2}. {product.brand} -- {dose} -- "
             f"{type_label(product.type)}{flag}{tag}")
    second = f"      {origin_label(product.statut)} -- {product.lab}"
    return [first, second]


def _availability_tag(product: Product) -> str:
    """The marker an off-market row carries, and nothing for an active one.

    Every bucket uses this. A withdrawn or not-renewed product rendered without
    its status reads as part of the current register -- the exact mistake this
    project exists to prevent -- so the marker is not a formatting choice made
    per section: it is applied wherever a non-active row can appear, including
    ``equivalents`` when ``--include-inactive`` folds those rows in.
    """
    if product.availability == "active":
        return ""
    return f"  [{availability_label(product.availability)}]"


def _render_bucket(products: list[Product], empty_note: str,
                   limit: int | None = None) -> list[str]:
    """Render a bucket, truncating to ``limit`` items when given.

    ``limit`` exists because a DCI can reach hundreds of rows across the whole
    substance group; a terminal answer has to stay readable, and ``--json`` is
    the route to the complete list. Each row carries its availability through
    ``_availability_tag``, because any bucket may hold more than one
    availability and a mixed list without markers is unreadable as a register.
    """
    if not products:
        return [f"  {empty_note}"]
    shown = products if limit is None else products[:limit]
    lines: list[str] = []
    for i, product in enumerate(shown, 1):
        lines.extend(_product_line(i, product, tag=_availability_tag(product)))
    if limit is not None and len(products) > limit:
        lines.append(f"  ... and {len(products) - limit} more "
                     f"(use --json for the full list).")
    return lines


def _render_candidates(result: LookupResult) -> list[str]:
    """Group a fuzzy hit by brand so the reader picks a *brand*, not a row."""
    by_brand: dict[str, list[Product]] = {}
    for product in result.candidates:
        by_brand.setdefault(product.brand_key, []).append(product)
    lines = []
    for rows in by_brand.values():
        brand = rows[0].brand
        doses = ", ".join(sorted({r.dosage for r in rows}))
        forms = ", ".join(sorted({r.form for r in rows}))
        lines.append(f"  {brand} -- {forms} -- {doses}")
    return lines


def render_text(result: LookupResult) -> str:
    """The terminal answer. Compact, aligned, and honest about its own limits."""
    if result.status == "not_found":
        return "\n".join(_header(result) + [
            "",
            f"No product in this nomenclature matches {result.query!r}.",
            "Nothing close enough to offer was found either -- this is a miss,",
            "not a guess. Check the spelling, or search by DCI or code.",
        ])

    if result.status == "ambiguous":
        return "\n".join(_header(result) + [
            "",
            f"{result.query!r} did not match a listed product exactly.",
            "It is close to the following, but a near match is not a match --",
            "this is ambiguous, and nothing has been chosen for you. Pick one",
            "and search again:",
            "",
            *_render_candidates(result),
            "",
            "No equivalence class is shown for a near match.",
        ])

    anchor = result.anchor
    availability = availability_label(anchor.availability)
    lines = _header(result) + [""]
    dose_known = anchor.dose_key is not None
    lines.append(f"Anchor: {anchor.brand} -- {anchor.dci}")
    lines.append(f"  form         : {anchor.form}")
    lines.append(f"  dosage       : {anchor.dosage}  "
                 f"[key {anchor.dose_key or 'unknown'}]"
                 + ("" if dose_known
                    else "  *** NOT COMPARABLE -- the dose is unknown, so no "
                         "equivalence class can be formed ***"))
    lines.append(f"  status       : {availability}"
                 + ("" if result.anchor_is_active
                    else "  *** OFF-MARKET -- do not present as available ***"))
    lines.append(f"  origin       : {origin_label(anchor.statut)}"
                 + (f" ({anchor.country})" if anchor.country else ""))
    lines.append(f"  type         : {type_label(anchor.type)}")
    if anchor.reg_no:
        lines.append(f"  registration : {anchor.reg_no}")
    if len(result.matched_rows) > 1:
        # Availability is not one value per brand, so say how many rows the
        # query matched rather than letting the anchor stand for all of them.
        others = len(result.matched_rows) - len(result.anchor_rows)
        lines.append(f"  NOTE: this query matched {len(result.matched_rows)} "
                     f"rows; the anchor is one of {len(result.anchor_rows)} "
                     f"at the {availability} status above"
                     + (f" ({others} other rows are listed below)." if others
                        else "."))
    if result.anchor_rule == ANCHOR_RULE_UNKNOWN_DOSE:
        lines.append("  NOTE: no active row of this substance has a "
                     "determinable dose, so the anchor falls back to an "
                     "unknown-dose row. Its dose is NOT comparable and the "
                     "equivalence class below is empty by design.")
    elif result.anchor_rule == ANCHOR_RULE_OFF_MARKET:
        lines.append("  NOTE: no row of this substance is active, so the "
                     "anchor falls back to an off-market row. Nothing here is "
                     "presented as available, and no equivalence class forms.")

    if anchor.availability == "withdrawn":
        # Opaque text by design: `withdrawn_at` holds ISO strings and verbatim
        # words like 'RETRAIT', so it is reprinted, never parsed.
        if anchor.withdrawn_at:
            lines.append(f"  withdrawn on : {anchor.withdrawn_at}")
        if anchor.withdrawn_reason:
            lines.append(f"  reason       : {anchor.withdrawn_reason}")
    elif anchor.availability == "not_renewed":
        lines.append("  reason       : registration not renewed")

    lines.append("")
    dose_heading = (f"same dose ({anchor.dose_key})" if dose_known
                    else "dose UNKNOWN -- not comparable")
    lines.append(f"EQUIVALENTS -- same DCI, same form ({anchor.form_key}), "
                 f"{dose_heading}:")
    lines.append("")
    lines.extend(_render_bucket(result.equivalents, "none."))

    lines.append("")
    lines.append("Other dosages -- same DCI and form, different dose "
                 "(NOT equivalent):")
    lines.append("")
    lines.extend(_render_bucket(result.other_dosages, "none.", limit=20))

    lines.append("")
    lines.append("Unknown dose -- same DCI and form, dose not comparable "
                 "(NOT evidence of a difference):")
    lines.append("")
    lines.extend(_render_bucket(result.unknown_dose, "none.", limit=20))

    lines.append("")
    lines.append("Other forms -- same DCI, different form "
                 "(NOT equivalent):")
    lines.append("")
    lines.extend(_render_bucket(result.other_forms, "none.", limit=20))

    if result.inactive:
        lines.append("")
        lines.append("Off-market at the anchor's form and dose "
                     "(NOT active -- do not present as available):")
        lines.append("")
        for i, product in enumerate(result.inactive, 1):
            lines.extend(_product_line(i, product,
                                       tag=_availability_tag(product)))
    elif result.include_inactive and result.equivalents:
        lines.append("")
        lines.append("--include-inactive: the once off-market rows at this form "
                     "and dose are folded into the list above; every row that "
                     "is not active there still carries its own marker.")

    if any(p.type == "BIO" for p in result.equivalents):
        lines.append("")
        lines.append("WARNING: a row above is marked ***BIOLOGIC***. A "
                     "biosimilar is not interchangeable with a chemical "
                     "generic the way a GE is -- do not substitute on type "
                     "alone.")

    lines.append("")
    lines.append("Equivalence here means same DCI, same form, same dose. It is "
                 "not a statement of bioequivalence, and substitution is the "
                 "pharmacist's or prescriber's decision.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lookup.py",
        description="Find a product in the Algerian national nomenclature and "
                    "report its equivalence class.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="brand name as printed (accent- and "
                                      "case-insensitive)")
    group.add_argument("--dci", help="international non-proprietary name")
    group.add_argument("--code", help="registration code, e.g. '03 B 081'")
    parser.add_argument("--json", action="store_true",
                        help="structured output instead of aligned text")
    parser.add_argument("--include-inactive", action="store_true",
                        help="fold not-renewed and withdrawn rows into the "
                             "equivalents list (the output will say so)")
    parser.add_argument("--index", help="path to the SQLite index "
                                        "(default: the committed one)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    result = lookup(name=args.name, dci=args.dci, code=args.code,
                    include_inactive=args.include_inactive,
                    index_path=args.index)

    if args.json:
        print(result.to_json())
    else:
        print(render_text(result))

    return 0 if result.status in ("found", "ambiguous") else 1


if __name__ == "__main__":
    sys.exit(main())

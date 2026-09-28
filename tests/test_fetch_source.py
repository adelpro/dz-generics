"""Tests for the ministry source fetcher's page parser.

These run offline against an inline fixture shaped like the real page, so a
ministry redesign is caught here rather than in a live download. The fixture
deliberately reproduces the trap: the non-renewed and withdrawal spreadsheets
are listed under the same heading as the releases, so a parser that pairs a
link with whichever version text preceded it will pick them up as releases.
"""
from fetch_source import parse_versions

BASE = "https://www.miph.gov.dz/fr/nomenclature-nationale-des-produits-pharmaceutiques/"

# Mirrors the real 2026 page: releases newest-first, then two non-version
# spreadsheets under the "produits retires / non renouveles" heading, then the
# older 2025 releases further down.
PAGE = """
<ul>
<li><strong><a href="https://www.miph.gov.dz/fr/wp-content/uploads/2026/09/clean_NOMENCLATURE.VERSION.AOUT_.2026-.xlsx">Version Ao&#251;t 2026</a></strong></li>
<li><strong><a href="https://www.miph.gov.dz/fr/wp-content/uploads/2026/07/clean_NOMENCLATURE.VERSION.JUIN_.2026-.xlsx">Version Juin 2026</a></strong></li>
<li><strong><a href="https://www.miph.gov.dz/fr/wp-content/uploads/2026/05/NOMENCLATURE.VERSION.AVRIL_.2026-.xlsx" target="_blank">Version Avril 2026</a></strong></li>
</ul>
<h3>Listes</h3>
<h6><a href="https://www.miph.gov.dz/fr/wp-content/uploads/2026/01/nomenclature-non-renouveles.xlsx">Liste des produits pharmaceutiques qui n&#8217;ont pas fait l&#8217;objet de renouvellement</a></h6>
<h6><a href="https://www.miph.gov.dz/fr/wp-content/uploads/2026/01/nomenclature-retrait.xlsx">liste des produits pharmaceutiques faisant l&#8217;objet de retrait</a></h6>
<h3><a href="https://www.miph.gov.dz/fr/wp-content/uploads/2026/01/NOMENCLATURE-VERSION-DECEMBRE-2025.xlsx">- Version D&#233;cembre 2025</a></h3>
<h3><a href="/wp-content/uploads/2025/12/NOMENCLATURE-VERSION-NOVEMBRE-2025.xlsx">- Version Novembre 2025</a></h3>
"""


def test_picks_the_newest_release_first():
    versions = parse_versions(PAGE)
    assert versions[0][0] == (2026, 8)
    assert versions[0][1].endswith("clean_NOMENCLATURE.VERSION.AOUT_.2026-.xlsx")


def test_sorts_across_the_year_boundary():
    order = [month for (year, month), _ in parse_versions(PAGE)]
    assert order == [8, 6, 4, 12, 11], "newest first, and 2026 before 2025"


def test_ignores_the_non_version_lists():
    """The regression this parser exists to prevent: a link paired with the
    version text above it instead of its own."""
    urls = [url for _, url in parse_versions(PAGE)]
    assert not any("non-renouveles" in u for u in urls)
    assert not any("nomenclature-retrait" in u for u in urls)
    assert len(urls) == 5


def test_parses_accented_month_names():
    """The page writes 'Août', the filenames write 'AOUT'."""
    versions = parse_versions(PAGE)
    assert (2026, 8) in [v for v, _ in versions]
    assert (2025, 12) in [v for v, _ in versions]


def test_resolves_relative_hrefs():
    """A root-relative href must become absolute, or the download 404s."""
    versions = dict((v, u) for v, u in parse_versions(PAGE))
    assert versions[(2025, 11)] == (
        "https://www.miph.gov.dz/wp-content/uploads/2025/12/"
        "NOMENCLATURE-VERSION-NOVEMBRE-2025.xlsx"
    )


def test_duplicate_version_keeps_the_first_url():
    page = (
        '<a href="https://x/a.xlsx">Version Janvier 2026</a>'
        '<a href="https://x/b.xlsx">Version Janvier 2026</a>'
    )
    versions = parse_versions(page)
    assert [u for _, u in versions] == ["https://x/a.xlsx"]


def test_empty_page_returns_nothing():
    assert parse_versions("<p>maintenance</p>") == []

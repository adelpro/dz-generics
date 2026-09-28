"""Download the newest Algerian national pharmaceutical nomenclature.

The ministry page lists one .xlsx per release, newest first. This fetches the
page, picks the newest version by parsing the French month and year out of
each link's anchor text, and downloads it into ``data/source/``.

    python fetch_source.py            # download the newest release
    python fetch_source.py --dry-run  # print the URL and stop

This is a build-time convenience, never part of the query path. The ministry
renames files and reshuffles upload paths between releases (the ``clean_``
prefix comes and goes, and the upload month does not always match the version
month), so this script is expected to break eventually. When it does, download
the file by hand, drop it in ``data/source/``, and run ``build_index.py`` --
a failure here must never block a lookup.

Standard library only, so refreshing the data needs no install.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PAGE_URL = (
    "https://www.miph.gov.dz/fr/"
    "nomenclature-nationale-des-produits-pharmaceutiques/"
)
USER_AGENT = "dz-generics/1.0 (+https://github.com/adelpro/dz-generics)"

# French month names as they appear in the anchor text. The file names use
# unaccented forms ("AOUT"), the page uses accented ones ("Août") -- match on
# the folded key, never on the raw string.
MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10,
    "novembre": 11, "decembre": 12,
}

# Anchor text like "Version Août 2026" or "Version Février 2026".
VERSION_RE = re.compile(r"version\s+([a-z]+)\s+(\d{4})", re.IGNORECASE)
# One anchor, capturing href and inner text.
ANCHOR_RE = re.compile(
    r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL
)


def fold(text: str) -> str:
    """Lowercase and strip accents, so 'Août' and 'AOUT' both become 'aout'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def fetch_page(url: str = PAGE_URL, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_versions(page: str, base_url: str = PAGE_URL) -> list[tuple[tuple[int, int], str]]:
    """Return ``[((year, month), url), ...]`` sorted newest first.

    A release is an anchor whose ``href`` ends in ``.xlsx`` **and** whose own
    text parses as a version. Requiring both on the same anchor is what keeps
    the non-renewed and withdrawal spreadsheets out: their links sit under the
    same heading but their text is not a version, so they are skipped rather
    than inheriting whichever version happened to precede them.
    """
    found: dict[tuple[int, int], str] = {}
    for match in ANCHOR_RE.finditer(page):
        href = match.group(1)
        if not href.lower().endswith(".xlsx"):
            continue
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group(2)))
        version = VERSION_RE.search(fold(text))
        if not version:
            continue
        month = MONTHS.get(version.group(1))
        if not month:
            continue
        # setdefault, so a duplicated version keeps the first URL seen.
        found.setdefault(
            (int(version.group(2)), month), urllib.parse.urljoin(base_url, href)
        )
    return sorted(found.items(), reverse=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be downloaded, save nothing")
    parser.add_argument("--out", default="data/source", type=Path,
                        help="directory to save into (default: data/source)")
    parser.add_argument("--page", default=PAGE_URL,
                        help="override the ministry page URL")
    args = parser.parse_args(argv)

    try:
        page = fetch_page(args.page)
    except (urllib.error.URLError, OSError) as exc:
        print(f"error: could not fetch the ministry page: {exc}", file=sys.stderr)
        print("Download the newest .xlsx by hand, put it in data/source/, "
              "and run build_index.py.", file=sys.stderr)
        return 1

    versions = parse_versions(page, args.page)
    if not versions:
        print("error: no version links found -- the page layout probably "
              "changed. Download by hand and run build_index.py.", file=sys.stderr)
        return 1

    (year, month), url = versions[0]
    print(f"newest release : {month:02d}/{year}")
    print(f"url            : {url}")
    print(f"other releases : {len(versions) - 1}")

    if args.dry_run:
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / Path(urllib.parse.urlparse(url).path).name
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    target.write_bytes(payload)
    print(f"saved          : {target} ({len(payload):,} bytes)")

    if len(payload) < 100_000:
        print("warning: the file is far smaller than a nomenclature (about "
              "1.2 MB expected). The page may have linked something else.",
              file=sys.stderr)
        return 2
    print("\nnext: python scripts/build_index.py", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

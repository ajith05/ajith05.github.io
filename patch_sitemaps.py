"""Patch <lastmod> in the built sitemap.xml and sitemapindex.xml.

Nikola takes <lastmod> from file mtimes, which on a fresh CI checkout are all
the build time. Instead, use the last time each page's content actually
changed on the deploy branch: if a page is byte-identical to the version on
that branch, use the date of the commit that last touched it; otherwise (it
changed, or is new) it is about to be deployed, so use the build time.

Usage: python patch_sitemaps.py [--output output] [--ref ghpages]
"""
import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ENTRY = re.compile(r"(<loc>(?P<loc>[^<]+)</loc>\s*<lastmod>)(?P<date>[^<]*)(</lastmod>)")


def git(*args, stdin=None):
    return subprocess.run(
        ["git", *args], input=stdin, capture_output=True, text=True, check=True
    ).stdout


def fmt(dt):
    """RFC 3339 in UTC at minute precision, as Nikola writes it."""
    return dt.astimezone(timezone.utc).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%MZ")


def output_path(loc):
    """Map a sitemap URL to its file path relative to the output folder."""
    path = unquote(urlparse(loc).path).lstrip("/")
    if not path or path.endswith("/"):
        path += "index.html"
    return path


class Dates:
    def __init__(self, output, ref):
        self.output = output
        self.ref = ref
        self.now = fmt(datetime.now(timezone.utc))
        self.deployed = {}  # path -> blob hash on the deploy branch
        for line in git("ls-tree", "-r", ref).splitlines():
            meta, path = line.split("\t", 1)
            self.deployed[path] = meta.split()[2]

    def lastmod(self, path):
        local = self.output / path
        if not local.is_file():
            raise FileNotFoundError(f"{local} is listed in the sitemap but was not built")
        local_hash = git("hash-object", "--no-filters", str(local)).strip()
        if self.deployed.get(path) != local_hash:
            return self.now
        committed = git("log", "-1", "--format=%cI", self.ref, "--", path).strip()
        return fmt(datetime.fromisoformat(committed))


def rewrite(text, date_for):
    """Replace every <lastmod> in text with date_for(loc); return (text, dates)."""
    dates = []

    def sub(m):
        date = date_for(m["loc"])
        dates.append(date)
        return f"{m[1]}{date}{m[4]}"

    return ENTRY.sub(sub, text), dates


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--ref", default="ghpages")
    args = parser.parse_args()

    dates = Dates(args.output, args.ref)
    sitemap = args.output / "sitemap.xml"
    index = args.output / "sitemapindex.xml"

    text, page_dates = rewrite(sitemap.read_text(encoding="utf-8"), lambda loc: dates.lastmod(output_path(loc)))
    if not page_dates:
        raise SystemExit(f"No <lastmod> entries found in {sitemap}")
    sitemap.write_text(text, encoding="utf-8")
    newest = max(page_dates)

    def index_date(loc):
        path = output_path(loc)
        return newest if path == "sitemap.xml" else dates.lastmod(path)

    text, _ = rewrite(index.read_text(encoding="utf-8"), index_date)
    index.write_text(text, encoding="utf-8")
    print(f"Patched {len(page_dates)} sitemap entries; newest lastmod {newest}")


if __name__ == "__main__":
    main()

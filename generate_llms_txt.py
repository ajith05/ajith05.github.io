"""Generate output/llms.txt, an index of the site's Markdown sources for LLMs.

Nikola copies each source file next to its rendered page (COPY_SOURCES), so
pages/<slug>.md is served at /<slug>/index.md and posts/<slug>.md at
/blog/<slug>/index.md. List those, using the title and description from each
file's front matter. Run it after `nikola build`.

Usage: python generate_llms_txt.py [--output output]
"""
import argparse
import re
import runpy
from datetime import datetime
from pathlib import Path

SKIP_SLUGS = {"404"}
SKIP_TAGS = {"draft", "private"}
META_BLOCK = re.compile(r"\A\s*<!--(.*?)-->", re.S)
META_LINE = re.compile(r"^\.\. (\w+):[ \t]*(.*)$", re.M)


def read_meta(path):
    block = META_BLOCK.match(path.read_text(encoding="utf-8"))
    if not block:
        raise SystemExit(f"{path}: no front matter comment found")
    return {k: v.strip() for k, v in META_LINE.findall(block[1])}


def collect(source_dir, url_dir, site_url, output):
    entries = []
    for path in sorted(Path(source_dir).glob("*.md")):
        meta = read_meta(path)
        slug = meta.get("slug") or path.stem
        tags = {t.strip() for t in meta.get("tags", "").split(",")}
        if slug in SKIP_SLUGS or tags & SKIP_TAGS:
            continue
        for key in ("title", "description", "date"):
            if not meta.get(key):
                raise SystemExit(f"{path}: missing '.. {key}:' in front matter")
        rel = "/".join(p for p in (url_dir, slug if slug != "index" else "", "index.md") if p)
        if not (output / rel).is_file():
            raise SystemExit(f"{path}: expected {output / rel} was not built")
        entries.append((datetime.fromisoformat(meta["date"]), meta["title"], site_url + rel, meta["description"]))
    return entries


def section(heading, entries, newest_first=False):
    entries = sorted(entries, key=lambda e: e[0], reverse=newest_first)
    lines = [f"## {heading}", ""]
    lines += [f"- [{title}]({url}): {description}" for _, title, url, description in entries]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("output"))
    args = parser.parse_args()

    conf = runpy.run_path("conf.py")
    site_url = conf["SITE_URL"].rstrip("/") + "/"

    pages = collect("pages", "", site_url, args.output)
    posts = collect("posts", "blog", site_url, args.output)
    if not pages:
        raise SystemExit("No pages found to list")

    parts = [f"# {conf['BLOG_TITLE']}", f"> {conf['BLOG_DESCRIPTION']}", section("Pages", pages)]
    if posts:
        parts.append(section("Blog posts", posts, newest_first=True))
    (args.output / "llms.txt").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote llms.txt with {len(pages)} pages and {len(posts)} posts")


if __name__ == "__main__":
    main()

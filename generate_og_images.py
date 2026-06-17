#!/usr/bin/env python3
"""Generate Open Graph images for Nikola posts and pages using Pillow."""

import argparse
import os
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── Configuration ────────────────────────────────────────────────────────────

CANVAS_W, CANVAS_H = 1200, 630
BG_COLOR = "#336699"           # web-safe blue, not strongly branded
ACCENT_COLOR = "#1E4D7A"       # darker shade for the top bar
TEXT_COLOR = "#FFFFFF"
ACCENT_BAR_H = 14              # px for the top accent strip
SEPARATOR_COLOR = (255, 255, 255, 100)  # semi-transparent white

FONT_PATH_DEFAULT = "fonts/Gurajada-Regular.ttf"
OUTPUT_DIR = Path("files/og")

AUTHOR_NAME = "Ajith Kanumuri"
HOMEPAGE_SUBTITLE = "Data Scientist & ML Engineer"

# Slug-to-source-file paths scanned during generation
SOURCE_DIRS = [("posts", "blog"), ("pages", "")]

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_nikola_meta(filepath: Path) -> dict:
    """Extract Nikola metadata from a Markdown source file."""
    meta = {}
    in_comment = False
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.strip() == "<!--":
                in_comment = True
                continue
            if line.strip() == "-->":
                break
            if in_comment:
                m = re.match(r"\.\.\s+(\w+):\s*(.*)", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip()
    return meta


def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, size)


def measure_text(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    """Return (width, height) of the rendered text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    max_width: int,
    start_size: int = 88,
    min_size: int = 32,
) -> tuple[ImageFont.FreeTypeFont, int]:
    """Find the largest font size where text fits within max_width on one line."""
    size = start_size
    while size >= min_size:
        font = load_font(font_path, size)
        w, _ = measure_text(draw, text, font)
        if w <= max_width:
            return font, size
        size -= 4
    return load_font(font_path, min_size), min_size


def wrap_and_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    max_width: int,
    start_size: int = 88,
    min_size: int = 32,
    max_lines: int = 3,
) -> tuple[list[str], ImageFont.FreeTypeFont]:
    """
    Return (lines, font) where the text is wrapped and sized to fit max_width.
    Tries single-line first, then wraps to multiple lines if needed.
    """
    for size in range(start_size, min_size - 1, -4):
        font = load_font(font_path, size)
        # try to wrap at this size
        chars_per_line = max(1, int(len(text) * max_width / max(1, measure_text(draw, text, font)[0])))
        for width_hint in range(chars_per_line, 0, -5):
            lines = textwrap.wrap(text, width=width_hint)
            if not lines:
                lines = [text]
            if len(lines) <= max_lines:
                if all(measure_text(draw, l, font)[0] <= max_width for l in lines):
                    return lines, font
    # absolute fallback
    font = load_font(font_path, min_size)
    return textwrap.wrap(text, width=30) or [text], font


def draw_centered_text_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font,
    center_y: int,
    canvas_w: int,
    color: str,
    line_spacing: float = 1.15,
) -> tuple[int, int]:
    """Draw lines centered horizontally around center_y. Returns (top_y, bottom_y)."""
    _, line_h = measure_text(draw, "Ag", font)
    step = int(line_h * line_spacing)
    total_h = step * (len(lines) - 1) + line_h
    y = center_y - total_h // 2
    top_y = y
    for line in lines:
        w, _ = measure_text(draw, line, font)
        x = (canvas_w - w) // 2
        draw.text((x, y), line, font=font, fill=color)
        y += step
    return top_y, top_y + total_h


def generate_og_image(
    *,
    title: str,
    subtitle: str,
    is_homepage: bool,
    out_path: Path,
    font_path: str,
    force: bool,
) -> bool:
    """Generate a single OG image. Returns True if image was written."""
    if out_path.exists() and not force:
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
    draw = ImageDraw.Draw(img, "RGBA")

    # Top accent bar
    draw.rectangle([0, 0, CANVAS_W, ACCENT_BAR_H], fill=ACCENT_COLOR)

    pad_x = 80          # horizontal padding
    max_text_w = CANVAS_W - 2 * pad_x
    content_top = ACCENT_BAR_H + 40
    content_bot = CANVAS_H - 40
    mid_y = (content_top + content_bot) // 2

    if is_homepage:
        # Large name, smaller subtitle
        name_font, _ = fit_font_size(draw, title, font_path, max_text_w, start_size=108, min_size=48)
        sub_font = load_font(font_path, 48)

        # Use raw bbox coords so draw positions align with visual extents.
        # bbox = (left, top, right, bottom) relative to the draw anchor.
        name_bbox = draw.textbbox((0, 0), title, font=name_font)
        sub_bbox = draw.textbbox((0, 0), subtitle, font=sub_font)

        gap = 32
        separator_h = 2

        # Center the visual block: from name's visual top to subtitle's visual bottom.
        # When text is drawn at y=block_top, its visual span is
        # [block_top + bbox[1], block_top + bbox[3]].
        visual_h = (name_bbox[3] - name_bbox[1]) + gap + separator_h + gap + (sub_bbox[3] - sub_bbox[1])
        # block_top chosen so visual centre == mid_y
        block_top = mid_y - name_bbox[1] - visual_h // 2

        # Name
        name_w = name_bbox[2] - name_bbox[0]
        draw.text(((CANVAS_W - name_w) // 2, block_top), title, font=name_font, fill=TEXT_COLOR)

        # Separator line — placed after the visual bottom of the name
        sep_y = block_top + name_bbox[3] + gap
        draw.rectangle([pad_x, sep_y, CANVAS_W - pad_x, sep_y + separator_h], fill=SEPARATOR_COLOR)

        # Subtitle
        sub_y = sep_y + separator_h + gap
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(((CANVAS_W - sub_w) // 2, sub_y), subtitle, font=sub_font, fill=TEXT_COLOR)

    else:
        # Title (large, wrappable) + author (smaller)
        author_font = load_font(font_path, 40)
        _, author_h = measure_text(draw, subtitle, author_font)
        gap = 36
        separator_h = 2

        # Reserve space at bottom for author + separator + gaps
        title_zone_bot = content_bot - gap - separator_h - gap - author_h
        title_zone_h = title_zone_bot - content_top
        title_center_y = content_top + title_zone_h // 2

        lines, title_font = wrap_and_fit(draw, title, font_path, max_text_w, start_size=80, min_size=28)
        _, line_h = measure_text(draw, "Ag", title_font)
        step = int(line_h * 1.2)
        _, title_bot = draw_centered_text_block(
            draw, lines, title_font, title_center_y, CANVAS_W, TEXT_COLOR, line_spacing=1.2
        )

        # Separator
        sep_y = title_zone_bot
        draw.rectangle([pad_x, sep_y, CANVAS_W - pad_x, sep_y + separator_h], fill=SEPARATOR_COLOR)

        # Author
        author_y = sep_y + separator_h + gap
        author_w, _ = measure_text(draw, subtitle, author_font)
        draw.text(((CANVAS_W - author_w) // 2, author_y), subtitle, font=author_font, fill=TEXT_COLOR)

    img.save(out_path, "PNG", optimize=True)
    return True


def update_previewimage_meta(filepath: Path, image_url: str) -> bool:
    """
    Inject or update `.. previewimage: <url>` in the file's Nikola metadata block.
    Returns True if the file was modified.
    """
    text = filepath.read_text(encoding="utf-8")
    new_line = f".. previewimage: {image_url}"

    # If already set to the correct value, skip
    if f".. previewimage: {image_url}" in text:
        return False

    # Replace existing previewimage line if present
    updated = re.sub(r"^\.\. previewimage:.*$", new_line, text, flags=re.MULTILINE)
    if updated != text:
        filepath.write_text(updated, encoding="utf-8")
        return True

    # Insert before the closing --> of the metadata comment block
    updated = re.sub(
        r"(-->)",
        f"{new_line}\n\\1",
        text,
        count=1,
    )
    if updated != text:
        filepath.write_text(updated, encoding="utf-8")
        return True

    return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate OG images for Nikola site")
    parser.add_argument("--font", default=FONT_PATH_DEFAULT, help="Path to .ttf font file")
    parser.add_argument("--force", action="store_true", help="Regenerate even if image already exists")
    parser.add_argument("--update-meta", action="store_true",
                        help="Add/update previewimage metadata in source files")
    args = parser.parse_args()

    font_path = args.font
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Font not found: {font_path}. Download it or pass --font <path>.")

    sources = []
    for src_dir, _ in SOURCE_DIRS:
        for md_file in Path(src_dir).glob("*.md"):
            sources.append(md_file)

    generated = 0
    skipped = 0

    for src_file in sorted(sources):
        meta = parse_nikola_meta(src_file)
        title = meta.get("title", "")
        slug = meta.get("slug", src_file.stem)

        if not title and not slug:
            print(f"  skip  {src_file} (no title or slug)")
            continue

        is_homepage = slug == "index"
        if is_homepage:
            main_text = AUTHOR_NAME
            sub_text = HOMEPAGE_SUBTITLE
        else:
            main_text = title or slug
            sub_text = AUTHOR_NAME

        out_path = OUTPUT_DIR / f"{slug}.png"
        written = generate_og_image(
            title=main_text,
            subtitle=sub_text,
            is_homepage=is_homepage,
            out_path=out_path,
            font_path=font_path,
            force=args.force,
        )

        if written:
            print(f"  wrote {out_path}")
            generated += 1
        else:
            print(f"  skip  {out_path} (already exists; use --force to regenerate)")
            skipped += 1

        if args.update_meta:
            image_url = f"/og/{slug}.png"
            changed = update_previewimage_meta(src_file, image_url)
            if changed:
                print(f"         updated previewimage in {src_file}")

    print(f"\nDone: {generated} generated, {skipped} skipped.")


if __name__ == "__main__":
    main()

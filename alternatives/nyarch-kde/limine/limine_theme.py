#!/usr/bin/env python3
"""Adds or removes the Nyarch look in limine.conf. Text in, text out; nothing else.

  limine_theme.py apply  CONF IMAGE_NAME HASH STYLE   prints the themed config
  limine_theme.py strip  CONF                         prints the config with the theme removed
  limine_theme.py check  CONF IMAGE_NAME HASH         exit 0 if the theme is present and intact

Our lines sit between two marker comments, before the first boot entry. Global lines we
replace are kept in the file, commented out with SAVED, so undo can put them back exactly.
"""
from __future__ import annotations

import re
import sys

BEGIN = "# >>> nyarch-limine-theme (remove with nyarch-limine.sh undo)"
END = "# <<< nyarch-limine-theme"
SAVED = "#nyarch-saved# "

# Global options this theme sets. Any existing line for one of these is commented out.
KEYS = {
    "wallpaper", "wallpaper_style", "backdrop",
    "term_palette", "term_palette_bright", "term_background", "term_foreground",
    "term_background_bright", "term_foreground_bright", "term_margin", "term_margin_gradient",
    "interface_branding_colour", "interface_branding_color",
    "interface_help_colour", "interface_help_color",
    "interface_help_colour_bright", "interface_help_color_bright",
}

# Nyarch's colours: blue 2298d3, light blue 71c7f2, pale blue b4e6ff, pink e32b6b, light pink f5b1cf,
# on the art's near-black 111017.
THEME = [
    ("backdrop", "111017"),
    ("term_background", "50111017"),
    ("term_foreground", "e8e6f0"),
    ("term_background_bright", "2a2838"),
    ("term_foreground_bright", "ffffff"),
    ("term_palette", "111017;e32b6b;7fd1a0;e6c07a;2298d3;f5b1cf;71c7f2;c8c6d4"),
    ("term_palette_bright", "4a4760;ff6b9b;a5ecc0;ffe0a0;71c7f2;ffd0e6;b4e6ff;ffffff"),
    ("interface_branding_colour", "71c7f2"),
    ("interface_help_colour", "f5b1cf"),
    ("interface_help_colour_bright", "ffffff"),
    ("term_margin", "64"),
    ("term_margin_gradient", "8"),
]

_KEY = re.compile(r"^\s*([A-Za-z_]+)\s*:")
_ENTRY = re.compile(r"^\s*/")          # "/Entry name" starts the boot entries


def _valid(name: str, digest: str, style: str | None = None) -> None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.(png|jpg|jpeg|bmp)", name):
        raise SystemExit(f"bad image name: {name}")
    if not re.fullmatch(r"[0-9a-f]{128}", digest):
        raise SystemExit("bad BLAKE2B hash")
    if style is not None and style not in ("stretched", "centered", "tiled"):
        raise SystemExit(f"bad wallpaper style: {style}")


def block(name: str, digest: str, style: str) -> list[str]:
    _valid(name, digest, style)
    return [BEGIN, f"wallpaper: boot():/{name}#{digest}", f"wallpaper_style: {style}"] + \
        [f"{k}: {v}" for k, v in THEME] + [END]


def strip(text: str) -> str:
    out, inside = [], False
    for line in text.splitlines():
        if line.strip() == BEGIN:
            inside = True
            if out and out[-1].strip() == "":
                out.pop()             # the blank line apply() put before the block
            continue
        if inside:
            if line.strip() == END:
                inside = False
            continue
        out.append(line[len(SAVED):] if line.startswith(SAVED) else line)
    if inside:
        raise SystemExit("theme start marker without an end marker; edit limine.conf by hand")
    return "\n".join(out) + "\n"


def apply(text: str, name: str, digest: str, style: str) -> str:
    lines = strip(text).splitlines()
    first_entry = next((i for i, l in enumerate(lines) if _ENTRY.match(l)), len(lines))
    head, tail = lines[:first_entry], lines[first_entry:]
    head = [SAVED + l if (m := _KEY.match(l)) and m.group(1).lower() in KEYS else l for l in head]
    while head and head[-1].strip() == "":
        head.pop()
    return "\n".join(head + ([""] if head else []) + block(name, digest, style) + [""] + tail) + "\n"


def check(text: str, name: str, digest: str) -> bool:
    _valid(name, digest)
    lines = text.splitlines()
    if BEGIN not in lines or END not in lines:
        return False
    b, e = lines.index(BEGIN), lines.index(END)
    first_entry = next((i for i, l in enumerate(lines) if _ENTRY.match(l)), len(lines))
    ours = lines[b + 1:e]
    return b < e <= first_entry and f"wallpaper: boot():/{name}#{digest}" in ours and \
        all(f"{k}: {v}" in ours for k, v in THEME)


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("apply", "strip", "check"):
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[2], encoding="utf-8") as f:
        text = f.read()
    if argv[1] == "apply" and len(argv) == 6:
        sys.stdout.write(apply(text, argv[3], argv[4], argv[5]))
    elif argv[1] == "strip" and len(argv) == 3:
        sys.stdout.write(strip(text))
    elif argv[1] == "check" and len(argv) == 5:
        return 0 if check(text, argv[3], argv[4]) else 1
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

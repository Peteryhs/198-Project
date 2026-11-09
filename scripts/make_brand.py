"""Final brand assets: mark, lockup, tile, and a presentation board.

The mark is one continuous stroke: a baseline that swells into a repetition and returns to it.
Drawn as a single path so there is no overlapping cap at the join - that seam was the flaw the
first round showed.

Colours are chosen by WCAG contrast, computed here, not by eye.

Run: ~/.hermes/bin/uv run --no-project python make_brand.py
"""

from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "final")

INK = "#1C1917"
PAPER = "#F5F0E6"
CLAY = "#9A3B12"
SAGE = "#3F5A46"
ASH = "#6B6157"


def lum(hexcode: str) -> float:
    c = [int(hexcode[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


CHECKS = [("ink on paper", INK, PAPER), ("clay on paper", CLAY, PAPER),
          ("sage on paper", SAGE, PAPER), ("ash on paper", ASH, PAPER),
          ("paper on ink", PAPER, INK), ("paper on clay", PAPER, CLAY),
          ("paper on sage", PAPER, SAGE)]

# One continuous path: bar, hump, bar. Coordinates on a 512 canvas, 88 clear margin.
MARK_PATH = ("M 128 376 L 168 376 A 88 88 0 0 1 344 376 L 384 376")


def mark(stroke: str, width: int = 42) -> str:
    return (f'<path d="{MARK_PATH}" fill="none" stroke="{stroke}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def svg_mark(fg: str, bg: str, size: int = 512) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
            f'width="{size}" height="{size}"><rect width="512" height="512" fill="{bg}"/>'
            f'{mark(fg)}\n</svg>\n')


def svg_tile() -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" '
            f'height="512"><rect width="512" height="512" rx="116" fill="{INK}"/>{mark(PAPER)}\n</svg>\n')


def svg_lockup() -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 512" width="1000" height="512">
  <rect width="1000" height="512" fill="{PAPER}"/>
  <g transform="translate(-40 -60) scale(0.78)">{mark(INK)}</g>
  <text x="380" y="300" font-family="Fraunces" font-size="132" font-weight="600"
        letter-spacing="-2" fill="{INK}">form</text>
</svg>
'''


def board(ratios: dict[str, float]) -> str:
    W, H = 1400, 1800
    gutter = 32
    col = (W - 2 * 64 - gutter) / 2

    def panel(x, y, w, h, label):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#FFFFFF" '
                f'stroke="#E2DCD0" stroke-width="1"/>'
                f'<text x="{x + 24}" y="{y + 34}" font-family="Inter" font-size="13" '
                f'letter-spacing="2.2" fill="{ASH}">{label.upper()}</text>')

    # Palette chips
    chips = [("Ink", INK, "type, the mark, the device body"),
             ("Paper", PAPER, "ground, band print, screen inverse"),
             ("Clay", CLAY, "the accent that carries the system"),
             ("Sage", SAGE, "a rep done well"),
             ("Ash", ASH, "secondary labels only")]

    sw = (col - 48) / len(chips)
    chip_svg = []
    for i, (name, hexv, role) in enumerate(chips):
        x = 64 + col + gutter + 24 + i * sw
        chip_svg.append(
            f'<rect x="{x:.0f}" y="560" width="{sw - 14:.0f}" height="100" fill="{hexv}" '
            f'stroke="#D8D2C6"/>'
            f'<text x="{x:.0f}" y="694" font-family="Inter" font-size="15" fill="{INK}">{name}</text>'
            f'<text x="{x:.0f}" y="714" font-family="Inter" font-size="13" fill="{ASH}">{hexv}</text>'
            f'<text x="{x:.0f}" y="732" font-family="Inter" font-size="11" fill="{ASH}">'
            f'{ratios[name.lower()]:.1f}:1 vs paper</text>')

    # Construction panel: three steps of the same path
    cons = []
    steps = [(1.0, 0), (0.0, 1)]
    cons.append(f'<g transform="translate(120 470) scale(0.52)">{mark(INK, 26)}</g>')
    cons.append('<text x="120" y="700" font-family="Inter" font-size="13" fill="#6B6157">'
                'bar, hump, bar &mdash; one path</text>')
    cons.append(f'<g transform="translate(420 470) scale(0.52)">{mark(INK, 42)}</g>')
    cons.append('<text x="420" y="700" font-family="Inter" font-size="13" fill="#6B6157">'
                'stroke 42 / 512 &mdash; round caps</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <rect width="{W}" height="{H}" fill="{PAPER}"/>

  <!-- header -->
  <g transform="translate(64 92) scale(0.42)">{mark(INK)}</g>
  <text x="330" y="204" font-family="Fraunces" font-size="118" font-weight="600"
        letter-spacing="-2" fill="{INK}">form</text>
  <text x="334" y="262" font-family="Inter" font-size="26" fill="{CLAY}">Good form counts.</text>
  <text x="334" y="300" font-family="Inter" font-size="15" fill="{ASH}">
    Repetition quality for home physiotherapy &nbsp;&middot;&nbsp; ECE 198 design project</text>
  <line x1="64" y1="336" x2="{W - 64}" y2="336" stroke="#DED7C9"/>

  <!-- construction -->
  {panel(64, 372, col, 372, "The mark")}
  {''.join(cons)}

  <!-- palette -->
  {panel(64 + col + gutter, 372, col, 372, "Colour")}
  {''.join(chip_svg)}

  <!-- type -->
  {panel(64, 776, col, 424, "Type")}
  <text x="104" y="960" font-family="Fraunces" font-size="112" font-weight="600"
        letter-spacing="-2" fill="{INK}">form</text>
  <text x="104" y="1004" font-family="Fraunces" font-size="34" fill="{INK}">
    Fraunces &mdash; wordmark</text>
  <text x="104" y="1046" font-family="Inter" font-size="19" fill="{INK}">
    Inter &mdash; counts, labels, instructions</text>
  <text x="104" y="1132" font-family="Inter" font-size="56" font-weight="600" fill="{INK}">
    12 &nbsp;reps&nbsp; 94%</text>
  <text x="104" y="1176" font-family="Inter" font-size="14" fill="{ASH}">
    Counts in Inter semibold at 56 px: the size an older reader needs for a kitchen-table glance.</text>

  <!-- in use -->
  {panel(64 + col + gutter, 776, col, 424, "In use")}
  <rect x="{64 + col + gutter + 40}" y="856" width="300" height="150" rx="10" fill="{INK}"/>
  <g transform="translate({64 + col + gutter + 58} 872) scale(0.2)">{mark(PAPER, 42)}</g>
  <text x="{64 + col + gutter + 132}" y="946" font-family="Inter" font-size="52"
        font-weight="600" fill="{PAPER}">12 / 12</text>
  <text x="{64 + col + gutter + 40}" y="1036" font-family="Inter" font-size="14" fill="{ASH}">
    one-bit screen, 2 cm wide: the mark survives as a solid hump</text>
  <rect x="{64 + col + gutter + 40}" y="1060" width="300" height="46" rx="23" fill="{CLAY}"/>
  <text x="{64 + col + gutter + 62}" y="1090" font-family="Inter" font-size="19"
        fill="{PAPER}">form&#183;band</text>
  <text x="{64 + col + gutter + 40}" y="1140" font-family="Inter" font-size="14" fill="{ASH}">
    band print: one colour, 46 mm wide, legible at a glance</text>

  <!-- tagline -->
  <line x1="64" y1="1240" x2="{W - 64}" y2="1240" stroke="#DED7C9"/>
  <text x="64" y="1390" font-family="Fraunces" font-size="92" fill="{INK}">Good form counts.</text>
  <text x="64" y="1450" font-family="Inter" font-size="22" fill="{ASH}">
    Two readings, one sentence: it tallies repetitions, and it takes form seriously.</text>

  <!-- name rationale -->
  <text x="64" y="1520" font-family="Inter" font-size="15" fill="{ASH}">
    Alternative headlines, if this one is too dry: &ldquo;Every rep, honestly.&rdquo; &nbsp;/&nbsp;
    &ldquo;Form worth keeping.&rdquo;</text>
  <text x="64" y="1560" font-family="Inter" font-size="15" fill="{ASH}">
    Name rejected: Tally (reads as bookkeeping, collides with an accounting brand),
    Steady (collides with a US Medicare brand).</text>
  <line x1="64" y1="1620" x2="{W - 64}" y2="1620" stroke="#DED7C9"/>
  <text x="64" y="1664" font-family="Inter" font-size="13" fill="{ASH}">
    Measured contrast, WCAG AA needs 4.5:1 for text: ink {ratios["ink"]:.1f}, clay {ratios["clay"]:.1f},
    sage {ratios["sage"]:.1f}, ash {ratios["ash"]:.1f} &mdash; all against paper {PAPER}.</text>
  <text x="64" y="1692" font-family="Inter" font-size="13" fill="{ASH}">
    Mark: single continuous stroke, no overlapping cap at the join. Version 2 &mdash; version 1 read
    as a bridge or a stray letter.</text>
</svg>
'''


HTML_ENTS = {
    "&mdash;": "\u2014", "&ndash;": "\u2013", "&middot;": "\u00b7",
    "&nbsp;": "\u00a0", "&ldquo;": "\u201c", "&rdquo;": "\u201d",
    "&amp;": "&amp;",  # keep escaped LAST so nothing above is re-escaped
}


def xmlsafe(text: str) -> str:
    """librsvg rejects HTML entities; SVG is strict XML. Swap them for the characters."""
    for ent, char in HTML_ENTS.items():
        if ent == "&amp;":
            continue
        text = text.replace(ent, char)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + text


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    ratios = {}
    for label, a, b in CHECKS:
        r = ratio(a, b)
        print(f"{label:16s} {r:5.2f}:1")
        ratios[label.split(" on ")[0]] = r
    for label in ("ink", "paper", "clay", "sage", "ash"):
        if label not in ratios:
            ratios[label] = ratio({"ink": INK, "paper": PAPER, "clay": CLAY,
                                   "sage": SAGE, "ash": ASH}[label], PAPER)

    files = {
        "form-mark-ink.svg": svg_mark(INK, PAPER),
        "form-mark-paper.svg": svg_mark(PAPER, INK),
        "form-tile.svg": svg_tile(),
        "form-lockup.svg": svg_lockup(),
        "form-board.svg": board(ratios),
    }
    for fn, content in files.items():
        open(os.path.join(OUT, fn), "w", encoding="utf-8").write(xmlsafe(content))

    subprocess.run(["magick", "-density", "150", os.path.join(OUT, "form-lockup.svg"),
                    os.path.join(OUT, "form-lockup.png")], check=True)
    subprocess.run(["magick", "-density", "150", os.path.join(OUT, "form-tile.svg"),
                    "-resize", "512x", os.path.join(OUT, "form-tile.png")], check=True)
    subprocess.run(["magick", "-density", "110", os.path.join(OUT, "form-board.svg"),
                    os.path.join(OUT, "form-board.png")], check=True)
    subprocess.run(["magick", "-density", "220", os.path.join(OUT, "form-mark-ink.svg"),
                    "-resize", "512x", os.path.join(OUT, "form-mark-512.png")], check=True)
    # One-bit proof at 32 px: the smallest the mark is expected to appear.
    subprocess.run(["magick", os.path.join(OUT, "form-mark-512.png"), "-colorspace", "Gray",
                    "-threshold", "50%", "-resize", "32x32",
                    os.path.join(OUT, "form-mark-32-1bit.png")], check=True)
    for fn in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, fn)
        if fn.endswith((".png", ".svg")):
            print(f"  {fn:26s} {os.path.getsize(p):>8,} B")


if __name__ == "__main__":
    main()

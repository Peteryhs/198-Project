# Tally brand system

Source: `tally-brand.png` in this directory. This file is the machine-readable version — an agent cannot
read the PNG, so every value below is the authority for implementation.

**A clear record of movement.**

An arm-exercise prototype for use at home. Count and pace on the device. Scoring in a separate program.

## Colour
| Name | Hex | Role |
|---|---|---|
| Ink | `#26372C` | every word, mark and line |
| Paper | `#F5F1E8` | primary background |
| Oat | `#D9C9A8` | secondary surface |
| Clay | `#995438` | restrained accent |
| White | `#FFFFFF` | reversed labels, screen surfaces |

**Ink carries every word, mark and line. Colour never carries a score or status.** No red/green pass-fail
colouring, no coloured badges: a wrong rep is said in words, in Ink.

## The mark
Two equal bars, **4 × 7 units**, one vertical at the upper left, one horizontal at the lower right, with a
**visible break at the bend**. Whole pixels, one colour, reversible out in White. No tick, no progress ring,
no implied "correct" angle. Render from those proportions in code; never import an image.

Usable down to 16 px. Same symbol and same name on hardware labels; no miniature tagline there, and clear
functional labels outrank the logo on the device.

## Type
- **Atkinson Hyperlegible**, Regular and Bold. Labels, instructions, summaries. Sentence case for copy,
  uppercase for section labels. Chosen for glyph distinction (`B8`, `O0`, `1Il`, `0123456789`).
- **Spleen** (bitmap) on the hardware's 1-bit 128 × 64 screen: 8 × 16 labels, 12 × 24 counts, no smoothing.
  Hardware only — not for the app.

## Copy rules
Plain language, sentence case, no exclamation marks, no emoji. Anything the classifier estimates is labelled
as an estimate. The set verdict is the headline; per-rep rows are secondary.

Standing lines: **A clear record of movement.** · **Prototype. Real limits.** · Scoring was built and
benchmarked using public physiotherapy recordings. The team's own hardware has not yet been tested with that
scoring.

Proposed identity: drawings and readouts are concepts, no patient results shown.

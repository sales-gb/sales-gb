#!/usr/bin/env python3
"""Render data/contributions.json as an animated SVG heatmap.

GitHub strips <script> and inline CSS from READMEs but does render SVGs via
<img> and plays their CSS keyframes -- so all the motion lives in here.
Standard library only.
"""

import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "contributions.json")
OUT = os.path.join(ROOT, "contrib-heatmap.svg")

# geometry
PAD = 18
LABEL_W = 30          # room for Mon / Wed / Fri
CELL = 12
GAP = 3
PITCH = CELL + GAP
GRID_X = PAD + LABEL_W
TITLE_Y = PAD + 14
MONTH_Y = TITLE_Y + 28
GRID_Y = MONTH_Y + 8

# palette: Tokyo Night ground, GitHub green ramp
BG = "#1a1b26"
EMPTY = "#232433"
RAMP = ["#0e4429", "#006d32", "#26a641", "#39d353"]
INK = "#c0caf5"
DIM = "#565f89"
LABEL = "#7a83a8"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# reveal timing (seconds)
COL_STEP = 0.028
ROW_STEP = 0.05


def color(level):
    return EMPTY if level <= 0 else RAMP[min(level, 4) - 1]


def main():
    static = os.environ.get("STATIC") == "1" or "--static" in sys.argv
    with open(DATA) as fh:
        data = json.load(fh)

    days = data["days"]
    start = date.fromisoformat(days[0]["date"])
    # GitHub's calendar starts on a Sunday; normalise to Sunday=0
    start_sunday = start.toordinal() - ((start.weekday() + 1) % 7)

    cells = []
    for day in days:
        offset = date.fromisoformat(day["date"]).toordinal() - start_sunday
        cells.append((offset // 7, offset % 7, day))

    weeks = max(c[0] for c in cells) + 1
    grid_w = weeks * PITCH - GAP
    grid_h = 7 * PITCH - GAP
    width = GRID_X + grid_w + PAD
    footer_y = GRID_Y + grid_h + 26
    height = footer_y + PAD

    reveal = (weeks - 1) * COL_STEP + 6 * ROW_STEP + 0.55

    late = "" if static else " late"
    out = []
    add = out.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{data["user"]} — {data["total"]} GitHub contributions in the last year">')

    add(f'''<style>
    .t   {{ font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; }}
    .tot {{ fill: {INK}; font-size: 14px; font-weight: 700; }}
    .dim {{ fill: {DIM}; font-size: 11px; }}
    .lbl {{ fill: {LABEL}; font-size: 10px; }}

    /* opacity:1 is the base state — no animation support means a complete,
       static graph rather than a blank card. */
    .c {{ opacity: 1; transform-box: fill-box; transform-origin: center;
         animation: pop .5s ease-out both; }}
    .hot {{ animation: pop .5s ease-out both, flash .8s ease-out both; }}
    @keyframes pop {{
      from {{ opacity: 0; transform: scale(.3); }}
      60%  {{ opacity: 1; transform: scale(1.1); }}
      to   {{ opacity: 1; transform: scale(1); }}
    }}
    @keyframes flash {{
      0%, 40% {{ filter: brightness(2.2); }}
      100%    {{ filter: brightness(1); }}
    }}
    .late {{ opacity: 1; animation: fade .5s ease-out both; animation-delay: {reveal:.2f}s; }}
    @keyframes fade {{ from {{ opacity: 0 }} to {{ opacity: 1 }} }}

    @media (prefers-reduced-motion: reduce) {{
      .c, .late {{ animation: none; opacity: 1; transform: none; }}
    }}
  </style>''')

    add(f'<rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="{BG}"/>')

    # header
    add(f'<text class="t tot{late}" x="{PAD}" y="{TITLE_Y}">{data["total"]:,} contributions '
        f'in the last year</text>')
    span = (f'{MONTHS[start.month - 1]} {start.year} — '
            f'{MONTHS[date.fromisoformat(days[-1]["date"]).month - 1]} '
            f'{date.fromisoformat(days[-1]["date"]).year}')
    add(f'<text class="t dim{late}" x="{width - PAD}" y="{TITLE_Y}" text-anchor="end">'
        f'{data["user"]} · {span}</text>')

    # month labels: mark a column when its week opens a new month
    prev = None
    for week in range(weeks):
        first = date.fromordinal(start_sunday + week * 7)
        if first.month != prev and week < weeks - 2:
            add(f'<text class="t lbl{late}" x="{GRID_X + week * PITCH}" y="{MONTH_Y}">'
                f'{MONTHS[first.month - 1]}</text>')
            prev = first.month

    # weekday labels
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        add(f'<text class="t lbl{late}" x="{PAD}" y="{GRID_Y + row * PITCH + CELL - 2}">{name}</text>')

    # the grid
    for week, row, day in cells:
        delay = week * COL_STEP + row * ROW_STEP
        cls = "" if static else ("c hot" if day["level"] >= 3 else "c")
        add(f'<rect class="{cls}" x="{GRID_X + week * PITCH}" y="{GRID_Y + row * PITCH}" '
            f'width="{CELL}" height="{CELL}" rx="2.5" fill="{color(day["level"])}" '
            f'style="animation-delay:{delay:.3f}s"><title>{day["count"]} on {day["date"]}</title></rect>')

    # footer: streaks left, legend right
    best = data["best_day"]
    add(f'<text class="t dim{late}" x="{PAD}" y="{footer_y}">'
        f'current streak {data["current_streak"]}d · longest {data["longest_streak"]}d · '
        f'{data["active_days"]} active days · best {best["count"]} on {best["date"]}</text>')

    legend_x = width - PAD - 5 * PITCH - 34
    add(f'<text class="t lbl{late}" x="{legend_x - 6}" y="{footer_y}" text-anchor="end">Less</text>')
    for i, fill in enumerate([EMPTY] + RAMP):
        add(f'<rect class="{late.strip() or "x"}" x="{legend_x + i * PITCH}" y="{footer_y - 9}" '
            f'width="{CELL}" height="{CELL}" rx="2.5" fill="{fill}"/>')
    add(f'<text class="t lbl{late}" x="{legend_x + 5 * PITCH + 1}" y="{footer_y}">More</text>')

    add("</svg>")

    with open(OUT, "w") as fh:
        fh.write("\n".join(out) + "\n")

    print(f"{weeks} weeks · {width}x{height} -> contrib-heatmap.svg")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Scrape the public contribution calendar into data/contributions.json.

No token, no GraphQL: GitHub serves the calendar as public HTML at
https://github.com/users/<user>/contributions -- the same fragment the profile
page itself renders. Standard library only, so CI needs no pip install.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

USER = os.environ.get("GH_USER") or "sales-gb"
URL = f"https://github.com/users/{USER}/contributions"
OUT = os.path.join(os.path.dirname(__file__), os.pardir, "data", "contributions.json")

CELL_RE = re.compile(r"<td[^>]*\bclass=\"ContributionCalendar-day\"[^>]*>")
ATTR_RE = re.compile(r"([a-zA-Z-]+)=\"([^\"]*)\"")
TIP_RE = re.compile(r"<tool-tip[^>]*\bfor=\"([^\"]+)\"[^>]*>(.*?)</tool-tip>", re.S)
COUNT_RE = re.compile(r"^([\d,]+)\s+contribution")


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "profile-art/1.0 (+https://github.com/%s)" % USER,
        "Accept": "text/html",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def parse(html):
    """-> list of {date, count, level}, ordered oldest first."""
    counts = {}
    for cell_id, text in TIP_RE.findall(html):
        text = re.sub(r"<[^>]+>", "", text).strip()
        m = COUNT_RE.match(text)
        counts[cell_id] = int(m.group(1).replace(",", "")) if m else 0

    days = []
    for m in CELL_RE.finditer(html):
        attrs = dict(ATTR_RE.findall(m.group(0)))
        day = attrs.get("data-date")
        if not day:
            continue
        days.append({
            "date": day,
            "count": counts.get(attrs.get("id", ""), 0),
            "level": int(attrs.get("data-level") or 0),
        })

    days.sort(key=lambda d: d["date"])
    return days


def streaks(days):
    """Current and longest run of consecutive days with >0 contributions.

    Today counts as a grace day: an empty today does not break the streak,
    which is how GitHub itself presents it.
    """
    today = date.today().isoformat()
    current = 0
    for d in reversed(days):
        if d["count"] > 0:
            current += 1
        elif d["date"] == today:
            continue
        else:
            break

    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)

    return current, longest


def main():
    try:
        html = fetch(URL)
    except urllib.error.URLError as err:
        sys.exit(f"could not reach {URL}: {err}")

    days = parse(html)
    if len(days) < 300:
        sys.exit(f"parsed only {len(days)} days -- GitHub markup probably changed")

    current, longest = streaks(days)
    best = max(days, key=lambda d: d["count"])

    payload = {
        "user": USER,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "range": {"from": days[0]["date"], "to": days[-1]["date"]},
        "total": sum(d["count"] for d in days),
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best["date"], "count": best["count"]},
        "active_days": sum(1 for d in days if d["count"] > 0),
        "days": days,
    }

    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(payload, fh, indent=1)
        fh.write("\n")

    print(f"{len(days)} days · {payload['total']} contributions · "
          f"streak {current} (longest {longest}) -> data/contributions.json")


if __name__ == "__main__":
    main()

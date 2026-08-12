#!/usr/bin/env python3
"""Generate static GitHub stats SVGs for the profile README.

The workflow supplies GITHUB_TOKEN, so no long-lived PAT is required.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import xml.sax.saxutils as saxutils
from collections import Counter
from pathlib import Path

OWNER = "poizdev"
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"

BG = "#0d1117"
CARD = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#58a6ff"
ACCENTS = ["#58a6ff", "#3fb950", "#bc8cff", "#f0883e", "#f778ba", "#79c0ff"]


def api(path: str) -> dict | list:
    req = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "poizdev-static-github-stats",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def esc(value: object) -> str:
    return saxutils.escape(str(value))


def svg(width: int, height: int, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" rx="10" fill="{BG}"/>
<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="9.5" fill="none" stroke="{BORDER}"/>
<style>text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}</style>
{body}
</svg>'''


def text(x: int, y: int, value: object, size: int = 14, color: str = TEXT, weight: int = 400, anchor: str = "start") -> str:
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>'


def get_data() -> tuple[dict, list[dict], dict]:
    user = api(f"/users/{OWNER}")
    repos: list[dict] = []
    page = 1
    while page <= 5:
        batch = api(f"/users/{OWNER}/repos?per_page=100&page={page}&type=owner&sort=updated")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    # Search counts are useful, but a transient search failure should not make
    # the entire profile generation fail.
    counts = {"commits": 0, "prs": 0, "issues": 0}
    for key, query in {
        "commits": f"author:{OWNER}",
        "prs": f"author:{OWNER} type:pr",
        "issues": f"author:{OWNER} type:issue",
    }.items():
        try:
            result = api("/search/commits?" + urllib.parse.urlencode({"q": query, "per_page": 1})) if key == "commits" else api("/search/issues?" + urllib.parse.urlencode({"q": query, "per_page": 1}))
            counts[key] = int(result.get("total_count", 0))
        except Exception:
            pass

    languages = Counter()
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            data = api(f"/repos/{OWNER}/{repo['name']}/languages")
            languages.update({name: int(size) for name, size in data.items()})
        except Exception:
            continue
        time.sleep(0.03)

    return user, repos, {**counts, "languages": languages}


def make_stats(user: dict, repos: list[dict], counts: dict) -> str:
    own_repos = [r for r in repos if not r.get("fork")]
    stars = sum(int(r.get("stargazers_count", 0)) for r in own_repos)
    items = [
        ("Repositories", len(own_repos)),
        ("Followers", int(user.get("followers", 0))),
        ("Stars", stars),
        ("Commits", counts["commits"]),
        ("Pull Requests", counts["prs"]),
        ("Issues", counts["issues"]),
    ]

    body = [text(28, 35, "GitHub Stats", 18, TEXT, 700)]
    body.append(text(28, 57, f"@{OWNER}", 12, MUTED, 400))
    positions = [(28, 92), (183, 92), (338, 92), (28, 151), (183, 151), (338, 151)]
    for (label, value), (x, y) in zip(items, positions):
        body.append(text(x, y, f"{value:,}", 22, ACCENT, 700))
        body.append(text(x, y + 20, label, 11, MUTED, 400))
    return svg(495, 195, "\n".join(body))


def make_languages(counts: dict) -> str:
    languages: Counter = counts["languages"]
    top = languages.most_common(6)
    total = sum(languages.values()) or 1

    body = [text(28, 35, "Top Languages", 18, TEXT, 700)]
    body.append(text(28, 57, "Across non-fork repositories", 12, MUTED, 400))

    y = 82
    bar_x, bar_w = 28, 439
    for index, (name, size) in enumerate(top):
        pct = size / total * 100
        width = max(2, bar_w * size / total)
        color = ACCENTS[index % len(ACCENTS)]
        body.append(f'<rect x="{bar_x}" y="{y}" width="{bar_w}" height="7" rx="3.5" fill="{BORDER}"/>')
        body.append(f'<rect x="{bar_x}" y="{y}" width="{width:.2f}" height="7" rx="3.5" fill="{color}"/>')
        body.append(text(28, y + 27, name, 12, TEXT, 600))
        body.append(text(467, y + 27, f"{pct:.1f}%", 11, MUTED, 500, "end"))
        y += 42

    if not top:
        body.append(text(28, 100, "No language data available yet.", 13, MUTED))

    return svg(495, 195, "\n".join(body))


def main() -> None:
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is required")
    ASSETS.mkdir(parents=True, exist_ok=True)
    user, repos, counts = get_data()
    (ASSETS / "github-stats.svg").write_text(make_stats(user, repos, counts), encoding="utf-8")
    (ASSETS / "github-languages.svg").write_text(make_languages(counts), encoding="utf-8")
    print("Generated assets/github-stats.svg and assets/github-languages.svg")


if __name__ == "__main__":
    main()

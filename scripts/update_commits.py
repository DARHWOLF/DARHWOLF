#!/usr/bin/env python3
"""Generate a profile README card from a user's recent public GitHub pushes.

Uses only the standard library. Intended to run via GitHub Actions on a schedule.
GitHub's public events API exposes at most 300 events from the previous 30 days.
"""

from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

USERNAME = os.environ.get("GITHUB_USERNAME", "DARHWOLF")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_FILE = REPO_ROOT / "assets" / "my-commits.svg"
README_FILE = REPO_ROOT / "README.md"
MAX_REPOS = 4
DAYS = 30
START_MARKER = "<!-- MY_COMMITS:START -->"
END_MARKER = "<!-- MY_COMMITS:END -->"


def api_get(path: str):
    """Get JSON from GitHub, failing safely rather than replacing data with blanks."""
    url = f"https://api.github.com/{path.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-my-commits-action",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=25) as response:
            return json.load(response)
    except (HTTPError, URLError, ValueError) as err:
        raise RuntimeError(f"GitHub API request failed: {path}: {err}") from err


def fetch_push_events(now: datetime):
    cutoff = now - timedelta(days=DAYS)
    events = []
    for page in range(1, 4):
        payload = api_get(f"users/{quote(USERNAME)}/events/public?per_page=100&page={page}")
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected GitHub public events response; keeping previous card")
        for event in payload:
            try:
                timestamp = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            except (KeyError, ValueError, TypeError):
                continue
            if timestamp < cutoff:
                continue
            repo = event.get("repo", {}).get("name", "")
            actor = event.get("actor", {}).get("login", "")
            ref = event.get("payload", {}).get("ref", "") or ""
            if (
                event.get("type") == "PushEvent"
                and actor.lower() == USERNAME.lower()
                and repo.lower() != f"{USERNAME}/{USERNAME}".lower()
                and re.fullmatch(r"[\w.-]+/[\w.-]+", repo)
                and not ref.startswith("refs/tags/")
            ):
                events.append((repo, timestamp, event.get("payload", {})))
        if len(payload) < 100:
            break
    return events


def get_recent_repos(events):
    grouped = defaultdict(list)
    for repo, timestamp, payload in events:
        grouped[repo].append((timestamp, payload))

    rows = []
    for repo, pushes in grouped.items():
        pushes.sort(key=lambda record: record[0], reverse=True)
        latest_time, latest_payload = pushes[0]
        ref = latest_payload.get("ref", "") or ""
        branch = ref.removeprefix("refs/heads/") if ref.startswith("refs/heads/") else ""
        rows.append({
            "repo": repo,
            "last_push": latest_time,
            "pushes": len(pushes),
            "branch": branch,
            "payload": latest_payload,
            "message": "",
        })
    rows.sort(key=lambda row: (-row["last_push"].timestamp(), row["repo"].lower()))
    return rows[:MAX_REPOS]


def add_commit_messages(rows):
    for row in rows:
        payload = row.pop("payload")
        commits = payload.get("commits") or []
        if commits and isinstance(commits[-1], dict):
            row["message"] = commits[-1].get("message", "") or ""
        if not row["message"]:
            head = payload.get("head") or ""
            if re.fullmatch(r"[0-9a-fA-F]{40}", head):
                try:
                    commit_data = api_get(f"repos/{row['repo']}/commits/{head}")
                    row["message"] = commit_data.get("commit", {}).get("message", "")
                except RuntimeError as err:
                    print(f"Note: no commit subject for {row['repo']}: {err}")
        row["message"] = (row["message"] or "Recent push").splitlines()[0].strip()
        if not row["message"]:
            row["message"] = "Recent push"
    return rows


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def cut(text: str, width: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def svg_text(x, y, text, *, size=16, color="#d6e6ff", weight=400, extra=""):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" {extra}>{esc(text)}</text>')


def render_svg(rows, initial=False):
    """Render a dependency-free, GitHub-safe SVG (no scripts/external assets)."""
    height = 505 if rows else 245
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" '
        f'viewBox="0 0 960 {height}" role="img" '
        'aria-label="My commits: recent public GitHub repositories">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop stop-color="#0a1628"/><stop offset="1" stop-color="#152d4c"/>'
        '</linearGradient><linearGradient id="accent" x1="0" x2="1">'
        '<stop stop-color="#50d6e9"/><stop offset="1" stop-color="#6f96ff"/>'
        '</linearGradient></defs>',
        f'<rect width="960" height="{height}" rx="24" fill="url(#bg)"/>',
        f'<rect x="1" y="1" width="958" height="{height-2}" rx="23" '
        'fill="none" stroke="#385474" stroke-opacity="0.7"/>',
        '<rect x="32" y="37" width="7" height="39" rx="3.5" fill="url(#accent)"/>',
        svg_text(57, 67, "My commits", size=34, color="#f2f8ff", weight=700),
        '<rect x="749" y="39" width="178" height="35" rx="17.5" '
        'fill="#243e5c" stroke="#345778"/>',
        '<circle cx="768" cy="56.5" r="5" fill="#4adeb9"/>',
        svg_text(784, 62, "AUTO-UPDATED", size=14, color="#b8d6f9", weight=700),
        svg_text(34, 105, "Recent pushes across public repositories · last 30 days", size=16, color="#a8bdd5"),
    ]
    if not rows:
        note = ("Run the GitHub Action once to load recent activity" if initial
                else "No public pushes found in the last 30 days")
        parts.extend([
            '<rect x="32" y="133" width="896" height="78" rx="16" '
            'fill="#1b3553" stroke="#385474"/>',
            svg_text(58, 181, note, size=20, color="#c9dbf3", weight=500),
        ])
    else:
        for i, row in enumerate(rows):
            x = 32 + (i % 2) * 457
            y = 130 + (i // 2) * 180
            parts.extend([
                f'<rect x="{x}" y="{y}" width="439" height="162" rx="16" '
                'fill="#1c3655" stroke="#385b80"/>',
                f'<rect x="{x}" y="{y+18}" width="4" height="44" rx="2" fill="url(#accent)"/>',
                svg_text(x + 22, y + 37, cut(row["repo"], 34),
                         size=21, color="#eef6ff", weight=700),
                svg_text(x + 22, y + 67, cut(row["message"], 50),
                         size=15, color="#acc5e0"),
                f'<line x1="{x+22}" y1="{y+91}" x2="{x+417}" y2="{y+91}" '
                'stroke="#385779" stroke-width="1"/>',
                svg_text(x + 22, y + 116,
                         f'Last push · {row["last_push"].strftime("%d %b %Y")}',
                         size=14, color="#b7cee6"),
                svg_text(x + 22, y + 142,
                         f'Branch: {cut(row["branch"] or "unknown", 33)}',
                         size=13, color="#8fb1d0"),
                f'<rect x="{x+327}" y="{y+109}" width="89" height="29" rx="14.5" '
                'fill="#284b69"/>',
                svg_text(x + 371, y + 128,
                         f'{row["pushes"]} push' + ("" if row["pushes"] == 1 else "es"),
                         size=13, color="#79e6c9", weight=600,
                         extra='text-anchor="middle"'),
            ])
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def markdown_section(rows):
    blocks = [
        START_MARKER,
        "## My commits",
        "",
        "![Recent public GitHub pushes by repository](./assets/my-commits.svg)",
        "",
    ]
    if rows:
        links = []
        for row in rows:
            repo = row["repo"]
            links.append(f'[{repo}](https://github.com/{quote(repo, safe="/")})')
        blocks += ["**Recent repositories:** " + " · ".join(links), ""]
    blocks += [
        "<sub>Public push activity from the past 30 days; refreshed automatically every six hours. "
        "Private work and unpushed local commits aren't included.</sub>",
        END_MARKER,
    ]
    return "\n".join(blocks)


def update_readme(rows):
    existing = README_FILE.read_text(encoding="utf-8")
    start = existing.find(START_MARKER)
    end = existing.find(END_MARKER)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError(f"Missing {START_MARKER} / {END_MARKER} markers in README.md")
    end += len(END_MARKER)
    replacement = markdown_section(rows)
    updated = existing[:start] + replacement + existing[end:]
    if updated != existing:
        README_FILE.write_text(updated, encoding="utf-8")


def main():
    now = datetime.now(timezone.utc)
    events = fetch_push_events(now)
    rows = add_commit_messages(get_recent_repos(events))
    SVG_FILE.parent.mkdir(exist_ok=True, parents=True)
    output = render_svg(rows)
    if not SVG_FILE.exists() or SVG_FILE.read_text(encoding="utf-8") != output:
        SVG_FILE.write_text(output, encoding="utf-8")
    update_readme(rows)
    print(f"Updated My commits with {len(rows)} repos and {len(events)} public push events")


if __name__ == "__main__":
    main()

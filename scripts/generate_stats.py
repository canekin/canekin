#!/usr/bin/env python3
"""Generate profile SVGs (stats, languages, contributions) and patch README markers.

Uses GitHub REST + GraphQL. PROFILE_TOKEN / GH_TOKEN with repo + read:user
enables private repo counts and private contribution days.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "canekin")
TOKEN = (
    os.environ.get("PROFILE_TOKEN")
    or os.environ.get("GH_TOKEN")
    or os.environ.get("GITHUB_TOKEN")
    or ""
)
ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
OUT_DIR = ROOT / "generated"
STATS_SVG = OUT_DIR / "stats.svg"
LANGS_SVG = OUT_DIR / "languages.svg"
CONTRIB_SVG = OUT_DIR / "contributions.svg"

# Shared card height so stats.svg and languages.svg render symmetrically
# side-by-side in the README, regardless of row count.
CARD_HEIGHT = 320
CARD_WIDTH = 520

LEVEL_COLORS = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#0e4429",
    "SECOND_QUARTILE": "#006d32",
    "THIRD_QUARTILE": "#26a641",
    "FOURTH_QUARTILE": "#39d353",
}
FALLBACK_GREENS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def humanize_delta(iso_ts: str | None) -> str:
    """Turn an ISO8601 UTC timestamp into a short relative label like '2d ago'."""
    if not iso_ts:
        return "n/a"
    try:
        dt = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return "n/a"
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 0:
        secs = 0
    if secs < 3600:
        return f"{max(1, int(secs // 60))}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    if secs < 86400 * 30:
        return f"{int(secs // 86400)}d ago"
    return dt.strftime("%Y-%m-%d")


def api_get(url: str) -> dict | list:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USERNAME}-profile-readme",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def graphql(query: str, variables: dict | None = None) -> dict:
    if not TOKEN:
        raise RuntimeError("GraphQL requires PROFILE_TOKEN / GITHUB_TOKEN")
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USERNAME}-profile-readme",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"]))
    return payload["data"]


def fetch_user() -> dict:
    return api_get(f"https://api.github.com/users/{USERNAME}")  # type: ignore[return-value]


def fetch_owned_repos() -> tuple[list[dict], bool]:
    repos: list[dict] = []
    page = 1
    used_auth = False
    while True:
        if TOKEN:
            url = (
                "https://api.github.com/user/repos"
                f"?per_page=100&page={page}&affiliation=owner&sort=updated"
            )
            try:
                batch = api_get(url)
                used_auth = True
            except urllib.error.HTTPError:
                url = (
                    f"https://api.github.com/users/{USERNAME}/repos"
                    f"?per_page=100&page={page}&type=owner"
                )
                batch = api_get(url)
                used_auth = False
        else:
            url = (
                f"https://api.github.com/users/{USERNAME}/repos"
                f"?per_page=100&page={page}&type=owner"
            )
            batch = api_get(url)
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    seen: set[int] = set()
    owned: list[dict] = []
    for r in repos:
        rid = r.get("id")
        if rid in seen or r.get("fork"):
            continue
        seen.add(rid)
        owned.append(r)
    return owned, used_auth


def compute_stats(user: dict, repos: list[dict], private_known: bool) -> dict:
    public = sum(1 for r in repos if not r.get("private"))
    private = sum(1 for r in repos if r.get("private"))
    if not private_known:
        public = max(public, int(user.get("public_repos") or 0))
        private = 0
    stars = sum(int(r.get("stargazers_count") or 0) for r in repos)

    last_pushed = max(
        (r.get("pushed_at") for r in repos if r.get("pushed_at")),
        default=None,
    )

    return {
        "public_repos": public,
        "private_repos": private,
        "private_known": private_known,
        "total_repos": public + private,
        "stars": stars,
        "followers": int(user.get("followers") or 0),
        "following": int(user.get("following") or 0),
        "last_commit": humanize_delta(last_pushed),
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def fetch_languages(repos: list[dict]) -> list[tuple[str, int]]:
    totals: dict[str, int] = defaultdict(int)
    for r in repos:
        if r.get("fork") or r.get("archived"):
            continue
        try:
            langs = api_get(r["languages_url"])
        except Exception:  # noqa: BLE001
            continue
        if isinstance(langs, dict):
            for name, bytes_count in langs.items():
                totals[name] += int(bytes_count)
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    return ranked[:8]


def fetch_contribution_calendar() -> dict:
    """Rolling ~1 year ending today (GitHub default window), incl. private when token allows."""
    to_dt = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(days=365)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          restrictedContributionsCount
          hasAnyRestrictedContributions
          contributionCalendar {
            totalContributions
            colors
            weeks {
              firstDay
              contributionDays {
                date
                contributionCount
                contributionLevel
                color
              }
            }
          }
        }
      }
    }
    """
    data = graphql(
        query,
        {
            "login": USERNAME,
            "from": from_dt.strftime("%Y-%m-%dT00:00:00Z"),
            "to": to_dt.strftime("%Y-%m-%dT23:59:59Z"),
        },
    )
    return data["user"]["contributionsCollection"]


def find_peak_month(weeks: list[dict]) -> str:
    """Label the densest calendar month inside the window."""
    by_month: dict[str, int] = defaultdict(int)
    for week in weeks:
        for day in week.get("contributionDays", []):
            date = day["date"]
            key = date[:7]  # YYYY-MM
            by_month[key] += int(day.get("contributionCount") or 0)
    if not by_month:
        return "n/a"
    best = max(by_month.items(), key=lambda x: x[1])[0]
    dt = datetime.strptime(best + "-01", "%Y-%m-%d")
    return dt.strftime("%b %Y")


def render_stats_svg(stats: dict) -> str:
    priv = str(stats["private_repos"]) if stats["private_known"] else "?"
    total = (
        str(stats["total_repos"])
        if stats["private_known"]
        else f"{stats['public_repos']}+"
    )
    rows = [
        ("public repos", str(stats["public_repos"]), "#22c55e"),
        ("private repos", priv, "#a3e635"),
        ("total repos", total, "#ededed"),
        ("stars", str(stats["stars"]), "#fbbf24"),
        ("followers", str(stats["followers"]), "#60a5fa"),
        ("last commit", stats["last_commit"], "#f472b6"),
    ]
    lines = []
    y = 110
    for label, value, color in rows:
        lines.append(
            f'<text x="28" y="{y}" fill="#9ca3af" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="14">'
            f'<tspan fill="#22c55e">»</tspan> {esc(label)}</text>'
            f'<text x="220" y="{y}" fill="{color}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="14" font-weight="700">{esc(value)}</text>'
        )
        y += 28
    hint = (
        "keep going!"
        if stats["private_known"]
        else "add PROFILE_TOKEN secret for private counts"
    )
    height = CARD_HEIGHT
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{height}" viewBox="0 0 {CARD_WIDTH} {height}" role="img" aria-label="GitHub stats for {esc(USERNAME)}">
  <title>{esc(USERNAME)} GitHub stats</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a0a0a"/><stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1f2937" stroke-width="1" opacity="0.45"/>
    </pattern>
  </defs>
  <rect width="{CARD_WIDTH}" height="{height}" rx="12" fill="url(#bg)"/>
  <rect width="{CARD_WIDTH}" height="{height}" rx="12" fill="url(#grid)"/>
  <rect x="1" y="1" width="{CARD_WIDTH - 2}" height="{height - 2}" rx="11" fill="none" stroke="#22c55e" stroke-opacity="0.35"/>
  <circle cx="28" cy="28" r="6" fill="#FF605C"/><circle cx="48" cy="28" r="6" fill="#FFBD44"/><circle cx="68" cy="28" r="6" fill="#00CA4E"/>
  <text x="92" y="33" fill="#9ca3af" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12">{esc(USERNAME)}@github:~/stats</text>
  <text x="28" y="58" fill="#22c55e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">{esc(USERNAME)}@ekin:~$ ./gh_stats</text>
  {"".join(lines)}
  <text x="28" y="{height - 20}" fill="#6b7280" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">updated {esc(stats["updated"])} · {esc(hint)}</text>
</svg>
'''


def render_languages_svg(langs: list[tuple[str, int]]) -> str:
    total = sum(v for _, v in langs) or 1
    palette = ["#22c55e", "#60a5fa", "#fbbf24", "#f472b6", "#a78bfa", "#34d399", "#fb7185", "#38bdf8"]
    bar_x, bar_y, bar_w, bar_h = 28, 70, 464, 14
    parts = []
    x = bar_x
    for i, (name, value) in enumerate(langs):
        w = max(2, round(bar_w * (value / total)))
        if i == len(langs) - 1:
            w = bar_x + bar_w - x
        parts.append(f'<rect x="{x}" y="{bar_y}" width="{w}" height="{bar_h}" fill="{palette[i % len(palette)]}"/>')
        x += w

    height = CARD_HEIGHT
    # Rows fill the space between the bar and the footer line, spaced evenly
    # so 1 language and 8 languages both look intentional inside the fixed card.
    row_start, row_end = 100, height - 40
    row_step = max(20, (row_end - row_start) // max(1, len(langs)))

    rows = []
    y = row_start
    for i, (name, value) in enumerate(langs):
        pct = value * 100 / total
        col = palette[i % len(palette)]
        rows.append(
            f'<circle cx="34" cy="{y - 4}" r="5" fill="{col}"/>'
            f'<text x="48" y="{y}" fill="#ededed" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">{esc(name)}</text>'
            f'<text x="460" y="{y}" fill="#9ca3af" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13" text-anchor="end">{pct:.1f}%</text>'
        )
        y += row_step

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{height}" viewBox="0 0 {CARD_WIDTH} {height}" role="img" aria-label="Top languages for {esc(USERNAME)}">
  <title>{esc(USERNAME)} top languages</title>
  <defs>
    <linearGradient id="bg2" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a0a0a"/><stop offset="100%" stop-color="#111827"/>
    </linearGradient>
  </defs>
  <rect width="{CARD_WIDTH}" height="{height}" rx="12" fill="url(#bg2)"/>
  <rect x="1" y="1" width="{CARD_WIDTH - 2}" height="{height - 2}" rx="11" fill="none" stroke="#22c55e" stroke-opacity="0.35"/>
  <circle cx="28" cy="28" r="6" fill="#FF605C"/><circle cx="48" cy="28" r="6" fill="#FFBD44"/><circle cx="68" cy="28" r="6" fill="#00CA4E"/>
  <text x="92" y="33" fill="#9ca3af" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12">{esc(USERNAME)}@github:~/languages</text>
  <text x="28" y="58" fill="#22c55e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">{esc(USERNAME)}@ekin:~$ top_langs</text>
  {"".join(parts)}
  {"".join(rows)}
  <text x="28" y="{height - 20}" fill="#6b7280" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">detected via GitHub API · top {len(langs)} by bytes</text>
</svg>
'''


def render_contributions_svg(collection: dict) -> str:
    cal = collection["contributionCalendar"]
    weeks = cal.get("weeks") or []
    total = int(cal.get("totalContributions") or 0)
    restricted = int(collection.get("restrictedContributionsCount") or 0)
    peak = find_peak_month(weeks)
    cell, gap = 11, 3
    left, top = 36, 48
    width = left + len(weeks) * (cell + gap) + 24
    height = top + 7 * (cell + gap) + 48

    # month labels
    month_labels = []
    prev_month = None
    for i, week in enumerate(weeks):
        days = week.get("contributionDays") or []
        if not days:
            continue
        d0 = datetime.strptime(days[0]["date"], "%Y-%m-%d")
        if d0.month != prev_month and d0.day <= 7:
            month_labels.append(
                f'<text x="{left + i * (cell + gap)}" y="34" fill="#8b949e" '
                f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">{esc(d0.strftime("%b"))}</text>'
            )
            prev_month = d0.month

    day_labels = []
    for idx, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        day_labels.append(
            f'<text x="8" y="{top + idx * (cell + gap) + 9}" fill="#8b949e" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10">{label}</text>'
        )

    cells = []
    for wi, week in enumerate(weeks):
        for day in week.get("contributionDays") or []:
            d = datetime.strptime(day["date"], "%Y-%m-%d")
            # GitHub weeks start on Sunday → weekday() Mon=0 … Sun=6 → map Sun=0
            dow = (d.weekday() + 1) % 7
            level = day.get("contributionLevel") or "NONE"
            color = day.get("color") or LEVEL_COLORS.get(level, FALLBACK_GREENS[0])
            count = int(day.get("contributionCount") or 0)
            x = left + wi * (cell + gap)
            y = top + dow * (cell + gap)
            cells.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" ry="2" fill="{color}">'
                f'<title>{esc(day["date"])}: {count} contribution{"s" if count != 1 else ""}</title></rect>'
            )

    legend_x = width - 140
    legend = [
        f'<text x="{legend_x}" y="{height - 14}" fill="#8b949e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10">Less</text>'
    ]
    for i, c in enumerate(FALLBACK_GREENS):
        legend.append(
            f'<rect x="{legend_x + 34 + i * (cell + gap)}" y="{height - 24}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>'
        )
    legend.append(
        f'<text x="{legend_x + 34 + 5 * (cell + gap) + 4}" y="{height - 14}" fill="#8b949e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10">More</text>'
    )

    private_note = (
        f" · includes private (+{restricted} restricted)"
        if restricted or collection.get("hasAnyRestrictedContributions")
        else " · public + private (if enabled in profile settings)"
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Contribution calendar for {esc(USERNAME)}">
  <title>{total} contributions in the last year</title>
  <rect width="{width}" height="{height}" rx="12" fill="#0a0a0a"/>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="11" fill="none" stroke="#21262d"/>
  <text x="16" y="22" fill="#ededed" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13" font-weight="700">{total} contributions in the last year</text>
  <text x="{width - 16}" y="22" fill="#22c55e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11" text-anchor="end">peak {esc(peak)}{esc(private_note)}</text>
  {"".join(month_labels)}
  {"".join(day_labels)}
  {"".join(cells)}
  {"".join(legend)}
</svg>
'''


def patch_readme(stats: dict, total_contrib: int | None) -> None:
    if not README.exists():
        return
    content = README.read_text(encoding="utf-8")
    priv_display = (
        str(stats["private_repos"])
        if stats["private_known"]
        else "_requires PROFILE_TOKEN_"
    )
    total = (
        str(stats["total_repos"])
        if stats["private_known"]
        else f"{stats['public_repos']}+"
    )
    block = f"""<!-- START_REPO_STATS -->
| Metric | Count |
| :--- | ---: |
| Public repos | **{stats['public_repos']}** |
| Private repos | **{priv_display}** |
| Total (owned, non-fork) | **{total}** |
| Stars | **{stats['stars']}** |
| Followers | **{stats['followers']}** |
| Last commit | **{stats['last_commit']}** |

<sub>Auto-refreshed by GitHub Actions · last run: {stats['updated']}</sub>
<!-- END_REPO_STATS -->"""

    if "<!-- START_REPO_STATS -->" in content and "<!-- END_REPO_STATS -->" in content:
        content = re.sub(
            r"<!-- START_REPO_STATS -->.*?<!-- END_REPO_STATS -->",
            block,
            content,
            count=1,
            flags=re.S,
        )

    line = (
        f"<!-- START_REPO_LINE -->`{stats['public_repos']} public` · "
        f"`{priv_display if stats['private_known'] else '?'} private` · "
        f"`{total} total`"
    )
    if total_contrib is not None:
        line += f" · `{total_contrib} contribs/yr`"
    line += "<!-- END_REPO_LINE -->"

    if "<!-- START_REPO_LINE -->" in content and "<!-- END_REPO_LINE -->" in content:
        content = re.sub(
            r"<!-- START_REPO_LINE -->.*?<!-- END_REPO_LINE -->",
            line,
            content,
            count=1,
            flags=re.S,
        )

    README.write_text(content, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    user = fetch_user()
    repos, used_auth = fetch_owned_repos()
    stats = compute_stats(user, repos, used_auth)
    STATS_SVG.write_text(render_stats_svg(stats), encoding="utf-8")

    langs = fetch_languages(repos)
    if not langs:
        langs = [("Python", 1)]
    LANGS_SVG.write_text(render_languages_svg(langs), encoding="utf-8")

    total_contrib = None
    if TOKEN:
        try:
            collection = fetch_contribution_calendar()
            CONTRIB_SVG.write_text(render_contributions_svg(collection), encoding="utf-8")
            total_contrib = int(
                collection["contributionCalendar"].get("totalContributions") or 0
            )
            print(
                "contributions",
                total_contrib,
                "restricted",
                collection.get("restrictedContributionsCount"),
            )
        except Exception as exc:  # noqa: BLE001
            print("contribution_fetch_failed", exc)
            if not CONTRIB_SVG.exists():
                CONTRIB_SVG.write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="120">'
                    '<rect width="720" height="120" fill="#0a0a0a"/>'
                    '<text x="24" y="64" fill="#22c55e" font-family="monospace" font-size="14">'
                    "contribution calendar unavailable — check PROFILE_TOKEN</text></svg>",
                    encoding="utf-8",
                )

    patch_readme(stats, total_contrib)
    print(json.dumps({**stats, "languages": [n for n, _ in langs]}, indent=2))


if __name__ == "__main__":
    main()
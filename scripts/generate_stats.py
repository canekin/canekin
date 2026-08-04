#!/usr/bin/env python3
"""Generate terminal-styled SVG stats + patch README markers.

Uses GitHub REST API. With a PAT that has `repo` scope, private repos are counted.
Without it, private count falls back to unknown.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_user() -> dict:
    return api_get(f"https://api.github.com/users/{USERNAME}")  # type: ignore[return-value]


def fetch_owned_repos() -> tuple[list[dict], bool]:
    """Return (repos, used_authenticated_endpoint)."""
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
        if rid in seen:
            continue
        seen.add(rid)
        if r.get("fork"):
            continue
        owned.append(r)
    return owned, used_auth


def compute_stats(user: dict, repos: list[dict], private_known: bool) -> dict:
    public = sum(1 for r in repos if not r.get("private"))
    private = sum(1 for r in repos if r.get("private"))

    if not private_known:
        # Public API may omit private repos entirely; trust profile public_repos as floor.
        public = max(public, int(user.get("public_repos") or 0))
        private = 0

    stars = sum(int(r.get("stargazers_count") or 0) for r in repos)
    return {
        "public_repos": public,
        "private_repos": private,
        "private_known": private_known,
        "total_repos": public + private,
        "stars": stars,
        "followers": int(user.get("followers") or 0),
        "following": int(user.get("following") or 0),
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_svg(stats: dict) -> str:
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
    ]

    lines_svg: list[str] = []
    y = 78
    for label, value, color in rows:
        lines_svg.append(
            f'<text x="28" y="{y}" fill="#9ca3af" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
            f'font-size="14">'
            f'<tspan fill="#22c55e">»</tspan> {esc(label)}</text>'
            f'<text x="220" y="{y}" fill="{color}" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
            f'font-size="14" font-weight="700">{esc(value)}</text>'
        )
        y += 28

    hint = (
        "private counts live · token ok"
        if stats["private_known"]
        else "add PROFILE_TOKEN secret for private counts"
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="520" height="250" viewBox="0 0 520 250" role="img" aria-label="GitHub stats for {esc(USERNAME)}">
  <title>{esc(USERNAME)} GitHub stats</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a0a0a"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1f2937" stroke-width="1" opacity="0.45"/>
    </pattern>
  </defs>
  <rect width="520" height="250" rx="12" fill="url(#bg)"/>
  <rect width="520" height="250" rx="12" fill="url(#grid)"/>
  <rect x="1" y="1" width="518" height="248" rx="11" fill="none" stroke="#22c55e" stroke-opacity="0.35"/>
  <circle cx="28" cy="28" r="6" fill="#FF605C"/>
  <circle cx="48" cy="28" r="6" fill="#FFBD44"/>
  <circle cx="68" cy="28" r="6" fill="#00CA4E"/>
  <text x="92" y="33" fill="#9ca3af" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="12">{esc(USERNAME)}@github:~/stats</text>
  <text x="28" y="58" fill="#22c55e" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="13">{esc(USERNAME)}@ekin:~$ ./gh_stats</text>
  {"".join(lines_svg)}
  <text x="28" y="230" fill="#6b7280" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="11">updated {esc(stats["updated"])} · {esc(hint)}</text>
</svg>
'''


def patch_readme(stats: dict) -> None:
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
    else:
        content += "\n\n" + block + "\n"

    line = (
        f"<!-- START_REPO_LINE -->`{stats['public_repos']} public` · "
        f"`{priv_display if stats['private_known'] else '?'} private` · "
        f"`{total} total`<!-- END_REPO_LINE -->"
    )
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
    # Authenticated /user/repos can see private; default Actions GITHUB_TOKEN cannot.
    private_known = used_auth and any("private" in r for r in repos)
    # More reliable: if we used auth endpoint, private flags are trustworthy.
    private_known = used_auth
    stats = compute_stats(user, repos, private_known)
    STATS_SVG.write_text(render_svg(stats), encoding="utf-8")
    patch_readme(stats)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

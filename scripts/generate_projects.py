#!/usr/bin/env python3
"""Generate recently-pushed project showcase SVG for the profile README.

Shows the 5 public, non-fork repos with the most recent commits (pushed_at),
excluding the profile repo itself.
"""

from __future__ import annotations

import json
import os
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
OUT_DIR = ROOT / "generated"
PROJECTS_SVG = OUT_DIR / "projects.svg"

TOP_N = 5
SVG_WIDTH = 900

# Prefer curated copy when GitHub description/topics are thin.
CURATED: dict[str, dict[str, object]] = {
    "IstanbulPark-AI-Train-2D": {
        "description": "Cars learn Istanbul Park with PPO / ML-Agents",
        "stack": ["Unity", "C#", "Python"],
    },
    "WiFi-Ruler": {
        "description": "Lock Wi-Fi to 2.4 / 5 / 6 GHz on Windows",
        "stack": ["Python", "WLAN API"],
    },
    "PriceTracker": {
        "description": "Async price watcher → Telegram alerts",
        "stack": ["Python", "Playwright"],
    },
    "TeslaInventoryTrack": {
        "description": "Live Tesla inventory notifier",
        "stack": ["C#", "WinForms", ".NET"],
    },
    "KararsizCarki": {
        "description": "Fun decision wheel for Android",
        "stack": ["Java", "Android"],
    },
    "GrappleClimb": {
        "description": "Physics-based vertical climb arcade",
        "stack": ["Unity", "C#"],
    },
}

TOPIC_LABELS = {
    "ml-agents": "ML-Agents",
    "reinforcement-learning": "RL",
    "ppo": "PPO",
    "unity": "Unity",
    "android": "Android",
    "dotnet": ".NET",
    "aspnet": "ASP.NET",
    "nextjs": "Next.js",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
}


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def humanize_delta(iso_ts: str | None) -> str:
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
    if secs < 86400 * 365:
        return f"{int(secs // (86400 * 30))}mo ago"
    return f"{int(secs // (86400 * 365))}y ago"


def truncate(text: str, max_len: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


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


def fetch_owned_public_repos() -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&type=owner&sort=pushed"
        )
        batch = api_get(url)
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def stack_for(repo: dict) -> list[str]:
    name = repo.get("name") or ""
    curated = CURATED.get(name, {})
    curated_stack = curated.get("stack")
    if isinstance(curated_stack, list) and curated_stack:
        return [str(x) for x in curated_stack]

    stack: list[str] = []
    language = repo.get("language")
    if language:
        stack.append(str(language))

    for topic in repo.get("topics") or []:
        label = TOPIC_LABELS.get(topic, topic.replace("-", " ").title())
        if label not in stack:
            stack.append(label)
        if len(stack) >= 4:
            break

    return stack[:4] or ["GitHub"]


def description_for(repo: dict) -> str:
    name = repo.get("name") or ""
    curated = CURATED.get(name, {})
    curated_desc = curated.get("description")
    if isinstance(curated_desc, str) and curated_desc.strip():
        return curated_desc.strip()
    raw = (repo.get("description") or "").strip()
    if raw:
        return raw
    language = repo.get("language") or "code"
    return f"Recent {language} project"


def select_recent_projects(repos: list[dict], limit: int = TOP_N) -> list[dict]:
    candidates: list[dict] = []
    for repo in repos:
        name = (repo.get("name") or "").lower()
        if name == USERNAME.lower():
            continue
        if repo.get("fork") or repo.get("archived") or repo.get("private"):
            continue
        if not repo.get("pushed_at"):
            continue
        candidates.append(repo)

    candidates.sort(key=lambda r: r["pushed_at"], reverse=True)

    projects: list[dict] = []
    for repo in candidates[:limit]:
        projects.append(
            {
                "name": repo["name"],
                "url": repo.get("html_url") or f"https://github.com/{USERNAME}/{repo['name']}",
                "description": description_for(repo),
                "stack": stack_for(repo),
                "pushed_at": repo["pushed_at"],
                "pushed_label": humanize_delta(repo["pushed_at"]),
                "language": repo.get("language") or "",
                "stars": int(repo.get("stargazers_count") or 0),
            }
        )
    return projects


def render_stack_pills(stack: list[str], x: int, y: int) -> tuple[str, int]:
    """Return SVG snippets and the x cursor after the last pill."""
    parts: list[str] = []
    cursor = x
    for i, item in enumerate(stack):
        label = truncate(item, 16)
        pad_x = 8
        text_w = max(28, len(label) * 7)
        w = text_w + pad_x * 2
        parts.append(
            f'<rect x="{cursor}" y="{y - 12}" width="{w}" height="20" rx="6" '
            f'fill="#14532d" fill-opacity="0.55" stroke="#22c55e" stroke-opacity="0.35"/>'
            f'<text x="{cursor + pad_x}" y="{y + 2}" fill="#86efac" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="11">{esc(label)}</text>'
        )
        cursor += w + 8
        if i >= 3:
            break
    return "".join(parts), cursor


def render_projects_svg(projects: list[dict]) -> str:
    row_h = 78
    header_h = 78
    footer_h = 40
    height = header_h + max(1, len(projects)) * row_h + footer_h
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows: list[str] = []
    for i, project in enumerate(projects):
        y0 = header_h + i * row_h
        y_name = y0 + 24
        y_desc = y0 + 46
        y_meta = y0 + 68
        idx = f"{i + 1:02d}"
        name = truncate(project["name"], 42)
        desc = truncate(project["description"], 78)
        pills, _ = render_stack_pills(project["stack"], 64, y_meta)

        # subtle alternating row wash
        if i % 2 == 0:
            rows.append(
                f'<rect x="16" y="{y0 + 4}" width="{SVG_WIDTH - 32}" height="{row_h - 8}" '
                f'rx="10" fill="#22c55e" fill-opacity="0.04"/>'
            )

        rows.append(
            f'<text x="28" y="{y_name}" fill="#22c55e" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="13" font-weight="700">{idx}</text>'
            f'<text x="64" y="{y_name}" fill="#ededed" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="16" font-weight="700">{esc(name)}</text>'
            f'<text x="{SVG_WIDTH - 28}" y="{y_name}" fill="#f472b6" text-anchor="end" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="12">{esc(project["pushed_label"])}</text>'
            f'<text x="64" y="{y_desc}" fill="#9ca3af" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="13">{esc(desc)}</text>'
            f"{pills}"
        )

    if not projects:
        rows.append(
            f'<text x="28" y="{header_h + 36}" fill="#9ca3af" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="14">no public projects found</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{height}" viewBox="0 0 {SVG_WIDTH} {height}" role="img" aria-label="Recently pushed projects for {esc(USERNAME)}">
  <title>{esc(USERNAME)} recently pushed projects</title>
  <defs>
    <linearGradient id="pbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a0a0a"/><stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <pattern id="pgrid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1f2937" stroke-width="1" opacity="0.45"/>
    </pattern>
  </defs>
  <rect width="{SVG_WIDTH}" height="{height}" rx="12" fill="url(#pbg)"/>
  <rect width="{SVG_WIDTH}" height="{height}" rx="12" fill="url(#pgrid)"/>
  <rect x="1" y="1" width="{SVG_WIDTH - 2}" height="{height - 2}" rx="11" fill="none" stroke="#22c55e" stroke-opacity="0.35"/>
  <circle cx="28" cy="28" r="6" fill="#FF605C"/><circle cx="48" cy="28" r="6" fill="#FFBD44"/><circle cx="68" cy="28" r="6" fill="#00CA4E"/>
  <text x="92" y="33" fill="#9ca3af" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12">canekin/~projects</text>
  <text x="28" y="58" fill="#22c55e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">can@ekin:~$ ls ~/projects --sort=pushed | head -{TOP_N}</text>
  {"".join(rows)}
  <text x="28" y="{height - 16}" fill="#6b7280" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">auto · last {len(projects)} pushes · updated {esc(updated)}</text>
</svg>
'''


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    repos = fetch_owned_public_repos()
    projects = select_recent_projects(repos)
    PROJECTS_SVG.write_text(render_projects_svg(projects), encoding="utf-8")
    print(
        json.dumps(
            [
                {
                    "name": p["name"],
                    "pushed_at": p["pushed_at"],
                    "pushed_label": p["pushed_label"],
                    "stack": p["stack"],
                }
                for p in projects
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Wrap Platane/snk SVG output in a contributions-style card frame.

Keeps the original snake grid / CSS animations intact (nested SVG).
Empty cells stay dark for github-dark palette — only the outer card chrome is added.
Also injects a live % label at the top-left of the bottom progress bar.
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
from xml.etree import ElementTree as ET

USERNAME = os.environ.get("GITHUB_USERNAME", "canekin")
TOKEN = (
    os.environ.get("PROFILE_TOKEN")
    or os.environ.get("GH_TOKEN")
    or os.environ.get("GITHUB_TOKEN")
    or ""
)
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "generated"
CONTRIB_SVG = OUT_DIR / "contributions.svg"
# Dark only — light snake is intentionally unused.
TARGETS = (OUT_DIR / "github-snake-dark.svg",)

# Match generated/contributions.svg chrome
PAD_X = 16
HEADER_H = 36
PAD_BOTTOM = 12
CARD_BG = "#0a0a0a"
CARD_BORDER = "#21262d"
FRAME_MARKER = 'data-framed="canekin-card"'
PCT_MARKER = 'data-progress-pct="1"'


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def unwrap_if_framed(svg: str) -> str:
    """If we already wrapped this file, recover the inner Platane SVG."""
    if FRAME_MARKER not in svg:
        return svg
    match = re.search(
        r'(<svg[^>]*data-snk-inner="1"[^>]*>.*)</svg>\s*</svg>\s*$',
        svg,
        flags=re.S,
    )
    if not match:
        raise ValueError("framed SVG is missing the nested Platane <svg>")
    inner = match.group(1) + "</svg>"
    return inner.replace(' data-snk-inner="1"', "", 1)


def parse_viewbox(svg: str) -> tuple[float, float, float, float]:
    m = re.search(r'viewBox="([^"]+)"', svg)
    if not m:
        raise ValueError("snake SVG missing viewBox")
    parts = [float(x) for x in m.group(1).split()]
    if len(parts) != 4:
        raise ValueError(f"unexpected viewBox: {m.group(1)}")
    return parts[0], parts[1], parts[2], parts[3]


def extract_inner_markup(svg: str) -> str:
    """Return markup inside the root <svg>...</svg>."""
    start = svg.find(">")
    end = svg.rfind("</svg>")
    if start < 0 or end < 0:
        raise ValueError("invalid SVG")
    return svg[start + 1 : end]


def meta_from_contributions_svg() -> tuple[str, str] | None:
    if not CONTRIB_SVG.exists():
        return None
    text = CONTRIB_SVG.read_text(encoding="utf-8")
    title = re.search(r"<title>([^<]+)</title>", text)
    peak = re.search(
        r'text-anchor="end">([^<]+)</text>',
        text,
    )
    if not title:
        return None
    left = title.group(1).strip()
    right = peak.group(1).strip() if peak else "animated contribution snake"
    return left, right


def meta_from_api() -> tuple[str, str] | None:
    if not TOKEN:
        return None
    to_dt = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(days=365)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date contributionCount }
            }
          }
        }
      }
    }
    """
    body = json.dumps(
        {
            "query": query,
            "variables": {
                "login": USERNAME,
                "from": from_dt.strftime("%Y-%m-%dT00:00:00Z"),
                "to": to_dt.strftime("%Y-%m-%dT23:59:59Z"),
            },
        }
    ).encode("utf-8")
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
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    if payload.get("errors"):
        return None
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    total = int(cal.get("totalContributions") or 0)
    by_month: dict[str, int] = defaultdict(int)
    for week in cal.get("weeks") or []:
        for day in week.get("contributionDays") or []:
            by_month[day["date"][:7]] += int(day.get("contributionCount") or 0)
    if by_month:
        best = max(by_month.items(), key=lambda x: x[1])[0]
        peak = datetime.strptime(best + "-01", "%Y-%m-%d").strftime("%b %Y")
    else:
        peak = "n/a"
    left = f"{total} contributions in the last year"
    right = f"peak {peak} · public + private (if enabled in profile settings)"
    return left, right


def resolve_labels() -> tuple[str, str]:
    return (
        meta_from_api()
        or meta_from_contributions_svg()
        or (
            "contribution snake · last year",
            "animated · public + private (if enabled in profile settings)",
        )
    )


def strip_progress_percent(svg: str) -> str:
    """Remove a previously injected progress % block (idempotent re-runs)."""
    return re.sub(
        rf"<style\s+{re.escape(PCT_MARKER)}>.*?</style>\s*"
        rf"<g\s+{re.escape(PCT_MARKER)}>.*?</g>\s*",
        "",
        svg,
        flags=re.S,
    )


def animation_duration_ms(svg: str) -> int:
    m = re.search(r"animation:none\s+(\d+)ms", svg)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)ms\s+linear\s+infinite", svg)
    if m:
        return int(m.group(1))
    return 20000


def progress_bar_anchor(svg: str) -> tuple[float, float]:
    """Top-left of the first progress-bar rect (class u)."""
    m = re.search(
        r'<rect class="u u0"[^>]*\bx="([^"]+)"[^>]*\by="([^"]+)"',
        svg,
    )
    if not m:
        m = re.search(
            r'<rect class="u u0"[^>]*\by="([^"]+)"[^>]*\bx="([^"]+)"',
            svg,
        )
        if not m:
            return 0.0, 144.0
        return float(m.group(2)), float(m.group(1))
    return float(m.group(1)), float(m.group(2))


def build_progress_percent(duration_ms: int, bar_x: float, bar_y: float) -> str:
    """Stacked opacity texts synced to the snake animation timeline."""
    # Baseline just above the bar — "sol üst" of the progress strip.
    label_x = bar_x
    label_y = bar_y - 3
    css = [
        f".pct{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;"
        f"font-size:10px;font-weight:700;fill:#8b949e;opacity:0;"
        f"animation:none {duration_ms}ms linear infinite}}"
    ]
    texts: list[str] = []
    for i in range(0, 101):
        start = float(i)
        end = float(i + 1) if i < 100 else 100.0
        if i == 0:
            kf = f"0%,{end - 0.001}%{{opacity:1}}{end}%,100%{{opacity:0}}"
        elif i == 100:
            kf = f"0%,{start - 0.001}%{{opacity:0}}{start}%,100%{{opacity:1}}"
        else:
            kf = (
                f"0%,{start - 0.001}%{{opacity:0}}"
                f"{start}%,{end - 0.001}%{{opacity:1}}"
                f"{end}%,100%{{opacity:0}}"
            )
        css.append(f"@keyframes pct{i}{{{kf}}}.pct.pct{i}{{animation-name:pct{i}}}")
        texts.append(
            f'<text class="pct pct{i}" x="{label_x}" y="{label_y}" '
            f'text-anchor="start">%{i}</text>'
        )
    style = f"<style {PCT_MARKER}>{''.join(css)}</style>"
    group = f"<g {PCT_MARKER}>{''.join(texts)}</g>"
    return style + group


def inject_progress_percent(svg: str) -> str:
    svg = strip_progress_percent(svg)
    duration = animation_duration_ms(svg)
    bar_x, bar_y = progress_bar_anchor(svg)
    block = build_progress_percent(duration, bar_x, bar_y)
    # Insert before the closing </svg> of the Platane root.
    end = svg.rfind("</svg>")
    if end < 0:
        raise ValueError("invalid SVG while injecting progress %")
    return svg[:end] + block + svg[end:]


def frame_svg(raw: str, left: str, right: str) -> str:
    raw = unwrap_if_framed(raw).strip()
    raw = inject_progress_percent(raw)
    # Validate XML-ish structure without requiring namespaces for animations
    try:
        ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"snake SVG is not well-formed XML: {exc}") from exc

    min_x, min_y, vb_w, vb_h = parse_viewbox(raw)
    inner = extract_inner_markup(raw)

    # Preserve original content size; add card padding around it
    inner_w = vb_w
    inner_h = vb_h
    outer_w = int(round(inner_w + PAD_X * 2))
    outer_h = int(round(HEADER_H + inner_h + PAD_BOTTOM))

    # Nested SVG keeps Platane coordinates / CSS keyframes untouched
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{outer_w}" height="{outer_h}" viewBox="0 0 {outer_w} {outer_h}" role="img" aria-label="Contribution snake for {esc(USERNAME)}" {FRAME_MARKER}>
  <title>{esc(left)}</title>
  <rect width="{outer_w}" height="{outer_h}" rx="12" fill="{CARD_BG}"/>
  <rect x="1" y="1" width="{outer_w - 2}" height="{outer_h - 2}" rx="11" fill="none" stroke="{CARD_BORDER}"/>
  <text x="16" y="22" fill="#ededed" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13" font-weight="700">{esc(left)}</text>
  <text x="{outer_w - 16}" y="22" fill="#22c55e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11" text-anchor="end">{esc(right)}</text>
  <svg data-snk-inner="1" x="{PAD_X}" y="{HEADER_H}" width="{inner_w}" height="{inner_h}" viewBox="{min_x} {min_y} {vb_w} {vb_h}" xmlns="http://www.w3.org/2000/svg">{inner}</svg>
</svg>
'''


def validate_animations(framed: str) -> None:
    if "@keyframes" not in framed:
        raise RuntimeError("framed SVG lost @keyframes — animation broken")
    if "animation-name" not in framed and "animation:" not in framed:
        raise RuntimeError("framed SVG lost animation rules")
    if 'class="s s0"' not in framed and "class='s s0'" not in framed:
        # Platane snake segments
        if re.search(r'class="s s\d+"', framed) is None:
            raise RuntimeError("framed SVG missing snake segments")
    if FRAME_MARKER not in framed:
        raise RuntimeError("frame marker missing")
    if PCT_MARKER not in framed:
        raise RuntimeError("progress percent marker missing")
    if ">%50</text>" not in framed and ">%50<" not in framed:
        # Class-based labels use >%50</text>
        if re.search(r">%50</text>", framed) is None:
            raise RuntimeError("progress percent labels missing")


def process_file(path: Path, left: str, right: str) -> bool:
    if not path.exists():
        print(f"skip missing {path.name}")
        return False
    raw = path.read_text(encoding="utf-8")
    framed = frame_svg(raw, left, right)
    validate_animations(framed)
    path.write_text(framed, encoding="utf-8")
    print(f"framed {path.name} ({len(framed)} bytes)")
    return True


def main() -> None:
    left, right = resolve_labels()
    print("labels:", left, "|", right)
    done = 0
    for path in TARGETS:
        if process_file(path, left, right):
            done += 1
    if done == 0:
        raise SystemExit("no snake SVGs found to frame")


if __name__ == "__main__":
    main()

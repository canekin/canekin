#!/usr/bin/env python3
"""Wrap Platane/snk SVG output in a contributions-style card frame.

Keeps the original snake grid / CSS animations intact (nested SVG).
Empty cells stay dark for github-dark palette — only the outer card chrome is added.
Also injects month labels above the grid and a live % on the progress bar.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
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
MONTH_MARKER = 'data-month-labels="1"'
SNK_CELL = 16  # Platane/snk default sizeCell


@dataclass
class FrameMeta:
    left: str
    peak: str | None = None  # e.g. "peak Jul 2026" — computed, never static fluff
    weeks: list = field(default_factory=list)


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


def peak_label_from_weeks(weeks: list) -> str | None:
    by_month: dict[str, int] = defaultdict(int)
    for week in weeks:
        for day in week.get("contributionDays") or []:
            by_month[day["date"][:7]] += int(day.get("contributionCount") or 0)
    if not by_month:
        return None
    best = max(by_month.items(), key=lambda x: x[1])[0]
    peak = datetime.strptime(best + "-01", "%Y-%m-%d").strftime("%b %Y")
    return f"peak {peak}"


def normalize_peak(text: str | None) -> str | None:
    """Keep only a real 'peak Mon YYYY' label; drop private/public fluff."""
    if not text:
        return None
    m = re.search(r"peak\s+([A-Za-z]{3}\s+\d{4})", text, flags=re.I)
    if not m:
        return None
    return f"peak {m.group(1)}"


def weeks_from_contributions_svg() -> list | None:
    if not CONTRIB_SVG.exists():
        return None
    text = CONTRIB_SVG.read_text(encoding="utf-8")
    dates = re.findall(
        r"<title>(\d{4}-\d{2}-\d{2}):\s*(\d+)\s+contribution",
        text,
    )
    if not dates:
        return None
    # Group into Sunday-start weeks as GitHub does (7 consecutive days).
    days = [{"date": d, "contributionCount": int(c)} for d, c in dates]
    weeks: list[list[dict]] = []
    for i in range(0, len(days), 7):
        chunk = days[i : i + 7]
        if chunk:
            weeks.append({"contributionDays": chunk})
    return weeks or None


def meta_from_contributions_svg() -> FrameMeta | None:
    if not CONTRIB_SVG.exists():
        return None
    text = CONTRIB_SVG.read_text(encoding="utf-8")
    title = re.search(r"<title>([^<]+)</title>", text)
    if not title:
        return None
    right_raw = re.search(r'text-anchor="end">([^<]+)</text>', text)
    weeks = weeks_from_contributions_svg() or []
    peak = normalize_peak(right_raw.group(1) if right_raw else None) or peak_label_from_weeks(
        weeks
    )
    return FrameMeta(left=title.group(1).strip(), peak=peak, weeks=weeks)


def meta_from_api() -> FrameMeta | None:
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
    weeks = cal.get("weeks") or []
    return FrameMeta(
        left=f"{total} contributions in the last year",
        peak=peak_label_from_weeks(weeks),
        weeks=weeks,
    )


def resolve_meta() -> FrameMeta:
    return meta_from_api() or meta_from_contributions_svg() or FrameMeta(
        left="contribution snake · last year",
        peak=None,
        weeks=[],
    )


def month_positions(weeks: list) -> list[tuple[int, str]]:
    """Week index → English month abbreviation (Aug, Sep, …)."""
    labels: list[tuple[int, str]] = []
    prev_month: int | None = None
    for i, week in enumerate(weeks):
        days = week.get("contributionDays") or []
        if not days:
            continue
        d0 = datetime.strptime(days[0]["date"], "%Y-%m-%d")
        # Same rule as generate_stats / GitHub: label when a new month begins.
        if d0.month != prev_month and d0.day <= 7:
            labels.append((i, d0.strftime("%b")))
            prev_month = d0.month
    return labels


def strip_progress_percent(svg: str) -> str:
    return re.sub(
        rf"<style\s+{re.escape(PCT_MARKER)}>.*?</style>\s*"
        rf"<g\s+{re.escape(PCT_MARKER)}>.*?</g>\s*",
        "",
        svg,
        flags=re.S,
    )


def strip_month_labels(svg: str) -> str:
    return re.sub(
        rf"<g\s+{re.escape(MONTH_MARKER)}>.*?</g>\s*",
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


def snk_week_count(svg: str) -> int:
    xs = {float(x) for x in re.findall(r'<rect class="c[^"]*" x="([^"]+)"', svg)}
    if not xs:
        return 0
    return int(round((max(xs) - min(xs)) / SNK_CELL)) + 1


def build_progress_percent(duration_ms: int, bar_x: float, bar_y: float) -> str:
    """Stacked opacity texts synced to the snake animation timeline."""
    label_x = bar_x
    # Baseline just above the bar; 16px type needs a bit more clearance.
    label_y = bar_y - 4
    css = [
        f".pct{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;"
        f"font-size:16px;font-weight:700;fill:#8b949e;opacity:0;"
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


def build_month_labels(weeks: list, week_count: int) -> str:
    if not weeks or week_count <= 0:
        return ""
    # Align calendar weeks to snk columns (snk uses the same last-year window).
    # If counts differ slightly, right-align so recent months sit over recent weeks.
    offset = max(0, week_count - len(weeks))
    parts: list[str] = []
    for wi, name in month_positions(weeks):
        col = wi + offset
        if col < 0 or col >= week_count:
            continue
        x = col * SNK_CELL
        parts.append(
            f'<text x="{x}" y="-14" fill="#8b949e" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="11">{esc(name)}</text>'
        )
    if not parts:
        return ""
    return f"<g {MONTH_MARKER}>{''.join(parts)}</g>"


def inject_progress_percent(svg: str) -> str:
    svg = strip_progress_percent(svg)
    duration = animation_duration_ms(svg)
    bar_x, bar_y = progress_bar_anchor(svg)
    block = build_progress_percent(duration, bar_x, bar_y)
    end = svg.rfind("</svg>")
    if end < 0:
        raise ValueError("invalid SVG while injecting progress %")
    return svg[:end] + block + svg[end:]


def inject_month_labels(svg: str, weeks: list) -> str:
    svg = strip_month_labels(svg)
    block = build_month_labels(weeks, snk_week_count(svg))
    if not block:
        return svg
    end = svg.rfind("</svg>")
    if end < 0:
        raise ValueError("invalid SVG while injecting month labels")
    return svg[:end] + block + svg[end:]


def frame_svg(raw: str, meta: FrameMeta) -> str:
    raw = unwrap_if_framed(raw).strip()
    raw = inject_month_labels(raw, meta.weeks)
    raw = inject_progress_percent(raw)
    try:
        ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"snake SVG is not well-formed XML: {exc}") from exc

    min_x, min_y, vb_w, vb_h = parse_viewbox(raw)
    inner = extract_inner_markup(raw)

    inner_w = vb_w
    inner_h = vb_h
    outer_w = int(round(inner_w + PAD_X * 2))
    outer_h = int(round(HEADER_H + inner_h + PAD_BOTTOM))

    peak_text = ""
    if meta.peak:
        peak_text = (
            f'\n  <text x="{outer_w - 16}" y="22" fill="#22c55e" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="11" text-anchor="end">{esc(meta.peak)}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{outer_w}" height="{outer_h}" viewBox="0 0 {outer_w} {outer_h}" role="img" aria-label="Contribution snake for {esc(USERNAME)}" {FRAME_MARKER}>
  <title>{esc(meta.left)}</title>
  <rect width="{outer_w}" height="{outer_h}" rx="12" fill="{CARD_BG}"/>
  <rect x="1" y="1" width="{outer_w - 2}" height="{outer_h - 2}" rx="11" fill="none" stroke="{CARD_BORDER}"/>
  <text x="16" y="22" fill="#ededed" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13" font-weight="700">{esc(meta.left)}</text>{peak_text}
  <svg data-snk-inner="1" x="{PAD_X}" y="{HEADER_H}" width="{inner_w}" height="{inner_h}" viewBox="{min_x} {min_y} {vb_w} {vb_h}" xmlns="http://www.w3.org/2000/svg">{inner}</svg>
</svg>
'''


def validate_animations(framed: str) -> None:
    if "@keyframes" not in framed:
        raise RuntimeError("framed SVG lost @keyframes — animation broken")
    if "animation-name" not in framed and "animation:" not in framed:
        raise RuntimeError("framed SVG lost animation rules")
    if re.search(r'class="s s\d+"', framed) is None:
        raise RuntimeError("framed SVG missing snake segments")
    if FRAME_MARKER not in framed:
        raise RuntimeError("frame marker missing")
    if PCT_MARKER not in framed:
        raise RuntimeError("progress percent marker missing")
    if "font-size:16px" not in framed:
        raise RuntimeError("progress percent not 16px")
    if re.search(r">%50</text>", framed) is None:
        raise RuntimeError("progress percent labels missing")
    if "public + private" in framed:
        raise RuntimeError("private/public fluff still present in frame")


def process_file(path: Path, meta: FrameMeta) -> bool:
    if not path.exists():
        print(f"skip missing {path.name}")
        return False
    raw = path.read_text(encoding="utf-8")
    framed = frame_svg(raw, meta)
    validate_animations(framed)
    path.write_text(framed, encoding="utf-8")
    print(f"framed {path.name} ({len(framed)} bytes)")
    return True


def main() -> None:
    meta = resolve_meta()
    print("labels:", meta.left, "|", meta.peak or "(no peak)")
    print("weeks:", len(meta.weeks), "months:", [n for _, n in month_positions(meta.weeks)])
    done = 0
    for path in TARGETS:
        if process_file(path, meta):
            done += 1
    if done == 0:
        raise SystemExit("no snake SVGs found to frame")


if __name__ == "__main__":
    main()

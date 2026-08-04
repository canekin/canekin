#!/usr/bin/env python3
"""Generate a terminal-styled connect / contact SVG for the profile README."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "connect.svg"
ICONS_PATH = Path(__file__).resolve().parent / "connect_icons.json"

SVG_WIDTH = 900
ICON_SIZE = 16

# channel, handle, url, icon slug, accent
CHANNELS: list[tuple[str, str, str, str, str]] = [
    ("portfolio", "canekin.com", "https://www.canekin.com", "googlechrome", "#22c55e"),
    ("linkedin", "mehmetcanekin", "https://linkedin.com/in/mehmetcanekin", "linkedin", "#0A66C2"),
    ("email", "iletisim@canekin.com", "mailto:hello@canekin.com", "gmail", "#EA4335"),
    ("github", "canekin", "https://github.com/canekin", "github", "#ededed"),
]


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load_icons() -> dict[str, dict[str, str]]:
    return json.loads(ICONS_PATH.read_text(encoding="utf-8"))


def render_icon(
    icons: dict[str, dict[str, str]],
    slug: str,
    x: float,
    y: float,
) -> str:
    meta = icons[slug]
    scale = ICON_SIZE / 24
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) scale({scale:.4f})">'
        f'<path fill="#{meta["color"]}" d="{meta["d"]}"/>'
        f"</g>"
    )


def render() -> str:
    icons = load_icons()
    header_h = 78
    row_h = 64
    footer_h = 40
    height = header_h + len(CHANNELS) * row_h + footer_h

    rows: list[str] = []
    for i, (channel, handle, _url, slug, accent) in enumerate(CHANNELS):
        y0 = header_h + i * row_h
        cy = y0 + row_h / 2

        if i % 2 == 0:
            rows.append(
                f'<rect x="16" y="{y0 + 4}" width="{SVG_WIDTH - 32}" height="{row_h - 8}" '
                f'rx="10" fill="#22c55e" fill-opacity="0.04"/>'
            )

        # left accent bar
        rows.append(
            f'<rect x="28" y="{y0 + 14}" width="3" height="{row_h - 28}" rx="1.5" fill="{accent}"/>'
        )

        icon_x = 48
        icon_y = cy - ICON_SIZE / 2
        rows.append(
            f'<circle cx="{icon_x + ICON_SIZE / 2}" cy="{cy}" r="16" '
            f'fill="{accent}" fill-opacity="0.12" stroke="{accent}" stroke-opacity="0.35"/>'
        )
        rows.append(render_icon(icons, slug, icon_x + 2, icon_y))

        rows.append(
            f'<text x="96" y="{cy - 6}" fill="#9ca3af" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="12">'
            f'<tspan fill="#22c55e">»</tspan> {esc(channel)}</text>'
            f'<text x="96" y="{cy + 14}" fill="{accent}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="15" font-weight="700">{esc(handle)}</text>'
            f'<text x="{SVG_WIDTH - 36}" y="{cy + 5}" fill="#4b5563" text-anchor="end" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="18">›</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{height}" viewBox="0 0 {SVG_WIDTH} {height}" role="img" aria-label="Connect with canekin">
  <title>canekin connect</title>
  <defs>
    <linearGradient id="cbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a0a0a"/><stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <pattern id="cgrid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1f2937" stroke-width="1" opacity="0.45"/>
    </pattern>
  </defs>
  <rect width="{SVG_WIDTH}" height="{height}" rx="12" fill="url(#cbg)"/>
  <rect width="{SVG_WIDTH}" height="{height}" rx="12" fill="url(#cgrid)"/>
  <rect x="1" y="1" width="{SVG_WIDTH - 2}" height="{height - 2}" rx="11" fill="none" stroke="#22c55e" stroke-opacity="0.35"/>
  <circle cx="28" cy="28" r="6" fill="#FF605C"/><circle cx="48" cy="28" r="6" fill="#FFBD44"/><circle cx="68" cy="28" r="6" fill="#00CA4E"/>
  <text x="92" y="33" fill="#9ca3af" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12">canekin/~connect</text>
  <text x="28" y="58" fill="#22c55e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">can@ekin:~$ ssh can@ekin</text>
  {"".join(rows)}
  <text x="28" y="{height - 14}" fill="#6b7280" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">echo "ship something cool today"</text>
</svg>
'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

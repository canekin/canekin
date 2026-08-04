#!/usr/bin/env python3
"""Generate a terminal-styled skills SVG with brand icons in each pill."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "skills.svg"
ICONS_PATH = Path(__file__).resolve().parent / "skill_icons.json"

SVG_WIDTH = 900
ICON_SIZE = 12
ICON_GAP = 6
PAD_X = 9
PILL_H = 26

# (label, icon slug | None)
LAYERS: list[tuple[str, list[tuple[str, str | None]], str]] = [
    (
        "languages",
        [
            ("C#", "csharp"),
            ("Python", "python"),
            ("TypeScript", "typescript"),
            ("JavaScript", "javascript"),
            ("SQL", "postgresql"),
        ],
        "#22c55e",
    ),
    (
        "web / app",
        [
            ("Next.js", "nextdotjs"),
            ("React", "react"),
            ("ASP.NET Core", "dotnet"),
            ("Node.js", "nodedotjs"),
            ("Tailwind", "tailwindcss"),
        ],
        "#60a5fa",
    ),
    (
        "build & ship",
        [
            ("Git", "git"),
            ("CI/CD", "githubactions"),
            ("Unity", "unity"),
            ("REST APIs", "swagger"),
            ("Vitest", "vitest"),
        ],
        "#fbbf24",
    ),
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


def pill_width(label: str, has_icon: bool) -> int:
    text_w = max(18, len(label) * 7)
    icon_w = ICON_SIZE + ICON_GAP if has_icon else 0
    return PAD_X * 2 + icon_w + text_w


def render_icon(
    icons: dict[str, dict[str, str]],
    slug: str,
    x: float,
    y: float,
) -> str:
    """Inline path (more reliable than <use> when SVG is shown via <img>)."""
    meta = icons[slug]
    scale = ICON_SIZE / 24
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) scale({scale:.4f})">'
        f'<path fill="#{meta["color"]}" d="{meta["d"]}"/>'
        f"</g>"
    )


def render_pills(
    icons: dict[str, dict[str, str]],
    items: list[tuple[str, str | None]],
    x: int,
    y: int,
    accent: str,
) -> str:
    parts: list[str] = []
    cursor = x
    for label, slug in items:
        has_icon = bool(slug)
        w = pill_width(label, has_icon)
        top = y - 14
        parts.append(
            f'<rect x="{cursor}" y="{top}" width="{w}" height="{PILL_H}" rx="7" '
            f'fill="{accent}" fill-opacity="0.12" stroke="{accent}" stroke-opacity="0.4"/>'
        )
        text_x = cursor + PAD_X
        if has_icon and slug:
            icon_y = top + (PILL_H - ICON_SIZE) / 2
            parts.append(render_icon(icons, slug, cursor + PAD_X, icon_y))
            text_x = cursor + PAD_X + ICON_SIZE + ICON_GAP
        parts.append(
            f'<text x="{text_x}" y="{y + 4}" fill="{accent}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="12" font-weight="600">{esc(label)}</text>'
        )
        cursor += w + 8
    return "".join(parts)


def render() -> str:
    icons = load_icons()
    header_h = 78
    layer_h = 74
    footer_h = 36
    height = header_h + len(LAYERS) * layer_h + footer_h

    rows: list[str] = []
    for i, (name, tools, accent) in enumerate(LAYERS):
        y0 = header_h + i * layer_h
        y_label = y0 + 26
        y_pills = y0 + 54

        if i % 2 == 0:
            rows.append(
                f'<rect x="16" y="{y0 + 4}" width="{SVG_WIDTH - 32}" height="{layer_h - 8}" '
                f'rx="10" fill="#22c55e" fill-opacity="0.04"/>'
            )

        rows.append(
            f'<text x="28" y="{y_label}" fill="#9ca3af" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="13">'
            f'<tspan fill="#22c55e">»</tspan> '
            f'<tspan fill="{accent}" font-weight="700">{esc(name)}</tspan>'
            f"</text>"
            f"{render_pills(icons, tools, 48, y_pills, accent)}"
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{height}" viewBox="0 0 {SVG_WIDTH} {height}" role="img" aria-label="Skills for canekin">
  <title>canekin skills</title>
  <defs>
    <linearGradient id="sbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a0a0a"/><stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <pattern id="sgrid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1f2937" stroke-width="1" opacity="0.45"/>
    </pattern>
  </defs>
  <rect width="{SVG_WIDTH}" height="{height}" rx="12" fill="url(#sbg)"/>
  <rect width="{SVG_WIDTH}" height="{height}" rx="12" fill="url(#sgrid)"/>
  <rect x="1" y="1" width="{SVG_WIDTH - 2}" height="{height - 2}" rx="11" fill="none" stroke="#22c55e" stroke-opacity="0.35"/>
  <circle cx="28" cy="28" r="6" fill="#FF605C"/><circle cx="48" cy="28" r="6" fill="#FFBD44"/><circle cx="68" cy="28" r="6" fill="#00CA4E"/>
  <text x="92" y="33" fill="#9ca3af" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12">canekin/~skills</text>
  <text x="28" y="58" fill="#22c55e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">can@ekin:~$ cat ~/skills.json</text>
  {"".join(rows)}
  <text x="28" y="{height - 14}" fill="#6b7280" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">stack in motion · full-stack / backend &amp; web</text>
</svg>
'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a terminal-styled skills SVG for the profile README."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "skills.svg"

SVG_WIDTH = 900

LAYERS: list[tuple[str, list[str], str]] = [
    (
        "languages",
        ["C#", "Python", "TypeScript", "JavaScript", "SQL"],
        "#22c55e",
    ),
    (
        "web / app",
        ["Next.js", "React", "ASP.NET Core", "Node.js", "Tailwind"],
        "#60a5fa",
    ),
    (
        "build & ship",
        ["Git", "CI/CD", "Unity", "REST APIs", "Vitest"],
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


def pill_width(label: str) -> int:
    return max(36, len(label) * 7 + 20)


def render_pills(items: list[str], x: int, y: int, accent: str) -> str:
    parts: list[str] = []
    cursor = x
    for item in items:
        w = pill_width(item)
        parts.append(
            f'<rect x="{cursor}" y="{y - 13}" width="{w}" height="24" rx="7" '
            f'fill="{accent}" fill-opacity="0.12" stroke="{accent}" stroke-opacity="0.4"/>'
            f'<text x="{cursor + 10}" y="{y + 4}" fill="{accent}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="12" font-weight="600">{esc(item)}</text>'
        )
        cursor += w + 8
    return "".join(parts)


def render() -> str:
    header_h = 78
    layer_h = 72
    footer_h = 36
    height = header_h + len(LAYERS) * layer_h + footer_h

    rows: list[str] = []
    for i, (name, tools, accent) in enumerate(LAYERS):
        y0 = header_h + i * layer_h
        y_label = y0 + 26
        y_pills = y0 + 52

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
            f'{render_pills(tools, 48, y_pills, accent)}'
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

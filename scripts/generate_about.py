#!/usr/bin/env python3
"""Generate a terminal-styled about card SVG for the profile README."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "about.svg"

SVG_WIDTH = 900

# label, value, accent
FIELDS: list[tuple[str, str, str]] = [
    ("name", "Can Ekin", "#ededed"),
    ("role", "Software Engineering student · Full-Stack / Backend & Web", "#22c55e"),
    ("stack", "C# · Python · Next.js · JavaScript · ASP.NET", "#60a5fa"),
    ("currently", "Bahçeşehir University · building cool stuff & open for opportunities", "#fbbf24"),
]


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def truncate(text: str, max_len: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def render() -> str:
    header_h = 78
    row_h = 48
    footer_h = 40
    height = header_h + len(FIELDS) * row_h + footer_h

    rows: list[str] = []
    for i, (label, value, accent) in enumerate(FIELDS):
        y = header_h + i * row_h + 30

        if i % 2 == 0:
            y0 = header_h + i * row_h
            rows.append(
                f'<rect x="16" y="{y0 + 4}" width="{SVG_WIDTH - 32}" height="{row_h - 8}" '
                f'rx="10" fill="#22c55e" fill-opacity="0.04"/>'
            )

        rows.append(
            f'<text x="36" y="{y}" fill="#9ca3af" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="14">'
            f'<tspan fill="#22c55e">»</tspan> {esc(label)}</text>'
            f'<text x="170" y="{y}" fill="#4b5563" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="14">:</text>'
            f'<text x="190" y="{y}" fill="{accent}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="14" font-weight="700">{esc(truncate(value, 72))}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{height}" viewBox="0 0 {SVG_WIDTH} {height}" role="img" aria-label="About Can Ekin">
  <title>canekin about</title>
  <defs>
    <linearGradient id="abg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a0a0a"/><stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <pattern id="agrid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1f2937" stroke-width="1" opacity="0.45"/>
    </pattern>
  </defs>
  <rect width="{SVG_WIDTH}" height="{height}" rx="12" fill="url(#abg)"/>
  <rect width="{SVG_WIDTH}" height="{height}" rx="12" fill="url(#agrid)"/>
  <rect x="1" y="1" width="{SVG_WIDTH - 2}" height="{height - 2}" rx="11" fill="none" stroke="#22c55e" stroke-opacity="0.35"/>
  <circle cx="28" cy="28" r="6" fill="#FF605C"/><circle cx="48" cy="28" r="6" fill="#FFBD44"/><circle cx="68" cy="28" r="6" fill="#00CA4E"/>
  <text x="92" y="33" fill="#9ca3af" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12">canekin/~about</text>
  <text x="28" y="58" fill="#22c55e" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">can@ekin:~$ whoami</text>
  {"".join(rows)}
  <text x="28" y="{height - 14}" fill="#6b7280" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">status · open to projects · canekin.com</text>
</svg>
'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

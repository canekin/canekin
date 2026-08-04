#!/usr/bin/env python3
"""Validate framed snake SVGs still contain working animation plumbing."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DARK = ROOT / "generated" / "github-snake-dark.svg"


def main() -> None:
    s = DARK.read_text(encoding="utf-8")
    checks = {
        "frame marker": 'data-framed="canekin-card"' in s,
        "inner snake": 'data-snk-inner="1"' in s,
        "keyframes": "@keyframes" in s,
        "animation-name": "animation-name" in s,
        "snake segments": re.search(r'class="s s\d+"', s) is not None,
        "dark empty cells": "--c0:#161b22" in s,
        "no light empty cells": "--c0:#ebedf0" not in s,
        "card bg": 'fill="#0a0a0a"' in s,
        "card border": 'stroke="#21262d"' in s,
        "rounded card": 'rx="12"' in s,
        "header left": "contributions in the last year" in s
        or "contribution snake" in s,
        "peak only": (
            re.search(r">peak [A-Za-z]{3} \d{4}</text>", s) is not None
            and "public + private" not in s
        ),
        "month labels": 'data-month-labels="1"' in s,
        "month Aug or similar": re.search(
            r">(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)</text>", s
        )
        is not None,
        "single outer frame": s.count('data-framed="canekin-card"') == 1,
        "single inner svg": s.count('data-snk-inner="1"') == 1,
        "progress bars": re.search(r'class="u u\d+"', s) is not None,
        "progress percent marker": 'data-progress-pct="1"' in s,
        "progress percent 16px": "font-size:16px" in s,
        "progress percent %50": ">%50</text>" in s,
        "progress percent %0": ">%0</text>" in s,
        "progress percent %100": ">%100</text>" in s,
        "style block": "<style>" in s and "</style>" in s,
    }
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)

    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "frame_snake.py")])
    s2 = DARK.read_text(encoding="utf-8")
    if s2.count('data-framed="canekin-card"') != 1 or s2.count('data-snk-inner="1"') != 1:
        failed.append("idempotent re-frame")
        print("FAIL idempotent re-frame")
    else:
        print("PASS idempotent re-frame")

    if s2.count('data-progress-pct="1"') != 2:
        failed.append("idempotent progress percent")
        print("FAIL idempotent progress percent")
    else:
        print("PASS idempotent progress percent")

    if s2.count('data-month-labels="1"') != 1:
        failed.append("idempotent month labels")
        print("FAIL idempotent month labels")
    else:
        print("PASS idempotent month labels")

    title = re.search(r"<title>([^<]+)</title>", s2)
    peak = re.search(r">peak [^<]+</text>", s2)
    print("title:", title.group(1) if title else "?")
    print("peak:", peak.group(0) if peak else "?")
    print("bytes:", len(s2))

    if failed:
        raise SystemExit(f"verification failed: {', '.join(failed)}")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()

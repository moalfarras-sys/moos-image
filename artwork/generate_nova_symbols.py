#!/usr/bin/env python3
"""Generate the original MoOS Nova symbolic UI icon family.

The SVGs avoid emoji, external desktop marks, font glyphs, and fragile filters.
They remain crisp from 20 px through 64 px in Qt's SVG renderer and use only
the canonical Nova palette.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "system_files" / "usr" / "share" / "icons" / "hicolor" / "scalable" / "actions"

P = {
    "surface": "#111A2E",
    "blue": "#2E7BFF",
    "cyan": "#22D3EE",
    "ice": "#7DEBFF",
    "violet": "#8B5CF6",
    "text": "#E6EDF7",
}


SYMBOLS = {
    "moos-identity": """
    <path d="M32 9 36 23 50 27 36 31 32 45 28 31 14 27 28 23Z" fill="url(#nova)" fill-opacity=".24"/>
    <path d="M32 9 36 23 50 27 36 31 32 45 28 31 14 27 28 23Z"/>
    <circle cx="49" cy="14" r="2.2" fill="#7DEBFF" stroke="none"/>
    <circle cx="15" cy="47" r="1.8" fill="#8B5CF6" stroke="none"/>
    """,
    "moos-ai": """
    <path d="M32 17V10m0 0 4-3m-4 3-4-3"/>
    <rect x="13" y="17" width="38" height="33" rx="12" fill="url(#nova)" fill-opacity=".16"/>
    <rect x="13" y="17" width="38" height="33" rx="12"/>
    <circle cx="25" cy="32" r="3.4" fill="#22D3EE" stroke="none"/>
    <circle cx="39" cy="32" r="3.4" fill="#8B5CF6" stroke="none"/>
    <path d="M24 42c5 3 11 3 16 0"/>
    """,
    "moos-gaming": """
    <path d="M20 22h24c5 0 8 5 9 13l1 8c1 5-4 8-8 4l-7-6H25l-7 6c-4 4-9 1-8-4l1-8c1-8 4-13 9-13Z" fill="url(#nova)" fill-opacity=".14"/>
    <path d="M20 22h24c5 0 8 5 9 13l1 8c1 5-4 8-8 4l-7-6H25l-7 6c-4 4-9 1-8-4l1-8c1-8 4-13 9-13Z"/>
    <path d="M22 30v10m-5-5h10"/>
    <circle cx="43" cy="32" r="2" fill="#22D3EE" stroke="none"/>
    <circle cx="48" cy="38" r="2" fill="#8B5CF6" stroke="none"/>
    """,
    "moos-android-apps": """
    <rect x="13" y="10" width="38" height="44" rx="12" fill="url(#nova)" fill-opacity=".13"/>
    <rect x="13" y="10" width="38" height="44" rx="12"/>
    <rect x="21" y="20" width="8" height="8" rx="2"/>
    <rect x="35" y="20" width="8" height="8" rx="2"/>
    <rect x="21" y="34" width="8" height="8" rx="2"/>
    <path d="M39 33v12m-6-6h12"/>
    """,
    "moos-safe-update": """
    <path d="M32 8 50 16v14c0 12-7 20-18 26-11-6-18-14-18-26V16Z" fill="url(#nova)" fill-opacity=".14"/>
    <path d="M32 8 50 16v14c0 12-7 20-18 26-11-6-18-14-18-26V16Z"/>
    <path d="M23 34a10 10 0 0 1 16-8l3 3m0-7v7h-7M41 34a10 10 0 0 1-16 8l-3-3m0 7v-7h7"/>
    """,
    "moos-nova-ui": """
    <path d="m32 10 20 11-20 11L12 21Z" fill="url(#nova)" fill-opacity=".20"/>
    <path d="m32 10 20 11-20 11L12 21Zm-17 21 17 9 17-9M15 40l17 9 17-9"/>
    <path d="m49 8 1.7 5.3L56 15l-5.3 1.7L49 22l-1.7-5.3L42 15l5.3-1.7Z" fill="#7DEBFF" stroke="none"/>
    """,
    "moos-cpu": """
    <rect x="17" y="17" width="30" height="30" rx="7" fill="url(#nova)" fill-opacity=".15"/>
    <rect x="17" y="17" width="30" height="30" rx="7"/><rect x="25" y="25" width="14" height="14" rx="3"/>
    <path d="M23 10v7m9-7v7m9-7v7M23 47v7m9-7v7m9-7v7M10 23h7m-7 9h7m-7 9h7m30-18h7m-7 9h7m-7 9h7"/>
    """,
    "moos-memory": """
    <rect x="8" y="18" width="48" height="28" rx="7" fill="url(#nova)" fill-opacity=".15"/>
    <rect x="8" y="18" width="48" height="28" rx="7"/>
    <rect x="15" y="25" width="8" height="12" rx="2"/><rect x="28" y="25" width="8" height="12" rx="2"/><rect x="41" y="25" width="8" height="12" rx="2"/>
    <path d="M16 46v6m8-6v6m8-6v6m8-6v6m8-6v6"/>
    """,
    "moos-gpu": """
    <rect x="8" y="13" width="48" height="34" rx="8" fill="url(#nova)" fill-opacity=".14"/>
    <rect x="8" y="13" width="48" height="34" rx="8"/><circle cx="31" cy="30" r="10"/>
    <path d="M31 20c5 4 5 8 0 10m10 0c-4 5-8 5-10 0m0 10c-5-4-5-8 0-10m-10 0c4-5 8-5 10 0M16 52h32M50 21h6"/>
    """,
    "moos-storage": """
    <ellipse cx="32" cy="15" rx="18" ry="7" fill="url(#nova)" fill-opacity=".18"/>
    <ellipse cx="32" cy="15" rx="18" ry="7"/><path d="M14 15v30c0 4 8 7 18 7s18-3 18-7V15M14 30c0 4 8 7 18 7s18-3 18-7"/>
    <circle cx="43" cy="44" r="2" fill="#22D3EE" stroke="none"/>
    """,
    "moos-network": """
    <circle cx="32" cy="13" r="5" fill="url(#nova)" fill-opacity=".22"/><circle cx="14" cy="45" r="5" fill="url(#nova)" fill-opacity=".22"/><circle cx="50" cy="45" r="5" fill="url(#nova)" fill-opacity=".22"/>
    <path d="M29 17 17 40m18-23 12 23M20 45h24M24 31c5-4 11-4 16 0"/>
    """,
    "moos-system": """
    <rect x="8" y="10" width="48" height="34" rx="8" fill="url(#nova)" fill-opacity=".13"/><rect x="8" y="10" width="48" height="34" rx="8"/>
    <path d="M24 54h16m-8-10v10m0-36 5 7-5 7-5-7Z"/><circle cx="32" cy="25" r="11"/>
    """,
    "moos-copy": """
    <rect x="20" y="12" width="31" height="36" rx="8" fill="url(#nova)" fill-opacity=".15"/><rect x="20" y="12" width="31" height="36" rx="8"/>
    <path d="M16 20h-2c-4 0-7 3-7 7v24c0 4 3 7 7 7h21c4 0 7-3 7-7v-3M29 25h13m-13 9h13"/>
    """,
    "moos-report": """
    <path d="M16 8h22l11 11v37H16Z" fill="url(#nova)" fill-opacity=".12"/><path d="M16 8h22l11 11v37H16Zm22 0v12h11M24 29h17M24 37h17M24 45h9m3 2 4 4 8-9"/>
    """,
    "moos-warning": """
    <path d="M32 8 57 53H7Z" fill="#FBBF24" fill-opacity=".15" stroke="#FBBF24"/><path d="M32 22v15" stroke="#FBBF24"/><circle cx="32" cy="45" r="2.4" fill="#FBBF24" stroke="none"/>
    """,
    "moos-phone": """
    <rect x="16" y="6" width="32" height="52" rx="10" fill="url(#nova)" fill-opacity=".12"/><rect x="16" y="6" width="32" height="52" rx="10"/>
    <path d="M27 13h10M27 51h10M25 29c3-4 7-4 10-1l3 3m1 4c-3 4-7 4-10 1l-3-3"/>
    """,
}


def document(body: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <!-- Original MoOS Nova symbol, © Moalfarras. No external logo or font glyph. -->
  <style id="current-color-scheme" type="text/css">
    .ColorScheme-Highlight {{ color: {P["blue"]}; }}
    .ColorScheme-Text {{ color: {P["text"]}; }}
  </style>
  <defs>
    <linearGradient id="nova" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{P["cyan"]}"/><stop offset="0.52" stop-color="{P["blue"]}"/><stop offset="1" stop-color="{P["violet"]}"/>
    </linearGradient>
  </defs>
  <rect x="3" y="3" width="58" height="58" rx="17" fill="{P["surface"]}" fill-opacity=".20" stroke="{P["cyan"]}" stroke-opacity=".14"/>
  <g fill="none" stroke="url(#nova)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
{body.strip()}
  </g>
</svg>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in SYMBOLS.items():
        (OUT / f"{name}.svg").write_text(document(body), encoding="utf-8", newline="\n")
    print(f"generated {len(SYMBOLS)} Nova symbolic icons")


if __name__ == "__main__":
    main()

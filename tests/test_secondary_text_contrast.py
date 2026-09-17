#!/usr/bin/env python3
"""Gate: the ink first-party apps use for SECONDARY text is readable on every shipped scheme.

WHY THIS EXISTS

Descriptions, navigation labels, hints, the sentence under a hero title: four first-party apps
(Mo AI, Mo Store, Welcome, the Installer) painted all of it with
`Kirigami.Theme.disabledTextColor` — the DISABLED role. KColorScheme derives that role by fading
the text 65% toward the background and tinting it ([ColorEffects:Disabled] in every MoOS scheme).
Computed from the shipped schemes, as secondary text it measured

    1.6 : 1   on the four light schemes        2.2 – 2.4 : 1   on the dark ones

against the 4.5:1 WCAG AA asks of normal-size text. Rendered from source, Mo Store's hero sentence
was close to invisible on the default light theme. Every gate was green: the gate on these tokens
required them to FOLLOW THE THEME (which the disabled role does), not to be legible.

MoOS Settings already had it right — `mutedColor: Qt.rgba(textColor.r, …, 0.72)`. All five apps
now derive their secondary ink the same way, and this gate does the arithmetic:

  * finds each app's secondary-ink token and reads its alpha;
  * composites the theme's text colour at that alpha over the view AND the window background of
    EVERY scheme under usr/share/color-schemes;
  * requires 4.5:1. A new palette or a "softer" alpha that drops below it fails here, by name.

It also refuses the disabled role as the binding of any of those tokens.
"""

from __future__ import annotations

import configparser
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "system_files/usr/share/moos/apps"
SCHEMES = ROOT / "system_files/usr/share/color-schemes"
AA = 4.5

# app -> the token that paints text a person reads (not placeholders, not disabled controls)
TOKENS = {"moai": "textLo", "store": "txt2", "welcome": "txt2", "installer": "txt2",
          "settings": "mutedColor"}


def luminance(colour: tuple[float, float, float]) -> float:
    def channel(value: float) -> float:
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(colour[0]) + 0.7152 * channel(colour[1]) + 0.0722 * channel(colour[2])


def contrast(one, other) -> float:
    high, low = sorted((luminance(one), luminance(other)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def over(foreground, background, alpha: float):
    return tuple(foreground[i] * alpha + background[i] * (1 - alpha) for i in range(3))


def token_alpha(app: str, token: str) -> tuple[float | None, str]:
    text = (APPS / app / "main.qml").read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
    match = re.search(rf"readonly\s+property\s+color\s+{token}\s*:\s*([^\n]+(?:\n\s{{20,}}[^\n]+)*)", code)
    if not match:
        return None, "missing"
    binding = " ".join(match.group(1).split())
    if "disabledTextColor" in binding:
        return None, binding
    alpha = re.search(r"Qt\.rgba\(\s*(?:Kirigami\.Theme\.)?textColor\.r\s*,[^)]*?,\s*([0-9.]+)\s*\)", binding)
    return (float(alpha.group(1)) if alpha else None), binding


def main() -> int:
    errors: list[str] = []
    schemes = sorted(SCHEMES.glob("*.colors"))
    if len(schemes) < 8:
        print(f"GATE FAIL: expected the MoOS colour schemes under {SCHEMES.relative_to(ROOT)}, "
              f"found {len(schemes)}")
        return 1
    worst = (99.0, "", "")
    for app, token in TOKENS.items():
        alpha, binding = token_alpha(app, token)
        if alpha is None:
            errors.append(f"{app}: `{token}` must be the theme's text colour at an alpha "
                          f"(Qt.rgba(Kirigami.Theme.textColor.r, …, a)); it is `{binding}`. The "
                          "disabled role measures 1.6:1 as secondary text on the light schemes.")
            continue
        for scheme in schemes:
            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = str
            parser.read(scheme, encoding="utf-8")
            for colour_set in ("Colors:View", "Colors:Window"):
                rgb = lambda key: tuple(int(v) for v in parser[colour_set][key].split(","))  # noqa: E731
                background, text = rgb("BackgroundNormal"), rgb("ForegroundNormal")
                value = contrast(over(text, background, alpha), background)
                if value < worst[0]:
                    worst = (value, app, f"{scheme.stem} {colour_set}")
                if value < AA:
                    errors.append(f"{app}: `{token}` at {alpha} is {value:.2f}:1 on {scheme.stem} "
                                  f"[{colour_set}] — under {AA}:1. Raise the alpha, or fix the "
                                  "scheme's text/background pair.")
    if errors:
        print("GATE FAIL: tests/test_secondary_text_contrast.py")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"secondary-text contrast gate passed ({len(TOKENS)} apps × {len(schemes)} schemes; "
          f"lowest {worst[0]:.2f}:1 — {worst[1]} on {worst[2]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

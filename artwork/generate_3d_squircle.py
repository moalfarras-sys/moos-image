#!/usr/bin/env python3
"""DEPRECATED — superseded by artwork/generate_moos_app_icons.py.

The MoOS application marks are theme-baked Liquid Glass SVGs with KDE colour
roles (not hardcoded RGB squircles).  Regenerating with this script would
overwrite the family with non-adaptive PNGs and break palette baking.

Use:
    python3 artwork/generate_moos_app_icons.py
    python3 artwork/generate_moos_themes.py
"""

raise SystemExit(
    "generate_3d_squircle.py is retired. "
    "Use artwork/generate_moos_app_icons.py for Liquid Glass app marks."
)

# Mo AI companion artwork

This directory owns the original Mo AI companion artwork. It uses the MoOS
palette and contains no third-party mascot, logo, emoji or font glyph.

`mascot-master.svg` is the editable source. `generate_moai_companion.py`
deterministically produces seven same-canvas runtime states: `idle`,
`attentive`, `thinking`, `success`, `warning`, `error` and `offline`.
`nova-companion-states.png` is the current generated review sheet, not a
historical screenshot.

The runtime QML preloads those states and cross-fades opacity. Motion is limited
to scene-graph transforms, stops with the hidden window and follows the MoOS
reduced-motion policy. `offline` means the Mo AI gateway is unavailable or has
no usable cloud-provider configuration; Mo AI is cloud-only.

Regenerate from the repository root:

```sh
python3 artwork/generate_moai_companion.py
python3 artwork/generate_moai_icon.py
```

The authoritative behavior and release gaps are in `PROJECT_STATE.md` and
`docs/DEVELOPMENT_PLAN.md`; executable artwork/runtime contracts live in the
tests.

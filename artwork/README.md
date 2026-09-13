# MoOS artwork sources

This directory contains only current editable sources, deterministic generators
and generated review sheets that are exercised by tests. Historical screenshots
belong in Git history, not in the working tree.

## Sources of truth

- `MOOS_UI2_DESIGN.md` — current Liquid Glass desktop design contract.
- `moos-design/tokens.json` and `moos-themes/palettes.json` — machine-readable
  design and palette tokens.
- `logo/` — official vector masters.
- `icons/mo-ai-1024.png` — protected commissioned Mo AI master.
- `master_icons/` — current first-party application masters.
- `moai/mascot-master.svg` — editable companion source.
- `moos-ui2/wallpapers/*-master*.png` — current wallpaper masters.

The review sheets under `moos-ui2/previews/` are retained because generators
and visual tests actively compare or inspect them. They are regenerated outputs,
not release evidence or old desktop captures.

## Regeneration

Run generators from the repository root. The common entry points are:

```sh
python3 artwork/generate_moos_app_icons.py
python3 artwork/generate_moos_symbolic_icons.py
python3 artwork/generate_moos_themes.py
python3 artwork/generate_moos_ui2.py
python3 artwork/generate_nova_visuals.py
python3 artwork/generate_nova_sounds.py
python3 artwork/verify_visuals.py
```

`generate_moos_app_icons.py` owns the ten first-party marks: Control Centre,
Store, Mo PC Remote, Updater, Themes, Installer, Recovery, Welcome, MoPlayer and
Mo AI. Third-party applications keep their own identity. The generator produces
the runtime icon ladders and the two current family/palette review sheets.

Palette icons are baked deliberately: relying on live recolouring made symbols
nearly invisible on measured dark Launcher surfaces. Contrast, byte identity,
runtime icon resolution, RTL layout and foreign-brand rejection are enforced by
the test suite and the image build.

Some package lookup filenames retain upstream technical names. Their bytes are
canonical MoOS artwork and the identity gates enforce that fact. Do not remove
those aliases without changing the package lookup path and proving every
user-visible surface.

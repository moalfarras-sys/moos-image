# MoOS Theme System Plan

Status is recorded against the current development branch. The theme system remains one UI2 engine with generated palette packages.

| Work item | Status | Evidence |
|---|---|---|
| Discover and quarantine post-marker home shadows | completed | `tests/test_theme_shadow_cleanup.py`; live `MoOSUI2Arena` moved to dated backup |
| Keep shadow cleanup idempotent and preserve unrelated user packages | completed | regression harness runs cleanup twice and preserves `PersonalTheme` |
| Remove task button rectangles in the shared generator | completed | `generate_moos_plasma_surfaces.py`, `generate_moos_themes.py`, and 16 regenerated UI2 packages |
| Keep task hover neutral while normal/minimized/focus show running state | completed | `python3 tests/test_moos_ui2.py` |
| Make wallpaper reconciliation wait for live containment readback | completed | `tests/test_theme_wallpaper_steady_state.py` and `tests/test_theme_wallpaper_readback.py` |
| Live switch and read back a family light theme | completed | live `org.moos.ui2.nova.light`, matching color/style/wallpaper readback |
| Remove the bordered box behind an open panel applet (`*-active-tab`) | completed | `tests/test_moos_ui2.py::test_open_applet_slot_is_never_a_bordered_box`; live launcher screenshot on `MoOSUI2NovaLight` |
| Stop every task state painting a flat tile slab | completed | `tests/test_moos_ui2.py::test_dock_task_states_never_paint_a_tile_box`; live dock read at 4K@225% |
| Write down and gate the MoOS rim scale across native controls | completed | `tests/test_moos_ui2.py::test_native_controls_hint_an_edge_instead_of_drawing_a_box` |
| Undo the two-slab bar: ONE centred capsule, merge not split | completed | `tests/test_moos_bar_single_panel.py` (8 cases incl. the exact 546 profile); live `PANELS=1` on Graphite/Amethyst/Aurora |
| Make moos-bar-apply idempotent and the sole writer of bar structure | completed | second run reports `no-change`; `merge_appletsrc` cannot create a containment |
| Apply the rim scale to the last always-on QML borders | completed | launcher plate, clock chip, hero clock emblem |
| Live logout/login persistence | pending | requires a session restart or reboot |
| 100/125/150/200% visual sweep | pending | not completed in this session |
| Full image build and CI-equivalent container gates | pending | repository gates still need a complete run |

Rollback: use branch/tag `backup/theme-system-2026-08-06` or `backup-theme-system-2026-08-06`. Live shadow previews are recoverable under `~/.local/share/MoOS/theme-shadow-backups/`.

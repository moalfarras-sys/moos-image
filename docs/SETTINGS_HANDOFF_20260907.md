# MoOS Settings — bounded product pass

Branch: `fix/settings-real-state-20260907`, isolated worktree based on `9c7ed7b7`.
Implementation commit: `f38c2450`. Evidence/handoff are the following documentation commit.
No merge, OS build, deployment, theme override or system preference change.

## Audit and fixes

| Surface | Finding and result |
| --- | --- |
| Overview | An unverified origin remained “Verifying”; no rollback still said “Rollback ready”; Bluetooth absence looked like “off”. Now distinguish signed/unverified/unknown, saved/absent/unknown rollback and absent/off/on Bluetooth. Official origin validation matches the update boundary. |
| Live state | Schema-only parsing accepted partial snapshots; missing/stale feeds could retain a green “Live system”. Validate structure and freshness, hide stale numbers, show a translated error with retry and recover automatically. The helper timestamps the completed publication. Storage-free bar now measures free space. |
| Connectivity | Captive portal/limited connections could be labelled online. Retain NetworkManager connectivity state and show sign-in/uncertain Internet/unknown distinctly. Network and Bluetooth rows show real state. |
| Devices | Sound row was static although PipeWire volume/mute was already available. It now shows the live output state. Real KDE modules continue to own detailed changes and absent-hardware explanations. |
| System | Storage, version and update rows were static. They now show live storage, installed version and staged restart state. “Time & region” only opened the clock: split Date & time and Language & region, with a fixed `kcm_regionandlang` route. |
| Recovery | Remove the unconditional protected badge and known-good image promise. Use the actual saved-deployment state. Staged updates never count as rollback targets. |
| Appearance, Apps, Privacy | Existing fixed graphical KCM/first-party destinations are retained. Every destination is checked against its executable and the installed Qt plugin tree. Missing destinations are disabled with an inline translated reason; unavailable overview shortcuts are hidden. No terminal/developer workflow or fake toggle was found in these pages. |
| Navigation/search | Rename the visible app to MoOS Settings. External-page icons explain the handoff to an existing module. Search now finds “audio” as well as “Sound”, clears correctly across navigation/Escape, resets scroll and keeps focused rows visible. |
| Arabic | Preserve the shared Locale authority already present on main. Fix double-mirrored text alignment/search-icon anchors, inset row content and isolate mixed Latin measurements in Arabic sentences. No new palette/theme. |

## Verification

- `tests/test_moos_settings.py`: 10 passing tests on the MoOS host, including executable JavaScript state/search/route tests, malformed/stale snapshots, official-origin matching, portal/offline/unknown states, missing modules and atomic publication.
- All 111 commands in the current `build.yml` Repo gates step pass on the host. Command results: `docs/evidence/settings-20260907/repo-gates.json`. Targeted Settings/experience/shell checks repeated after final UI corrections.
- Native QtTest keyboard events in **the review app's own window**: type `audio`, get one Sound result, Escape clears both model and visible field, repeated navigation/search stays synchronized. Both languages print `SETTINGS_INTERACTIONS_PASSED`.
- `tests/qml/settings-review.qml` loads the actual source QML with `moos-qml-shell` on Wayland and captures all eight pages. Actual read-only host data comes from the source status helper. `unavailable`, `empty-search`, and `missing-module` are explicitly injected test fixtures; the latter also exercises an unverified image, zero rollback and captive portal. They are not claims about the host.
- English review uses a temporary `XDG_CONFIG_HOME` with a copy of the active palette and English `plasma-localerc`: the real KDE session's Arabic locale overrides LANG alone. The owner's configuration remains untouched.
- Real routing: the source Settings `openRoute("moos://settings/audio")` opened the installed Sound module through the registered scheme; its 85% output matched the Settings summary (`sound-route-ar.png`). The new region route is covered by the source-router/availability agreement test and a real `kcm_regionandlang` launch.
- Before: `docs/evidence/settings-20260907/before-live.png`. After: `after-en/` and `after-ar/` in that directory. Frames inspected for layout, direction, mixed text and error/disabled states at 1400×900; the real language/region module was also opened and captured as `region-backend-ar.png`.

## Integration limits

Settings intentionally delegates detailed edits to the existing graphical system modules, with an external-page indicator. This pass does not embed/reimplement those upstream modules. Availability proves the shipped destination exists; it cannot guarantee every hardware device works. Hardware pairing, printer installation and the full 4K/HiDPI matrix remain hardware/release acceptance, not completed tests. Integrate the status helper, QML, launcher metadata and router together; old status documents are deliberately rejected. No release artifact was built or staged.

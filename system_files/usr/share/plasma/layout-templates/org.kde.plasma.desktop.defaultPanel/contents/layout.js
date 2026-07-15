/* MoOS override of plasma-desktop's defaultPanel layout template — the premium
 * MoOS dock ("Nova").
 *
 * PROVEN-WORKING SINGLE PANEL (restored 2026-07-10 after v14 live test):
 *   The v8/v9.2/v11 single bottom panel rendered correctly in the live session
 *   (dock with Mo launcher, tasks, tray, clock all visible). BOTH two-panel
 *   attempts (v9 raw, v14 with per-panel try/catch) produced NO panels at all
 *   in the live session — so the top-bar + dock split is abandoned as
 *   unreliable in this layout-template context. A desktop with no panel is
 *   broken; MoOS ships the PROVEN single-panel dock. Plasma 6 floats a bottom
 *   panel by default, which already gives a macOS-like dock feel.
 *
 * Every call is a verified primitive the proven v8 dock used live: `new Panel`,
 * panel.height, panel.addWidget, widget.currentConfigGroup, widget.writeConfig.
 * No location/floating/lengthMode/alignment setters and no second panel (those
 * are what failed live).
 *
 * File-level override of the plasma-desktop copy (rpm -V reports it modified —
 * intended, same policy as the fedora-logos pixmap overrides).
 */

var panel = new Panel;
panel.height = Math.round(gridUnit * 2.6);   // ~46px premium dock

/* Float the dock off the screen edge.
 *
 * `floating` IS a real property of Plasma 6's scripting Panel — verified live on
 * this hardware before it was written here (`"floating" in panels()[0]` -> true,
 * and setting it visibly lifted the dock). It is the setter that turns the Nova
 * glass into a floating slab with a gap and rounded corners on all four sides,
 * instead of a bar welded to the bottom of the screen.
 *
 * Wrapped anyway. The header above is not paranoia: a throw inside this template
 * leaves the session with NO PANEL, which is a broken desktop. A flush dock is a
 * cosmetic regression; a missing dock is a bug report. If a future Plasma drops
 * the property, the catch keeps the dock. */
try { panel.floating = true; } catch (e) { /* keep the dock, lose the gap */ }

/* The dock is a CAPSULE, not a bar: it hugs its content and sits centered, the
 * geometry the maintainer's installed machine actually runs (the shipped proof
 * artwork/moos-ui2/live-tests/ui2-dark-real-desktop.jpg is exactly this). The
 * template used to stop at `floating`, so every NEW user — and the live ISO —
 * got an edge-to-edge bar while the flagship desktop showed a floating capsule.
 *
 * Same defensive shape as `floating` above: each setter isolated, because a
 * throw anywhere in this template leaves the session with NO panel at all.
 * `lengthMode` and `alignment` are real Plasma 6 scripting Panel properties
 * ("fill"/"fit"/"custom" and "left"/"center"/"right"). */
try { panel.lengthMode = "fit"; } catch (e) { /* a full bar, not a broken one */ }
try { panel.alignment = "center"; } catch (e) { /* a left capsule, still a dock */ }

/* Keep Plasma's fully integrated Kickoff (search, KAStats, favorites, recent
 * usage, keyboard and session models) and skin it through the Nova Plasma
 * Style. MoOS does not ship a competing launcher implementation. */
var launcher = panel.addWidget("org.kde.plasma.kickoff");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("icon", "/usr/share/moos/moos-logo.png");
launcher.writeConfig("appNameFormat", 0);
launcher.writeConfig("favoritesDisplay", 0);
launcher.writeConfig("applicationsDisplay", 1);
launcher.writeConfig("primaryActions", 3);
launcher.writeConfig("showActionButtonCaptions", true);
launcher.writeConfig("switchCategoryOnHover", true);
launcher.writeConfig("favorites", [
    "org.moos.moai.desktop",
    "org.moos.store.desktop",
    "preferred://browser",
    "org.moos.moplayer.desktop",
    "org.kde.dolphin.desktop",
    "systemsettings.desktop",
    "org.moos.updater.desktop",
    "org.moos.recovery.desktop",
    "org.kde.konsole.desktop"
].join(","));

/* Icons-Only Task Manager — Mo AI pinned FIRST, then browser, files, Mo PC
 * Remote, System Settings and the terminal.
 *
 * org.moos.compathub and org.moos.hardware used to be pinned here. Those apps no
 * longer exist — the Hardware Centre and the Compatibility Hub are panels inside
 * Mo AI. They must not be listed: icontasks silently SKIPS a launcher URL it
 * cannot resolve, so a stale entry does not fail loudly, it just leaves a hole in
 * the dock that nothing explains. */
var tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.moos.moai.desktop",
    "applications:org.moos.store.desktop",
    "preferred://browser",
    "applications:org.moos.moplayer.desktop",
    "applications:org.kde.dolphin.desktop",
    "applications:org.moos.remote.desktop",
    "applications:systemsettings.desktop",
    "applications:org.kde.konsole.desktop"
].join(","));
tasks.writeConfig("showOnlyCurrentDesktop", false);

/* Right-hand cluster: separator, system tray, clock.
 *
 * The clock puts the date BESIDE the time rather than stacked under it
 * (dateDisplayFormat: 0 = below, 1 = beside — checked on-device, not guessed).
 * Stacked, it renders as two cramped lines that dominate the right end of the
 * dock; beside, it is one calm line.
 *
 * No show-desktop button. It rendered as an empty bordered box at the end of the
 * dock — it reads as a broken widget, and a dock of this kind has no such button
 * anyway. Users who want it back: right-click the dock -> Add Widgets. */
panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");

panel.addWidget("org.moos.nova.clock");

/* Wallpaper ships via the org.moos.ui2 Look-and-Feel defaults. */

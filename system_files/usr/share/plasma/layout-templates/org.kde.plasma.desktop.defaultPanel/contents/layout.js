/* MoOS override of plasma-desktop's defaultPanel layout template — the premium
 * MoOS dock ("Horizon Bar").
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
 * ONE PANEL IS THE DESIGN, NOT A LIMITATION. Rev 30 split the bar into a
 * centred dock capsule and a corner system capsule so the task area could hold
 * the true screen centre (Plasma has no flexible spacer applet, and the system
 * zone outweighs the brand button by ~450 physical px, measured). Shipped, it
 * read as two detached pieces of glass with a wide gap and the clock marooned
 * in the corner; the owner rejected it. Rev 33 merges it back: this template
 * seeds the one panel, and moos-bar-apply now MERGES any extra bottom panel
 * into it on every apply. The task area sitting slightly off geometric centre
 * is accepted; breaking the bar in half to fix it is not. Both files are
 * mirrors of /usr/share/moos/moos-bar.conf and the gates
 * tests/test_moos_bar_single_panel.py + verify_user_experience.py pin them
 * together.
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
panel.height = Math.round(gridUnit * 3.05);  // ~54px MoOS command dock

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

/* One button, one search surface. org.moos.brand keeps its historic package id
 * so upgrades replace the existing emblem in place, but it now provides
 * org.kde.plasma.launchermenu and owns the complete launcher. Its implementation
 * uses Plasma's native Kicker, KActivities and KRunner/Milou models; this is not
 * a second application database or a shell-command launcher. Keep the whole
 * block guarded: an absent optional applet must never leave a fresh session with
 * no panel. */
try {
    var launcher = panel.addWidget("org.moos.brand");
    launcher.currentConfigGroup = ["General"];
    launcher.writeConfig("favoritesClient", "org.moos.launcher.favorites");
    launcher.writeConfig("favoriteApps", [
        "org.moos.moai.desktop",
        "org.moos.store.desktop",
        "preferred://browser",
        "org.moos.moplayer.desktop",
        "org.kde.dolphin.desktop",
        "systemsettings.desktop",
        "org.moos.updater.desktop",
        "org.moos.recovery.desktop"
    ].join(","));
    launcher.writeConfig("defaultPage", 0);
    launcher.writeConfig("showRecent", true);
    launcher.writeConfig("compactTiles", false);
    /* Popup geometry belongs to the applet's root Configuration group, not
     * General. Seed it for a brand-new profile too: otherwise the launcher is
     * visually 792x576 through its QML minimum, but live readback remains zero
     * until the user opens/resizes it for the first time. */
    launcher.currentConfigGroup = [];
    launcher.writeConfig("popupWidth", 792);
    launcher.writeConfig("popupHeight", 576);
} catch (e) { /* the bar survives launcherless */ }

/* Icons-Only Task Manager — Mo AI pinned FIRST, then browser, files, Mo PC
 * Remote, System Settings and the terminal.
 *
 * ONE remote icon, not two. Mo PC Remote and Fast Remote used to sit side by
 * side in the dock — two glyphs for one feature, which reads as clutter, not
 * power. They are now merged: Fast Remote lives INSIDE Mo PC Remote — a toggle
 * switch in its panel AND a right-click jump-list action (Desktop Actions in
 * org.moos.remote.desktop) — so the single Mo PC Remote icon is the whole
 * remote-control surface. org.moos.fastremote.desktop is kept NoDisplay only to
 * back the Meta+R global shortcut; it is deliberately NOT pinned here.
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
    "applications:org.moos.remote.desktop"
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
var systray = panel.addWidget("org.kde.plasma.systemtray");
// MoOS keeps the everyday device toggles one click away in the status area
// instead of buried behind the tray arrow — reaching Wi-Fi, Bluetooth, volume
// and brightness is the whole point of a status tray, and hiding them is the
// single most common "where is my Bluetooth" complaint. The keyboard/language
// indicator is pinned too: with several layouts configured it can drop out of
// the tray entirely, so it belongs in the always-shown list. Everything else
// stays auto (shown only when it has something to say). This is the Apple-style
// "control centre in the corner" without a custom plasmoid. This list is a
// mirror of moos-bar.conf [tray] shownItems; the gate keeps them equal.
systray.currentConfigGroup = ["General"];
systray.writeConfig("shownItems", "org.kde.plasma.networkmanagement,org.kde.plasma.volume,org.kde.plasma.notifications,org.kde.plasma.keyboardlayout");
// extraItems = items the tray KNOWS about; each one's own Active/Passive status
// then decides whether it is out or behind the arrow. The context island must be
// here and must NOT be in shownItems: forcing it visible would make permanent
// the one thing it exists to avoid.
systray.writeConfig("extraItems", "org.moos.island");

panel.addWidget("org.moos.nova.clock");

/* Wallpaper ships via the org.moos.ui2 Look-and-Feel defaults. */

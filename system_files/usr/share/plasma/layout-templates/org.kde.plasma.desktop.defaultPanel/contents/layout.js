/* MoOS override of plasma-desktop's defaultPanel layout template — the
 * PREMIUM, macOS-caliber two-panel desktop shell ("Nova").
 *
 * WHY THIS PATH: the Look-and-Feel contents/layouts mechanism produced NO
 * panel in earlier live tests, while the stock defaultPanel template path is
 * PROVEN to work on this exact image lineage (a normal panel appeared). So
 * MoOS brands the template plasmashell actually loads. This is a file-level
 * override of the plasma-desktop copy; rpm -V will report it as modified —
 * intended, same policy as the fedora-logos pixmap overrides.
 *
 * Layout: a thin TOP menu-bar (macOS-style) + a floating, centered BOTTOM
 * dock. Both are built with the desktop-scripting `Panel` object, which the
 * defaultPanel template runs inside plasmashell.
 *
 * ============================ VERIFIED API FACTS ============================
 * Every call below was verified against KDE source / docs on 2026-07-10.
 *
 * Panel scripting object Q_PROPERTYs — plasma-workspace shell/scripting/panel.h
 *   location(QString RW) alignment(QString RW) offset(int RW)
 *   lengthMode(QString RW) length(int RW) minimumLength/maximumLength(int RW)
 *   height(int RW) hiding(QString RW) floating(bool RW) screen(int RW)
 *   formFactor(QString RO). Source:
 *   https://invent.kde.org/plasma/plasma-workspace/-/raw/master/shell/scripting/panel.h
 *
 * `new Panel` may be called MULTIPLE times in one layout.js → multiple
 *   independent panels. Source (KDE scripting API reference):
 *   https://develop.kde.org/docs/plasma/scripting/api/
 *
 * Valid string values — plasma-workspace shell/scripting/panel.cpp comparisons:
 *   location  : "top" "bottom" "left" "right" "floating"
 *   lengthMode: "fill" "fit" "custom"        alignment: "left" "center" "right"
 *   hiding    : "none" "autohide" "dodgewindows" "windowsgobelow"
 *
 * addWidget("plugin.id") returns a Widget; configure it with
 *   widget.currentConfigGroup = ["Group"]; widget.writeConfig(key, value).
 *   Source: https://develop.kde.org/docs/plasma/scripting/
 *
 * Plasmoid ids (metadata.json, plasma-desktop / plasma-workspace):
 *   org.kde.plasma.kickoff        org.kde.plasma.icontasks (Id confirmed)
 *   org.kde.plasma.panelspacer    org.kde.plasma.systemtray
 *   org.kde.plasma.digitalclock   org.kde.plasma.kimpanel
 *   panelspacer config key: "expanding" (bool, default true) — when true the
 *   spacer eats all free space. Source: plasma-workspace applets/panelspacer/main.xml
 *
 * icontasks REUSES taskmanager's config (metadata X-Plasma-RootPath =
 *   org.kde.plasma.taskmanager). Verified keys in
 *   plasma-desktop applets/taskmanager/main.xml:
 *     launchers (StringList) — accepts "preferred://browser" and
 *                              "applications:<id>.desktop" entries
 *     showOnlyCurrentDesktop (Bool, default true)
 *     fill (Bool, default true)   iconSpacing (Int, default 1)
 *   NOTE: Plasma 6 has NO "launchInPlace" key and NO "iconSize" key — icon
 *   size is derived from panel thickness, so the dock's HEIGHT sets it.
 *   Unresolvable launcher URLs are silently skipped by icontasks (no crash).
 *
 * gridUnit / languageId are globals provided by the scripting engine (used by
 * the upstream template too). No exotic calls — every line is a verified,
 * plain property assignment or addWidget/writeConfig.
 * ===========================================================================
 */

var gu = gridUnit;                        // px per Plasma grid unit (DPI-aware)
var TOP_HEIGHT  = Math.round(gu * 1.6);   // ~28px thin menu-bar
var DOCK_HEIGHT = Math.round(gu * 3.1);   // ~56px floating dock (large icons)

/* ---------- TOP PANEL: the macOS menu-bar analog --------------------------
 * Thin, NOT floating, spans the full width (lengthMode "fill"), pinned to the
 * top edge. Far left: the MoOS launcher (Apple-menu analog). An expanding
 * spacer pushes the status cluster (system tray + clock) to the far right. */
var top = new Panel;
top.location = "top";
top.floating = false;
top.height = TOP_HEIGHT;
top.lengthMode = "fill";

// MoOS launcher wears the MoOS emblem instead of the KDE logo.
var launcher = top.addWidget("org.kde.plasma.kickoff");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("icon", "/usr/share/moos/moos-logo.png");

// Expanding spacer (default expanding=true; set explicitly to document intent).
var topSpacer = top.addWidget("org.kde.plasma.panelspacer");
topSpacer.currentConfigGroup = ["General"];
topSpacer.writeConfig("expanding", true);

/* Optional Input-Method panel, added to the right cluster only for locales
 * whose language pulls in an IME backend (kept verbatim from upstream). MoOS
 * is bilingual AR|EN and neither is in the list, so this is a no-op here — it
 * stays for correctness on other installs. */
var imeLangs = ["as", "bn", "bo", "brx", "doi", "gu", "hi", "ja", "kn", "ko",
                "kok", "ks", "lep", "mai", "ml", "mni", "mr", "ne", "or", "pa",
                "sa", "sat", "sd", "si", "ta", "te", "th", "ur", "vi",
                "zh_CN", "zh_TW"];
if (imeLangs.indexOf(languageId) != -1) {
    top.addWidget("org.kde.plasma.kimpanel");
}

top.addWidget("org.kde.plasma.systemtray");
top.addWidget("org.kde.plasma.digitalclock");

/* ---------- BOTTOM DOCK: the floating, centered "island" dock -------------
 * Floating, shrinks to its contents (lengthMode "fit") and centers — the
 * signature macOS look. The Icons-Only Task Manager is the ONLY widget; its
 * thickness (DOCK_HEIGHT) determines the icon size. */
var dock = new Panel;
dock.location = "bottom";
dock.floating = true;
dock.height = DOCK_HEIGHT;
dock.lengthMode = "fit";
dock.alignment = "center";

var tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
/* Mo AI is pinned FIRST — the star of the dock — then the browser, files, the
 * MoOS hubs, System Settings and the terminal. StringList is stored as a
 * comma-joined string (icontasks re-splits on commas); this matches the
 * proven pattern from the previous working template. */
tasks.writeConfig("launchers", [
    "applications:org.moos.moai.desktop",
    "preferred://browser",
    "applications:org.kde.dolphin.desktop",
    "applications:org.moos.compathub.desktop",
    "applications:org.moos.hardware.desktop",
    "applications:systemsettings.desktop",
    "applications:org.kde.konsole.desktop"
].join(","));
// Show tasks from every virtual desktop (default shows current desktop only).
tasks.writeConfig("showOnlyCurrentDesktop", false);

/* Desktop wallpaper (NovaHorizon) is intentionally NOT set here: this template
 * only builds panels, exactly like the upstream defaultPanel template. The
 * wallpaper ships via the org.moos.nova Look-and-Feel defaults
 * ([Wallpaper] Image=NovaHorizon) — unchanged by this file. */

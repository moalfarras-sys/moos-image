/*
 * MoOS Nova — default desktop layout (Plasma 6)
 * org.moos.nova/contents/layouts/org.kde.plasma.desktop-layout.js
 *
 * WHEN THIS RUNS (important):
 *   This script is NOT read on every boot. Plasma executes it only when the
 *   Global Theme is applied WITH "Desktop and window layout" checked
 *   (System Settings -> Colors & Themes -> Global Theme, or
 *   `plasma-apply-lookandfeel --apply org.moos.nova`), AND on the very first
 *   plasmashell start (no plasma-org.kde.plasma.desktop-appletsrc yet) when
 *   org.moos.nova is the distro default Look-and-Feel, i.e.
 *   [KDE] LookAndFeelPackage=org.moos.nova in the system kdeglobals defaults.
 *   Existing users keep their layout — this only shapes NEW sessions.
 *   Ref: https://userbase.kde.org/Plasma/Create_a_Look_and_Feel_Package
 *
 * VERIFIED API FACTS (all checked 2026-07-09, Plasma 6 / master):
 *  1. Panel scripting object: `new Panel`, r/w props location, height,
 *     hiding, alignment, offset, lengthMode ("fill"|"fit"|"custom", since 6.0),
 *     length, minimumLength, maximumLength; containment props
 *     wallpaperPlugin, currentConfigGroup; functions addWidget(),
 *     writeConfig(), reloadConfig(); globals desktops(), screenGeometry(),
 *     gridUnit, languageId.
 *     Source: https://develop.kde.org/docs/plasma/scripting/api/
 *  2. `panel.floating` IS scriptable in Plasma 6:
 *     Q_PROPERTY(bool floating READ floating WRITE setFloating) on the
 *     scripting Panel class (inherits Containment).
 *     Source: https://github.com/KDE/plasma-workspace/blob/master/shell/scripting/panel.h
 *  3. Widget order & plugin ids mirror KDE's own Plasma 6 default panel
 *     template (kickoff, icontasks, marginsseparator, systemtray,
 *     digitalclock, showdesktop; we drop the pager for a cleaner look):
 *     Source: https://github.com/KDE/plasma-desktop/blob/master/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js
 *  4. Kickoff icon config: entry "icon" (String, group [General], default
 *     "start-here-kde-symbolic"). Absolute file paths are accepted as icon
 *     sources.
 *     Source: https://github.com/KDE/plasma-desktop/blob/master/applets/kickoff/main.xml
 *  5. Task manager launchers: entry "launchers" (StringList, group
 *     [General]); launcher URL format is "preferred://browser" /
 *     "applications:<desktop-file-id>" as seen in its default value
 *     "applications:systemsettings.desktop,...,preferred://filemanager,preferred://browser".
 *     Source: https://github.com/KDE/plasma-desktop/blob/master/applets/taskmanager/main.xml
 *  6. Wallpaper per containment: set wallpaperPlugin = "org.kde.image",
 *     then currentConfigGroup = ["Wallpaper", "org.kde.image", "General"]
 *     and writeConfig("Image", ...). The "Image" entry is
 *     "Wallpaper image path or wallpaper name" (String), so a wallpaper
 *     *package* directory like /usr/share/wallpapers/NovaHorizon is valid.
 *     Sources: https://github.com/KDE/plasma-workspace/blob/master/wallpapers/image/imagepackage/contents/config/main.xml
 *              https://develop.kde.org/docs/plasma/scripting/  (writeConfig pattern)
 */

// ---------------------------------------------------------------------------
// Desktop containments: Nova Horizon wallpaper on every screen/desktop
// ---------------------------------------------------------------------------
var allDesktops = desktops();
for (var i = 0; i < allDesktops.length; i++) {
    var d = allDesktops[i];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/NovaHorizon/");
    d.reloadConfig();
}

// ---------------------------------------------------------------------------
// ONE bottom panel — floating, 44 px, MoOS widget set
// ---------------------------------------------------------------------------
var panel = new Panel;
panel.location = "bottom";
panel.height = 44;
panel.floating = true;      // verified scriptable, see fact (2)
panel.hiding = "none";
panel.lengthMode = "fill";

// Mirror KDE's default-panel 21:9 cap so ultrawide screens do not get a
// comically long floating bar (same math as fact (3) reference).
var maximumAspectRatio = 21 / 9;
if (panel.formFactor === "horizontal") {
    var geo = screenGeometry(panel.screen);
    var maximumWidth = Math.ceil(geo.height * maximumAspectRatio);
    if (geo.width > maximumWidth) {
        panel.alignment = "center";
        panel.lengthMode = "custom";
        panel.minimumLength = maximumWidth;
        panel.maximumLength = maximumWidth;
    }
}

// --- App launcher (Kickoff) with the MoOS logo ----------------------------
var kickoff = panel.addWidget("org.kde.plasma.kickoff");
kickoff.currentConfigGroup = ["General"];
// moos-logo.png ships in this image (build.sh installs system_files ->
// /usr/share/moos/moos-logo.png). If it were ever missing, Kickoff just
// shows an empty button — nothing breaks.
kickoff.writeConfig("icon", "/usr/share/moos/moos-logo.png");
kickoff.reloadConfig();

// --- Icons-only task manager with MoOS default pins -----------------------
var tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers",
    "preferred://browser," +
    "applications:org.kde.dolphin.desktop," +
    "applications:org.kde.konsole.desktop");
tasks.reloadConfig();

// --- Right-hand cluster ----------------------------------------------------
panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");
panel.addWidget("org.kde.plasma.showdesktop");

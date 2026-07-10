/* MoOS override of plasma-desktop's defaultPanel layout template — the premium
 * macOS-style MoOS shell: a TOP MENU BAR + a floating BOTTOM DOCK ("Nova").
 *
 * ---------------------------------------------------------------------------
 * WHY THIS EXACT SHAPE (2026-07-10, rebuilt after a source audit of KDE)
 * ---------------------------------------------------------------------------
 * The v9 two-panel attempt produced NO panels: some statement threw and, with
 * the whole script running as one QJSEngine program, an uncaught throw aborts
 * EVERYTHING, leaving zero panels (a broken desktop). The old file guessed the
 * culprit was `floating` / `lengthMode="fit"` / `alignment="center"`. That
 * guess was WRONG — an audit of the actual KDE scripting class proves all
 * three are real, writable properties:
 *
 *   plasma-workspace/shell/scripting/panel.h  (verified verbatim):
 *     Q_PROPERTY(QString  location   READ location   WRITE setLocation)
 *     Q_PROPERTY(int      height     READ height     WRITE setHeight)
 *     Q_PROPERTY(QString  alignment  READ alignment  WRITE setAlignment)
 *     Q_PROPERTY(int      offset     READ offset     WRITE setOffset)
 *     Q_PROPERTY(QString  lengthMode READ lengthMode WRITE setLengthMode)
 *     Q_PROPERTY(bool     floating   READ floating   WRITE setFloating)
 *   panel.cpp: Panel::floating() defaults to readEntry("floating", true).
 *
 * So none of those setters throw merely by existing. To make TWO panels
 * RELIABLE (requirement #1 = panels MUST render) we instead defend against
 * *any* runtime throw by isolating each panel in its own try/catch, so a
 * failure while building one panel can never abort the other.
 *
 * try/catch IS safe here: Plasma desktop scripting was ported to QJSEngine
 * (KDE Phabricator D13112, "100% API compatible"), and QJSEngine is a full
 * ECMAScript engine — try/catch/finally are standard and supported. A failed
 * addWidget surfaces as a normal JS TypeError (calling .writeConfig on a null
 * widget), which the surrounding catch swallows.
 *
 * ---------------------------------------------------------------------------
 * ORDERING DECISIONS (each cites its source)
 * ---------------------------------------------------------------------------
 *  1. `location` is set BEFORE any addWidget.
 *     Source: KDE official scripting example (develop.kde.org .../scripting/
 *     examples/) shows exactly:
 *         const panel = new Panel
 *         panel.location = "top";
 *         panel.height = Math.round(gridUnit * 1.5);
 *         panel.addWidget("org.kde.plasma.appmenu");
 *  2. Two panels, each `location`+`height`(+`alignment`) set before widgets.
 *     Source: KDE UserBase "Unity-like look and feel … Desktop Scripting API"
 *     tutorial builds a top panel AND a second panel, setting location /
 *     alignment / height before addWidget on each.
 *  3. Structural props (location, height, floating) set BEFORE addWidget;
 *     content-sized props (lengthMode="fit", alignment="center") set AFTER
 *     addWidget so "fit" measures the dock's REAL content width instead of an
 *     empty (0-width) panel. Rationale: panel.cpp setLengthMode drives the
 *     view's length from current contents.
 *  4. `new Panel` (no `plasma.` prefix, no parens) — the exact form the proven
 *     v8 single-panel MoOS dock used and that rendered live.
 *  5. Widget config uses currentConfigGroup=["General"] + writeConfig — the
 *     same primitive the proven v8 dock used for the kickoff icon & launchers.
 *
 * This is a file-level override of the plasma-desktop copy (rpm -V will report
 * it modified — intended, same policy as the fedora-logos pixmap overrides).
 *
 * CAVEAT: authored from KDE source + official examples; not yet re-verified in
 * a live plasmashell session. If, against the source evidence, a panel still
 * fails to appear, the try/catch guarantees the OTHER panel still renders, and
 * the fallback is documented at the bottom of this file.
 */

/* =====================================================================
 * TOP MENU BAR  — macOS-style, edge-attached, full width (~27px).
 * Uses only rock-solid primitives; lengthMode is left at its default
 * "fill" so the bar spans the whole screen edge like the macOS menu bar.
 * ===================================================================== */
try {
    var top = new Panel;
    top.location = "top";                       // BEFORE addWidget (KDE example)
    top.height = Math.round(gridUnit * 1.5);    // ~27px (KDE example uses 1.5)
    top.floating = false;                       // menu bar hugs the edge, no island

    /* Left: the MoOS emblem as the "Apple-menu" launcher. */
    var moMenu = top.addWidget("org.kde.plasma.kickoff");
    moMenu.currentConfigGroup = ["General"];
    moMenu.writeConfig("icon", "/usr/share/moos/moos-logo.png");

    /* Expanding spacer pushes the status cluster to the right edge.
     * panelspacer expands by default; set it explicitly for certainty. */
    var spacer = top.addWidget("org.kde.plasma.panelspacer");
    spacer.currentConfigGroup = ["General"];
    spacer.writeConfig("expanding", true);

    /* Right cluster: system tray then the clock (macOS menu-bar order). */
    top.addWidget("org.kde.plasma.systemtray");
    top.addWidget("org.kde.plasma.digitalclock");
} catch (topError) {
    /* Swallow so a menu-bar failure can never take the dock down with it. */
}

/* =====================================================================
 * BOTTOM DOCK — floating, centered, content-width island (~46px).
 * icontasks only: the tray & clock now live in the top bar, exactly like
 * macOS (menu-bar status up top, app dock at the bottom).
 * ===================================================================== */
try {
    var dock = new Panel;
    dock.location = "bottom";                   // BEFORE addWidget (KDE example)
    dock.height = Math.round(gridUnit * 2.6);   // ~46px premium dock (proven v8 value)
    dock.floating = true;                        // macOS floating island (also the default)

    /* Icons-Only Task Manager — Mo AI pinned FIRST (the star), then browser,
     * files, the MoOS hubs, System Settings and the terminal. icontasks
     * silently skips any launcher URL it cannot resolve (no crash). */
    var tasks = dock.addWidget("org.kde.plasma.icontasks");
    tasks.currentConfigGroup = ["General"];
    tasks.writeConfig("launchers", [
        "applications:org.moos.moai.desktop",
        "preferred://browser",
        "applications:org.kde.dolphin.desktop",
        "applications:org.moos.compathub.desktop",
        "applications:org.moos.hardware.desktop",
        "applications:systemsettings.desktop",
        "applications:org.kde.konsole.desktop"
    ].join(","));
    tasks.writeConfig("showOnlyCurrentDesktop", false);

    /* Content-width centering set AFTER addWidget so "fit" measures the real
     * icon row (an empty panel would fit to ~0). Both are verified-valid
     * writable properties (panel.h). If either misbehaves at runtime the
     * catch keeps the dock as a full-width floating panel — still a dock. */
    dock.alignment = "center";
    dock.lengthMode = "fit";
} catch (dockError) {
    /* Swallow: the addWidget above already ran, so the dock still exists even
     * if the fit/center tail threw. */
}

/* ---------------------------------------------------------------------------
 * FALLBACK (documented, not code): if live testing ever shows the two-panel
 * split failing, revert to the single proven bottom dock by deleting the TOP
 * block and the `alignment`/`lengthMode` tail, leaving one floating bottom
 * Panel with kickoff+icontasks+tray+clock — the exact v8 shape that rendered.
 *
 * Wallpaper (NovaHorizon) ships via the org.moos.nova Look-and-Feel defaults,
 * exactly like the upstream template — this file only builds the panels.
 * --------------------------------------------------------------------------- */

// Private Plasma-host input driver. Injected only into a temporary package copy.
// No shortcuts, settings, authentication or owner-session input are modified.
import QtQuick
import QtQuick.Window
import QtTest as Test

Item {
    id: driver
    required property var surface
    required property var field
    required property var appGrid
    required property var homeGrid
    required property var homeScroll
    required property var canvas
    required property var pages
    required property var navigation
    required property var categories
    required property var powerButton
    required property var powerMenu

    function textItem(item, value) {
        if (item.text === value) return item;
        for (const child of item.children || []) {
            const found = textItem(child, value);
            if (found) return found;
        }
        return null;
    }
    function verify(value, message) {
        if (!value) console.error("MOOS_ADAPTIVE_ASSERT " + message);
        check.verify(value, message);
    }
    function compare(actual, expected, message) {
        if (actual !== expected) console.error("MOOS_ADAPTIVE_ASSERT " + message
            + " actual=" + actual + " expected=" + expected);
        check.compare(actual, expected, message);
    }
    Test.TestCase { id: check; when: false; name: "MoOSAdaptiveLauncher" }
    Timer {
        interval: 1200
        running: true
        repeat: false
        onTriggered: {
            try {
                const v = driver.surface;
                const l = v.launcher;
                driver.Window.window.title = "MoOS Adaptive Input Gate";
                // Windowed hosts lack plasmashell's inherited RTL parent.
                v.LayoutMirroring.enabled = v.rtl;
                v.LayoutMirroring.childrenInherit = true;
                check.wait(100);
                driver.verify(v.width > 0 && v.height > 0, "real full representation");
                driver.verify(driver.canvas.x >= 0 && driver.canvas.y >= 0,
                             "canvas starts inside surface");
                driver.verify(driver.canvas.x + driver.canvas.width <= v.width + 1
                    && driver.canvas.y + driver.canvas.height <= v.height + 1,
                    "canvas fits surface");
                for (let p = 0; p < 4; ++p) {
                    const nav = v.navForPage(p);
                    driver.verify(nav.width >= 44 && nav.height >= 44, "44px navigation");
                }
                driver.verify(driver.appGrid.cellWidth >= 100, "readable application cells");
                driver.verify(driver.appGrid.columns >= 1 && driver.appGrid.columns <= 4,
                             "one through four columns");
                l.activePage = 1;
                check.wait(80);
                const allApps = driver.appGrid.count;
                driver.verify(l.appRootModel.count > 2, "native app categories are present");
                driver.categories.positionViewAtIndex(2, ListView.Contain);
                check.wait(80);
                const category = driver.categories.itemAtIndex(2);
                driver.verify(category && category.visible && category.height >= 44,
                    "native category is a visible touch target");
                check.mouseClick(category);
                check.wait(80);
                driver.compare(l.appsModelRow, 2, "pointer selects native category");
                driver.verify(driver.appGrid.model === l.appRootModel.modelForRow(2),
                    "grid consumes the actual selected Kicker model");
                driver.verify(driver.appGrid.count > 0 && driver.appGrid.count <= allApps,
                    "category has actual application entries");
                check.keyClick(v.rtl ? Qt.Key_Left : Qt.Key_Right);
                check.wait(80);
                driver.compare(l.appsModelRow, Math.min(3, l.appRootModel.count - 1),
                    "logical arrow changes category");
                v.focusCategory(1);
                check.wait(80);
                driver.compare(driver.appGrid.count, allApps, "All restores complete catalogue");
                driver.Window.window.requestActivate();
                check.tryCompare(driver.Window.window, "active", true);
                v.focusSearch();
                check.keyClick(Qt.Key_Down);
                driver.verify(driver.appGrid.activeFocus, "Down enters real app catalogue");
                check.keyClick(Qt.Key_Backtab, Qt.ShiftModifier);
                driver.verify(v.navForPage(1).activeFocus, "Backtab returns to current navigation");
                if (v.compact) {
                    check.keyClick(v.rtl ? Qt.Key_Right : Qt.Key_Left);
                    driver.verify(v.navForPage(0).activeFocus, "logical previous compact tab");
                } else {
                    check.keyClick(Qt.Key_Up);
                    driver.verify(v.navForPage(0).activeFocus, "previous wide navigation");
                }
                check.keyClick(Qt.Key_Return);
                driver.compare(l.activePage, 0, "keyboard changes page");
                // Qt touch input uses the actual ItemDelegate and native Kicker state.
                const apps = v.navForPage(1);
                const touch = check.touchEvent(apps);
                touch.press(0, apps, apps.width/2, apps.height/2).commit();
                touch.release(0, apps, apps.width/2, apps.height/2).commit();
                check.wait(80);
                driver.compare(l.activePage, 1, "touch changes page");
                driver.verify(apps.activeFocus, "touch focus follows selected page");
                v.focusSearch();
                for (const letter of "moos-adaptive-test") check.keyClick(letter);
                driver.compare(l.searchQuery, "moos-adaptive-test", "native text editing");
                check.keyClick(Qt.Key_Escape);
                driver.compare(l.searchQuery, "", "Escape clears query");
                if (v.compact) {
                    check.mouseClick(driver.powerButton);
                    check.wait(100);
                    driver.verify(driver.powerMenu.visible && driver.powerMenu.count > 0,
                                 "real session actions remain reachable");
                    check.keyClick(Qt.Key_Escape);
                    check.tryCompare(driver.powerMenu, "visible", false, 1000,
                                     "Escape dismisses power menu after its finite transition");
                }
                // Visit every real page; no program or session action is executed.
                for (let p = 0; p < 4; ++p) {
                    check.mouseClick(v.navForPage(p));
                    check.wait(30);
                    driver.compare(l.activePage, p, "all pages remain selectable");
                    driver.verify(v.navForPage(p).activeFocus, "pointer focus follows selected page");
                }
                l.activePage = 0;
                check.wait(100);
                const orbitTitle = driver.textItem(v, v.local("مدارك", "Your orbit"));
                driver.verify(orbitTitle !== null, "real Home section title exists");
                driver.compare(orbitTitle.effectiveHorizontalAlignment,
                    v.rtl ? Text.AlignRight : Text.AlignLeft,
                    "section text follows the logical leading edge once");
                console.info("MOOS_ADAPTIVE_INPUT_PASS " + JSON.stringify({
                    width: v.width, height: v.height, rtl: v.rtl,
                    compact: v.compact, columns: driver.appGrid.columns, motion: v.motionMedium,
                    homeContent: driver.homeScroll.contentHeight,
                    homeViewport: driver.homeScroll.height,
                    touch: true, keyboard: true, sessionMenu: v.compact,
                    nativeCategories: l.appRootModel.count - 1, categoryBrowsing: true
                }));
            } catch (error) {
                console.error("MOOS_ADAPTIVE_INPUT_FAIL " + String(error));
            }
        }
    }
}

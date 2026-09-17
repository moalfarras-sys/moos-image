/*
    MoOS Arrange — put the windows in front of you in order, in one action.

    SPDX-License-Identifier: GPL-2.0-or-later

    WHY A KWIN SCRIPT

    KWin scripts are the documented extension point for window management, and a
    script is loaded from disk, so MoOS adds one instead of patching anything.
    KWin already has edge tiling and a custom tile editor; what it has no answer
    for is "take the three windows I am looking at and lay them out", which is
    the one-action arrangement the MoOS plan asks for.

    THE SURFACE IS THE WINDOW MENU, NOT A NEW WINDOW

    registerUserActionsMenu() adds a submenu to the menu a person already gets
    from a title bar (right-click, or the window menu button). That makes this
    discoverable without inventing a popup, without taking a slot on the Bar,
    and without anything running while it is not used: the callback is invoked
    only when the menu opens. Shortcuts are registered as well for people who
    never open that menu.

    WHICH WINDOWS

    The normal, non-minimised windows on the CURRENT desktop and the SAME screen
    as the window the action started from, ordered top-most first, which is what
    "the windows in front of you" means in practice. Panels, docks, splash
    screens and windows that keep out of the task bar are never moved.

    WHY THE ASYMMETRIC LAYOUT HAS NO HANDED VERSION

    A "main pane plus two" layout has to decide which side the main pane takes,
    and on MoOS that is a reading-direction question: the answer differs for an
    Arabic desk and an English one. A KWin script has no access to the session
    locale - there is no Qt.locale() here and no import - so rather than hard-code
    one culture's answer or invent a config nobody will find, the main pane goes
    to the side the ACTIVE window is already nearest. The window being worked in
    stays where it is and grows, which is locale-free and is what a person
    expects from the window they just right-clicked.
*/

const NAME = "moos-arrange";

// MoOS Tokens space2 / space3, in logical pixels: the gap between two arranged
// windows, and the margin left around the whole arrangement.
const GAP = 8;
const MARGIN = 8;

function log(message) {
    // console.info is the one print that reaches the journal from a KWin script.
    console.info(NAME + ": " + message);
}

// KWin 6.7.5 has NO `window.onCurrentDesktop`. Reading it returns undefined, and
// undefined in the middle of an && chain quietly rejects every window - which is
// exactly what the first version of this script did, arranging nothing and saying
// so. Virtual-desktop membership is the `desktops` array, and an EMPTY array means
// "on all desktops", not "on none". Measured by printing the live window object.
function isOnCurrentDesktop(window) {
    const desktops = window.desktops;
    if (!desktops || desktops.length === 0) {
        return true;
    }
    return desktops.indexOf(workspace.currentDesktop) !== -1;
}

function isArrangeable(window) {
    return !!window
        && window.normalWindow
        && !window.minimized
        && !window.skipTaskbar
        && !window.skipSwitcher
        && !window.fullScreen
        && isOnCurrentDesktop(window)
        // `moveable` and `resizeable`, both with the e: `movable`/`resizable`
        // read as undefined here. Confirmed on the live window object.
        && window.moveable
        && window.resizeable;
}

// Top-most first. stackingOrder runs bottom to top, and "the windows in front of
// you" are the ones at the top of it.
function windowsOn(output) {
    const ordered = [];
    const stack = workspace.stackingOrder;
    for (let i = stack.length - 1; i >= 0; --i) {
        const window = stack[i];
        if (isArrangeable(window) && (!output || window.output === output)) {
            ordered.push(window);
        }
    }
    return ordered;
}

function anchor(window) {
    // MaximizeArea is the space a maximised window gets: the screen minus the
    // MoOS Bar and any other panel. Arranging into the full output would slide
    // every window under the Bar.
    return workspace.clientArea(KWin.MaximizeArea, window);
}

function place(window, x, y, width, height) {
    if (window.maximizeMode !== undefined && window.maximizeMode !== 0) {
        window.setMaximize(false, false);
    }
    window.frameGeometry = {
        x: Math.round(x), y: Math.round(y),
        width: Math.round(width), height: Math.round(height),
    };
}

// Lay windows out over `area` using a list of fractional rectangles.
// Each cell is [x, y, width, height] as a fraction of the usable area.
function layout(windows, cells, area) {
    const usableX = area.x + MARGIN;
    const usableY = area.y + MARGIN;
    const usableWidth = area.width - MARGIN * 2;
    const usableHeight = area.height - MARGIN * 2;
    const count = Math.min(windows.length, cells.length);
    for (let i = 0; i < count; ++i) {
        const cell = cells[i];
        // Half a gap is taken off each side of every shared edge, which is the
        // same as a full gap between neighbours and no gap at the outer edges.
        const left = cell[0] > 0 ? GAP / 2 : 0;
        const top = cell[1] > 0 ? GAP / 2 : 0;
        const right = cell[0] + cell[2] < 1 ? GAP / 2 : 0;
        const bottom = cell[1] + cell[3] < 1 ? GAP / 2 : 0;
        place(windows[i],
              usableX + usableWidth * cell[0] + left,
              usableY + usableHeight * cell[1] + top,
              usableWidth * cell[2] - left - right,
              usableHeight * cell[3] - top - bottom);
    }
    return count;
}

function columns(number) {
    const cells = [];
    for (let i = 0; i < number; ++i) {
        cells.push([i / number, 0, 1 / number, 1]);
    }
    return cells;
}

const QUARTERS = [[0, 0, 0.5, 0.5], [0.5, 0, 0.5, 0.5],
                  [0, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]];

// The main pane takes the side the leading window is already nearest, so the
// window a person is working in stays put and grows. See the note at the top.
function mainAndTwoCells(leader, area) {
    const centre = leader.frameGeometry.x + leader.frameGeometry.width / 2;
    const mainOnLeft = centre <= area.x + area.width / 2;
    const main = mainOnLeft ? [0, 0, 0.6, 1] : [0.4, 0, 0.6, 1];
    const sideX = mainOnLeft ? 0.6 : 0;
    return [main, [sideX, 0, 0.4, 0.5], [sideX, 0.5, 0.4, 0.5]];
}

function arrange(kind, startFrom) {
    const leader = startFrom || workspace.activeWindow;
    if (!leader) {
        log("nothing to arrange: no active window");
        return;
    }
    const area = anchor(leader);
    let windows = windowsOn(leader.output);
    if (windows.length === 0) {
        log("nothing to arrange on this screen");
        return;
    }
    // Whichever window the action started from leads the arrangement.
    const index = windows.indexOf(leader);
    if (index > 0) {
        windows.splice(index, 1);
        windows.unshift(leader);
    }

    let placed = 0;
    if (kind === "centre") {
        place(leader,
              area.x + area.width * 0.14, area.y + area.height * 0.10,
              area.width * 0.72, area.height * 0.80);
        placed = 1;
    } else if (kind === "main") {
        placed = layout(windows, mainAndTwoCells(leader, area), area);
    } else if (kind === "quarters") {
        placed = layout(windows, QUARTERS, area);
    } else {
        placed = layout(windows, columns(kind === "halves" ? 2 : 3), area);
    }
    log("arranged " + placed + " window(s) as " + kind);
}

// Bilingual, because MoOS ships its strings rather than Qt catalogues. The menu
// shows both so one desk reads correctly in either language.
const ACTIONS = [
    ["halves", "نصفان | Halves", "Meta+Alt+2"],
    ["thirds", "أثلاث | Thirds", "Meta+Alt+3"],
    ["quarters", "أرباع | Quarters", "Meta+Alt+4"],
    ["main", "نافذة رئيسية ونافذتان | Main and two", "Meta+Alt+1"],
    ["centre", "في المنتصف | Centre this window", "Meta+Alt+C"],
];

for (const action of ACTIONS) {
    const kind = action[0];
    registerShortcut("MoOS Arrange: " + kind, "MoOS Arrange: " + action[1],
                     action[2], function () { arrange(kind); });
}

registerUserActionsMenu(function (window) {
    if (!isArrangeable(window)) {
        return null;
    }
    const items = [];
    for (const action of ACTIONS) {
        const kind = action[0];
        items.push({
            text: action[1],
            triggered: function () { arrange(kind, window); },
        });
    }
    return { text: "رتّب النوافذ | Arrange windows", items: items };
});

log("ready");

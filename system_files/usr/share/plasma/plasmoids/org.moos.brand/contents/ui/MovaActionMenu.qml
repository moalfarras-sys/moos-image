/*
    SPDX-FileCopyrightText: 2013 Aurélien Gâteau <agateau@kde.org>
    SPDX-FileCopyrightText: 2014-2015 Eike Hein <hein@kde.org>
    SPDX-FileCopyrightText: 2024 ivan tkachenko <me@ratijas.tk>

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2

import org.kde.plasma.components as PC3

import "code/kicker-tools.js" as Tools

// Kicker's ActionMenu, presented inside the launcher's own window.
//
// Upstream opens a QMenu (PlasmaExtras.Menu). On the V3 touch screen a finger
// outside that separate Wayland popup did not close it, and the next tap was
// spent closing it instead of reaching the category or tile under the finger.
// An in-window Plasma menu closes on the first outside press, takes the
// launcher's typeface and size, and gives every row a finger-sized height.
// It is modal without a dimmer: that press only dismisses it. Passing it
// through let a dismissing tap launch the tile under the finger (Kate, V3). Kicker still owns every action ID, its arguments and
// what triggering does.
QtObject {
    id: root

    property Item visualParent
    property var delegate
    property string favoriteIdentity: ""
    property var nativeModel

    // See tools.js for a list of possible members
    property var actionList

    // Presentation only. labelFor(actionItem) may give a clearer local label
    // for a native action; it never changes the action ID it triggers.
    property string fontFamily: ""
    property int fontPixelSize: 14
    property int rowHeight: 48
    property var labelFor: null
    // A popup lives in the window overlay, outside the launcher's inherited
    // LayoutMirroring: without this an Arabic menu put its icons on the left
    // and its words against the wrong edge (V3, 2026-11-25).
    property bool mirrored: false

    readonly property bool opened: __menu ? __menu.opened : false

    property PC3.Menu __menu

    signal actionClicked(string actionId, var actionArgument)
    signal closed()

    onActionListChanged: {
        __refreshMenu();
    }

    onOpenedChanged: {
        if (!opened) {
            closed();
        }
    }

    function triggerAction(actionId: string, actionArgument: var): void {
        // The native model may retire a delegate while its menu is open.
        if (!delegate || !delegate.visible || delegate.index < 0
                || delegate.favoriteId !== favoriteIdentity || delegate.baseModel !== nativeModel) {
            if (__menu) __menu.close();
            return;
        }
        if (actionId === "_mova_move_earlier" || actionId === "_mova_move_later") {
            delegate.movePinned(actionId === "_mova_move_earlier" ? -1 : 1);
            return;
        }
        if (Tools.triggerAction(delegate.baseModel, delegate.index, actionId, actionArgument) === true) {
            delegate.interactionConcluded()
        }
    }

    // x/y are in visualParent's coordinates. Without them the menu sits
    // under the middle of its item, so the finger that opened it does not
    // cover its first row. The Popup keeps itself inside the window.
    function open(x: var, y: var): void {
        if (!actionList || !__menu || !visualParent) {
            return;
        }
        const px = x !== undefined ? x : (visualParent.width - __menu.implicitWidth) / 2;
        const py = y !== undefined ? y : visualParent.height * 0.62;
        __menu.popup(visualParent, px, py);
    }

    function close(): void {
        if (__menu) __menu.close();
    }

    function label(actionItem: var): string {
        const native = String(actionItem.text ?? "");
        if (typeof root.labelFor !== "function") return native;
        const local = root.labelFor(actionItem);
        return local ? String(local) : native;
    }

    function iconName(actionItem: var): string {
        // Kicker hands icon names as strings; anything else stays unpainted
        // rather than being coerced into a wrong name.
        return typeof actionItem.icon === "string" ? actionItem.icon : "";
    }

    function __refreshMenu(): void {
        if (__menu) {
            __menu.close();
            __menu.destroy();
            __menu = null;
        }

        if (!actionList) {
            return;
        }

        __menu = contextMenuComponent.createObject(root);

        __fillMenu(__menu, actionList);
    }

    // Rows start under the menu's own list so they are scene items before
    // addItem() places them in its content model.
    function __fillMenu(menu: PC3.Menu, actionItems: var): void {
        actionItems.forEach(actionItem => {
            if (actionItem.type === "separator") {
                const separator = contextSeparatorComponent.createObject(menu.contentItem);
                menu.addItem(separator);
                menu.content.push(separator);
            } else if (actionItem.subActions) {
                // This is a menu
                const submenu = contextMenuComponent.createObject(menu, {
                    title: root.label(actionItem)
                });
                __fillMenu(submenu, actionItem.subActions);
                menu.addMenu(submenu);
                menu.content.push(submenu);
            } else {
                const entry = contextMenuItemComponent.createObject(menu.contentItem, { actionItem });
                menu.addItem(entry);
                menu.content.push(entry);
            }
        });
    }

    readonly property list<QtObject> __data: [
        Component {
            id: contextMenuComponent

            PC3.Menu {
                // The created rows in action order, for review tooling.
                property var content: []
                // Popup.mirrored follows its locale: cascades and arrows.
                locale: Qt.locale(root.mirrored ? "ar" : "en_US")
                font.family: root.fontFamily
                font.pixelSize: root.fontPixelSize
                closePolicy: QQC2.Popup.CloseOnEscape | QQC2.Popup.CloseOnPressOutside
                modal: true
                dim: false
            }
        },

        Component {
            id: contextSeparatorComponent

            PC3.MenuSeparator {
                LayoutMirroring.enabled: root.mirrored
                LayoutMirroring.childrenInherit: true
            }
        },

        Component {
            id: contextMenuItemComponent

            PC3.MenuItem {
                id: entry
                required property var actionItem

                // The row's own layout: icon at the logical start, words
                // aligned to it.
                LayoutMirroring.enabled: root.mirrored
                LayoutMirroring.childrenInherit: true
                implicitHeight: Math.max(root.rowHeight,
                    contentItem.implicitHeight + topPadding + bottomPadding)
                font.family: root.fontFamily
                font.pixelSize: root.fontPixelSize
                font.weight: Font.Medium
                action: QQC2.Action {
                    text: root.label(entry.actionItem)
                    icon.name: root.iconName(entry.actionItem)
                    enabled: entry.actionItem.type !== "title" && (entry.actionItem.enabled ?? true)
                    checkable: entry.actionItem.checkable ?? false
                    checked: entry.actionItem.checked ?? false
                    onTriggered: root.triggerAction(entry.actionItem.actionId,
                        entry.actionItem.actionArgument)
                }
            }
        }
    ]
}

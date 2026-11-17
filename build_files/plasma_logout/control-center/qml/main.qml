/*
    SPDX-FileCopyrightText: 2011 Marco Martin <mart@kde.org>
    SPDX-FileCopyrightText: 2020 Konrad Materka <materka@gmail.com>
    SPDX-FileCopyrightText: 2026 Nathaniel Krebs <areyoufeelingitnowmrkrebs@gmail.com>

    SPDX-License-Identifier: LGPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.moos.ui as MoUI

import org.kde.draganddrop as DnD
import org.kde.kirigami as Kirigami
import org.kde.kitemmodels as KItemModels
import org.kde.ksvg as KSvg
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid

ContainmentItem {
    id: root

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool reverseLayout: Plasmoid.configuration.reverseIconOrder

    Layout.minimumWidth: cameraApplet ? 72 : nativeAttention ? 52 : 44
    Layout.minimumHeight: 44

    LayoutMirroring.enabled: !vertical && ((Application.layoutDirection === Qt.RightToLeft) !== reverseLayout)
    LayoutMirroring.childrenInherit: true

    readonly property alias systemTrayState: systemTrayState
    readonly property int itemSize: Kirigami.Units.iconSizes.smallMedium
    readonly property alias visibleLayout: centerEntry
    readonly property alias hiddenLayout: expandedRepresentation.hiddenLayout
    readonly property bool oneRowOrColumn: true

    readonly property alias hiddenModel: hiddenModel

    property var centerApplets: []
    property var cameraApplet: null
    readonly property bool centerHistoryVisible: systemTrayState.expanded && !expandedRepresentation.detailVisible
    readonly property var centerHistoryIds: expandedRepresentation ? expandedRepresentation.presentedNotificationIds : []
    onCenterHistoryVisibleChanged: synchronizeNotificationPresentation()
    onCenterHistoryIdsChanged: synchronizeNotificationPresentation()
    function synchronizeNotificationPresentation() {
        for (const applet of centerApplets) {
            if (applet && applet.Plasmoid.pluginName === "org.kde.plasma.notifications"
                    && typeof applet.moosCenterHistoryVisible === "boolean") {
                applet.moosCenterHistoryIds = centerHistoryVisible ? centerHistoryIds : [];
                applet.moosCenterHistoryVisible = centerHistoryVisible;
            }
        }
    }
    readonly property bool nativeAttention: attentionModel.count > 0
    function updateIndicators() {
        let camera = null;
        for (const applet of centerApplets) {
            if (!applet) continue;
            const owner = applet.Plasmoid;
            if (owner.pluginName === "org.kde.plasma.cameraindicator" && owner.status === PlasmaCore.Types.ActiveStatus) camera = applet;
        }
        cameraApplet = camera;
    }
    function registerApplet(applet) {
        if (applet && centerApplets.indexOf(applet) < 0) centerApplets = centerApplets.concat([applet]);
        Qt.callLater(updateIndicators);
        Qt.callLater(synchronizeNotificationPresentation);
    }
    function unregisterApplet(applet) {
        if (applet && typeof applet.moosCenterHistoryVisible === "boolean") {
            applet.moosCenterHistoryVisible = false;
            applet.moosCenterHistoryIds = [];
        }
        centerApplets = centerApplets.filter(item => item !== applet);
        Qt.callLater(updateIndicators);
    }
    function openNativeApplet(id) {
        for (const applet of centerApplets) {
            if (applet && applet.Plasmoid.pluginName === id) {
                systemTrayState.setActiveApplet(applet);
                return true;
            }
        }
        return false;
    }

    Component.onCompleted: {
        // We need all the plasmoiditems to be there for correct working of shortcuts.
        // Instantiators create the plasmoiditems: ensure this is done after
        // this containmentitem actually  exists so they can be immediately parented properly
        // set active and not the model, as this will cause an assert deep in Qt
        // Union hiddenInstantiator owns all accepted applets.
        hiddenInstantiator.active = true;
    }

    Connections {
        target: Plasmoid
        function onActivated() {
            systemTrayState.expanded = !systemTrayState.expanded;
        }
    }

    // Native status covers application notifiers as well as applets.
    KItemModels.KSortFilterProxyModel {
        id: attentionModel
        filterRoleName: "status"
        filterRowCallback: (row, parent) => {
            const status = sourceModel.data(sourceModel.index(row, 0, parent), filterRole);
            return status === PlasmaCore.Types.NeedsAttentionStatus || status === PlasmaCore.Types.RequiresAttentionStatus;
        }
        Component.onCompleted: sourceModel = Plasmoid.systemTrayModel
    }

    KItemModels.KSortFilterProxyModel {
        id: hiddenModel
        filterRoleName: "effectiveStatus"
        dynamicSortFilter: !systemTrayState.expanded
        filterRowCallback: (sourceRow, sourceParent) => {
            let value = sourceModel.data(sourceModel.index(sourceRow, 0, sourceParent), filterRole);
            return value === PlasmaCore.Types.PassiveStatus || value === PlasmaCore.Types.ActiveStatus
        }
        Component.onCompleted: sourceModel = Plasmoid.systemTrayModel // avoid unnecessary binding, it causes loops
    }

    // Re-evaluate filters when the popup closes to apply any status changes
    // that accumulated while the popup was open
    Connections {
        target: systemTrayState
        function onExpandedChanged() {
            if (!systemTrayState.expanded) {
                hiddenModel.invalidateFilter();
            }
        }
    }

    Instantiator {
        id: hiddenInstantiator
        // It's important that those are inactive at creation time
        // to not create plasmoiditems too soon
        active: false
        model: hiddenModel
        delegate: Connections {
            id: trayDelegate
            readonly property Connections nativeStatusObserver: Connections {
                target: trayDelegate.applet?.Plasmoid ?? null
                function onStatusChanged() { root.updateIndicators(); }
            }
            required property QtObject applet
            required property int row
            Component.onCompleted: root.registerApplet(applet)
            Component.onDestruction: root.unregisterApplet(applet)
            target: applet
            function onExpandedChanged(expanded: bool) {
                if (expanded) {
                    systemTrayState.setActiveApplet(applet, row)
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent

        onWheel: wheel => {
            // Don't propagate unhandled wheel events
            wheel.accepted = true;
        }

        SystemTrayState {
            id: systemTrayState
        }

        CurrentItemHighLight {
            location: Plasmoid.location
            parent: root
        }

        DnD.DropArea {
            anchors.fill: parent

            preventStealing: true

            /** Extracts the name of the system tray applet in the drag data if present
            * otherwise returns null*/
            function systemTrayAppletName(event) {
                if (event.mimeData.formats.indexOf("text/x-plasmoidservicename") < 0) {
                    return null;
                }
                const plasmoidId = event.mimeData.getDataAsByteArray("text/x-plasmoidservicename");

                if (!Plasmoid.isSystemTrayApplet(plasmoidId)) {
                    return null;
                }
                return plasmoidId;
            }

            onDragEnter: event => {
                if (!systemTrayAppletName(event)) {
                    event.ignore();
                }
            }

            onDrop: event => {
                const plasmoidId = systemTrayAppletName(event);
                if (!plasmoidId) {
                    event.ignore();
                    return;
                }

                if (Plasmoid.configuration.extraItems.indexOf(plasmoidId) < 0) {
                    const extraItems = Plasmoid.configuration.extraItems;
                    extraItems.push(plasmoidId);
                    Plasmoid.configuration.extraItems = extraItems;
                }
            }
        }


        // One panel entry. All native tray delegates live inside the popup.
        PC3.ToolButton {
            id: centerEntry
            objectName: "moosControlCenterEntry"
            anchors.centerIn: parent
            width: root.vertical ? root.width : root.Layout.minimumWidth
            height: root.vertical ? 44 : root.height
            icon.name: "moos-settings-symbolic"
            text: MoUI.Locale.local("مركز التحكم", "Control Center") + (root.cameraApplet ? " · " + root.cameraApplet.toolTipSubText : "")
            contentItem: RowLayout {
                spacing: 4
                // MoOS level glyph. Opening the center glides each knob to its
                // "tuned" position in a short stagger and lights it with the
                // native accent; closing returns it. Finite, event-driven, and
                // instantaneous when the owner turns animations off.
                Item {
                    objectName: "moosControlCenterGlyph"
                    Layout.alignment: Qt.AlignCenter
                    implicitWidth: 20; implicitHeight: 22
                    Repeater {
                        model: [[0.25, 0.72], [0.72, 0.28], [0.4, 0.62]]
                        Item {
                            id: level
                            required property int index
                            required property var modelData
                            y: index * 7; width: 20; height: 7
                            Rectangle {
                                y: 3; width: 20; height: 1.5; radius: .75
                                color: systemTrayState.expanded ? Qt.alpha(Kirigami.Theme.highlightColor, .55) : Kirigami.Theme.textColor
                                Behavior on color { ColorAnimation { duration: MoUI.Tokens.motionGeometry } }
                            }
                            Rectangle {
                                objectName: "moosControlCenterKnob"
                                x: (systemTrayState.expanded ? level.modelData[1] : level.modelData[0]) * 14
                                y: 1; width: 6; height: 6; radius: 3
                                color: systemTrayState.expanded ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                                border.width: 1; border.color: Kirigami.Theme.backgroundColor
                                Behavior on x { NumberAnimation { duration: MoUI.Tokens.motionEmphasis > 0 ? MoUI.Tokens.motionEmphasis + level.index * 50 : 0; easing.type: Easing.OutBack; easing.overshoot: 1.6 } }
                                Behavior on color { ColorAnimation { duration: MoUI.Tokens.motionGeometry } }
                            }
                        }
                    }
                }
                Kirigami.Icon { visible: !!root.cameraApplet; source: root.cameraApplet?.Plasmoid.icon ?? ""; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                Rectangle { visible: root.nativeAttention; Layout.preferredWidth: 5; Layout.preferredHeight: 5; radius: 2.5; color: Kirigami.Theme.highlightColor }
            }
            display: PC3.AbstractButton.IconOnly
            activeFocusOnTab: true
            checked: systemTrayState.expanded
            onClicked: systemTrayState.expanded = !systemTrayState.expanded
            PC3.ToolTip { text: parent.text }
            DragHandler {
                target: null
                xAxis.enabled: root.vertical
                yAxis.enabled: !root.vertical
                property real travel: 0
                onActiveTranslationChanged: if (active) travel = root.vertical ? activeTranslation.x : activeTranslation.y
                onCanceled: travel = 0
                onActiveChanged: {
                    if (active) travel = 0;
                    else {
                        const inward = (Plasmoid.location === PlasmaCore.Types.TopEdge || Plasmoid.location === PlasmaCore.Types.LeftEdge) ? travel > 40 : travel < -40;
                        if (inward) systemTrayState.expanded = true;
                    }
                }
            }
        }

        Timer {
            id: expandedSync
            interval: 100
            onTriggered: systemTrayState.expanded = dialog.visible;
        }

        //Main popup
        PlasmaCore.AppletPopup {
            id: dialog
            objectName: "popupWindow"
            visualParent: root
            popupDirection: switch (Plasmoid.location) {
                case PlasmaCore.Types.TopEdge:
                    return Qt.BottomEdge
                case PlasmaCore.Types.LeftEdge:
                    return Qt.RightEdge
                case PlasmaCore.Types.RightEdge:
                    return Qt.LeftEdge
                default:
                    return Qt.TopEdge
            }
            margin: (Plasmoid.containmentDisplayHints & PlasmaCore.Types.ContainmentPrefersFloatingApplets) ? Kirigami.Units.largeSpacing : 0

            Behavior on margin {
                NumberAnimation {
                    // Since the panel animation won't be perfectly in sync,
                    // using a duration larger than the panel animation results
                    // in a better-looking animation.
                    duration: Kirigami.Units.veryLongDuration
                    easing.type: Easing.OutCubic
                }
            }

            floating: Plasmoid.location == PlasmaCore.Desktop

            removeBorderStrategy: Plasmoid.location === PlasmaCore.Types.Floating
                ? PlasmaCore.AppletPopup.AtScreenEdges
                : PlasmaCore.AppletPopup.AtScreenEdges | PlasmaCore.AppletPopup.AtPanelEdges


            hideOnWindowDeactivate: !Plasmoid.configuration.pin
            visible: systemTrayState.expanded
            appletInterface: root

            backgroundHints: (Plasmoid.containmentDisplayHints & PlasmaCore.Types.ContainmentPrefersOpaqueBackground) ? PlasmaCore.AppletPopup.SolidBackground : PlasmaCore.AppletPopup.StandardBackground

            onVisibleChanged: {
                if (!visible) {
                    expandedSync.restart();
                } else {
                    dialog.requestActivate();
                    if (expandedRepresentation.plasmoidContainer.visible) {
                        expandedRepresentation.plasmoidContainer.forceActiveFocus();
                    } else if (expandedRepresentation.hiddenLayout.visible) {
                        expandedRepresentation.hiddenLayout.forceActiveFocus();
                    }
                }
            }
            mainItem: ExpandedRepresentation {
                id: expandedRepresentation

                Keys.onEscapePressed: event => {
                    systemTrayState.expanded = false
                }

                // Being there forces the items to fully load, and they will be reparented in the stack one by one, this item is *never* visible
                // it's important this item is parented to the popup, otherwise the full representation will be reparented every time the popup opens or closes
                Item {
                    id: preloadedStorage
                    visible: false
                }

                // Draws a line between the applet dialog and the panel
                KSvg.SvgItem {
                    id: separator
                    // Only draw for popups of panel applets, not desktop applets
                    visible: [PlasmaCore.Types.TopEdge, PlasmaCore.Types.LeftEdge, PlasmaCore.Types.RightEdge, PlasmaCore.Types.BottomEdge]
                        .includes(Plasmoid.location) && !dialog.margin
                    anchors {
                        topMargin: -dialog.topPadding
                        leftMargin: -dialog.leftPadding
                        rightMargin: -dialog.rightPadding
                        bottomMargin: -dialog.bottomPadding
                    }
                    z: 999 /* Draw the line on top of the applet */
                    elementId: (Plasmoid.location === PlasmaCore.Types.TopEdge || Plasmoid.location === PlasmaCore.Types.BottomEdge) ? "horizontal-line" : "vertical-line"
                    imagePath: "widgets/line"
                    // QTBUG-120464: Use AnchorChanges instead of bindings as it's officially supported: https://doc.qt.io/qt-6/qtquick-positioning-anchors.html#changing-anchors
                    states: [
                        State {
                            when: Plasmoid.location === PlasmaCore.Types.TopEdge
                            AnchorChanges {
                                target: separator
                                anchors {
                                    top: separator.parent.top
                                    left: separator.parent.left
                                    right: separator.parent.right
                                }
                            }
                            PropertyChanges {
                                separator.height: 1
                            }
                        },
                        State {
                            when: Plasmoid.location === PlasmaCore.Types.LeftEdge
                            AnchorChanges {
                                target: separator
                                anchors {
                                    left: separator.parent.left
                                    top: separator.parent.top
                                    bottom: separator.parent.bottom
                                }
                            }
                            PropertyChanges {
                                separator.width: 1
                            }
                        },
                        State {
                            when: Plasmoid.location === PlasmaCore.Types.RightEdge
                            AnchorChanges {
                                target: separator
                                anchors {
                                    top: separator.parent.top
                                    right: separator.parent.right
                                    bottom: separator.parent.bottom
                                }
                            }
                            PropertyChanges {
                                separator.width: 1
                            }
                        },
                        State {
                            when: Plasmoid.location === PlasmaCore.Types.BottomEdge
                            AnchorChanges {
                                target: separator
                                anchors {
                                    left: separator.parent.left
                                    right: separator.parent.right
                                    bottom: separator.parent.bottom
                                }
                            }
                            PropertyChanges {
                                separator.height: 1
                            }
                        }
                    ]
                }

                LayoutMirroring.enabled: Application.layoutDirection === Qt.RightToLeft
                LayoutMirroring.childrenInherit: true
            }
        }
    }
}

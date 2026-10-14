pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Mo Store — what an installed app may do, and the person's say in it. A Linux app: one switch per
// permission with a line about it, a row that a broader permission already covers says so, and
// Reset returns the app to what it asked for. A web app: Allow · Ask each time · Don't allow for
// each thing its catalogue entry may ask. An app that runs as the person (added from a file, a
// Windows program, a developer tool) has no switches, and the sheet says why, plainly. Every
// change is a backend job, and the rows show what the backend reads back afterwards.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Popup {
    id: permissionsSheet
    required property var win
    readonly property var design: win.design
    property var app: null
    readonly property string kind: win.appKind(permissionsSheet.app)
    readonly property var document: win.permissionDoc && permissionsSheet.app && win.permissionDoc.id === permissionsSheet.app.id
                                    ? win.permissionDoc : null
    readonly property var rows: permissionsSheet.document && permissionsSheet.document.rows ? permissionsSheet.document.rows : []
    readonly property bool busy: win.jobIsActive()
    anchors.centerIn: Overlay.overlay
    width: Math.min(win.fs(620), win.width - win.fs(80))
    height: Math.min(permissionBody.implicitHeight + design.space5 * 2, win.height - win.fs(80))
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: SheetBackground { win: permissionsSheet.win }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, permissionsSheet.win.lightScheme ? 0.32 : 0.54) }
    enter: Transition {
        NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: permissionsSheet.win.motionEnabled ? permissionsSheet.design.motionEmphasis : 0; easing.type: Easing.OutCubic }
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: permissionsSheet.win.motionEnabled ? permissionsSheet.design.motionPress : 0 }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: permissionsSheet.win.motionEnabled ? permissionsSheet.design.motionFast : 0 }
    }
    onOpened: doneButton.forceActiveFocus()

    ColumnLayout {
        id: permissionBody
        anchors.fill: parent
        anchors.margins: permissionsSheet.design.space5
        spacing: permissionsSheet.design.space4
        LayoutMirroring.enabled: permissionsSheet.win.rtl
        LayoutMirroring.childrenInherit: true
        Accessible.role: Accessible.Dialog
        Accessible.name: permissionTitle.text

        RowLayout {
            Layout.fillWidth: true
            spacing: permissionsSheet.design.space4
            AppIcon { win: permissionsSheet.win; app: permissionsSheet.app; size: permissionsSheet.win.fs(52) }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    horizontalAlignment: Text.AlignLeft
                    id: permissionTitle
                    Layout.fillWidth: true
                    text: permissionsSheet.win.rtl ? "أذونات " + permissionsSheet.win.localName(permissionsSheet.app)
                                                   : permissionsSheet.win.localName(permissionsSheet.app) + " permissions"
                    color: permissionsSheet.win.txt
                    font.family: permissionsSheet.win.uiFont
                    font.pixelSize: permissionsSheet.win.typePx(20)
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: permissionsSheet.win.safetyTitle(permissionsSheet.app)
                    color: permissionsSheet.win.txt2
                    font.family: permissionsSheet.win.uiFont
                    font.pixelSize: permissionsSheet.win.typePx(13)
                    elide: Text.ElideRight
                }
            }
        }

        // The rows, or the honest reason there are none.
        Text {
            Layout.fillWidth: true
            visible: text !== ""
            text: permissionsSheet.win.permissionState === "loading" ? permissionsSheet.win.local("تُقرأ أذوناته…", "Reading its permissions…")
                : permissionsSheet.win.permissionState === "unsupported" ? permissionsSheet.win.needsUpdateText
                : permissionsSheet.win.permissionState === "failed" ? permissionsSheet.win.local("تعذّرت قراءة أذوناته.", "Its permissions could not be read.")
                : permissionsSheet.document && permissionsSheet.document.note_key
                  ? permissionsSheet.win.permissionNoteText(permissionsSheet.document.note_key)
                : permissionsSheet.document && permissionsSheet.rows.length === 0
                  ? permissionsSheet.win.local("لا يطلب هذا التطبيق أي إذن يمكن تغييره.", "This app asks for nothing that can be changed.")
                : ""
            color: permissionsSheet.win.txt2
            font.family: permissionsSheet.win.uiFont
            font.pixelSize: permissionsSheet.win.typePx(14)
            wrapMode: Text.WordWrap
        }

        Flickable {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(permissionColumn.implicitHeight, permissionsSheet.win.fs(380))
            visible: permissionsSheet.rows.length > 0
            contentWidth: width
            contentHeight: permissionColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ColumnLayout {
                id: permissionColumn
                width: parent.width
                spacing: 0
                Repeater {
                    model: permissionsSheet.rows
                    delegate: ColumnLayout {
                        id: permissionEntry
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: 0
                        Rectangle {
                            visible: permissionEntry.index > 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(1, permissionsSheet.win.fs(1))
                            color: permissionsSheet.win.cardBorder
                        }
                        PermissionRow {
                            win: permissionsSheet.win
                            Layout.fillWidth: true
                            key: permissionEntry.modelData.key
                            allowed: permissionEntry.modelData.state === "allow"
                            ask: permissionEntry.modelData.ask === true
                            changeable: permissionEntry.modelData.changeable === true
                            mode: permissionsSheet.kind === "webapp" ? "choice" : "switch"
                            busy: permissionsSheet.busy
                            onChosen: (value) => permissionsSheet.win.setPermission(permissionsSheet.app, permissionEntry.modelData.key, value)
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: permissionsSheet.design.space2
            spacing: permissionsSheet.design.space3
            ActionButton {
                win: permissionsSheet.win
                visible: permissionsSheet.kind === "flatpak" && permissionsSheet.rows.length > 0
                pill: true
                label: permissionsSheet.win.local("أعِد ما طلبه التطبيق", "Reset to what it asked for")
                glyphName: "refresh"
                enabled: !permissionsSheet.busy
                triggered: function() { permissionsSheet.win.setPermission(permissionsSheet.app, "network", "reset") }
            }
            Item { Layout.fillWidth: true }
            Text {
                visible: permissionsSheet.busy
                text: permissionsSheet.win.local("يُطبَّق…", "Applying…")
                color: permissionsSheet.win.txt2
                font.family: permissionsSheet.win.uiFont
                font.pixelSize: permissionsSheet.win.typePx(13)
            }
            ActionButton {
                id: doneButton
                win: permissionsSheet.win
                pill: true
                primary: true
                label: permissionsSheet.win.local("تم", "Done")
                triggered: function() { permissionsSheet.close() }
            }
        }
    }
}

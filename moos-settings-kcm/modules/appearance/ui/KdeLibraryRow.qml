// SPDX-License-Identifier: GPL-2.0-or-later
// Native installed choices and native KNewStuff catalogue, with one owner each.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.kde.newstuff as NewStuff
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: row
    required property string libraryConfig
    property string glyph: "grid"
    property string description: ""
    // Fonts need the native font manager's complete installation workflow.
    property string libraryRoute: ""
    property bool directDownloadEnabled: true
    property bool rtl: false
    property string installedLabel: rtl ? "المثبتة" : "Installed"
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                Kirigami.Theme.textColor.b, 0.72)
    signal openLibraryRoute(string route)
    signal manageInstalled()

    focusPolicy: Qt.NoFocus
    hoverEnabled: false
    background: null
    Accessible.role: Accessible.Grouping
    Accessible.name: text
    Accessible.description: description

    signal browseOnline(string config)

    contentItem: GridLayout {
        columns: row.width > Kirigami.Units.gridUnit * 32 ? 2 : 1
        columnSpacing: Kirigami.Units.largeSpacing
        rowSpacing: Kirigami.Units.smallSpacing
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            MoUI.SymbolIcon {
                symbol: MoUI.SymbolCatalog.resolve(row.glyph)
                foreground: Kirigami.Theme.textColor
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: Kirigami.Units.iconSizes.smallMedium
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Controls.Label {
                    Layout.fillWidth: true
                    text: row.text
                    wrapMode: Text.WordWrap
                    Accessible.ignored: true
                }
                Controls.Label {
                    Layout.fillWidth: true
                    text: row.description
                    color: row.secondaryInk
                    wrapMode: Text.WordWrap
                    Accessible.ignored: true
                }
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: Kirigami.Units.smallSpacing
            Controls.Button {
                text: row.installedLabel
                implicitHeight: Math.max(44, implicitContentHeight + topPadding + bottomPadding)
                Accessible.name: (row.rtl ? "إدارة المثبت: " : "Manage installed: ") + row.text
                onClicked: row.manageInstalled()
            }
            Controls.Button {
                text: row.libraryRoute !== "" ? (row.rtl ? "المكتبة" : "Library")
                                             : (row.rtl ? "من الإنترنت" : "Online")
                icon.name: "get-hot-new-stuff"
                implicitHeight: Math.max(44, implicitContentHeight + topPadding + bottomPadding)
                enabled: row.enabled && (row.libraryRoute !== "" ||
                         (row.directDownloadEnabled && row.libraryConfig !== "" && NewStuff.Settings.allowedByKiosk))
                Accessible.name: (row.libraryRoute !== "" ? (row.rtl ? "إدارة المكتبة: " : "Manage library: ")
                                                       : (row.rtl ? "مكتبة المظهر عبر الإنترنت: " : "Online appearance library: ")) + row.text
                onClicked: row.libraryRoute !== "" ? row.openLibraryRoute(row.libraryRoute)
                                                    : row.browseOnline(row.libraryConfig)
                Controls.ToolTip.visible: hovered && row.libraryConfig === ""
                Controls.ToolTip.text: row.rtl ? "هذه المكتبة غير متاحة في الإعداد الحالي." : "This catalogue is unavailable in the current configuration."
            }
        }
    }
}

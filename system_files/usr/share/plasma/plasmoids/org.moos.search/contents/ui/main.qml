pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: compactRepresentation
    fullRepresentation: compactRepresentation
    Layout.minimumWidth: 132
    Layout.preferredWidth: 184
    Layout.maximumWidth: 184
    readonly property bool rtl: MoUI.Locale.rtl
    toolTipMainText: rtl ? "بحث في التطبيقات والملفات والإعدادات" : "Search apps, files and settings"

    compactRepresentation: Item {
        implicitWidth: Math.round(Math.min(184, Math.max(132, Screen.width * 0.12)))
        implicitHeight: 44
        Layout.minimumWidth: 132
        Layout.preferredWidth: implicitWidth
        Layout.maximumWidth: 184
        Layout.minimumHeight: 44

        QQC2.TextField {
            id: query
            anchors.fill: parent
            anchors.topMargin: 5
            anchors.bottomMargin: 5
            leftPadding: root.rtl ? 12 : 38
            rightPadding: root.rtl ? 38 : 12
            placeholderText: root.rtl ? "ابحث في MoOS" : "Search MoOS"
            font.family: root.rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
            font.pixelSize: 13
            color: Kirigami.Theme.textColor
            placeholderTextColor: Qt.alpha(Kirigami.Theme.textColor, 0.72)
            horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
            selectByMouse: true
            Accessible.name: root.toolTipMainText
            function search() {
                const term = text.trim();
                if (!term) { forceActiveFocus(); return; }
                Qt.openUrlExternally("moos://search/" + encodeURIComponent(term));
            }
            onAccepted: search()
            Keys.onEscapePressed: { clear(); focus = false; }
            background: Rectangle {
                radius: 12
                color: Qt.alpha(Kirigami.Theme.textColor, query.activeFocus ? 0.13 : 0.07)
                border.width: query.activeFocus ? 2 : 1
                border.color: query.activeFocus ? Kirigami.Theme.highlightColor
                    : Qt.alpha(Kirigami.Theme.textColor, 0.15)
                Behavior on color {
                    ColorAnimation { duration: MoUI.Tokens.duration(Kirigami.Units.longDuration > 1, 120) }
                }
            }
            QQC2.ToolButton {
                anchors.verticalCenter: parent.verticalCenter
                x: root.rtl ? parent.width - width : 0
                width: 36; height: parent.height
                icon.name: "moos-search-symbolic"
                icon.width: 18; icon.height: 18
                Accessible.name: root.rtl ? "بحث" : "Search"
                onClicked: query.search()
                background: Item {}
            }
        }
    }
}

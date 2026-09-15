pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

// The Horizon Bar search entry.
//
// A panel does not take keyboard focus unless an applet asks for it: Plasma's panel grants input
// only while a plasmoid reports PlasmaCore.Types.AcceptingInputStatus. The first version of this
// applet was a bare TextField that never asked, so a click showed a focus ring while every
// keystroke still went to the previously focused window (reported on the physical station,
// 2026-09-15). The field now requests input while the user is searching and releases it as soon as
// the query is handed on.
//
// Results come from KRunner, Plasma's system search (applications, files, settings, calculator,
// units, web shortcuts), which keeps updating live while the user continues typing there. The bar
// field is the entry point, not a second results surface: a short typing pause hands the query
// over, Enter hands it over at once, and the magnifier or Enter on an empty field opens search.
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    // Only while searching: holding AcceptingInputStatus permanently would make the panel take
    // keyboard focus away from every window.
    Plasmoid.status: searching ? PlasmaCore.Types.AcceptingInputStatus : PlasmaCore.Types.ActiveStatus
    preferredRepresentation: compactRepresentation
    fullRepresentation: compactRepresentation
    Layout.minimumWidth: 132
    Layout.preferredWidth: 184
    Layout.maximumWidth: 184
    readonly property bool rtl: MoUI.Locale.rtl
    property bool searching: false
    toolTipMainText: rtl ? "بحث في التطبيقات والملفات والإعدادات" : "Search apps, files and settings"

    function openSearch(term) {
        root.searching = false;
        Qt.openUrlExternally("moos://search/" + encodeURIComponent(term));
    }

    compactRepresentation: Item {
        implicitWidth: Math.round(Math.min(184, Math.max(132, Screen.width * 0.12)))
        implicitHeight: 44
        Layout.minimumWidth: 132
        Layout.preferredWidth: implicitWidth
        Layout.maximumWidth: 184
        Layout.minimumHeight: 44

        Timer {
            id: handoff
            // Long enough to gather a word typed at ordinary speed, short enough to feel live.
            interval: 350
            onTriggered: query.submit()
        }

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

            function begin() {
                root.searching = true;
                forceActiveFocus();
            }
            function submit() {
                handoff.stop();
                const term = text.trim();
                clear();
                focus = false;
                root.openSearch(term);
            }

            onPressed: begin()
            onTextEdited: {
                root.searching = true;
                if (text.trim().length > 0) handoff.restart();
                else handoff.stop();
            }
            onAccepted: submit()
            onActiveFocusChanged: {
                if (!activeFocus && text.length === 0) {
                    handoff.stop();
                    root.searching = false;
                }
            }
            Keys.onEscapePressed: {
                handoff.stop();
                clear();
                focus = false;
                root.searching = false;
            }
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
                onClicked: query.submit()
                background: Item {}
            }
        }
    }
}

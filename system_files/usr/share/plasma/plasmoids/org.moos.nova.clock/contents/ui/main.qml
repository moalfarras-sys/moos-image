import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: compactRepresentation
    toolTipMainText: Qt.formatDateTime(now, "dddd d MMMM yyyy, HH:mm")
    property date now: new Date()
    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft

    Timer { interval: 1000; running: true; repeat: true; onTriggered: root.now = new Date() }

    compactRepresentation: Item {
        implicitWidth: clockRow.implicitWidth + Kirigami.Units.smallSpacing * 3
        implicitHeight: Kirigami.Units.gridUnit * 2
        Accessible.name: Qt.formatDateTime(root.now, "dddd d MMMM yyyy, HH:mm")
        RowLayout {
            id: clockRow
            anchors.centerIn: parent
            spacing: Kirigami.Units.smallSpacing
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight
            Text {
                text: Qt.formatTime(root.now, "HH:mm")
                color: PlasmaCore.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(12, Kirigami.Units.gridUnit * 0.78)
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
            }
            Rectangle {
                Layout.preferredWidth: 1
                Layout.preferredHeight: Kirigami.Units.gridUnit * 0.8
                color: PlasmaCore.Theme.textColor
                opacity: 0.18
            }
            Text {
                text: Qt.formatDate(root.now, "ddd d MMM")
                color: PlasmaCore.Theme.textColor
                opacity: 0.66
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(9, Kirigami.Units.gridUnit * 0.58)
                font.weight: Font.Medium
            }
        }
    }
}

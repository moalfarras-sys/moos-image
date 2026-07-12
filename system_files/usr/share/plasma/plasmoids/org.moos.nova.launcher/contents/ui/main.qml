import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    Plasmoid.icon: "moos-logo"
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    switchWidth: Kirigami.Units.gridUnit * 22
    switchHeight: Kirigami.Units.gridUnit * 26
    property int selected: 0
    readonly property var essentials: [
        { name: qsTr("Mo AI"), icon: "moos-moai", url: "moos://app/moai" },
        { name: qsTr("Files"), icon: "system-file-manager", url: "applications:org.kde.dolphin.desktop" },
        { name: qsTr("Settings"), icon: "settings-configure", url: "applications:systemsettings.desktop" },
        { name: qsTr("Terminal"), icon: "utilities-terminal", url: "applications:org.kde.konsole.desktop" },
        { name: qsTr("Mo Remote"), icon: "moos-phone", url: "moos://app/remote" },
        { name: qsTr("Updater"), icon: "moos-updater", url: "applications:org.moos.updater.desktop" },
        { name: qsTr("Recovery"), icon: "moos-recovery", url: "applications:org.moos.recovery.desktop" },
        { name: qsTr("Hardware"), icon: "moos-hardware", url: "applications:org.moos.hardware.desktop" }
    ]
    function launch(url) { Qt.openUrlExternally(url); root.expanded = false }
    function search() {
        const q = searchField.text.trim()
        if (q.length) { Qt.openUrlExternally("moos://search/" + encodeURIComponent(q)); root.expanded = false }
    }

    compactRepresentation: Item {
        implicitWidth: Kirigami.Units.gridUnit * 2.2
        implicitHeight: implicitWidth
        Kirigami.Icon { anchors.centerIn: parent; width: parent.width * 0.66; height: width; source: "moos-logo" }
        TapHandler { onTapped: root.expanded = !root.expanded }
    }

    fullRepresentation: Item {
        implicitWidth: Kirigami.Units.gridUnit * 36
        implicitHeight: Kirigami.Units.gridUnit * 29
        LayoutMirroring.enabled: Qt.locale().textDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        Rectangle { anchors.fill: parent; color: "#F20B1220"; radius: 22; border.color: "#334A6F"; border.width: 1 }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.gridUnit
            spacing: Kirigami.Units.largeSpacing
            RowLayout {
                Kirigami.Icon { source: "moos-logo"; Layout.preferredWidth: 34; Layout.preferredHeight: 34 }
                ColumnLayout { spacing: 0; Text { text: qsTr("MoOS"); color: "#F4F8FF"; font.pixelSize: 19; font.weight: Font.DemiBold }
                    Text { text: qsTr("Nova workspace"); color: "#8FA4C4"; font.pixelSize: 11 } }
                Item { Layout.fillWidth: true }
                QQC2.ToolButton { icon.name: "system-shutdown"; Accessible.name: qsTr("Power and session"); onClicked: root.launch("moos://session/power") }
            }
            QQC2.TextField {
                id: searchField
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 2.7
                placeholderText: qsTr("Search apps, files, settings and actions…")
                leftPadding: Kirigami.Units.gridUnit * 2.6
                font.pixelSize: 15
                Keys.onReturnPressed: root.search()
                Keys.onEnterPressed: root.search()
                background: Rectangle { radius: 14; color: "#CC16233A"; border.color: searchField.activeFocus ? "#4FC3FF" : "#314361"; border.width: 1 }
                Kirigami.Icon { source: "search"; width: 20; height: 20; anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter; opacity: 0.72 }
            }
            Text { text: qsTr("ESSENTIALS"); color: "#7F94B5"; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
            GridLayout {
                id: essentialsGrid
                Layout.fillWidth: true; columns: 4; uniformCellWidths: true
                columnSpacing: Kirigami.Units.smallSpacing; rowSpacing: Kirigami.Units.smallSpacing
                Repeater { model: root.essentials
                    delegate: QQC2.AbstractButton {
                        id: appButton
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 5
                        onClicked: root.launch(modelData.url)
                        background: Rectangle { radius: 14; color: appButton.hovered ? "#263A5C" : "#141F34"; border.color: appButton.hovered ? "#426895" : "#22324C" }
                        contentItem: Column { spacing: 6; Kirigami.Icon { anchors.horizontalCenter: parent.horizontalCenter; width: 30; height: 30; source: appButton.modelData.icon }
                            Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: appButton.modelData.name; color: "#DDE8FA"; font.pixelSize: 11 } }
                    }
                }
            }
            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                Repeater { model: [qsTr("All apps"), qsTr("Work"), qsTr("Create"), qsTr("System")]
                    delegate: QQC2.Button { required property string modelData; text: modelData; flat: true; onClicked: { searchField.text = modelData; searchField.forceActiveFocus() } }
                }
                Item { Layout.fillWidth: true }
            }
            Item { Layout.fillHeight: true }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: "#263852" }
            RowLayout {
                Kirigami.Icon { source: "user-identity"; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
                Text { text: qsTr("Your workspace"); color: "#C8D5E8"; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                QQC2.Button { text: qsTr("Lock"); icon.name: "system-lock-screen"; flat: true; onClicked: root.launch("moos://session/lock") }
                QQC2.Button { text: qsTr("Log out"); icon.name: "system-log-out"; flat: true; onClicked: root.launch("moos://session/logout") }
            }
        }
        Component.onCompleted: searchField.forceActiveFocus()
    }
}

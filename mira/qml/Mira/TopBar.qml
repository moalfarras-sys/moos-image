import QtQuick
import QtQuick.Layouts

// Minimal top bar: identity + live services on one side, destinations and preferences on the other.
Item {
    id: bar
    property bool compact: false
    signal openSheet(string name)
    implicitHeight: 52

    RowLayout {
        anchors.fill: parent
        spacing: 10

        // identity
        Row {
            spacing: 10
            Layout.alignment: Qt.AlignVCenter
            Avatar { width: 34; height: 34; anchors.verticalCenter: parent.verticalCenter }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: -2
                T { text: "MIRA"; font.pixelSize: 15; font.weight: Font.Bold; font.letterSpacing: 4; wrapMode: Text.NoWrap }
                T { text: mira.s.tagline; font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap }
            }
        }

        Item { Layout.preferredWidth: 8 }

        Row {
            spacing: 6
            visible: !bar.compact
            Layout.alignment: Qt.AlignVCenter
            ServicePill { label: mira.s.svc_echo; state_: mira.services.echo; detail: mira.echo.state || "" }
            ServicePill { label: mira.s.svc_home; state_: mira.services.home; detail: mira.home.message || "" }
            ServicePill { label: mira.s.svc_moai; state_: mira.services.moai }
        }

        Item { Layout.fillWidth: true }

        Row {
            spacing: 6
            Layout.alignment: Qt.AlignVCenter
            IconButton { iconName: "home"; tip: mira.s.home; onClicked: bar.openSheet("home") }
            IconButton { iconName: "monitor"; tip: mira.s.computer; onClicked: bar.openSheet("computer") }
            IconButton { iconName: "chat"; tip: mira.s.conversation; visible: bar.compact; onClicked: bar.openSheet("chat") }
            IconButton { iconName: "face"; tip: mira.s.switch_face; onClicked: mira.toggleFace() }
            IconButton { iconName: "language"; tip: mira.s.language; onClicked: mira.setLang(mira.lang === "ar" ? "en" : "ar") }
            IconButton { iconName: "settings"; tip: mira.s.settings; onClicked: bar.openSheet("settings") }
        }
    }
}

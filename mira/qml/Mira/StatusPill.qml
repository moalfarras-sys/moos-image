import QtQuick

// A small state chip: tone ok | warn | error | info | off, with an optional glyph.
Rectangle {
    id: pill
    property string text: ""
    property string tone: "info"
    property string icon: ""
    readonly property color c: tone === "ok" ? Theme.ok : tone === "warn" ? Theme.amber : tone === "error" ? Theme.danger
                              : tone === "off" ? Theme.off : Theme.cyan
    implicitHeight: 24
    implicitWidth: row.implicitWidth + 18
    radius: 12
    color: Qt.rgba(c.r, c.g, c.b, 0.14)
    border.width: 1; border.color: Qt.rgba(c.r, c.g, c.b, 0.40)
    Accessible.role: Accessible.StaticText
    Accessible.name: text
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 5
        Icon { visible: pill.icon !== ""; name: pill.icon || "check"; size: 13; weight: 2; color: pill.c; anchors.verticalCenter: parent.verticalCenter }
        T { text: pill.text; font.pixelSize: Theme.tiny + 1; color: pill.c; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
    }
}

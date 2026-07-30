import QtQuick
import org.kde.kirigami as Kirigami

// Symbolic icons are masks supplied by the active MoOS icon theme. Kirigami
// applies this foreground role at render time, so light/dark/accent changes do
// not require a second asset or a generated data URL.
Kirigami.Icon {
    id: icon

    property string symbol: ""
    property color foreground: Kirigami.Theme.textColor

    source: symbol
    color: foreground
    implicitWidth: 20
    implicitHeight: 20
    Accessible.ignored: true
}

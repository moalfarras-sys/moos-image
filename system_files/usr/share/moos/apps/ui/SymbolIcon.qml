import QtQuick
import org.kde.kirigami as Kirigami

// First-party app controls consume the active MoOS symbol as a true mask.
// KIconLoader deliberately preserves the multi-role palette when a normal
// themed icon is requested (Launcher, tray and shell surfaces need that).
// Buttons instead need their exact foreground state — selected, destructive,
// disabled — so isMask is explicit here and Kirigami applies `foreground`
// without manufacturing private data-URL SVGs.
Kirigami.Icon {
    id: icon

    property string symbol: ""
    property color foreground: Kirigami.Theme.textColor

    source: symbol
    isMask: true
    color: foreground
    implicitWidth: 20
    implicitHeight: 20
    Accessible.ignored: true
}

import QtQuick
import org.kde.kirigami as Kirigami

// First-party controls use the palette-baked Tidal Cut symbol as a true mask
// so primary, destructive and disabled states get the exact semantic ink.
Kirigami.Icon {
    id: icon

    property string symbol: ""
    property color foreground: Kirigami.Theme.textColor

    source: symbol
    isMask: true
    color: foreground
    implicitWidth: Tokens.iconControl
    implicitHeight: Tokens.iconControl
    Accessible.ignored: true
}

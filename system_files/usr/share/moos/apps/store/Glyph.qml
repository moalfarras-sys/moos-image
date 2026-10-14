pragma ComponentBehavior: Bound

import QtQuick
import org.moos.ui as MoUI

// Mo Store — a control glyph from MoOS's shared symbolic vocabulary, tinted from the
// window's palette. Application artwork stays AppStream's (AppArtwork.qml); every
// control glyph comes from the MoOS layer through win.glyphIcon(), which owns the
// alias table.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
MoUI.SymbolIcon {
    id: glyph
    required property var win
    property string name: "spark"
    property color tint: win.txt
    symbol: win.glyphIcon(name)
    foreground: tint
}

import QtQuick

// Aurora Glass. One material for every MoOS surface that floats above the desk.
//
// Glass with nothing but alpha disappears over a busy wallpaper: the eye has no
// edge to hold on to, so a menu over a photograph reads as a smudge and a sheet
// over the bar reads as one soup. Real glass has two edges — a darker rim where
// it meets what is behind it, and a brighter line along the edge the light falls
// on — and those two hairlines are what make a stack of surfaces read as depth.
//
// `depth` says how far forward this surface sits (see Tokens' "Aurora Glass"):
// scene for the desktop's own cards, panel for the bar, popover for menus and
// search, dialog for questions. Denser and darker-rimmed the further forward it
// is, so a popover over the bar over the desk reads as three sheets, not one.
Surface {
    id: glass

    property bool floating: false
    property int depth: Tokens.glassLevelPopover

    // With a blur pass behind it, the frosted density the palette asks for. Without
    // one — the essential tier, llvmpipe, or an owner who turned blur off — the same
    // colour, opaque enough that the wallpaper stops competing with the text.
    fillOpacity: Tokens.glassFill(surfaceColor, depth,
                                  floating ? Tokens.floatingGlassOpacity
                                           : Tokens.glassRestingOpacity)
    color: Qt.alpha(surfaceColor, fillOpacity)
    radius: Tokens.radiusPanel
    // A selected surface keeps the accent rim it always had; everything else
    // takes the palette's own shadow instead of a tint of the ink colour.
    border.color: selected ? Qt.alpha(accentColor, rimOpacity)
                           : Tokens.glassEdge(surfaceColor, depth)

    // The light on the top edge. Inset by the corner so it lives on the straight
    // part of the rim, one pixel tall, and the only white MoOS paints.
    Rectangle {
        anchors.top: parent.top
        anchors.topMargin: 1
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - parent.radius * 1.6)
        height: 1
        color: Tokens.glassSpecular(glass.surfaceColor, glass.depth)
        visible: parent.width > parent.radius * 2 && glass.opacity > 0
    }
}

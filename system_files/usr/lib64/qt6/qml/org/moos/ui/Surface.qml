import QtQuick
import org.kde.kirigami as Kirigami

// Base semantic surface. Palette profiles provide the colours; Design Core
// provides the shape and state amplitudes.
Rectangle {
    id: surface

    property bool interactive: false
    property bool selected: false
    property bool pressed: false
    property bool hovered: false
    property color surfaceColor: Kirigami.Theme.backgroundColor
    property color inkColor: Kirigami.Theme.textColor
    property color accentColor: Kirigami.Theme.highlightColor
    property real fillOpacity: interactive
        ? Tokens.stateOpacity(enabled, hovered, pressed, selected) : 1
    property real rimOpacity: selected ? Tokens.glassSelectedOpacity
                                     : Tokens.glassBorderOpacity

    radius: Tokens.radiusCard
    // The MoOS corner (owner steering 2026-11-22: "one square corner and the
    // rest curved, like the buttons, on every card"). Three corners keep the
    // surface's radius; the TOP-TRAILING one is square — top right when
    // reading left to right, top left in Arabic — with only Tokens.radiusSquare
    // of softening so its edge stays crisp at every scale. The session action
    // glyphs and the window action tiles already carry this short corner.
    // Pills and circles (radius reaching half the short side) stay round: a
    // square corner belongs to a card, not to a capsule.
    property bool squareCorner: true
    readonly property bool cornerApplies: squareCorner
        && radius * 2 < Math.min(width, height) - 1
    readonly property real squareRadius: Math.min(radius, Tokens.radiusSquare)
    topLeftRadius: cornerApplies && LayoutMirroring.enabled ? squareRadius : radius
    topRightRadius: cornerApplies && !LayoutMirroring.enabled ? squareRadius : radius
    color: interactive ? Qt.alpha(inkColor, fillOpacity) : surfaceColor
    border.width: Tokens.borderHairline
    border.color: Qt.alpha(selected ? accentColor : inkColor, rimOpacity)
    opacity: enabled ? 1 : Tokens.disabledOpacity
}

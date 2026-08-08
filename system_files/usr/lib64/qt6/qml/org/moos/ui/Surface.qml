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
    color: interactive ? Qt.alpha(inkColor, fillOpacity) : surfaceColor
    border.width: Tokens.borderHairline
    border.color: Qt.alpha(selected ? accentColor : inkColor, rimOpacity)
    opacity: enabled ? 1 : Tokens.disabledOpacity
}

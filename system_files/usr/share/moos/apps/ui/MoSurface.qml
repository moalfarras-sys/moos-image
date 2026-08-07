import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: surface

    property bool interactive: false
    property bool selected: false
    property color surfaceColor: Kirigami.Theme.backgroundColor
    property color inkColor: Kirigami.Theme.textColor
    property color accentColor: Kirigami.Theme.highlightColor

    radius: tokens.radiusCard
    color: surfaceColor
    border.width: tokens.borderHairline
    border.color: Qt.alpha(inkColor, selected ? tokens.glassSelectedOpacity
                                               : tokens.glassBorderOpacity)

    Tokens { id: tokens }
}

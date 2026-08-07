import QtQuick

MoSurface {
    property bool elevated: false

    border.color: Qt.alpha(inkColor, elevated ? tokens.glassHoverOpacity
                                               : tokens.glassBorderOpacity)

    Tokens { id: tokens }
}

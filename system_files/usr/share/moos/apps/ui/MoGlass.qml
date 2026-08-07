import QtQuick

MoSurface {
    property real fillOpacity: tokens.glassRestingOpacity

    color: Qt.alpha(surfaceColor, fillOpacity)

    Tokens { id: tokens }
}

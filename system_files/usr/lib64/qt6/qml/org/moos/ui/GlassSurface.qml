import QtQuick

Surface {
    property bool floating: false

    fillOpacity: floating ? Tokens.floatingGlassOpacity
                          : Tokens.glassRestingOpacity
    color: Qt.alpha(surfaceColor, fillOpacity)
    radius: Tokens.radiusPanel
}

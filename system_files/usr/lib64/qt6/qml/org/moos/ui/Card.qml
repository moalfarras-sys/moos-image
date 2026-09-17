import QtQuick
import org.kde.kirigami as Kirigami

Surface {
    property bool elevated: false

    interactive: true
    rimOpacity: elevated || hovered ? Tokens.glassHoverOpacity
                                    : Tokens.glassBorderOpacity
    scale: pressed ? Tokens.pressScale : hovered ? Tokens.hoverScale : 1

    Behavior on scale {
        NumberAnimation {
            duration: Tokens.scaled(Kirigami.Units.longDuration,
                                    Tokens.motionFast)
            easing.type: Tokens.easeStandard
        }
    }
}

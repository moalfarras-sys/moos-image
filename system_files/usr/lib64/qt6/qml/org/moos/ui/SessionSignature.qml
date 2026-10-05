import QtQuick
import QtQuick.Window

// The MoOS session signature: the emblem, the wordmark and one accent stroke.
//
// Every session surface — login, lock and power — signs itself with this, once,
// in its leading top corner. It is deliberately dumb: the caller supplies the
// ink and the accent (the login scene knows its wallpaper's tones, the lock and
// power screens ask the colour scheme), and it reads nothing ambient and imports
// nothing but QtQuick, so it paints on the first frame in every engine that
// loads it, under software rendering too. It never moves by itself.
Row {
    id: signature

    // The height of the scene it signs; every size below is a share of it, with
    // a floor that keeps the mark legible in a 640x480 firmware mode.
    property real sceneHeight: 864
    // No default worth having: a signature must be drawn in its scene's own ink.
    property color ink
    property color accent: ink

    spacing: Math.max(8, Math.round(sceneHeight * 0.012))

    Image {
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(34, Math.round(signature.sceneHeight * 0.042))
        height: width
        // The canonical mark the identity firewall pins.
        source: "file:///usr/share/pixmaps/moos-logo.png"
        sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
        fillMode: Image.PreserveAspectFit
        asynchronous: false
        smooth: true
        mipmap: true
    }

    Column {
        anchors.verticalCenter: parent.verticalCenter
        spacing: Math.max(3, Math.round(signature.sceneHeight * 0.006))

        Text {
            text: "MoOS"
            color: signature.ink
            font.family: "IBM Plex Sans Arabic"
            font.pixelSize: Math.max(21, Math.round(signature.sceneHeight * 0.03))
            font.weight: Font.DemiBold
            font.letterSpacing: 1
            // QtRendering, not NativeRendering: the station's panel runs a
            // FRACTIONAL scale, native hinting snaps stems to whole device
            // pixels, and the wordmark lands off-grid beside a crisp emblem.
            renderType: Text.QtRendering
        }
        Rectangle {
            // Starts under the first letter in either reading direction.
            anchors.left: parent.left
            width: Math.max(26, Math.round(signature.sceneHeight * 0.04))
            height: 2
            radius: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop {
                    position: 0.0
                    color: signature.LayoutMirroring.enabled ? Qt.alpha(signature.accent, 0.0)
                                                             : signature.accent
                }
                GradientStop {
                    position: 1.0
                    color: signature.LayoutMirroring.enabled ? signature.accent
                                                             : Qt.alpha(signature.accent, 0.0)
                }
            }
        }
    }
}

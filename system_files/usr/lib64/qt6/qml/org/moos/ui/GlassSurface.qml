import QtQuick
import org.kde.kirigami as Kirigami

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

    // A surface arrives as one physical sheet: a very small settle and one
    // travelling glint along its leading edge. This is deliberately finite.
    // It never owns a Timer, never repeats while idle, and a hidden surface is
    // left at its final geometry. `animateArrival: false` is available for a
    // caller that is itself already moving the complete surface.
    property bool animateArrival: true
    readonly property bool arrivalAnimating: arrival.running
    property bool arrivalPlayed: false
    property real arrivalScale: 1.0

    function finishArrival() {
        arrival.stop()
        arrivalScale = 1.0
        arrivalGlint.opacity = 0.0
        arrivalPlayed = true
    }

    function playArrival() {
        if (arrivalPlayed || !animateArrival || !visible || width <= 0 || height <= 0)
            return
        if (Kirigami.Units.longDuration <= 1) {
            finishArrival()
            return
        }
        arrivalPlayed = true
        arrivalScale = 0.985
        arrivalGlint.x = -arrivalGlint.width
        arrivalGlint.opacity = 0.0
        arrival.restart()
    }

    transform: Scale {
        origin.x: glass.width / 2
        origin.y: glass.height / 2
        xScale: glass.arrivalScale
        yScale: glass.arrivalScale
    }

    Component.onCompleted: Qt.callLater(glass.playArrival)
    onVisibleChanged: {
        if (visible) Qt.callLater(glass.playArrival)
        else if (arrival.running) glass.finishArrival()
    }
    onWidthChanged: if (!arrivalPlayed && width > 0) Qt.callLater(glass.playArrival)

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
    // part of the rim. The resting hairline holds the edge; a brighter, soft
    // segment crosses it ONCE when the sheet arrives. Both stay inside this
    // clipped track, so the glint never spills across a rounded corner.
    Item {
        id: specularTrack
        anchors.top: parent.top
        anchors.topMargin: 1
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - parent.radius * 1.6)
        height: 2
        clip: true
        visible: parent.width > parent.radius * 2 && glass.opacity > 0

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: Tokens.glassSpecular(glass.surfaceColor, glass.depth)
        }

        Rectangle {
            id: arrivalGlint
            y: 0
            width: Math.max(36, specularTrack.width * 0.24)
            height: 1
            opacity: 0
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Tokens.glassSpecular(glass.surfaceColor, glass.depth) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    ParallelAnimation {
        id: arrival
        NumberAnimation {
            target: glass
            property: "arrivalScale"
            from: 0.985
            to: 1.0
            duration: Tokens.motionEmphasis
            easing.type: Tokens.easeEmphasis
        }
        SequentialAnimation {
            NumberAnimation {
                target: arrivalGlint
                property: "opacity"
                from: 0.0
                to: 0.78
                duration: Math.max(1, Math.round(Tokens.motionFast * 0.55))
                easing.type: Tokens.easeStandard
            }
            NumberAnimation {
                target: arrivalGlint
                property: "opacity"
                from: 0.78
                to: 0.0
                duration: Math.max(1, Tokens.motionEmphasis - Math.round(Tokens.motionFast * 0.55))
                easing.type: Tokens.easeStandard
            }
        }
        NumberAnimation {
            target: arrivalGlint
            property: "x"
            from: -arrivalGlint.width
            to: specularTrack.width
            duration: Tokens.motionEmphasis
            easing.type: Tokens.easeEmphasis
        }
        onFinished: glass.finishArrival()
    }
}

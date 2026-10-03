import QtQuick

// A colour wheel: hue around the ring, saturation from the white centre outwards. Drawn once
// (Canvas, no shader: it works on every scene graph), so dragging costs nothing but the knob.
// `picked(hex)` fires when the finger lifts — a lamp takes a second to answer, so a stream of
// colours while dragging would only queue up.
Item {
    id: wheel
    property color current: "#9B7BFF"
    signal picked(string hex)
    implicitWidth: 220
    implicitHeight: 220

    property real knobHue: 0
    property real knobSat: 0
    function syncKnob() {
        knobHue = Math.max(0, current.hsvHue)
        knobSat = current.hsvSaturation
    }
    onCurrentChanged: if (!area.pressed) syncKnob()
    Component.onCompleted: syncKnob()

    readonly property real r: Math.min(width, height) / 2 - 6
    readonly property color knobColor: Qt.hsva(knobHue, knobSat, 1, 1)

    Canvas {
        id: disc
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            const cx = width / 2, cy = height / 2, rad = wheel.r
            ctx.reset()
            // hue: counter-clockwise from 3 o'clock, the same direction the pointer maths uses
            const g = ctx.createConicalGradient(cx, cy, 0)
            const stops = ["#FF0000", "#FFFF00", "#00FF00", "#00FFFF", "#0000FF", "#FF00FF", "#FF0000"]
            for (let i = 0; i < stops.length; i++) g.addColorStop(i / (stops.length - 1), stops[i])
            ctx.beginPath()
            ctx.arc(cx, cy, rad, 0, Math.PI * 2)
            ctx.fillStyle = g
            ctx.fill()
            // saturation: white in the middle
            const w = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad)
            w.addColorStop(0, "rgba(255,255,255,1)")
            w.addColorStop(0.18, "rgba(255,255,255,0.85)")
            w.addColorStop(1, "rgba(255,255,255,0)")
            ctx.fillStyle = w
            ctx.fill()
            // a thin glass rim
            ctx.lineWidth = 1.5
            ctx.strokeStyle = "rgba(255,255,255,0.22)"
            ctx.stroke()
        }
    }

    // the knob
    Rectangle {
        id: knob
        readonly property real angle: wheel.knobHue * Math.PI * 2
        width: area.pressed ? 30 : 24; height: width; radius: width / 2
        x: wheel.width / 2 + Math.cos(angle) * wheel.knobSat * wheel.r - width / 2
        y: wheel.height / 2 - Math.sin(angle) * wheel.knobSat * wheel.r - height / 2
        color: wheel.knobColor
        border.width: 3
        border.color: "white"
        Behavior on width { NumberAnimation { duration: Theme.fast } }
        Rectangle { anchors.fill: parent; anchors.margins: -4; radius: width / 2; color: "transparent"
                    border.width: 1; border.color: Qt.rgba(0, 0, 0, 0.35) }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        cursorShape: Qt.CrossCursor
        function take(mx, my) {
            const dx = mx - wheel.width / 2, dy = wheel.height / 2 - my
            const dist = Math.sqrt(dx * dx + dy * dy)
            let a = Math.atan2(dy, dx)
            if (a < 0) a += Math.PI * 2
            wheel.knobHue = a / (Math.PI * 2)
            wheel.knobSat = Math.min(1, dist / wheel.r)
        }
        onPressed: function(e) { take(e.x, e.y) }
        onPositionChanged: function(e) { if (pressed) take(e.x, e.y) }
        onReleased: wheel.picked(wheel.hex(wheel.knobColor))
    }
    Accessible.role: Accessible.ColorChooser
    Accessible.name: mira.s.lu_color

    function hex(c) {
        function two(v) { const s = Math.round(v * 255).toString(16); return s.length < 2 ? "0" + s : s }
        return "#" + two(c.r) + two(c.g) + two(c.b)
    }
}

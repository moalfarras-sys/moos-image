pragma Singleton
import QtQuick

// Mira Neural OS design tokens. One place for colour, type, space, radius and motion.
// Dark premium canvas; cyan = live/listening, violet = thinking/selection, rose = Mira's voice.
QtObject {
    // canvas
    readonly property color bg0: "#04050D"
    readonly property color bg1: "#080B1C"
    readonly property color bg2: "#0D1230"
    // glass (fallback fills that work without blur)
    readonly property color glass: Qt.rgba(0.075, 0.09, 0.19, 0.72)
    readonly property color glassStrong: Qt.rgba(0.07, 0.085, 0.18, 0.92)
    readonly property color glassHover: Qt.rgba(0.12, 0.14, 0.28, 0.78)
    readonly property color hairline: Qt.rgba(0.62, 0.72, 1.0, 0.13)
    readonly property color hairlineStrong: Qt.rgba(0.62, 0.78, 1.0, 0.26)
    readonly property color innerLight: Qt.rgba(1, 1, 1, 0.06)
    // ink
    readonly property color ink: "#F4F1FF"
    readonly property color ink2: Qt.rgba(0.957, 0.945, 1.0, 0.72)
    readonly property color ink3: Qt.rgba(0.957, 0.945, 1.0, 0.50)
    // accents
    readonly property color cyan: "#35D8F4"
    readonly property color mint: "#3DF2C4"
    readonly property color violet: "#9B7BFF"
    readonly property color rose: "#FF6FB5"
    readonly property color amber: "#FFC46B"
    readonly property color danger: "#FF5C7A"
    readonly property color ok: "#48E0A0"
    readonly property color off: "#6B7390"

    function phaseColor(phase, style) {
        switch (phase) {
        case "listening": return mint
        case "thinking": return violet
        case "speaking": return rose
        case "executing": return amber
        case "error": return danger
        case "offline": return off
        default: return style === "holo" ? cyan : rose
        }
    }
    function phaseColor2(phase, style) {
        switch (phase) {
        case "listening": return cyan
        case "thinking": return "#5B8CFF"
        case "speaking": return violet
        case "executing": return rose
        case "error": return "#7A1E3A"
        case "offline": return "#2A3050"
        default: return style === "holo" ? violet : violet
        }
    }

    // type
    readonly property string font: "IBM Plex Sans Arabic"
    readonly property string mono: "JetBrains Mono"
    readonly property int tiny: 11
    readonly property int small: 12
    readonly property int body: 14
    readonly property int title: 17
    readonly property int heading: 22
    readonly property int display: 30

    // space and shape
    readonly property int s1: 4
    readonly property int s2: 8
    readonly property int s3: 12
    readonly property int s4: 16
    readonly property int s5: 24
    readonly property int s6: 32
    readonly property int rSmall: 10
    readonly property int rControl: 14
    readonly property int rPanel: 22
    readonly property int rDock: 30

    // motion (ms); Reduced Motion multiplies to exactly zero
    property real motionScale: 1.0
    readonly property int fast: Math.round(120 * motionScale)
    readonly property int normal: Math.round(220 * motionScale)
    readonly property int emphasized: Math.round(360 * motionScale)
}

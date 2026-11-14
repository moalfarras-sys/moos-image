pragma Singleton
import QtQuick
import org.moos.ui as MoUI

// Mira keeps her expressive face colours while native KDE owns the reading
// surface, font and semantic ink. The same MoOS material/motion owner serves
// the shell; no copied preference or second appearance configuration lives here.
QtObject {
    id: theme
    property SystemPalette nativePalette: SystemPalette { colorGroup: SystemPalette.Active }
    readonly property bool light: MoUI.Tokens.isLight(nativePalette.window)
    readonly property color bg0: nativePalette.window
    readonly property color bg1: nativePalette.base
    readonly property color bg2: nativePalette.alternateBase
    readonly property real glassAlpha: MoUI.Tokens.glassFill(bg0, MoUI.Tokens.glassLevelPanel, 0.82)
    readonly property real glassStrongAlpha: MoUI.Tokens.glassFill(bg0, MoUI.Tokens.glassLevelDialog, 0.92)
    readonly property color glass: Qt.alpha(bg0, glassAlpha)
    readonly property color glassStrong: Qt.alpha(bg0, glassStrongAlpha)
    readonly property color glassHover: Qt.tint(glass, Qt.alpha(nativePalette.highlight, 0.08))
    readonly property color hairline: MoUI.Tokens.glassEdge(bg0, MoUI.Tokens.glassLevelPanel)
    readonly property color hairlineStrong: Qt.alpha(nativePalette.highlight, 0.45)
    readonly property color innerLight: MoUI.Tokens.glassSpecular(bg0, MoUI.Tokens.glassLevelPanel)
    readonly property color ink: nativePalette.windowText
    readonly property color ink2: Qt.alpha(ink, 0.78)
    readonly property color ink3: Qt.alpha(ink, 0.76)
    readonly property color accent: nativePalette.highlight
    readonly property color onAccent: nativePalette.highlightedText

    // The original coloured expression stays in the face/voice stage. Reading
    // accents use a darker variant on pale surfaces so status remains legible.
    readonly property color faceCyan: "#35D8F4"
    readonly property color faceMint: "#3DF2C4"
    readonly property color faceViolet: "#9B7BFF"
    readonly property color faceRose: "#FF6FB5"
    readonly property color faceAmber: "#FFC46B"
    readonly property color faceDanger: "#FF5C7A"
    readonly property color faceOff: "#6B7390"
    function readingAccent(color) { return light ? Qt.darker(color, 2.6) : color }
    readonly property color cyan: readingAccent(faceCyan)
    readonly property color mint: readingAccent(faceMint)
    readonly property color violet: readingAccent(faceViolet)
    readonly property color rose: readingAccent(faceRose)
    readonly property color amber: readingAccent(faceAmber)
    readonly property color danger: readingAccent(faceDanger)
    readonly property color ok: readingAccent("#48E0A0")
    readonly property color off: light ? nativePalette.mid : faceOff

    function phaseColor(phase, style) {
        switch (phase) {
        case "listening": return faceMint
        case "thinking": return faceViolet
        case "speaking": return faceRose
        case "executing": return faceAmber
        case "error": return faceDanger
        case "offline": return faceOff
        default: return style === "holo" ? faceCyan : faceRose
        }
    }
    function phaseColor2(phase, style) {
        switch (phase) {
        case "listening": return faceCyan
        case "thinking": return "#5B8CFF"
        case "speaking": return faceViolet
        case "executing": return faceRose
        case "error": return "#7A1E3A"
        case "offline": return "#2A3050"
        default: return faceViolet
        }
    }

    // Basic controls cache Application.font. Listen to the same QApplication
    // signal the native platform emits instead of mirroring its settings.
    property font nativeFont: Qt.application.font
    property Connections fontUpdates: Connections {
        target: typeof miraApplication === "undefined" ? null : miraApplication
        function onFontChanged(font) { theme.nativeFont = font }
    }
    readonly property string font: nativeFont.family
    readonly property string mono: MoUI.Tokens.monospaceFamily
    readonly property int tiny: MoUI.Tokens.typeCaption
    readonly property int small: MoUI.Tokens.typeSecondary
    readonly property int body: MoUI.Tokens.typeBody
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
    readonly property real motionScale: MoUI.Tokens.liveLongDuration <= 1 ? 0.0 : MoUI.Tokens.liveLongDuration / 200.0
    readonly property int fast: Math.round(120 * motionScale)
    readonly property int normal: Math.round(220 * motionScale)
    readonly property int emphasized: Math.round(360 * motionScale)
}

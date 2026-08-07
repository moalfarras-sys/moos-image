import QtQuick

// MoOS first-party application metrics.
//
// Keep this object deliberately small: it is the shared contract for rhythm,
// shape, type and finite interaction motion, not a second theme engine. Colour
// continues to come from Kirigami.Theme so every active MoOS scheme owns it.
QtObject {
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 24
    readonly property int space6: 32

    readonly property int radiusSmall: 8
    readonly property int radiusControl: 12
    readonly property int radiusCard: 16
    readonly property int radiusPanel: 24

    readonly property int targetCompact: 40
    readonly property int targetControl: 44

    readonly property int typeCaption: 11
    readonly property int typeSecondary: 13
    readonly property int typeBody: 14
    readonly property int typeLabel: 15
    readonly property int typeTitle: 20
    readonly property int typeHeadline: 24
    readonly property int typeDisplay: 32

    readonly property int motionFast: 120
    readonly property int motionPress: 160
    readonly property int motionGeometry: 220
    readonly property int motionPage: 320

    // Shared surface, state and layout rails. Components may add geometry
    // specific to their content, but identity values belong here.
    readonly property real glassRestingOpacity: 0.22
    readonly property real glassHoverOpacity: 0.25
    readonly property real glassSelectedOpacity: 0.40
    readonly property real glassBorderOpacity: 0.34
    readonly property int borderHairline: 1
    readonly property int panelHeight: 54
    readonly property int dialogWidth: 792
    readonly property int dialogHeight: 576
    readonly property int iconSmall: 16
    readonly property int iconControl: 20
    readonly property int iconLarge: 24
    readonly property int shadowBlur: 15
    readonly property real disabledOpacity: 0.48
    readonly property real hoverScale: 1.02

    // Map legacy point choices onto the reviewed first-party type ramp while
    // preserving the user's system font scale. This also establishes 11 px as
    // the minimum functional text size.
    function typeSize(requested, scale) {
        var role = requested <= typeCaption ? typeCaption
                 : requested <= typeSecondary ? typeSecondary
                 : requested <= typeBody ? typeBody
                 : requested <= 17 ? typeLabel
                 : requested <= 22 ? typeTitle
                 : requested <= 28 ? typeHeadline
                 : typeDisplay
        return Math.round(role * Math.max(0.75, scale || 1))
    }

    function duration(enabled, role) {
        return enabled ? role : 0
    }
}

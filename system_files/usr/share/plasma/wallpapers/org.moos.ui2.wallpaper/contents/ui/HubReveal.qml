// Finite feedback for the shared Hub. No timer or idle animation.
import QtQuick
import org.moos.ui as MoUI

Item {
    id: reveal
    required property bool motionEnabled
    property int motionLevel: 1
    property real progress: 1
    property int previewEpoch: 0

    function preview() {
        previewEpoch++
        if (!entrance) return
        entrance.stop()
        progress = 1
        if (motionEnabled) {
            progress = 0
            const epoch = previewEpoch
            // Let duration bindings settle after enabling motion. Starting in
            // the change handler can still see the previous zero duration.
            Qt.callLater(function() {
                if (!reveal || !entrance) return
                if (reveal.motionEnabled && reveal.previewEpoch === epoch)
                    entrance.start()
            })
        }
    }
    onMotionLevelChanged: preview()
    onMotionEnabledChanged: {
        preview()
    }
    Component.onCompleted: preview()
    NumberAnimation {
        id: entrance
        target: reveal
        property: "progress"
        to: 1
        duration: reveal.motionEnabled
            ? (reveal.motionLevel >= 2 ? MoUI.Tokens.motionPage : MoUI.Tokens.motionGeometry) : 0
        easing.type: Easing.OutCubic
    }
}

pragma ComponentBehavior: Bound

import QtQuick

// Mo Store — how a page arrives: it fades in while rising 16 px into place, on the shared page
// rhythm (motionPage, OutCubic), every time it becomes the page on screen. A page binds its
// `transform` to `shift` and names itself as `target`. With animations off both durations are
// exactly 0, so the page is simply there.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: enter
    required property var win
    required property Item target
    readonly property Translate shift: Translate { id: offset }
    readonly property bool shown: enter.target !== null && enter.target.visible

    visible: false
    width: 0
    height: 0

    onShownChanged: {
        if (!enter.shown) return
        if (!enter.win.motionEnabled) {
            arrive.stop()
            enter.target.opacity = 1
            offset.y = 0
            return
        }
        arrive.restart()
    }

    ParallelAnimation {
        id: arrive
        NumberAnimation {
            target: enter.target
            property: "opacity"
            from: 0
            to: 1
            duration: enter.win.motionEnabled ? enter.win.design.motionPage : 0
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: offset
            property: "y"
            from: 16
            to: 0
            duration: enter.win.motionEnabled ? enter.win.design.motionPage : 0
            easing.type: Easing.OutCubic
        }
    }
}

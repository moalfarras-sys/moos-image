// A Hub card that holds more than one face.
//
// The three cards answer one question each — what time is it, what is the weather,
// how is the machine — and the question that follows on a real desk ("what is the
// date this week") used to need an app. The card is already on the desk, so it
// carries that answer as a second face.
//
// TWO RULES, and both come from where the hub lives.
//
// It is painted by the WALLPAPER, which is exactly why it can never cover an icon
// or a window — and exactly why no pointer event reaches it. Measured on the
// station on 2026-09-18: neither a click nor a wheel over a card arrived, because
// the desktop containment takes both. So this component holds NO input handler of
// its own (the dashboard's passivity is a shipped contract, gated in
// tests/test_moos_ui2.py). The face is chosen by `page`, which the wallpaper reads
// from its own configuration and the desktop's right-click menu writes.
//
// And it never turns itself: no carousel, no timer, no ambient rotation. A desktop
// that changes while nobody is looking is a distraction, and on a 4K wallpaper it
// is also a permanent repaint.
pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: stack

    required property bool motionEnabled
    // The faces, in order. Each one is an Item that fills the stack.
    default property alias pageData: pages.data
    property int page: 0
    readonly property int pageCount: pages.children.length
    readonly property var design: MoUI.Tokens

    Item {
        id: viewport
        anchors.fill: parent
        anchors.bottomMargin: stack.pageCount > 1 ? dots.height + 4 : 0

        Item {
            id: pages
            anchors.fill: parent
            onChildrenChanged: stack.applyPages()
        }
    }

    // Faces are cross-faded in place rather than slid: a slide inside a 300 px card
    // reads as a glitch at 4K, and the hub must never look like it is moving on the
    // wallpaper it is painted into.
    function applyPages() {
        for (let index = 0; index < pages.children.length; ++index) {
            const item = pages.children[index]
            // Anchor to the item's OWN parent — QML refuses an anchor to anything
            // that is not a parent or sibling ("Cannot anchor to an item that isn't
            // a parent or sibling", seen the first time this loaded live).
            item.anchors.fill = item.parent
            item.visible = Qt.binding(() => index === stack.page || item.opacity > 0)
            item.opacity = Qt.binding(() => index === stack.page ? 1 : 0)
            item.enabled = Qt.binding(() => index === stack.page)
        }
    }
    Component.onCompleted: stack.applyPages()

    // One dot per face, the current one drawn as a short bar: the card says it has
    // another side without asking to be pressed.
    Row {
        id: dots
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        spacing: 4
        visible: stack.pageCount > 1
        height: 4

        Repeater {
            model: stack.pageCount
            delegate: Rectangle {
                required property int index
                width: index === stack.page ? 12 : 4
                height: 4
                radius: 2
                color: Kirigami.Theme.textColor
                opacity: index === stack.page ? 0.62 : 0.24
                Behavior on width {
                    enabled: stack.motionEnabled
                    NumberAnimation {
                        duration: stack.design.motionFast
                        easing.type: stack.design.easeStandard
                    }
                }
                Behavior on opacity {
                    enabled: stack.motionEnabled
                    NumberAnimation { duration: stack.design.motionFast }
                }
            }
        }
    }
}

pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — an app's one button: Get, Open, Update, Visit, Added, Installed or Unavailable, by
// what is true of the app now (win.primaryAction). While a job works on this app the button
// becomes its progress: the job's real percentage filling the pill, or — when the backend gives
// no number — an honest indeterminate sweep that runs only while that job runs.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: button
    required property var win
    readonly property var design: win.design
    property var app: null
    // A filled accent pill on a hero or an app page; a quieter tinted one on cards.
    property bool prominent: false
    property bool large: false
    property bool tabStop: true
    // On a surface painted in an app's colour (the hero) the button wears that surface's ink
    // instead of the theme's accent, which could clash with — or vanish into — the app's colour.
    property bool onColour: false
    property color colourInk: win.inkOnDark
    property color colourBase: win.accent
    readonly property string action: win.primaryAction(button.app)
    readonly property string jobState: win.appJobState(button.app)
    readonly property real progress: win.appJobProgress(button.app)
    readonly property bool working: button.action === "progress"
    readonly property bool inert: button.action === "installed" || button.action === "blocked"
                                  || (button.action !== "progress" && win.jobIsActive()
                                      && (button.action === "get" || button.action === "update"
                                          || button.action === "website"))
    readonly property bool filled: !button.inert && !button.working
                                   && (button.prominent || button.action === "update")
    readonly property color ink: button.onColour
                               ? (button.filled ? button.colourBase : button.colourInk)
                               : button.filled ? win.accentText
                               : button.inert ? win.txt2
                               : win.lightScheme ? Qt.darker(win.accent, 1.05) : win.accent
    readonly property string label: {
        if (button.working) {
            if (button.jobState === "waiting") return win.local("في الانتظار", "Waiting")
            if (button.jobState === "starting") return win.local("يبدأ…", "Starting…")
            return button.progress >= 0 ? Math.round(button.progress) + "%" : win.local("جارٍ…", "Working…")
        }
        return win.primaryLabel(button.action)
    }
    readonly property string glyph: button.action === "open" ? "external"
                                  : button.action === "update" ? "refresh"
                                  : button.action === "installed" || button.action === "added" ? "check"
                                  : button.action === "website" ? "globe"
                                  : button.action === "blocked" ? "lock" : ""

    implicitHeight: button.large ? win.fs(44) : win.fs(34)
    implicitWidth: Math.max(button.large ? win.fs(132) : win.fs(84),
                            content.implicitWidth + (button.large ? design.space5 : design.space4) * 2)
    radius: height / 2
    color: button.onColour
         ? (button.filled ? button.colourInk : win.tint(button.colourInk, buttonHover.hovered ? 0.30 : 0.18))
         : button.filled ? win.accent
         : button.inert ? win.tint(win.txt, win.lightScheme ? 0.07 : 0.09)
         : win.tint(win.accent, buttonHover.hovered ? 0.26 : (win.lightScheme ? 0.14 : 0.17))
    border.width: button.action === "added" ? 1 : 0
    border.color: win.tint(win.accent, 0.6)
    scale: feedback.value
    activeFocusOnTab: button.tabStop && !button.inert && !button.working
    Accessible.role: Accessible.Button
    Accessible.name: button.label + (button.app ? ", " + button.win.localName(button.app) : "")
    Accessible.onPressAction: button.press()
    Keys.onReturnPressed: button.press()
    Keys.onEnterPressed: button.press()
    Keys.onSpacePressed: button.press()
    Behavior on color { ColorAnimation { duration: button.win.motionEnabled ? button.design.motionFast : 0 } }

    function press() {
        if (button.inert || button.working) return
        button.win.performPrimary(button.app)
    }

    MoUI.SpringFeedback {
        id: feedback
        active: button.visible
        motionEnabled: button.win.motionEnabled
        targetScale: buttonTap.pressed && !button.inert ? button.design.pressScale : 1
    }
    HoverHandler { id: buttonHover; enabled: !button.inert; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: buttonTap; enabled: !button.inert; onTapped: button.press() }
    FocusRing { win: button.win }

    // The job's progress, inside the pill.
    Item {
        anchors.fill: parent
        visible: button.working
        clip: true
        Rectangle {
            anchors.fill: parent
            radius: button.radius
            color: button.win.tint(button.onColour ? button.colourInk : button.win.accent, 0.16)
        }
        Rectangle {
            visible: button.progress >= 0
            height: parent.height
            width: parent.width * Math.max(0.06, Math.min(1, button.progress / 100))
            radius: button.radius
            color: button.win.tint(button.onColour ? button.colourInk : button.win.accent, 0.42)
            anchors.left: parent.left
            Behavior on width { NumberAnimation { duration: button.win.motionEnabled ? button.design.motionGeometry : 0; easing.type: Easing.OutCubic } }
        }
        Rectangle {
            id: sweep
            visible: button.progress < 0
            width: parent.width * 0.38
            height: parent.height
            radius: button.radius
            color: button.win.tint(button.onColour ? button.colourInk : button.win.accent, 0.38)
            // The one endless motion a card may carry, and only while its job runs.
            SequentialAnimation on x {
                running: sweep.visible && button.working && button.win.motionEnabled
                loops: Animation.Infinite
                NumberAnimation {
                    from: button.win.rtl ? (sweep.parent ? sweep.parent.width : 0) : -sweep.width
                    to: button.win.rtl ? -sweep.width : (sweep.parent ? sweep.parent.width : 0)
                    duration: button.win.motionEnabled ? button.design.motionPortal * 3 : 0
                    easing.type: Easing.InOutQuad
                }
            }
        }
    }

    RowLayout {
        id: content
        anchors.centerIn: parent
        spacing: button.design.space1 + 2
        Glyph {
            win: button.win
            visible: button.glyph !== "" && !button.working
            name: button.glyph === "" ? "spark" : button.glyph
            tint: button.ink
            Layout.preferredWidth: button.large ? button.win.fs(16) : button.win.fs(14)
            Layout.preferredHeight: button.large ? button.win.fs(16) : button.win.fs(14)
        }
        Text {
            text: button.label
            color: button.working ? (button.onColour ? button.colourInk : button.win.txt) : button.ink
            font.family: button.win.uiFont
            font.pixelSize: button.large ? button.win.typePx(15) : button.win.typePx(13)
            font.weight: Font.DemiBold
        }
    }
}

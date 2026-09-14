// Execute with the source QML_IMPORT_PATH and moos-qml-shell. No desktop writes.
import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtTest as Test
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Window {
    id: review
    visible: true
    width: 760
    height: 320
    title: "MoOS · Motion review"
    color: Kirigami.Theme.backgroundColor
    property bool motionAllowed: true
    property bool feedbackActive: true
    property real targetScale: 1
    property int activations: 0
    Rectangle {
        id: plate
        anchors.centerIn: parent
        width: 680; height: 232
        radius: MoUI.Tokens.radiusPanel
        color: Kirigami.Theme.backgroundColor
        border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.30)
        ColumnLayout {
            anchors.centerIn: parent
            spacing: MoUI.Tokens.space5
            Text {
                text: MoUI.Locale.local("MoOS · استجابة طبيعية وهادئة", "MoOS · Quiet, physical response")
                color: Kirigami.Theme.textColor
                font.family: MoUI.Tokens.interfaceFamily
                font.pixelSize: MoUI.Tokens.typeTitle
            }
            RowLayout {
                spacing: MoUI.Tokens.space4
                MoUI.Button {
                    id: action
                    label: MoUI.Locale.local("افتح مساحة العمل", "Open workspace")
                    primary: true
                    motionEnabled: review.motionAllowed
                    onClicked: review.activations++
                }
                MoUI.Button {
                    label: MoUI.Locale.local("الإعدادات", "Settings")
                    iconName: "settings-configure"
                    motionEnabled: review.motionAllowed
                }
                MoUI.IconButton {
                    symbol: "media-playback-start"
                    accessibleLabel: MoUI.Locale.local("تشغيل", "Play")
                    motionEnabled: review.motionAllowed
                }
            }
        }
    }
    Item {
        id: probe
        scale: response.value
        MoUI.SpringFeedback {
            id: response
            active: review.feedbackActive
            targetScale: review.targetScale
            motionEnabled: review.motionAllowed
        }
    }
    Test.TestCase { id: driver; name: "MoOSMotion"; when: false }
    MoUI.SpringFeedback {
        id: initialReduced
        targetScale: 0.92
        motionEnabled: false
    }
    Timer {
        interval: 300
        running: true
        onTriggered: {
            try {
                driver.compare(initialReduced.value, 0.92)
                driver.compare(initialReduced.settling, false)
                review.targetScale = MoUI.Tokens.pressScale
                driver.wait(32)
                console.warn("INITIAL_SPRING", response.settling, response.value, probe.scale, review.targetScale)
                driver.verify(response.settling, "physical spring starts")
                var began = Date.now()
                driver.tryCompare(response, "settling", false, 700)
                driver.compare(probe.scale, MoUI.Tokens.pressScale)
                console.warn("SPRING_SETTLED_MS", Date.now() - began + 32)

                // Reverse during flight, then disable while moving. Both the
                // endpoint and the original binding must survive completion.
                review.targetScale = MoUI.Tokens.hoverScale
                driver.wait(32)
                review.targetScale = 1
                driver.wait(16)
                review.motionAllowed = false
                console.warn("REDUCED_DURING_FLIGHT", response.settling, probe.scale, review.targetScale)
                driver.compare(response.settling, false)
                driver.compare(probe.scale, 1)
                review.targetScale = MoUI.Tokens.pressScale
                driver.compare(probe.scale, MoUI.Tokens.pressScale)
                driver.compare(response.settling, false)
                review.targetScale = 1
                driver.compare(probe.scale, 1)
                review.motionAllowed = true
                review.targetScale = MoUI.Tokens.hoverScale
                driver.wait(32)
                review.feedbackActive = false
                driver.compare(response.settling, false)
                driver.compare(probe.scale, MoUI.Tokens.hoverScale)
                review.targetScale = 1
                driver.compare(probe.scale, 1)
                driver.compare(response.settling, false)
                review.feedbackActive = true
                review.motionAllowed = false

                // Real shared button input, not just a synthetic scale.
                review.requestActivate()
                action.forceActiveFocus()
                driver.keyPress(Qt.Key_Space)
                driver.compare(action.down, true)
                driver.compare(action.scale, 1) // hit target never shrinks
                driver.compare(action.background.scale, MoUI.Tokens.pressScale)
                driver.compare(action.contentItem.scale, MoUI.Tokens.pressScale)
                driver.keyRelease(Qt.Key_Space)
                driver.compare(review.activations, 1)
                driver.compare(action.scale, 1)
                driver.compare(action.background.scale, 1)
                action.enabled = false
                driver.keyClick(Qt.Key_Space)
                driver.compare(review.activations, 1)
                action.enabled = true
                review.motionAllowed = true
                driver.mouseClick(action)
                driver.compare(review.activations, 2)
                driver.wait(700)
                driver.compare(action.scale, 1)
                driver.compare(action.background.scale, 1)
                driver.compare(response.settling, false)
                console.warn("MOOS_MOTION_PASSED: settle, reversal, reduced motion, binding, keyboard, pointer, disabled, idle")
                var output = Qt.application.arguments.filter(a => a.indexOf("--out=") === 0)[0]
                if (output) {
                    plate.grabToImage(function(result) {
                        if (!result.saveToFile(output.substring(6))) { Qt.exit(1); return }
                        Qt.quit()
                    })
                } else Qt.quit()
            } catch (error) { console.error(error); Qt.exit(1) }
        }
    }
}

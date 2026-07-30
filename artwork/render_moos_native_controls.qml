// Deterministic visual-review harness for the MoOS native Plasma controls.
//
// This intentionally uses KSvg.FrameSvgItem and Plasma Components 3, the same
// code paths used by plasmashell. Rendering the source SVG as one flat image is
// misleading because Plasma selects and stretches individual element prefixes.
//
// Run inside a real Plasma Wayland session:
//   QT_QPA_PLATFORM=wayland qml-qt6 artwork/render_moos_native_controls.qml
//
// The capture is written to /var/tmp/moos-native-controls-kframe.png.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksvg as KSvg
import org.kde.plasma.components as PC3
// Required so KSvg resolves the running Plasma theme rather than a fallback.
import org.kde.plasma.core as PlasmaCore

QQC2.ApplicationWindow {
    id: window

    width: 1240
    height: 780
    visible: true
    color: Kirigami.Theme.backgroundColor
    title: "MoOS native controls · KSvg proof"

    readonly property int radiusM: 12
    readonly property color quietSurface: Qt.alpha(
        Kirigami.Theme.alternateBackgroundColor, 0.72)
    readonly property color quietBorder: Qt.alpha(
        Kirigami.Theme.textColor, 0.14)

    component StateSample: ColumnLayout {
        id: sample

        required property string asset
        required property string statePrefix
        required property string caption
        property string content: caption
        property bool compact: false

        spacing: 6

        Item {
            Layout.preferredWidth: sample.compact ? 116 : 164
            Layout.preferredHeight: sample.compact ? 40 : 46

            KSvg.FrameSvgItem {
                anchors.fill: parent
                imagePath: `widgets/${sample.asset}`
                prefix: sample.statePrefix
            }

            PC3.Label {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                text: sample.content
                color: Kirigami.Theme.textColor
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                font.pixelSize: 13
                font.weight: Font.Medium
            }
        }

        PC3.Label {
            Layout.alignment: Qt.AlignHCenter
            text: sample.caption
            color: Kirigami.Theme.disabledTextColor
            font.pixelSize: 11
        }
    }

    component StateStrip: ColumnLayout {
        id: strip

        required property string title
        required property string asset
        required property var states
        property bool compact: false

        Layout.fillWidth: true
        spacing: 10

        PC3.Label {
            text: strip.title
            color: Kirigami.Theme.textColor
            font.pixelSize: 15
            font.weight: Font.DemiBold
        }

        RowLayout {
            spacing: 12

            Repeater {
                model: strip.states

                delegate: StateSample {
                    required property var modelData
                    asset: strip.asset
                    statePrefix: String(modelData.prefix)
                    caption: String(modelData.caption)
                    content: String(modelData.content || modelData.caption)
                    compact: strip.compact
                }
            }
        }
    }

    Item {
        id: preview
        anchors.fill: parent

        Rectangle {
            anchors.fill: parent
            color: Kirigami.Theme.backgroundColor
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 18

            RowLayout {
                Layout.fillWidth: true
                spacing: 16

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    PC3.Label {
                        text: "MoOS native control language"
                        color: Kirigami.Theme.textColor
                        font.pixelSize: 22
                        font.weight: Font.DemiBold
                    }

                    PC3.Label {
                        text: "Active Plasma theme · exact FrameSvg slicing · semantic states"
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: 12
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 148
                    Layout.preferredHeight: 32
                    radius: 10
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.12)
                    border.width: 1
                    border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.44)

                    PC3.Label {
                        anchors.centerIn: parent
                        text: "KSvg / PC3"
                        color: Kirigami.Theme.highlightColor
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: window.quietBorder
            }

            StateStrip {
                title: "Button hierarchy"
                asset: "button"
                states: [
                    { prefix: "normal", caption: "Rest", content: "Continue" },
                    { prefix: "hover", caption: "Hover", content: "Continue" },
                    { prefix: "focus", caption: "Keyboard focus", content: "Continue" },
                    { prefix: "pressed", caption: "Pressed", content: "Continue" },
                    { prefix: "toolbutton-hover", caption: "Tool hover", content: "⋯" },
                    { prefix: "toolbutton-pressed", caption: "Tool pressed", content: "⋯" }
                ]
            }

            StateStrip {
                title: "Text field"
                asset: "lineedit"
                states: [
                    { prefix: "base", caption: "Rest", content: "Search MoOS" },
                    { prefix: "hover", caption: "Hover", content: "Search MoOS" },
                    { prefix: "focus", caption: "Pointer focus", content: "Search MoOS" },
                    { prefix: "focusframe", caption: "Keyboard focus", content: "Search MoOS" }
                ]
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 28

                StateStrip {
                    Layout.fillWidth: false
                    title: "List rows"
                    asset: "listitem"
                    compact: true
                    states: [
                        { prefix: "normal", caption: "Rest", content: "Network" },
                        { prefix: "hover", caption: "Hover", content: "Network" },
                        { prefix: "pressed", caption: "Selected", content: "Network" },
                        { prefix: "section", caption: "Section", content: "Network" }
                    ]
                }

                StateStrip {
                    Layout.fillWidth: false
                    title: "Menu and view rows"
                    asset: "viewitem"
                    compact: true
                    states: [
                        { prefix: "normal", caption: "Rest", content: "Open" },
                        { prefix: "hover", caption: "Hover", content: "Open" },
                        { prefix: "selected", caption: "Selected", content: "Open" },
                        { prefix: "selected+hover", caption: "Selected hover", content: "Open" }
                    ]
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 142
                radius: window.radiusM
                color: window.quietSurface
                border.width: 1
                border.color: window.quietBorder

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 14

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        PC3.Label {
                            text: "Real Plasma Components 3"
                            color: Kirigami.Theme.textColor
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }

                        PC3.Label {
                            text: "Control metrics, padding and type are rendered by Plasma itself."
                            color: Kirigami.Theme.disabledTextColor
                            font.pixelSize: 11
                        }
                    }

                    PC3.Button {
                        text: "Continue"
                    }

                    PC3.Button {
                        text: "Selected"
                        checkable: true
                        checked: true
                    }

                    PC3.Button {
                        text: "Unavailable"
                        enabled: false
                    }

                    PC3.TextField {
                        Layout.preferredWidth: 188
                        placeholderText: "Search MoOS"
                    }

                    PC3.ItemDelegate {
                        Layout.preferredWidth: 132
                        text: "Appearance"
                        icon.name: "moos-ui-symbolic"
                        highlighted: true
                    }

                    ColumnLayout {
                        Layout.preferredWidth: 154
                        LayoutMirroring.enabled: true
                        LayoutMirroring.childrenInherit: true
                        spacing: 4

                        PC3.Label {
                            text: "RTL"
                            color: Kirigami.Theme.disabledTextColor
                            font.pixelSize: 10
                        }

                        PC3.MenuItem {
                            Layout.fillWidth: true
                            text: "إعدادات النظام"
                            icon.name: "moos-settings-symbolic"
                            highlighted: true
                        }
                    }
                }
            }

            PC3.Label {
                Layout.alignment: Qt.AlignRight
                text: "No input simulation · no perpetual animation · captured after layout settles"
                color: Kirigami.Theme.disabledTextColor
                font.pixelSize: 10
            }
        }
    }

    Timer {
        interval: 1400
        running: true
        repeat: false
        onTriggered: preview.grabToImage(function(result) {
            if (!result.saveToFile("/var/tmp/moos-native-controls-kframe.png"))
                console.error("could not save native-control preview")
            Qt.quit()
        })
    }
}

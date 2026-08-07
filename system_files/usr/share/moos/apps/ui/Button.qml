import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Accessible, palette-owned action control shared by first-party QML apps.
// AbstractButton provides pointer, keyboard, checked and accessibility
// semantics; this file owns only MoOS's shape, rhythm and interaction states.
QQC2.AbstractButton {
    id: control

    property string label: ""
    property string iconName: ""
    property bool primary: false
    property bool destructive: false
    property bool compact: false
    property bool motionEnabled: Kirigami.Units.longDuration > 1

    property color surfaceColor: Kirigami.Theme.backgroundColor
    property color accentColor: Kirigami.Theme.highlightColor
    property color dangerColor: Kirigami.Theme.negativeTextColor
    property color textColor: Kirigami.Theme.textColor
    property color mutedTextColor: Kirigami.Theme.disabledTextColor
    property color accentForegroundColor: Kirigami.Theme.highlightedTextColor
    property color outlineColor: Qt.alpha(textColor, tokens.glassBorderOpacity)
    property real cornerRadius: tokens.radiusControl
    property int fontPixelSize: tokens.typeSecondary
    property int iconPixelSize: tokens.typeBody

    readonly property color actionColor: destructive ? dangerColor : accentColor
    // `negativeTextColor` is an ink role, not a guaranteed fill/ink pair.
    // Destructive actions therefore stay on the current surface with negative
    // ink + outline. Only highlightColor uses highlightedTextColor as its
    // theme-defined paired foreground.
    readonly property color restingColor: primary ? accentColor : surfaceColor
    readonly property color foregroundColor: !enabled ? mutedTextColor
                                            : primary ? accentForegroundColor
                                            : destructive ? dangerColor
                                            : textColor
    readonly property real stateLayerOpacity: !enabled ? 0
                                              : down ? tokens.glassSelectedOpacity
                                              : hovered ? tokens.glassHoverOpacity
                                             : 0

    text: label
    hoverEnabled: true
    activeFocusOnTab: enabled && visible
    Accessible.role: Accessible.Button
    Accessible.name: label

    implicitHeight: compact ? tokens.targetCompact : tokens.targetControl
    implicitWidth: Math.max(tokens.targetControl,
        contentRow.implicitWidth + tokens.space5)
    leftPadding: tokens.space3
    rightPadding: tokens.space3
    topPadding: tokens.space2
    bottomPadding: tokens.space2
    opacity: enabled ? 1 : tokens.disabledOpacity
    scale: enabled && down ? 0.97 : 1

    Behavior on scale {
        NumberAnimation {
            duration: control.motionEnabled ? tokens.motionFast : 0
            easing.type: Easing.OutCubic
        }
    }

    background: Rectangle {
        radius: control.cornerRadius
        color: control.enabled ? control.restingColor : control.surfaceColor
        border.width: control.primary ? 0 : 1
        border.color: !control.enabled ? control.outlineColor
                    : control.destructive ? Qt.alpha(control.dangerColor,
                        control.hovered || control.activeFocus ? 0.82 : 0.52)
                    : control.hovered ? Qt.alpha(control.actionColor, 0.58)
                    : control.outlineColor

        Behavior on border.color {
            ColorAnimation {
                duration: control.motionEnabled ? tokens.motionFast : 0
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: control.primary
                ? Qt.alpha(control.accentForegroundColor, control.stateLayerOpacity)
                : Qt.alpha(control.actionColor, control.stateLayerOpacity)
            opacity: control.enabled ? 1 : 0

            Behavior on color {
                ColorAnimation {
                    duration: control.motionEnabled ? tokens.motionFast : 0
                }
            }
        }
    }

    contentItem: RowLayout {
        id: contentRow
        spacing: tokens.space2

        SymbolIcon {
            visible: control.iconName !== ""
            symbol: control.iconName
            foreground: control.foregroundColor
            Layout.preferredWidth: control.iconPixelSize
            Layout.preferredHeight: control.iconPixelSize
        }
        Text {
            Layout.fillWidth: true
            text: control.label
            color: control.foregroundColor
            font.family: control.font.family
            font.pixelSize: control.fontPixelSize
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    FocusRing {
        anchors.fill: control
        accentColor: control.actionColor
        controlRadius: control.cornerRadius
    }

    Tokens { id: tokens }
}

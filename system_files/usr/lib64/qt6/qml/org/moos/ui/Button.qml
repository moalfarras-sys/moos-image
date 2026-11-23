import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Accessible semantic action control shared by every first-party QML surface.
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
    property color outlineColor: Qt.alpha(textColor, Tokens.glassBorderOpacity)
    property real cornerRadius: Tokens.radiusControl
    property int fontPixelSize: Tokens.typeSecondary
    property int iconPixelSize: Tokens.iconControl

    readonly property color actionColor: destructive ? dangerColor : accentColor
    readonly property color restingColor: primary ? accentColor : surfaceColor
    readonly property color foregroundColor: !enabled ? mutedTextColor
                                            : primary ? accentForegroundColor
                                            : destructive ? dangerColor
                                            : textColor
    readonly property real stateLayerOpacity: !enabled ? 0
                                              : down ? Tokens.surfacePressedOpacity
                                              : hovered ? Tokens.surfaceHoverOpacity : 0

    text: label
    hoverEnabled: true
    activeFocusOnTab: enabled && visible
    Accessible.role: Accessible.Button
    Accessible.name: label

    implicitHeight: Math.max(compact ? Tokens.targetCompact : Tokens.targetControl,
                             contentRow.implicitHeight + topPadding + bottomPadding)
    implicitWidth: Math.max(Tokens.targetControl,
        contentRow.implicitWidth + leftPadding + rightPadding)
    leftPadding: Tokens.space3
    rightPadding: Tokens.space3
    topPadding: Tokens.space2
    bottomPadding: Tokens.space2
    opacity: enabled ? 1 : Tokens.disabledOpacity

    SpringFeedback {
        id: feedback
        active: control.visible
        targetScale: control.enabled && control.down ? Tokens.pressScale : 1
        motionEnabled: control.motionEnabled
    }

    background: Rectangle {
        scale: feedback.value
        id: plate
        radius: control.cornerRadius
        topLeftRadius: LayoutMirroring.enabled ? Math.min(radius, Tokens.radiusSquare) : radius
        topRightRadius: LayoutMirroring.enabled ? radius : Math.min(radius, Tokens.radiusSquare)
        color: control.enabled ? control.restingColor : control.surfaceColor
        border.width: control.primary ? 0 : Tokens.borderHairline
        border.color: !control.enabled ? control.outlineColor
                    : control.destructive ? Qt.alpha(control.dangerColor,
                        control.hovered || control.activeFocus
                            ? Tokens.destructiveHoverBorderOpacity
                            : Tokens.destructiveBorderOpacity)
                    : control.hovered ? Qt.alpha(control.actionColor,
                        Tokens.focusOpacity) : control.outlineColor

        Behavior on border.color {
            ColorAnimation {
                duration: Tokens.duration(control.motionEnabled, Tokens.motionFast)
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            topLeftRadius: plate.topLeftRadius
            topRightRadius: plate.topRightRadius
            color: control.primary ? "transparent" : Qt.alpha(control.actionColor, control.stateLayerOpacity)
            border.width: control.primary && (control.hovered || control.down) ? Tokens.focusWidth : 0
            border.color: Qt.alpha(control.accentForegroundColor, control.down ? 0.48 : 0.30)
            opacity: control.enabled ? 1 : 0

            Behavior on color {
                ColorAnimation {
                    duration: Tokens.duration(control.motionEnabled, Tokens.motionFast)
                }
            }
        }
    }

    contentItem: Item {
        implicitWidth: contentRow.implicitWidth
        implicitHeight: contentRow.implicitHeight
        // The press answers on the content item itself (the motion contract
        // reads contentItem.scale); the row inside only centres the content.
        scale: feedback.value
        RowLayout {
            id: contentRow
            anchors.centerIn: parent
            width: Math.min(implicitWidth, parent.width)
            spacing: Tokens.space2

            SymbolIcon {
                visible: control.iconName.length > 0
                symbol: control.iconName
                foreground: control.foregroundColor
                Layout.preferredWidth: control.iconPixelSize
                Layout.preferredHeight: control.iconPixelSize
            }
            Text {
                visible: control.label.length > 0
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: control.label
                textFormat: Text.PlainText
                color: control.foregroundColor
                font.family: control.font.family
                font.pixelSize: control.fontPixelSize
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
    }

    FocusRing {
        anchors.fill: control
        accentColor: control.actionColor
        controlRadius: control.cornerRadius
        topLeftRadius: plate.topLeftRadius + Tokens.focusGap
        topRightRadius: plate.topRightRadius + Tokens.focusGap
    }
}

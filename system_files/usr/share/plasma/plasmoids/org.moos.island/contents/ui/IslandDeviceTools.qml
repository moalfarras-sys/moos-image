pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PC3
import org.moos.ui as MoUI
import org.moos.keyboard as MoKeyboard

ColumnLayout {
    id: tools
    required property bool rtl
    signal back()
    spacing: MoUI.Tokens.space3
    LayoutMirroring.enabled: false
    LayoutMirroring.childrenInherit: true

    function focusBack() { backButton.forceActiveFocus(Qt.TabFocusReason); }
    Keys.onEscapePressed: event => { tools.back(); event.accepted = true; }

    RowLayout {
        Layout.fillWidth: true
        layoutDirection: tools.rtl ? Qt.RightToLeft : Qt.LeftToRight
        spacing: MoUI.Tokens.space3

        PC3.ToolButton {
            id: backButton
            objectName: "islandDeviceToolsBack"
            Layout.minimumWidth: MoUI.Tokens.targetComfortable
            Layout.minimumHeight: MoUI.Tokens.targetComfortable
            icon.name: tools.rtl ? "go-next-symbolic" : "go-previous-symbolic"
            text: tools.rtl ? "رجوع" : "Back"
            display: PC3.AbstractButton.IconOnly
            PC3.ToolTip.text: text
            PC3.ToolTip.visible: hovered
            PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
            onClicked: tools.back()
            Keys.onReturnPressed: event => { if (!event.isAutoRepeat) clicked(); event.accepted = true; }
            Keys.onEnterPressed: event => { if (!event.isAutoRepeat) clicked(); event.accepted = true; }
        }

        PC3.Label {
            Layout.fillWidth: true
            text: tools.rtl ? "أدوات الجهاز" : "Device tools"
            font.pixelSize: MoUI.Tokens.typeTitle
            font.weight: Font.DemiBold
            horizontalAlignment: tools.rtl ? Text.AlignRight : Text.AlignLeft
            wrapMode: Text.Wrap
        }
    }

    MoKeyboard.SystemStrip {
        Layout.fillWidth: true
        Layout.preferredHeight: implicitHeight
        rtl: tools.rtl
        language: tools.rtl ? "ar" : "en"
    }
}

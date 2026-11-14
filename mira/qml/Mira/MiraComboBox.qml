pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic

// Keep ComboBox's native selection, keyboard and activation owner. Only its
// reading surfaces follow Mira's shared palette, material and type system.
ComboBox {
    id: control
    implicitWidth: 240
    implicitHeight: Math.max(44, contentItem.implicitHeight + topPadding + bottomPadding)
    padding: 12
    topPadding: 8
    bottomPadding: 8
    spacing: 8
    leftPadding: padding + (mirrored ? indicator.width + spacing : 0)
    rightPadding: padding + (mirrored ? 0 : indicator.width + spacing)
    hoverEnabled: true
    font.family: Theme.font
    font.pixelSize: Theme.body

    contentItem: T {
        objectName: "comboCurrentText"
        text: control.displayText
        font: control.font
        color: control.enabled ? Theme.ink : Theme.ink3
        wrapMode: Text.NoWrap
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: control.mirrored ? Text.AlignRight : Text.AlignLeft
    }
    indicator: Icon {
        objectName: "comboIndicator"
        name: "chevron-down"
        size: 16
        x: control.mirrored ? control.padding : control.width - width - control.padding
        y: (control.height - height) / 2
        color: control.enabled ? Theme.ink2 : Theme.ink3
    }
    background: Rectangle {
        radius: Theme.rControl
        color: control.down || control.hovered ? Theme.glassHover : Theme.glass
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.accent : Theme.hairlineStrong
    }
    delegate: ItemDelegate {
        id: entry
        required property var model
        required property int index
        objectName: "comboEntry" + index
        width: ListView.view.width
        implicitHeight: Math.max(44, contentItem.implicitHeight + topPadding + bottomPadding)
        padding: 12
        topPadding: 8
        bottomPadding: 8
        font: control.font
        highlighted: control.highlightedIndex === index
        hoverEnabled: control.hoverEnabled
        contentItem: T {
            text: entry.model[control.textRole]
            font: entry.font
            color: Theme.ink
            wrapMode: Text.NoWrap
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: control.mirrored ? Text.AlignRight : Text.AlignLeft
        }
        background: Rectangle {
            radius: Theme.rSmall
            color: entry.highlighted || entry.down ? Qt.tint(Theme.bg1, Qt.alpha(Theme.accent, 0.12))
                                                  : entry.hovered ? Theme.bg2 : "transparent"
            border.width: entry.visualFocus ? 1 : 0
            border.color: Theme.accent
        }
    }
    popup: Popup {
        objectName: "comboPopup"
        y: control.height + 4
        width: control.width
        height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding,
                         Math.max(0, control.Window.height - topMargin - bottomMargin))
        padding: 6
        topMargin: 12
        bottomMargin: 12
        font: control.font
        palette: control.palette
        contentItem: ListView {
            objectName: "comboList"
            clip: true
            implicitHeight: contentHeight
            model: control.delegateModel
            currentIndex: control.highlightedIndex
            highlightMoveDuration: 0
            ScrollIndicator.vertical: ScrollIndicator { }
        }
        background: Rectangle {
            objectName: "comboPopupBackground"
            radius: Theme.rControl
            // Popups need an opaque reading floor over any app or wallpaper.
            color: Theme.bg1
            border.width: 1
            border.color: Theme.hairlineStrong
        }
    }
}

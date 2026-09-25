// SPDX-License-Identifier: GPL-2.0-or-later
// A three-way choice (glass clarity, wallpaper motion) inside a FormCard. The filled
// segment is the value moos-theme MEASURED; pressing another one only asks for it, and
// nothing lights until the page has read the new value back. A segment is not checkable,
// so a press can never paint the wish as though it were the state.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: choice

    property string glyph: ""
    property string description: ""
    // [{ value: "still", label: "Still" }, …]
    property var options: []
    // The measured value; "" while it is not known.
    property string current: ""
    // The value a running change asked for; "" when none is running.
    property string requestedValue: ""
    readonly property bool motion: Kirigami.Units.longDuration > 1
    readonly property bool wide: width > Kirigami.Units.gridUnit * 24
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    signal picked(string value)

    focusPolicy: Qt.NoFocus
    hoverEnabled: false
    background: null
    Accessible.role: Accessible.Grouping
    Accessible.name: text
    Accessible.description: description

    contentItem: ColumnLayout {
        spacing: MoUI.Tokens.space3

        RowLayout {
            Layout.fillWidth: true
            spacing: MoUI.Tokens.space3

            MoUI.SymbolIcon {
                Layout.alignment: Qt.AlignTop
                visible: choice.glyph !== ""
                symbol: MoUI.SymbolCatalog.resolve(choice.glyph)
                foreground: Kirigami.Theme.highlightColor
                implicitWidth: MoUI.Tokens.iconLarge
                implicitHeight: MoUI.Tokens.iconLarge
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: MoUI.Tokens.space1

                Controls.Label {
                    Layout.fillWidth: true
                    text: choice.text
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignLeft
                    wrapMode: Text.WordWrap
                    Accessible.ignored: true
                }
                Controls.Label {
                    Layout.fillWidth: true
                    visible: choice.description !== ""
                    text: choice.description
                    color: choice.secondaryInk
                    horizontalAlignment: Text.AlignLeft
                    wrapMode: Text.WordWrap
                    Accessible.ignored: true
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: choice.wide ? Math.max(1, choice.options.length) : 1
            columnSpacing: MoUI.Tokens.space2
            rowSpacing: MoUI.Tokens.space2
            uniformCellWidths: true

            Repeater {
                model: choice.options

                delegate: Controls.AbstractButton {
                    id: segment

                    required property var modelData
                    readonly property bool selected: segment.modelData.value === choice.current
                    readonly property bool asked: segment.modelData.value === choice.requestedValue

                    Layout.fillWidth: true
                    implicitHeight: Math.max(MoUI.Tokens.targetControl, segmentRow.implicitHeight + MoUI.Tokens.space2 * 2)
                    implicitWidth: segmentRow.implicitWidth + MoUI.Tokens.space4 * 2
                    enabled: choice.enabled
                    hoverEnabled: true
                    focusPolicy: Qt.StrongFocus
                    activeFocusOnTab: true
                    Accessible.role: Accessible.RadioButton
                    Accessible.checkable: true
                    Accessible.checked: selected
                    Accessible.name: segment.modelData.label
                    onClicked: choice.picked(segment.modelData.value)
                    Keys.onReturnPressed: if (enabled) choice.picked(segment.modelData.value)
                    Keys.onEnterPressed: if (enabled) choice.picked(segment.modelData.value)

                    background: Rectangle {
                        radius: MoUI.Tokens.radiusControl
                        color: segment.selected ? Qt.alpha(Kirigami.Theme.highlightColor, 0.20)
                             : segment.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.09)
                             : Qt.alpha(Kirigami.Theme.textColor, 0.04)
                        border.width: segment.selected ? MoUI.Tokens.focusWidth : MoUI.Tokens.borderHairline
                        border.color: segment.selected || segment.asked ? Kirigami.Theme.highlightColor
                                                                        : Qt.alpha(Kirigami.Theme.textColor, 0.16)
                        Behavior on color {
                            ColorAnimation { duration: choice.motion ? MoUI.Tokens.motionFast : 0 }
                        }

                        MoUI.FocusRing {
                            controlRadius: MoUI.Tokens.radiusControl
                            visible: segment.visualFocus
                        }
                    }
                    contentItem: Item {
                        implicitWidth: segmentRow.implicitWidth
                        implicitHeight: segmentRow.implicitHeight

                        RowLayout {
                            id: segmentRow
                            anchors.centerIn: parent
                            spacing: MoUI.Tokens.space2

                            MoUI.SymbolIcon {
                                visible: segment.selected || segment.asked
                                symbol: MoUI.SymbolCatalog.resolve(segment.selected ? "check" : "refresh")
                                foreground: Kirigami.Theme.highlightColor
                                implicitWidth: MoUI.Tokens.iconSmall
                                implicitHeight: MoUI.Tokens.iconSmall
                            }
                            Controls.Label {
                                text: segment.modelData.label
                                textFormat: Text.PlainText
                                color: Kirigami.Theme.textColor
                                font.weight: segment.selected ? Font.DemiBold : Font.Normal
                                Accessible.ignored: true
                            }
                        }
                    }
                }
            }
        }
    }
}

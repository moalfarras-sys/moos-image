// SPDX-License-Identifier: GPL-2.0-or-later
// One thing an update brought: what it is, a shortcut when it has one, and a way to
// try it when MoOS has a route there. `fresh` marks what this machine did not have
// before its last update.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: news

    required property var entry
    property bool tryable: false
    readonly property bool fresh: !!entry.fresh
    readonly property var keys: entry.keys || []
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    signal tryRequested(string route)

    function local(pair) { return MoUI.Locale.local((pair || {}).ar || "", (pair || {}).en || "") }

    focusPolicy: Qt.NoFocus
    hoverEnabled: false
    background: null
    Accessible.role: Accessible.Grouping
    Accessible.name: local(entry.title)
    Accessible.description: local(entry.body)

    contentItem: RowLayout {
        spacing: MoUI.Tokens.space4

        Rectangle {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 2.5
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2.5
            Layout.alignment: Qt.AlignTop
            radius: MoUI.Tokens.radiusSmall
            color: news.fresh ? Kirigami.Theme.highlightColor
                              : Qt.alpha(Kirigami.Theme.highlightColor, 0.15)

            MoUI.SymbolIcon {
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.smallMedium
                height: Kirigami.Units.iconSizes.smallMedium
                symbol: MoUI.SymbolCatalog.resolve(news.entry.glyph)
                foreground: news.fresh ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.highlightColor
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: MoUI.Tokens.space2

            RowLayout {
                Layout.fillWidth: true
                spacing: MoUI.Tokens.space3

                Controls.Label {
                    Layout.fillWidth: true
                    text: news.local(news.entry.title)
                    textFormat: Text.PlainText
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignLeft
                    wrapMode: Text.WordWrap
                    Accessible.ignored: true
                }
                MoosChip {
                    visible: news.fresh
                    Layout.alignment: Qt.AlignTop
                    glyph: "spark"
                    label: MoUI.Locale.local("جديد", "New")
                    tone: "neutral"
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                text: news.local(news.entry.body)
                textFormat: Text.PlainText
                color: news.secondaryInk
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
            // The shortcut starts where the sentence starts, but its keys read in the order
            // they are pressed, in every language.
            Row {
                Layout.topMargin: MoUI.Tokens.space1
                visible: news.keys.length > 0
                spacing: MoUI.Tokens.space2
                LayoutMirroring.enabled: false
                LayoutMirroring.childrenInherit: true

                Repeater {
                    model: news.keys
                    delegate: MoosKeyCap {
                        required property string modelData
                        keyName: modelData
                    }
                }
            }
            Controls.Button {
                visible: news.tryable
                text: MoUI.Locale.local("جرّبه الآن", "Try it")
                icon.name: MoUI.SymbolCatalog.resolve(MoUI.Locale.rtl ? "arrow-back" : "arrow")
                Accessible.description: news.local(news.entry.title)
                onClicked: news.tryRequested(news.entry.route)
            }
        }
    }
}

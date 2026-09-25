// SPDX-License-Identifier: GPL-2.0-or-later
// One MoOS look in the grid: the package's own preview, its name and sentence from its
// metadata, and a check only on the look moos-theme REPORTED — never on the one just
// clicked. A look being applied shows that it is being applied, nothing more.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Controls.AbstractButton {
    id: card

    // One entry of kcm.moosThemes(): id, name, nameAr, summaryEn, summaryAr, preview, light.
    property var look: ({})
    // moos-theme reported this look as the one the desktop wears.
    property bool active: false
    // A change to this look is running.
    property bool pending: false
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property string title: rtl ? String(look.nameAr || look.name || "") : String(look.name || "")
    readonly property string summary: rtl ? String(look.summaryAr || "") : String(look.summaryEn || "")
    readonly property bool lit: hovered || visualFocus
    readonly property bool keyboardFocus: visualFocus
    readonly property bool pressedNow: down
    readonly property bool motion: Kirigami.Units.longDuration > 1
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    activeFocusOnTab: true
    padding: MoUI.Tokens.space2
    implicitWidth: Kirigami.Units.gridUnit * 10
    implicitHeight: topPadding + bottomPadding + (contentItem ? contentItem.implicitHeight : 0)
    scale: pressedNow ? MoUI.Tokens.pressScale : (lit && enabled ? MoUI.Tokens.hoverScale : 1.0)
    Behavior on scale {
        NumberAnimation {
            duration: card.motion ? MoUI.Tokens.motionFast : 0
            easing.type: MoUI.Tokens.easeStandard
        }
    }

    Accessible.role: Accessible.RadioButton
    Accessible.checkable: true
    Accessible.checked: active
    Accessible.name: title
    Accessible.description: summary
    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onEnterPressed: if (enabled) clicked()

    background: Rectangle {
        radius: MoUI.Tokens.radiusCard
        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: Qt.alpha(Kirigami.Theme.textColor, card.lit ? 0.10 : 0.06)
            }
            GradientStop {
                position: 1.0
                color: Qt.alpha(Kirigami.Theme.textColor, card.lit ? 0.05 : 0.02)
            }
        }
        border.width: card.active ? MoUI.Tokens.focusWidth : MoUI.Tokens.borderHairline
        border.color: card.active || card.lit ? Kirigami.Theme.highlightColor
                                              : Qt.alpha(Kirigami.Theme.textColor, 0.14)
        Behavior on border.color {
            ColorAnimation { duration: card.motion ? MoUI.Tokens.motionFast : 0 }
        }
    }

    contentItem: ColumnLayout {
        spacing: MoUI.Tokens.space2

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(width * 9 / 16)

            Kirigami.ShadowedImage {
                id: preview
                anchors.fill: parent
                source: card.look.preview || ""
                radius: MoUI.Tokens.radiusControl
                color: Qt.alpha(Kirigami.Theme.textColor, 0.08)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                mipmap: true
                // Decode only the pixels this card shows: crisp at 200 %, and sixteen
                // previews never hold sixteen full frames in memory.
                sourceSize: Qt.size(Math.max(64, Math.round(width * Screen.devicePixelRatio)),
                                    Math.max(36, Math.round(height * Screen.devicePixelRatio)))
                Accessible.ignored: true
            }
            // A package without a preview still shows which kind of look it is.
            MoUI.SymbolIcon {
                anchors.centerIn: parent
                visible: preview.status !== Image.Ready
                symbol: MoUI.SymbolCatalog.resolve(card.look.light ? "sun" : "moon")
                foreground: card.secondaryInk
                implicitWidth: MoUI.Tokens.iconHero
                implicitHeight: MoUI.Tokens.iconHero
            }
            Rectangle {
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: MoUI.Tokens.space2
                visible: card.active || card.pending
                width: MoUI.Tokens.iconLarge + MoUI.Tokens.space1 * 2
                height: width
                radius: width / 2
                color: card.active ? Kirigami.Theme.highlightColor
                                   : Qt.alpha(Kirigami.Theme.backgroundColor, 0.88)
                border.width: MoUI.Tokens.borderHairline
                border.color: Qt.alpha(card.active ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor, 0.3)

                MoUI.SymbolIcon {
                    anchors.centerIn: parent
                    symbol: MoUI.SymbolCatalog.resolve(card.active ? "check" : "refresh")
                    // The selected badge takes the scheme's contrasting ink, never white.
                    foreground: card.active ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                    implicitWidth: MoUI.Tokens.iconSmall
                    implicitHeight: MoUI.Tokens.iconSmall
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: MoUI.Tokens.space1
            Layout.rightMargin: MoUI.Tokens.space1
            spacing: MoUI.Tokens.space2

            Controls.Label {
                Layout.fillWidth: true
                text: card.title
                textFormat: Text.PlainText
                font.weight: Font.DemiBold
                color: Kirigami.Theme.textColor
                horizontalAlignment: Text.AlignLeft
                elide: Text.ElideRight
                Accessible.ignored: true
            }
            MoUI.SymbolIcon {
                symbol: MoUI.SymbolCatalog.resolve(card.look.light ? "sun" : "moon")
                foreground: card.secondaryInk
                implicitWidth: MoUI.Tokens.iconSmall
                implicitHeight: MoUI.Tokens.iconSmall
            }
        }
        Controls.Label {
            Layout.fillWidth: true
            Layout.leftMargin: MoUI.Tokens.space1
            Layout.rightMargin: MoUI.Tokens.space1
            Layout.bottomMargin: MoUI.Tokens.space1
            visible: text !== ""
            text: card.summary
            textFormat: Text.PlainText
            color: card.secondaryInk
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            horizontalAlignment: Text.AlignLeft
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
            Accessible.ignored: true
        }
        // Cards of one row share its height; the preview and the name stay at the top.
        Item { Layout.fillHeight: true }
    }

    MoUI.FocusRing {
        controlRadius: MoUI.Tokens.radiusCard
        visible: card.keyboardFocus
    }
}

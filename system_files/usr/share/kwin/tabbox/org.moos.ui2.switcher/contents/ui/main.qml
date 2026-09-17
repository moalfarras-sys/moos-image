/*
    MoOS Switcher — what Alt+Tab shows on a MoOS desktop.

    SPDX-License-Identifier: GPL-2.0-or-later

    WHY THIS PACKAGE EXISTS

    KWin's window switcher is a KPackage read from disk, so MoOS can ship its
    own beside the stock ones and select it in kwinrc. Nothing upstream is
    replaced or patched: the five stock layouts stay installed and a user can
    pick one again in System Settings.

    Measured on the station (44.20260917.858, KWin 6.7.5, 3840x2160 at 265%,
    Arabic session) before this file existed, the stock `thumbnail_grid` had
    three problems that belong to MoOS, not to KWin:

      * it read `Application.layoutDirection` to decide its reading order.
        MoOS ships bilingual QML strings instead of Qt translation catalogues,
        so that property is LeftToRight on EVERY MoOS session including an
        Arabic one - which is exactly what `org/moos/ui/Locale.qml` warns
        about. The switcher therefore ran left-to-right while the desk around
        it ran right-to-left. This file takes its direction from
        `MoUI.Locale.rtl`, the one authority, so the newest window is where an
        Arabic reader's eye starts.
      * its geometry, type and corner radii were Breeze's, not MoOS's. Colour
        was the only thing the MoOS Plasma style could reach, so the surface
        was the right hue and the wrong shape.
      * it animated on Kirigami durations rather than MoOS Motion, so the one
        moment the whole desk holds still felt like a different product.

    WHAT IT DRAWS

    One horizontal strip of live window thumbnails on the MoOS glass the rest
    of the shell uses, the selected card lifted by the shared finite spring and
    ringed in the palette's accent, with the full caption of the selected
    window written once underneath instead of elided under every card.

    MOTION

    Every animation here is finite and guarded by `motionEnabled`, which reads
    Plasma's own reduced-motion signal (`Kirigami.Units.longDuration > 1`, the
    same test `org/moos/ui/SpringFeedback.qml` uses). With animations off the
    spring is not merely fast, it never starts: the strip jumps. Nothing here
    runs while the switcher is closed - KWin destroys the dialog's contents.
*/
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.kwin as KWin
import org.moos.ui as MoUI

KWin.TabBoxSwitcher {
    id: tabBox

    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property real screenAspect: screenGeometry.height > 0
        ? screenGeometry.width / screenGeometry.height : 16 / 9

    currentIndex: strip.currentIndex

    PlasmaCore.Dialog {
        id: dialog

        location: PlasmaCore.Types.Floating
        visible: tabBox.visible
        flags: Qt.Popup | Qt.X11BypassWindowManagerHint
        x: tabBox.screenGeometry.x + Math.round((tabBox.screenGeometry.width - width) / 2)
        y: tabBox.screenGeometry.y + Math.round((tabBox.screenGeometry.height - height) / 2)

        mainItem: ColumnLayout {
            id: body

            // The strip mirrors with the LOCALE, never with
            // Application.layoutDirection - see the note at the top of this file.
            LayoutMirroring.enabled: MoUI.Locale.rtl
            LayoutMirroring.childrenInherit: true

            spacing: MoUI.Tokens.space3

            readonly property int count: tabBox.model ? tabBox.model.rowCount() : 0
            // A card is a share of the screen, so the strip is proportionate on a
            // 1080p laptop and on this 4K station, and is then clamped so it never
            // becomes a stamp or a poster.
            readonly property int cardWidth: Math.round(Math.max(176,
                Math.min(288, tabBox.screenGeometry.width * 0.17)))
            readonly property int thumbnailHeight: Math.round(cardWidth / tabBox.screenAspect)
            readonly property int cardHeight: thumbnailHeight + MoUI.Tokens.space2 * 2
            readonly property int stride: cardWidth + MoUI.Tokens.space3
            // How many cards fit across 88% of the screen; the rest scroll.
            readonly property int columns: Math.max(1,
                Math.min(count, Math.floor((tabBox.screenGeometry.width * 0.88) / stride)))

            Layout.minimumWidth: MoUI.Tokens.dialogCompactWidth

            ListView {
                id: strip

                Layout.preferredWidth: Math.max(MoUI.Tokens.dialogCompactWidth,
                                                body.columns * body.stride - MoUI.Tokens.space3)
                Layout.preferredHeight: body.cardHeight
                Layout.alignment: Qt.AlignHCenter

                orientation: ListView.Horizontal
                spacing: MoUI.Tokens.space3
                clip: true
                focus: true
                keyNavigationWraps: true
                boundsBehavior: Flickable.StopAtBounds
                highlightMoveDuration: MoUI.Tokens.duration(tabBox.motionEnabled,
                    MoUI.Tokens.scaled(Kirigami.Units.longDuration,
                                       MoUI.Tokens.motionGeometry))
                model: tabBox.model

                delegate: Item {
                    id: card

                    required property int index
                    required property string caption
                    required property var icon
                    required property var windowId
                    required property bool minimized

                    readonly property bool selected: index === strip.currentIndex

                    width: body.cardWidth
                    height: body.cardHeight

                    Accessible.role: Accessible.PageTab
                    Accessible.name: card.caption
                    Accessible.selected: card.selected

                    // The one moving part: the shared finite spring, on scale only,
                    // so the strip's layout and hit targets never move.
                    MoUI.SpringFeedback {
                        id: lift
                        active: tabBox.motionEnabled
                        targetScale: card.selected ? 1 : 0.94
                    }

                    MoUI.Surface {
                        id: plate

                        anchors.fill: parent
                        radius: MoUI.Tokens.radiusCard
                        scale: lift.value
                        // Selection reads as an accent RING around a lightly
                        // tinted plate, not as a filled slab. Surface's
                        // interactive mode paints a selected row at 40% ink,
                        // which is right for a list row and wrong behind a
                        // thumbnail: on the station it came out as a muddy band
                        // framing the window picture. These are the component's
                        // own knobs (surfaceColor, selected, rimOpacity), not a
                        // private reimplementation of it.
                        interactive: false
                        selected: card.selected
                        rimOpacity: card.selected ? 1 : MoUI.Tokens.glassBorderOpacity
                        border.width: card.selected ? MoUI.Tokens.focusWidth
                                                    : MoUI.Tokens.borderHairline
                        surfaceColor: card.selected
                            ? Qt.alpha(Kirigami.Theme.highlightColor, 0.18)
                            : Qt.alpha(Kirigami.Theme.textColor,
                                       pointer.hovered ? MoUI.Tokens.surfaceHoverOpacity
                                                       : MoUI.Tokens.surfaceRestingOpacity)
                        // A minimised window is still listed, and says so.
                        opacity: card.minimized && !card.selected
                            ? MoUI.Tokens.mutedOpacity : 1

                        KWin.WindowThumbnail {
                            anchors.fill: parent
                            anchors.margins: MoUI.Tokens.space2
                            wId: card.windowId
                        }

                        // The application's own icon, on a chip, in the corner the
                        // reader starts from.
                        Rectangle {
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            anchors.margins: MoUI.Tokens.space2
                            width: MoUI.Tokens.iconLarge + MoUI.Tokens.space2
                            height: width
                            radius: MoUI.Tokens.radiusSmall
                            color: Qt.alpha(Kirigami.Theme.backgroundColor,
                                            MoUI.Tokens.floatingGlassOpacity)

                            Kirigami.Icon {
                                anchors.centerIn: parent
                                width: MoUI.Tokens.iconLarge
                                height: width
                                source: card.icon
                            }
                        }

                        // Closing a window from the switcher is a capability the
                        // stock layout had, so MoOS keeps it rather than quietly
                        // dropping it. `close(index)` was confirmed to be a real
                        // function on KWin 6.7.5's tab-box model by reading
                        // `typeof` off the live model on the station - this is not
                        // a button wired to a method that might not exist.
                        MoUI.IconButton {
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: MoUI.Tokens.space2
                            visible: card.selected || pointer.hovered
                            symbol: "moos-close-symbolic"
                            // Round, the way every other circular control on the
                            // desk is; a square chip over a window picture read as
                            // a second window.
                            cornerRadius: MoUI.Tokens.radiusPill
                            accessibleLabel: MoUI.Locale.local("أغلق النافذة",
                                                               "Close window")
                            // Tab belongs to the switcher itself while it is open;
                            // this control must never take it.
                            activeFocusOnTab: false
                            onClicked: tabBox.model.close(card.index)
                        }
                    }

                    HoverHandler {
                        id: pointer
                        cursorShape: Qt.PointingHandCursor
                    }

                    TapHandler {
                        onSingleTapped: {
                            // With no modifier held there is nothing to release, so a
                            // tap is the choice itself; otherwise it selects and the
                            // release activates, the way the stock layouts behave.
                            if (tabBox.noModifierGrab) {
                                tabBox.model.activate(card.index)
                            } else {
                                strip.currentIndex = card.index
                            }
                        }
                        onDoubleTapped: tabBox.model.activate(card.index)
                    }
                }

                Connections {
                    target: tabBox
                    function onCurrentIndexChanged() {
                        strip.currentIndex = tabBox.currentIndex
                        strip.positionViewAtIndex(strip.currentIndex, ListView.Contain)
                    }
                }
            }

            // The caption is written ONCE, in full, for the window that is
            // actually selected - rather than elided under every card.
            Text {
                Layout.fillWidth: true
                Layout.maximumWidth: strip.Layout.preferredWidth
                Layout.alignment: Qt.AlignHCenter

                text: strip.currentItem ? strip.currentItem.caption : ""
                visible: body.count > 0
                color: Kirigami.Theme.textColor
                font.family: MoUI.Tokens.interfaceFamily
                font.pixelSize: MoUI.Tokens.typeTitle
                font.weight: MoUI.Tokens.weightMedium
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideMiddle
                textFormat: Text.PlainText
            }

            Text {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter

                text: MoUI.Locale.local("لا نوافذ مفتوحة", "No open windows")
                visible: body.count === 0
                // Secondary ink is the theme's text at 72%, never the disabled
                // role: see tests/test_secondary_text_contrast.py.
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                               Kirigami.Theme.textColor.b, 0.72)
                font.family: MoUI.Tokens.interfaceFamily
                font.pixelSize: MoUI.Tokens.typeBody
                horizontalAlignment: Text.AlignHCenter
                textFormat: Text.PlainText
            }
        }
    }
}

pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Mo Store — the one review before anything installs: every picked app with where it comes from
// and how it installs, what MoOS promises (no administrator access; a publisher's website never
// installs by itself), and Back / Install. One app or a whole set, the same sheet.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Popup {
    id: review
    required property var win
    readonly property var design: win.design
    anchors.centerIn: Overlay.overlay
    width: Math.min(win.fs(640), win.width - win.fs(80))
    height: Math.min(sheetBody.implicitHeight + design.space5 * 2, win.height - win.fs(80))
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: SheetBackground { win: review.win }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, review.win.lightScheme ? 0.32 : 0.54) }
    enter: Transition {
        NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: review.win.motionEnabled ? review.design.motionEmphasis : 0; easing.type: Easing.OutCubic }
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: review.win.motionEnabled ? review.design.motionPress : 0 }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: review.win.motionEnabled ? review.design.motionFast : 0 }
    }
    onOpened: installButton.forceActiveFocus()

    ColumnLayout {
        id: sheetBody
        objectName: "reviewSheet"
        anchors.fill: parent
        anchors.margins: review.design.space5
        spacing: review.design.space4
        LayoutMirroring.enabled: review.win.rtl
        LayoutMirroring.childrenInherit: true
        Accessible.role: Accessible.Dialog
        Accessible.name: reviewTitle.text

        RowLayout {
            Layout.fillWidth: true
            spacing: review.design.space4
            Rectangle {
                Layout.preferredWidth: review.win.fs(48)
                Layout.preferredHeight: review.win.fs(48)
                radius: width / 2
                color: review.win.tint(review.win.accent, review.win.lightScheme ? 0.14 : 0.18)
                Glyph { win: review.win; anchors.centerIn: parent; width: review.win.fs(24); height: width; name: "shield"; tint: review.win.accent }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    horizontalAlignment: Text.AlignLeft
                    id: reviewTitle
                    Layout.fillWidth: true
                    text: review.win.onlyWebPicks()
                        ? review.win.pickCount === 1
                            ? (review.win.rtl ? "راجع الموقع الخارجي" : "Review external website")
                            : (review.win.rtl ? "راجع المواقع الخارجية" : "Review external websites")
                        : review.win.pickedWebCount() > 0
                            ? (review.win.rtl ? "راجع قبل المتابعة" : "Review before continuing")
                            : (review.win.rtl ? "راجع قبل التثبيت" : "Review before installing")
                    color: review.win.txt
                    font.family: review.win.uiFont
                    font.pixelSize: review.win.typePx(20)
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: review.win.onlyWebPicks()
                        ? (review.win.rtl
                            ? "سيفتح متجر Mo صفحة الناشر الرسمية؛ وأنت تُكمل أي تنزيل من هناك."
                            : "Mo Store opens the publisher's official page; you complete any download there.")
                        : review.win.pickedWebCount() > 0
                            ? (review.win.rtl
                                ? "تُثبَّت التطبيقات لحسابك وحده، وتفتح العناصر الخارجية صفحات ناشريها الرسمية."
                                : "Apps install for your account only; external items open their publishers' official pages.")
                            : (review.win.rtl
                                ? "تُثبَّت لحسابك وحده. ما يأتي من خارج الكتالوج المعزول موضّح أدناه."
                                : "They install for your account only. Anything from outside the sandboxed catalogue is marked below.")
                    color: review.win.txt2
                    font.family: review.win.uiFont
                    font.pixelSize: review.win.typePx(13)
                    wrapMode: Text.WordWrap
                }
            }
        }

        ListView {
            id: pickList
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, review.win.fs(320))
            clip: true
            spacing: review.design.space2
            model: Object.keys(review.win.picks)
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Rectangle {
                id: reviewItem
                required property var modelData
                readonly property var app: review.win.appById(modelData)
                readonly property bool outside: reviewItem.app !== null
                    && !!(reviewItem.app.requires_review === true
                          || (reviewItem.app.install && reviewItem.app.install.requires_review === true))
                width: ListView.view.width
                height: review.win.fs(68)
                radius: review.design.radiusCard
                color: review.win.tint(review.win.txt, review.win.lightScheme ? 0.04 : 0.05)
                border.width: 1
                border.color: review.win.cardBorder
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: review.design.space3
                    anchors.rightMargin: review.design.space3
                    spacing: review.design.space3
                    AppIcon { win: review.win; app: reviewItem.app; size: review.win.fs(44); showKind: true }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: review.win.localName(reviewItem.app)
                            color: review.win.txt
                            font.family: review.win.uiFont
                            font.pixelSize: review.win.typePx(14)
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: review.win.reviewDetail(reviewItem.app)
                            color: reviewItem.outside ? review.win.warningInk : review.win.txt2
                            font.family: review.win.uiFont
                            font.pixelSize: review.win.typePx(12)
                            elide: Text.ElideRight
                        }
                    }
                    CompatBadge {
                        win: review.win
                        app: reviewItem.app
                        compact: true
                        visible: reviewItem.app !== null && review.win.compatOf(reviewItem.app).known
                                 && review.win.compatOf(reviewItem.app).verdict !== "ok"
                    }
                    CircleButton {
                        win: review.win
                        size: review.win.fs(32)
                        glyph: "close"
                        accessibleName: review.win.local("أزل من القائمة: ", "Take off the list: ") + review.win.localName(reviewItem.app)
                        onActivated: review.win.setPicked(reviewItem.modelData, false)
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: promise.implicitHeight + review.design.space3 * 2
            radius: review.design.radiusCard
            color: review.win.tint(review.win.accent, review.win.lightScheme ? 0.09 : 0.11)
            RowLayout {
                id: promise
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: review.design.space3
                spacing: review.design.space3
                Glyph { win: review.win; name: "lock"; tint: review.win.accent; Layout.preferredWidth: review.win.fs(20); Layout.preferredHeight: review.win.fs(20) }
                Text {
                    Layout.fillWidth: true
                    text: review.win.rtl
                        ? "لا صلاحيات مسؤول، والمواقع الخارجية لا تثبّت شيئًا تلقائيًا؛ أدوات المطوّرين المعلَّمة قد تشغّل سكربتات حزمها بعد موافقتك."
                        : "No administrator access, and external websites never install anything by themselves. Marked developer tools may run their package scripts after your approval."
                    color: review.win.txt
                    font.family: review.win.uiFont
                    font.pixelSize: review.win.typePx(12)
                    wrapMode: Text.WordWrap
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: review.design.space3
            ActionButton {
                win: review.win
                pill: true
                label: review.win.rtl ? "رجوع" : "Back"
                triggered: function() { review.close() }
            }
            Item { Layout.fillWidth: true }
            ActionButton {
                id: installButton
                win: review.win
                pill: true
                label: review.win.onlyWebPicks()
                    ? review.win.pickCount === 1
                        ? (review.win.rtl ? "افتح الموقع الرسمي" : "Open official website")
                        : (review.win.rtl ? "افتح المواقع الرسمية" : "Open official websites")
                    : review.win.pickedWebCount() > 0
                        ? (review.win.rtl ? "تابع مع " : "Continue with ") + review.win.pickCount
                        : review.win.pickCount === 1
                            ? (review.win.rtl ? "ثبّت" : "Install")
                            : (review.win.rtl ? "ثبّت " : "Install ") + review.win.pickCount
                glyphName: review.win.onlyWebPicks() ? "external" : "download"
                primary: true
                enabled: review.win.pickCount > 0 && !review.win.jobIsActive()
                Keys.onReturnPressed: if (enabled) review.win.beginInstall()
                triggered: function() { review.win.beginInstall() }
            }
        }
    }
}

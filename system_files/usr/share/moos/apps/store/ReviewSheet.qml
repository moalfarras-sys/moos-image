pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Mo Store — the one review before anything installs: every picked app with its
// source, what MoOS promises (no administrator access; websites never install by
// themselves) and Back / Install.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Popup {
    id: review
    required property var win
    readonly property var design: win.design
    anchors.centerIn: Overlay.overlay
    width: Math.min(600, win.width - 70)
    height: Math.min(610, win.height - 70)
    modal: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle {
        radius: design.radiusPanel
        color: win.surface
        border.width: 1
        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.4)
    }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.54) }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 13
        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                Layout.preferredWidth: win.fs(48)
                Layout.preferredHeight: win.fs(48)
                radius: design.radiusCard
                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                Glyph { win: review.win; anchors.centerIn: parent; width: 25; height: 25; name: "shield"; tint: win.accent }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                Text {
                    text: win.onlyWebPicks()
                        ? win.pickCount === 1
                            ? (win.rtl ? "راجع الموقع الخارجي" : "Review external website")
                            : (win.rtl ? "راجع المواقع الخارجية" : "Review external websites")
                        : win.pickedWebCount() > 0
                            ? (win.rtl ? "راجع قبل المتابعة" : "Review before continuing")
                            : (win.rtl ? "راجع قبل التثبيت" : "Review before installing")
                    color: win.txt
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(18)
                    font.bold: true
                }
                Text {
                    text: win.onlyWebPicks()
                        ? (win.rtl
                            ? "سيفتح Mo Store صفحة الناشر الرسمية عبر HTTPS؛ وأنت تُكمل أي تنزيل من هناك."
                            : "Mo Store opens the publisher's official HTTPS page; you complete any download there.")
                        : win.pickedWebCount() > 0
                            ? (win.rtl
                                ? "تُثبت التطبيقات لحسابك وحده، وتفتح العناصر الخارجية صفحات ناشريها الرسمية."
                                : "Apps install for your account only; external items open their publishers' official pages.")
                            : (win.rtl
                                ? "سيجري التثبيت لحسابك وحده. المصادر المتقدمة موضحة أدناه."
                                : "Apps install for your account only. Advanced sources are clearly marked below.")
                    color: win.txt2
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(10)
                }
            }
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: win.fs(1); color: win.outline; opacity: 0.6 }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: design.space2
            model: Object.keys(win.picks)
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Rectangle {
                id: reviewItem
                required property var modelData
                readonly property var app: win.appById(modelData)
                width: ListView.view.width
                height: 68
                radius: design.radiusCard
                color: Qt.rgba(win.canvas.r, win.canvas.g, win.canvas.b, 0.5)
                border.width: 1
                border.color: win.outline
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10
                    AppArtwork { win: review.win; app: reviewItem.app; size: 44 }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            Layout.fillWidth: true
                            text: win.localName(reviewItem.app)
                            color: win.txt
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(12)
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: win.reviewDetail(reviewItem.app)
                            color: reviewItem.app
                                   && (reviewItem.app.requires_review
                                       || (reviewItem.app.install
                                           && reviewItem.app.install.requires_review))
                                   ? win.violet : win.txt2
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(9)
                            elide: Text.ElideRight
                        }
                    }
                    ActionButton {
                        win: review.win
                        label: win.rtl ? "إزالة" : "Remove"
                        glyphName: "trash"
                        triggered: function() { win.setPicked(reviewItem.modelData, false) }
                    }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: win.fs(58)
            radius: design.radiusCard
            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.1)
            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 9
                Glyph { win: review.win; name: "lock"; tint: win.accent; Layout.preferredWidth: win.fs(20); Layout.preferredHeight: win.fs(20) }
                Text {
                    Layout.fillWidth: true
                    text: win.rtl
                        ? "لا صلاحية مسؤول، والمواقع الخارجية لا تثبّت تلقائياً؛ أدوات npm المعلّمة قد تشغّل سكربتات الحزمة بعد موافقتك."
                        : "No administrator access, and external websites never install automatically. Marked npm tools may run package scripts after your approval."
                    color: win.txt
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(10)
                    wrapMode: Text.WordWrap
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            ActionButton {
                win: review.win
                label: win.rtl ? "رجوع" : "Back"
                glyphName: "external"
                triggered: function() { review.close() }
            }
            Item { Layout.fillWidth: true }
            ActionButton {
                win: review.win
                label: win.onlyWebPicks()
                    ? win.pickCount === 1
                        ? (win.rtl ? "افتح الموقع الرسمي" : "Open official website")
                        : (win.rtl ? "افتح المواقع الرسمية" : "Open official websites")
                    : win.pickedWebCount() > 0
                        ? (win.rtl ? "تابع مع " : "Continue with ") + win.pickCount
                        : (win.rtl ? "ثبّت " : "Install ") + win.pickCount
                glyphName: win.onlyWebPicks() ? "external" : "download"
                primary: true
                enabled: win.pickCount > 0 && !win.jobIsActive()
                triggered: function() { win.beginInstall() }
            }
        }
    }
}

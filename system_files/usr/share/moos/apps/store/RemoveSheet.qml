pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Mo Store — removing an app. Keep my data is the default; "Remove the app and its data" says
// exactly what goes for this kind of app before anything is touched. A Windows program's own space
// goes with it either way, and the sheet says so instead of offering a choice it cannot keep.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Popup {
    id: removeSheet
    required property var win
    readonly property var design: win.design
    property var app: null
    property bool withData: false
    readonly property string kind: win.appKind(removeSheet.app)
    readonly property bool keepPossible: removeSheet.kind !== "windows"
    readonly property bool dataSupported: win.bridgeHas("removeAppData")
    anchors.centerIn: Overlay.overlay
    width: Math.min(win.fs(560), win.width - win.fs(80))
    height: Math.min(removeBody.implicitHeight + design.space5 * 2, win.height - win.fs(80))
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: SheetBackground { win: removeSheet.win }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, removeSheet.win.lightScheme ? 0.32 : 0.54) }
    enter: Transition {
        NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: removeSheet.win.motionEnabled ? removeSheet.design.motionEmphasis : 0; easing.type: Easing.OutCubic }
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: removeSheet.win.motionEnabled ? removeSheet.design.motionPress : 0 }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: removeSheet.win.motionEnabled ? removeSheet.design.motionFast : 0 }
    }
    onAboutToShow: removeSheet.withData = false
    onOpened: cancelButton.forceActiveFocus()

    function dataLine() {
        switch (removeSheet.kind) {
        case "webapp":
            return removeSheet.win.local("تُحذف تسجيلات دخوله وملفات تعريف الارتباط وبيانات الموقع المحفوظة.",
                                         "Its sign-ins, cookies and saved site data are deleted.")
        case "android":
            return removeSheet.win.local("تُحذف بياناته داخل مساحة أندرويد.", "Its data inside the Android space is deleted.")
        case "appdrop":
        case "vendor":
        case "dropped":
            return removeSheet.win.local("تُحذف ملفاته وما حفظه في مجلده. ما حفظه في أماكن أخرى من مجلد المنزل يبقى.",
                                         "Its files and what it saved in its own folder are deleted. Anything it saved elsewhere in your home folder stays.")
        case "npm":
            return removeSheet.win.local("تُزال الأداة. الملفات التي أنشأتها بنفسك تبقى.", "The tool is removed. Files you created with it stay.")
        default:
            return removeSheet.win.local("تُحذف إعداداته وملفاته المحفوظة في مجلده الخاص، وأذوناته.",
                                         "Its settings, the files it saved in its own folder, and its permissions are deleted.")
        }
    }

    ColumnLayout {
        id: removeBody
        anchors.fill: parent
        anchors.margins: removeSheet.design.space5
        spacing: removeSheet.design.space4
        LayoutMirroring.enabled: removeSheet.win.rtl
        LayoutMirroring.childrenInherit: true
        Accessible.role: Accessible.Dialog
        Accessible.name: removeTitle.text

        RowLayout {
            Layout.fillWidth: true
            spacing: removeSheet.design.space4
            AppIcon { win: removeSheet.win; app: removeSheet.app; size: removeSheet.win.fs(56) }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    horizontalAlignment: Text.AlignLeft
                    id: removeTitle
                    Layout.fillWidth: true
                    text: removeSheet.win.rtl ? "إزالة " + removeSheet.win.localName(removeSheet.app) + "؟"
                                              : "Remove " + removeSheet.win.localName(removeSheet.app) + "?"
                    color: removeSheet.win.txt
                    font.family: removeSheet.win.uiFont
                    font.pixelSize: removeSheet.win.typePx(20)
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: removeSheet.win.publisherLine(removeSheet.app)
                    color: removeSheet.win.txt2
                    font.family: removeSheet.win.uiFont
                    font.pixelSize: removeSheet.win.typePx(13)
                    elide: Text.ElideRight
                }
            }
        }

        // The two answers, as two cards; the first is chosen until the person chooses otherwise.
        Repeater {
            model: removeSheet.keepPossible ? [false, true] : [true]
            delegate: Rectangle {
                id: option
                required property var modelData
                readonly property bool chosen: removeSheet.keepPossible ? removeSheet.withData === option.modelData : true
                readonly property bool usable: !option.modelData || !removeSheet.keepPossible || removeSheet.dataSupported
                Layout.fillWidth: true
                Layout.preferredHeight: optionRow.implicitHeight + removeSheet.design.space4 * 2
                radius: removeSheet.design.radiusCard
                color: option.chosen ? removeSheet.win.tint(option.modelData ? removeSheet.win.dangerInk : removeSheet.win.accent,
                                                            removeSheet.win.lightScheme ? 0.10 : 0.12)
                                     : removeSheet.win.tint(removeSheet.win.txt, removeSheet.win.lightScheme ? 0.03 : 0.04)
                border.width: option.chosen ? 2 : 1
                border.color: option.chosen ? (option.modelData ? removeSheet.win.dangerInk : removeSheet.win.accent)
                                            : removeSheet.win.cardBorder
                opacity: option.usable ? 1 : 0.6
                activeFocusOnTab: true
                Accessible.role: Accessible.RadioButton
                Accessible.name: optionTitle.text
                Accessible.checked: option.chosen
                Accessible.onPressAction: if (option.usable) removeSheet.withData = option.modelData
                Keys.onSpacePressed: if (option.usable) removeSheet.withData = option.modelData
                FocusRing { win: removeSheet.win }
                TapHandler { enabled: option.usable; onTapped: removeSheet.withData = option.modelData }
                RowLayout {
                    id: optionRow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: removeSheet.design.space4
                    spacing: removeSheet.design.space3
                    Rectangle {
                        Layout.preferredWidth: removeSheet.win.fs(20)
                        Layout.preferredHeight: removeSheet.win.fs(20)
                        Layout.alignment: Qt.AlignTop
                        radius: width / 2
                        color: "transparent"
                        border.width: 2
                        border.color: option.chosen ? (option.modelData ? removeSheet.win.dangerInk : removeSheet.win.accent) : removeSheet.win.txt2
                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width * 0.5
                            height: width
                            radius: width / 2
                            visible: option.chosen
                            color: option.modelData ? removeSheet.win.dangerInk : removeSheet.win.accent
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            id: optionTitle
                            Layout.fillWidth: true
                            text: !option.modelData ? removeSheet.win.local("أزله واحتفظ ببياناتي", "Remove it, keep my data")
                                : removeSheet.keepPossible ? removeSheet.win.local("أزل التطبيق وبياناته", "Remove the app and its data")
                                : removeSheet.win.local("أزل البرنامج ومساحته", "Remove the program and its space")
                            color: removeSheet.win.txt
                            font.family: removeSheet.win.uiFont
                            font.pixelSize: removeSheet.win.typePx(15)
                            font.weight: Font.DemiBold
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            text: !option.modelData
                                ? removeSheet.win.local("تبقى إعداداته وملفاته على هذا الجهاز، فإن ثبّته مجددًا عاد كما كان.",
                                                        "Its settings and files stay on this computer, so installing it again brings it back as it was.")
                                : !removeSheet.keepPossible
                                  ? removeSheet.win.local("لكل برنامج ويندوز مساحته الخاصة، وتُحذف معه بكل ما حُفظ فيها.",
                                                          "Each Windows program has a space of its own, and it is deleted with everything saved in it.")
                                : !removeSheet.dataSupported ? removeSheet.win.needsUpdateText
                                : removeSheet.dataLine()
                            color: removeSheet.win.txt2
                            font.family: removeSheet.win.uiFont
                            font.pixelSize: removeSheet.win.typePx(13)
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: removeSheet.design.space2
            spacing: removeSheet.design.space3
            Item { Layout.fillWidth: true }
            ActionButton {
                id: cancelButton
                win: removeSheet.win
                pill: true
                label: removeSheet.win.local("إلغاء", "Cancel")
                triggered: function() { removeSheet.close() }
            }
            ActionButton {
                win: removeSheet.win
                pill: true
                destructive: true
                label: removeSheet.win.local("إزالة", "Remove")
                glyphName: "trash"
                enabled: removeSheet.app !== null && !removeSheet.win.jobIsActive()
                triggered: function() {
                    if (removeSheet.withData && removeSheet.keepPossible) removeSheet.win.removeSelectedWithData(removeSheet.app)
                    else removeSheet.win.removeSelected(removeSheet.app)
                }
            }
        }
    }
}

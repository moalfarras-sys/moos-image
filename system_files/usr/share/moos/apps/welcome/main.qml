// MoOS Welcome — premium first-run welcome (replaces plasma-welcome).
// Pure-QML script app launched by /usr/bin/moos-welcome via the qml-qt6 runner.
// Nova "expressive glass" styling; bilingual AR|EN; RTL-safe.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    width: 860
    height: 620
    minimumWidth: 720
    minimumHeight: 540
    title: "MoOS"
    color: "#0B1220"

    // ---- palette ----
    readonly property color navy:    "#0B1220"
    readonly property color surface: "#111A2E"
    readonly property color raised:  "#1A2740"
    readonly property color blue:    "#2E7BFF"
    readonly property color cyan:    "#22D3EE"
    readonly property color violet:  "#8B5CF6"
    readonly property color txt:     "#E6EDF7"
    readonly property color txt2:    "#9FB0C9"

    // Launch a MoOS app/action for real. Pure QML has no Process API, but
    // Qt.openUrlExternally routes "moos://…" through xdg-open to the whitelisted
    // handler /usr/bin/moos-open (registered as x-scheme-handler/moos). So these
    // buttons actually OPEN the app instead of copying text to the clipboard.
    function openApp(url, label) {
        Qt.openUrlExternally(url)
        toastLabel.text = "جارٍ الفتح… | Opening…  " + label
        toast.visible = true; toastTimer.restart()
    }

    // ---- ambient background glow ----
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0B1220" }
            GradientStop { position: 1.0; color: "#0A1B33" }
        }
    }
    Rectangle {  // soft radial-ish accent top-right
        width: 460; height: 460; radius: 230
        anchors.right: parent.right; anchors.top: parent.top
        anchors.rightMargin: -140; anchors.topMargin: -160
        color: win.blue; opacity: 0.10
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 18

        // ---- hero ----
        RowLayout {
            Layout.fillWidth: true
            spacing: 18
            Image {
                source: "file:///usr/share/moos/moos-logo.png"
                sourceSize.width: 72; sourceSize.height: 72
                Layout.preferredWidth: 72; Layout.preferredHeight: 72
            }
            ColumnLayout {
                spacing: 2
                Text {
                    text: "أهلاً بك في MoOS  |  Welcome to MoOS"
                    color: win.txt; font.family: "IBM Plex Sans"
                    font.pixelSize: 26; font.bold: true
                }
                Text {
                    text: "نظام حديث، فاخر، وسريع — بهوية Moalfarras  ·  A modern, premium, fast OS"
                    color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 14
                }
            }
            Item { Layout.fillWidth: true }
        }

        // ---- feature grid ----
        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 14; columnSpacing: 14

            Repeater {
                model: [
                    { i: "✦", t: "هوية كاملة | Full identity", d: "من الإقلاع حتى سطح المكتب" , c: win.blue },
                    { i: "🧠", t: "Mo AI", d: "مساعد يتحكم بالنظام محلياً", c: win.violet },
                    { i: "🎮", t: "ألعاب | Gaming", d: "Steam · Proton · Bottles", c: win.cyan },
                    { i: "🤖", t: "Android", d: "تطبيقات أندرويد عبر Waydroid", c: win.blue },
                    { i: "🛡️", t: "تحديثات آمنة | Safe updates", d: "rollback بضغطة", c: win.violet },
                    { i: "🎨", t: "Nova UI", d: "زجاج تعبيري وألوان نيون", c: win.cyan }
                ]
                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 96
                    radius: 14
                    color: win.surface
                    border.width: 1; border.color: Qt.rgba(1,1,1,0.06)
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 14; spacing: 4
                        RowLayout {
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: modelData.c }
                            Text { text: modelData.t; color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 15; font.bold: true }
                        }
                        Text { text: modelData.d; color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12.5; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        // ---- action buttons ----
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            component NavButton: Rectangle {
                property string label
                property color accent: win.blue
                property var onTap
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                radius: 12
                color: ma.containsMouse ? Qt.lighter(accent, 1.1) : accent
                Text { anchors.centerIn: parent; text: parent.label; color: "white"; font.family: "IBM Plex Sans"; font.pixelSize: 15; font.bold: true }
                MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: parent.onTap() }
                Behavior on color { ColorAnimation { duration: 120 } }
            }
            NavButton { label: "ثبّت الأساسيات | Install essentials"; accent: win.blue;   onTap: function(){ win.openApp("moos://app/setup",  "التطبيقات | apps") } }
            NavButton { label: "افتح Mo AI | Open Mo AI";            accent: win.violet; onTap: function(){ win.openApp("moos://app/moai",   "Mo AI") } }
            NavButton { label: "مركز التوافق | Compatibility";       accent: win.raised; onTap: function(){ win.openApp("moos://app/compat", "التوافق | compat") } }
        }

        Text {
            id: hintText
            Layout.fillWidth: true
            text: "كل شيء محلي وآمن — بهوية MoOS بالكامل.  |  Everything local and safe — fully MoOS."
            color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12; wrapMode: Text.WordWrap
        }
    }

    // ---- toast ----
    Rectangle {
        id: toast
        visible: false
        anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 18
        width: toastLabel.implicitWidth + 32; height: 40; radius: 20
        color: win.raised; border.width: 1; border.color: win.cyan
        Text { id: toastLabel; anchors.centerIn: parent; text: "MoOS"; color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 13 }
        Timer { id: toastTimer; interval: 2200; onTriggered: toast.visible = false }
    }
}

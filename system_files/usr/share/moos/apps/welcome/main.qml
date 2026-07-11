// MoOS Welcome — premium first-run welcome (replaces plasma-welcome).
// Pure-QML script app launched by /usr/bin/moos-welcome via the qml-qt6 runner.
// Nova "expressive glass" styling; bilingual AR|EN; RTL-safe.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

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
    Image {
        source: "file:///usr/share/wallpapers/NovaHorizon/contents/images_dark/3840x2160.png"
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        opacity: 0.28
        smooth: true
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

        // RTL/LTR layout direction settings based on session locale
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true

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
                    { i: "moos-identity", t: "هوية كاملة | Full identity", d: "من الإقلاع حتى سطح المكتب", c: win.blue },
                    { i: "moos-ai", t: "Mo AI", d: "مساعد يتحكم بالنظام محلياً", c: win.violet },
                    { i: "moos-gaming", t: "ألعاب | Gaming", d: "Steam · Proton · Bottles", c: win.cyan },
                    { i: "moos-android-apps", t: "Android", d: "تطبيقات أندرويد عبر Waydroid", c: win.blue },
                    { i: "moos-safe-update", t: "تحديثات آمنة | Safe updates", d: "rollback بضغطة واحدة", c: win.violet },
                    { i: "moos-nova-ui", t: "Nova UI", d: "زجاج تعبيري وألوان نيون", c: win.cyan }
                ]
                delegate: Rectangle {
                    id: cardItem
                    Layout.fillWidth: true
                    Layout.preferredHeight: 96
                    radius: 16
                    color: cardHover.hovered ? Qt.rgba(26/255, 39/255, 64/255, 0.75) : Qt.rgba(17/255, 26/255, 46/255, 0.45)
                    border.width: 1.5
                    border.color: cardHover.hovered ? modelData.c : Qt.rgba(1, 1, 1, 0.08)
                    scale: cardHover.hovered ? 1.025 : 1.0

                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                    Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }

                    HoverHandler {
                        id: cardHover
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 14

                        Rectangle {
                            width: 48
                            height: 48
                            radius: 12
                            color: Qt.rgba(modelData.c.r, modelData.c.g, modelData.c.b, 0.15)
                            border.width: 1
                            border.color: Qt.rgba(modelData.c.r, modelData.c.g, modelData.c.b, 0.3)
                            Layout.alignment: Qt.AlignVCenter

                            Kirigami.Icon {
                                anchors.centerIn: parent
                                source: modelData.i
                                implicitWidth: 28
                                implicitHeight: 28
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Text {
                                text: modelData.t
                                color: win.txt
                                font.family: "IBM Plex Sans"
                                font.pixelSize: 15
                                font.bold: true
                            }
                            Text {
                                text: modelData.d
                                color: win.txt2
                                font.family: "IBM Plex Sans"
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
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
                property string iconName
                property color accent: win.blue
                property var onTap
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                radius: 12
                color: ma.containsMouse ? Qt.lighter(accent, 1.1) : accent
                
                RowLayout {
                    anchors.centerIn: parent
                    spacing: 8
                    Kirigami.Icon {
                        source: parent.parent.iconName
                        implicitWidth: 20
                        implicitHeight: 20
                        color: "white"
                        visible: parent.parent.iconName !== ""
                    }
                    Text {
                        text: parent.parent.label
                        color: "white"
                        font.family: "IBM Plex Sans"
                        font.pixelSize: 15
                        font.bold: true
                    }
                }
                
                MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: parent.onTap() }
                Behavior on color { ColorAnimation { duration: 120 } }
            }
            NavButton { label: "ثبّت الأساسيات | Install essentials"; iconName: "moos-install"; accent: win.blue;   onTap: function(){ win.openApp("moos://app/setup",  "التطبيقات | apps") } }
            NavButton { label: "افتح Mo AI | Open Mo AI";            iconName: "moos-ai"; accent: win.violet; onTap: function(){ win.openApp("moos://app/moai",   "Mo AI") } }
            NavButton { label: "مركز التوافق | Compatibility";       iconName: "moos-gaming"; accent: win.raised; onTap: function(){ win.openApp("moos://app/compat", "التوافق | compat") } }
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

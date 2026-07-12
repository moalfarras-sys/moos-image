// =============================================================================
// MoOS Hardware Center v0 — نظرة عامة على الأجهزة | device overview (viewer)
//
// Pure-QML "script app": no compiled code. Launched by /usr/bin/moos-hardware,
// which FIRST collects a read-only snapshot to /tmp/moos-hw.json (QML has no
// Process API) and THEN starts this window through the Qt6 qml runner
// (Fedora binary /usr/bin/qml-qt6, shipped by qt6-qtdeclarative-devel).
//
// This window only DISPLAYS the collected JSON — it never executes anything.
// The single "actionable" hint (NVIDIA -> moos-nvidia) is copy-only: a mono box
// + clipboard copy, exactly like the Compatibility Hub. See
// MOOS_HARDWARE_CENTER_PLAN.md (§4 Overview, §7 NVIDIA, §8 Report).
// =============================================================================
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    title: "مركز الأجهزة | Hardware Center"
    width: 820
    height: 620
    minimumWidth: 720
    minimumHeight: 520
    color: novaBg

    // --- Nova palette (MOOS_DESIGN_SYSTEM.md / branding/PALETTE.md) ----------
    readonly property color novaBg:      "#0B1220"
    readonly property color novaSurface: "#111A2E"
    readonly property color novaRaised:  "#1A2740"
    readonly property color novaBlue:    "#2E7BFF"
    readonly property color novaCyan:    "#22D3EE"
    readonly property color novaViolet:  "#8B5CF6"
    readonly property color novaText:    "#E6EDF7"
    readonly property color novaMuted:   "#9FB0C9"
    readonly property color novaEdge:    "#22304A"   // resting card border
    readonly property color novaAmber:   "#F5A524"   // honest warning accent

    readonly property string uiFont:   "IBM Plex Sans"
    readonly property string monoFont: "JetBrains Mono"

    // Collected snapshot (populated in Component.onCompleted). rawJson is the
    // exact bytes read from disk — that is what the footer button copies.
    property var hw: ({})
    property string rawJson: ""

    // No page toolbar chrome — the page draws its own Nova header.
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    // Return a non-empty plain string for a field, else the honest fallback.
    function fieldOr(v) {
        return (v !== undefined && v !== null && String(v).length > 0)
            ? String(v) : "unavailable"
    }

    // True when the detected GPU string mentions NVIDIA (drives the amber note).
    readonly property bool gpuIsNvidia:
        root.hw.gpu !== undefined
        && String(root.hw.gpu).toUpperCase().indexOf("NVIDIA") !== -1
    readonly property bool needsAction: root.hw.health === "action-needed"

    // -------------------------------------------------------------------------
    // Read the collector output. file:// XHR on a local path usually reports
    // status 0 (not 200), so we key off DONE + non-empty responseText instead.
    // -------------------------------------------------------------------------
    Component.onCompleted: {
        var xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                if (xhr.responseText && xhr.responseText.length > 0) {
                    root.rawJson = xhr.responseText
                    try {
                        root.hw = JSON.parse(xhr.responseText)
                    } catch (e) {
                        root.hw = {}
                    }
                }
            }
        }
        xhr.open("GET", "file:///tmp/moos-hw.json")
        xhr.send()
    }

    // -------------------------------------------------------------------------
    // Reusable info card: accent bar + title + monospace, selectable value.
    // Optional amber NVIDIA note with a copy-to-clipboard command box.
    // RTL-safe: pure Layouts, no left/right anchors — mirrors with the locale.
    // -------------------------------------------------------------------------
    component HwCard: Rectangle {
        id: card

        property string titleText
        property string value: "unavailable"
        property color accent: root.novaBlue
        property bool showNvidia: false
        property string iconName: ""

        radius: 16
        color: cardHover.hovered ? Qt.rgba(26/255, 39/255, 64/255, 0.75) : Qt.rgba(17/255, 26/255, 46/255, 0.45)
        border.width: cardHover.hovered ? 2 : 1
        border.color: cardHover.hovered ? card.accent : root.novaEdge
        scale: cardHover.hovered ? 1.015 : 1.0

        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }
        Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }

        implicitHeight: cardInner.implicitHeight + 36
        implicitWidth: 320

        HoverHandler { id: cardHover }

        ColumnLayout {
            id: cardInner
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    width: 40
                    height: 40
                    radius: 10
                    color: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.15)
                    border.width: 1
                    border.color: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.3)
                    Layout.alignment: Qt.AlignVCenter
                    visible: card.iconName !== ""

                    Kirigami.Icon {
                        anchors.centerIn: parent
                        source: card.iconName
                        implicitWidth: 24
                        implicitHeight: 24
                    }
                }

                Text {
                    text: card.titleText
                    color: root.novaText
                    font.family: root.uiFont
                    font.pixelSize: 15
                    font.bold: true
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            // --- the value (monospace, selectable, read-only) ---------------
            TextEdit {
                text: card.value
                readOnly: true
                selectByMouse: true
                textFormat: TextEdit.PlainText
                color: root.novaText
                selectionColor: root.novaBlue
                selectedTextColor: "#FFFFFF"
                font.family: root.monoFont
                font.pixelSize: 12
                wrapMode: TextEdit.Wrap
                Layout.fillWidth: true
            }

            // --- amber NVIDIA hint (GPU card only) --------------------------
            RowLayout {
                visible: card.showNvidia
                spacing: 8
                Layout.fillWidth: true
                
                Kirigami.Icon {
                    source: "moos-warning"
                    implicitWidth: 20
                    implicitHeight: 20
                    color: root.novaAmber
                    Layout.alignment: Qt.AlignTop
                }
                
                Text {
                    text: "كرت NVIDIA مكتشف. لأفضل تعريف، انتقل إلى صورة MoOS الخاصة بـ NVIDIA — انسخ ونفّذ في Konsole:\nNVIDIA GPU detected. For the best driver, switch to the NVIDIA MoOS image — copy & run in Konsole:"
                    color: root.novaAmber
                    font.family: root.uiFont
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                    lineHeight: 1.25
                    Layout.fillWidth: true
                }
            }

            Rectangle {
                visible: card.showNvidia
                Layout.fillWidth: true
                radius: 8
                color: root.novaRaised
                border.width: 1
                border.color: root.novaAmber
                implicitHeight: nvCol.implicitHeight + 22

                ColumnLayout {
                    id: nvCol
                    anchors.fill: parent
                    anchors.margins: 11
                    spacing: 7

                    TextEdit {
                        id: nvCmd
                        text: "sudo bootc switch ghcr.io/moalfarras-sys/moos-nvidia:latest"
                        readOnly: true
                        selectByMouse: true
                        textFormat: TextEdit.PlainText
                        color: root.novaText
                        selectionColor: root.novaBlue
                        selectedTextColor: "#FFFFFF"
                        font.family: root.monoFont
                        font.pixelSize: 12
                        wrapMode: TextEdit.WrapAnywhere
                        Layout.fillWidth: true
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        QQC2.Button {
                            id: nvCopyBtn
                            text: "نسخ الأمر | Copy"
                            leftPadding: 14
                            rightPadding: 14
                            topPadding: 7
                            bottomPadding: 7
                            contentItem: RowLayout {
                                spacing: 6
                                LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
                                Kirigami.Icon {
                                    source: "moos-copy"
                                    implicitWidth: 16
                                    implicitHeight: 16
                                    color: "white"
                                }
                                Text {
                                    text: nvCopyBtn.text
                                    color: "#FFFFFF"
                                    font.family: root.uiFont
                                    font.pixelSize: 12
                                    font.bold: true
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    Layout.fillWidth: true
                                }
                            }
                            background: Rectangle {
                                radius: 8
                                color: nvCopyBtn.down ? Qt.darker(root.novaAmber, 1.25)
                                     : nvCopyBtn.hovered ? Qt.lighter(root.novaAmber, 1.12)
                                     : root.novaAmber
                            }
                            onClicked: {
                                nvCmd.selectAll()
                                nvCmd.copy()
                                nvCmd.deselect()
                                nvCopied.opacity = 1
                                nvCopiedTimer.restart()
                            }
                        }

                        Text {
                            id: nvCopied
                            text: "✓ نُسخ | Copied"
                            color: root.novaCyan
                            font.family: root.uiFont
                            font.pixelSize: 12
                            opacity: 0
                            Behavior on opacity { NumberAnimation { duration: 180 } }
                        }

                        Item { Layout.fillWidth: true }

                        Timer {
                            id: nvCopiedTimer
                            interval: 2000
                            onTriggered: nvCopied.opacity = 0
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }   // pin content to top on tall rows
        }
    }

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        background: Rectangle {
            color: root.novaBg
            Image {
                source: "file:///usr/share/wallpapers/NovaHorizonII/contents/images_dark/3840x2160.png"
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                opacity: 0.22
                smooth: true
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // RTL: mirror the whole tree under Arabic locales.
            LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
            LayoutMirroring.childrenInherit: true

            // --- header ------------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Image {
                    source: "file:///usr/share/moos/moos-logo.png"
                    sourceSize.width: 88
                    sourceSize.height: 88
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 44
                    fillMode: Image.PreserveAspectFit
                    visible: status === Image.Ready
                }

                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    Text {
                        text: "مركز الأجهزة | Hardware Center"
                        color: root.novaText
                        font.family: root.uiFont
                        font.pixelSize: 20
                        font.bold: true
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    Text {
                        text: root.needsAction
                            ? "اكتمل الفحص — يوجد إجراء موصى به | Scan complete — action recommended"
                            : "اكتمل الفحص — الجهاز جاهز | Scan complete — this device is ready"
                        color: root.novaMuted
                        font.family: root.uiFont
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }

            // --- the six cards -----------------------------------------------
            QQC2.ScrollView {
                id: scroller
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

                GridLayout {
                    width: scroller.availableWidth
                    columns: width > 640 ? 2 : 1
                    columnSpacing: 14
                    rowSpacing: 14

                    HwCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaBlue
                        iconName: "moos-cpu"
                        titleText: "المعالج | CPU"
                        value: root.fieldOr(root.hw.cpu)
                    }

                    HwCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaCyan
                        iconName: "moos-memory"
                        titleText: "الذاكرة | Memory"
                        value: root.fieldOr(root.hw.memory)
                    }

                    HwCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaViolet
                        iconName: "moos-gpu"
                        titleText: "كرت الشاشة | GPU"
                        value: root.fieldOr(root.hw.gpu)
                        showNvidia: root.gpuIsNvidia
                    }

                    HwCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaBlue
                        iconName: "moos-storage"
                        titleText: "الأقراص | Disks"
                        value: root.fieldOr(root.hw.disks)
                    }

                    HwCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaCyan
                        iconName: "moos-network"
                        titleText: "الشبكة | Network"
                        value: root.fieldOr(root.hw.network)
                    }

                    HwCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaViolet
                        iconName: "moos-system"
                        titleText: "النظام | System"
                        value: root.fieldOr(root.hw.os)
                    }
                }
            }

            // --- footer: copy full report -----------------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                QQC2.Button {
                    id: smartBtn
                    visible: root.needsAction
                    text: "إصلاح التعريف | Apply driver fix"
                    leftPadding: 16
                    rightPadding: 16
                    topPadding: 9
                    bottomPadding: 9
                    contentItem: Text {
                        text: smartBtn.text
                        color: "white"
                        font.family: root.uiFont
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    background: Rectangle {
                        radius: 8
                        color: smartBtn.hovered ? Qt.lighter(root.novaAmber, 1.1) : root.novaAmber
                    }
                    onClicked: Qt.openUrlExternally("moos://do/install-nvidia")
                }

                QQC2.Button {
                    id: reportBtn
                    leftPadding: 16
                    rightPadding: 16
                    topPadding: 9
                    bottomPadding: 9
                    text: "نسخ تقرير كامل | Copy full report"
                    contentItem: RowLayout {
                        spacing: 6
                        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
                        Kirigami.Icon {
                            source: "moos-report"
                            implicitWidth: 16
                            implicitHeight: 16
                            color: "white"
                        }
                        Text {
                            text: reportBtn.text
                            color: "#FFFFFF"
                            font.family: root.uiFont
                            font.pixelSize: 13
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            Layout.fillWidth: true
                        }
                    }
                    background: Rectangle {
                        radius: 8
                        color: reportBtn.down ? Qt.darker(root.novaBlue, 1.25)
                             : reportBtn.hovered ? Qt.lighter(root.novaBlue, 1.12)
                             : root.novaBlue
                    }
                    onClicked: {
                        reportEdit.selectAll()
                        reportEdit.copy()
                        reportEdit.deselect()
                        reportCopied.opacity = 1
                        reportCopiedTimer.restart()
                    }
                }

                Text {
                    id: reportCopied
                    text: "✓ نُسخ التقرير إلى الحافظة | Report copied"
                    color: root.novaCyan
                    font.family: root.uiFont
                    font.pixelSize: 12
                    opacity: 0
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: "طبقات صادقة، لا وعود كاذبة — MoOS | Honest layers, no false promises"
                    color: root.novaMuted
                    opacity: 0.7
                    font.family: root.uiFont
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignRight
                }

                Timer {
                    id: reportCopiedTimer
                    interval: 2000
                    onTriggered: reportCopied.opacity = 0
                }
            }
        }

        // Off-screen holder of the raw JSON — the footer button copies FROM
        // here (selectAll + copy). Kept renderable (opacity 0, clipped, 1x1) so
        // the clipboard copy always works, without affecting the layout.
        TextEdit {
            id: reportEdit
            text: root.rawJson
            readOnly: true
            textFormat: TextEdit.PlainText
            width: 1
            height: 1
            opacity: 0
            clip: true
            wrapMode: TextEdit.NoWrap
        }
    }
}

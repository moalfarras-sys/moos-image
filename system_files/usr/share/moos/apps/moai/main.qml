// Mo AI v0 — MoOS built-in assistant (chat MVP, local-first via RamaLama)
// Launched by /usr/bin/moai (qml-qt6 runtime — pure QML, no compilation).
//
// Backend: `ramalama serve` → llama.cpp llama-server, an OpenAI-compatible
// REST API. RamaLama's default serving port is 8080 (ramalama-serve docs:
// "The default serving port will be 8080 if available") and moai-start
// passes --port 8080 explicitly so it always matches the constant below.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    // ── The single API constant — change the port here if you serve elsewhere.
    //    (QML property names must start lowercase, hence `api` not `API`.)
    readonly property string api: "http://127.0.0.1:8080/v1/chat/completions"

    readonly property string systemPrompt:
        "You are Mo AI, the built-in assistant of MoOS, a beautiful " +
        "Arabic/English Linux OS by Moalfarras. Answer concisely in the " +
        "user's language."

    // Rendered as Markdown → `moai-start` shows monospace.
    readonly property string offlineHelp:
        "لا أستطيع الوصول إلى العقل المحلي.\n" +
        "I can't reach the local brain.\n\n" +
        "شغّل العقل أولاً | Start the brain first:\n\n" +
        "`moai-start`\n\n" +
        "ثم أعد المحاولة | then try again."

    // Nova dark brand palette (MOOS_DESIGN)
    readonly property color brandBg: "#0B1220"
    readonly property color brandSurface: "#111A2E"
    readonly property color brandRaised: "#1A2740"
    readonly property color brandBlue: "#2E7BFF"
    readonly property color brandCyan: "#22D3EE"
    readonly property color brandText: "#E6EDF7"
    readonly property color brandSecondary: "#9FB0C9"

    property bool serverUp: false
    property bool busy: false
    property var history: []   // [{role, content}] user/assistant only, last 12

    title: "Mo AI"
    width: 420
    height: 680
    minimumWidth: 360
    minimumHeight: 480
    color: brandBg

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    Component.onCompleted: chatModel.append({
        role: "assistant",
        text: "أهلاً! أنا **Mo AI** — مساعدك المحلي في MoOS.\n\n" +
              "Hi! I'm **Mo AI** — your local assistant on MoOS."
    })

    ListModel { id: chatModel }

    // Poll the server so the header badge stays honest. /v1/models is a
    // cheap llama-server endpoint that exists whenever chat/completions does.
    Timer {
        interval: 4000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const xhr = new XMLHttpRequest()
            xhr.open("GET", root.api.replace("/chat/completions", "/models"))
            xhr.onreadystatechange = function () {
                if (xhr.readyState === XMLHttpRequest.DONE)
                    root.serverUp = (xhr.status === 200)
            }
            xhr.send()
        }
    }

    function trimHistory() {
        if (history.length > 12)
            history = history.slice(-12)
    }

    function removeTypingBubble() {
        if (chatModel.count > 0
                && chatModel.get(chatModel.count - 1).role === "typing")
            chatModel.remove(chatModel.count - 1)
    }

    function send() {
        const msg = input.text.trim()
        if (msg === "" || busy)
            return
        input.text = ""
        chatModel.append({ role: "user", text: msg })
        history.push({ role: "user", content: msg })
        trimHistory()
        chatModel.append({ role: "typing", text: "..." })
        busy = true

        const xhr = new XMLHttpRequest()
        xhr.open("POST", api)
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            root.busy = false
            root.removeTypingBubble()
            let reply = ""
            if (xhr.status === 200) {
                try {
                    reply = JSON.parse(xhr.responseText)
                                .choices[0].message.content.trim()
                } catch (e) {
                    reply = ""
                }
            }
            if (reply !== "") {
                chatModel.append({ role: "assistant", text: reply })
                root.history.push({ role: "assistant", content: reply })
                root.trimHistory()
            } else {
                chatModel.append({ role: "assistant", text: root.offlineHelp })
            }
        }
        xhr.send(JSON.stringify({
            model: "default",
            messages: [{ role: "system", content: systemPrompt }]
                          .concat(history),
            stream: false
        }))
    }

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        background: Rectangle { color: root.brandBg }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── Header ──────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                color: root.brandSurface

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 10

                    Image {
                        source: "file:///usr/share/moos/moos-logo.png"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        sourceSize.width: 56
                        sourceSize.height: 56
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                    }

                    Text {
                        text: "Mo AI"
                        color: root.brandText
                        font.family: "IBM Plex Sans"
                        font.pixelSize: 17
                        font.weight: Font.DemiBold
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: root.serverUp ? "● محلي | local"
                                            : "✗ غير متصل | offline"
                        color: root.serverUp ? root.brandCyan
                                             : root.brandSecondary
                        font.family: "IBM Plex Sans"
                        font.pixelSize: 12
                    }
                }

                Rectangle {   // hairline under the header
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: root.brandRaised
                }
            }

            // ── Chat ────────────────────────────────────────────────────
            ListView {
                id: listView
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 2
                topMargin: 8
                bottomMargin: 8
                model: chatModel
                onCountChanged: Qt.callLater(listView.positionViewAtEnd)

                QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                delegate: Item {
                    width: listView.width
                    height: bubble.height + 6

                    Rectangle {
                        id: bubble
                        readonly property bool mine: model.role === "user"
                        // anchors (not x:) so locale LayoutMirroring (RTL)
                        // flips the bubbles correctly.
                        anchors.right: mine ? parent.right : undefined
                        anchors.left: mine ? undefined : parent.left
                        anchors.rightMargin: 12
                        anchors.leftMargin: 12
                        y: 3
                        radius: 10
                        // user: brand blue at 20% alpha; assistant: raised
                        color: mine ? "#332E7BFF" : root.brandRaised
                        width: msgText.width + 24
                        height: msgText.implicitHeight + 18

                        Text {
                            id: msgText
                            x: 12
                            y: 9
                            width: Math.min(implicitWidth,
                                            (listView.width * 0.82) - 24)
                            text: model.text
                            textFormat: model.role === "assistant"
                                        ? Text.MarkdownText : Text.PlainText
                            wrapMode: Text.Wrap
                            color: root.brandText
                            linkColor: root.brandCyan
                            font.family: "IBM Plex Sans"
                            font.pixelSize: 14
                            onLinkActivated: function (link) {
                                Qt.openUrlExternally(link)
                            }

                            SequentialAnimation on opacity {
                                running: model.role === "typing"
                                loops: Animation.Infinite
                                NumberAnimation {
                                    from: 1.0; to: 0.25; duration: 450
                                }
                                NumberAnimation {
                                    from: 0.25; to: 1.0; duration: 450
                                }
                            }
                        }
                    }
                }
            }

            // ── Input row ───────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 64
                color: root.brandSurface

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    QQC2.TextField {
                        id: input
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        placeholderText: "اسأل Mo AI... | Ask Mo AI..."
                        placeholderTextColor: root.brandSecondary
                        color: root.brandText
                        font.family: "IBM Plex Sans"
                        font.pixelSize: 14
                        leftPadding: 12
                        rightPadding: 12
                        background: Rectangle {
                            color: root.brandRaised
                            radius: 8
                            border.width: 1
                            border.color: input.activeFocus ? root.brandBlue
                                                            : "#243350"
                        }
                        onAccepted: root.send()
                    }

                    QQC2.Button {
                        id: sendBtn
                        Layout.fillHeight: true
                        Layout.preferredWidth: 96
                        enabled: !root.busy && input.text.trim().length > 0
                        background: Rectangle {
                            radius: 8
                            color: !sendBtn.enabled ? "#1E3A66"
                                 : sendBtn.pressed ? "#2568D9"
                                 : root.brandBlue
                        }
                        contentItem: Text {
                            text: "إرسال | Send"
                            color: sendBtn.enabled ? "#FFFFFF"
                                                   : root.brandSecondary
                            font.family: "IBM Plex Sans"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: root.send()
                    }
                }
            }
        }
    }
}

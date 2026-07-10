// =============================================================================
// MoOS Compatibility Hub v0 — الشاشة الرئيسية (٤ بطاقات) | main screen (4 cards)
//
// Pure-QML "script app": no compiled code. Launched by /usr/bin/moos-compat
// through the Qt6 qml runner (Fedora binary: /usr/bin/qml-qt6, shipped by
// qt6-qtdeclarative-devel — verified 2026-07-10 on packages.fedoraproject.org).
//
// v0 is an honest ROUTER, not an installer: QML has no Process API, and by
// design this window never executes privileged commands. Each card explains
// one engine, shows the exact Konsole command in a monospace box and copies
// it to the clipboard (TextEdit selectAll+copy). The polkit-backed wizards
// arrive with the compiled Hub — see MOOS_COMPATIBILITY_PLAN.md §7.
// =============================================================================
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    title: "مركز التوافق | MoOS Compatibility Hub"
    width: 900
    height: 600
    minimumWidth: 760
    minimumHeight: 540
    color: novaBg

    // --- Nova palette (MOOS_DESIGN_SYSTEM.md / branding/PALETTE.md) ---------
    readonly property color novaBg:      "#0B1220"
    readonly property color novaSurface: "#111A2E"
    readonly property color novaRaised:  "#1A2740"
    readonly property color novaBlue:    "#2E7BFF"
    readonly property color novaCyan:    "#22D3EE"
    readonly property color novaViolet:  "#8B5CF6"
    readonly property color novaText:    "#E6EDF7"
    readonly property color novaMuted:   "#9FB0C9"
    readonly property color novaEdge:    "#22304A"   // resting card border

    readonly property string uiFont:   "IBM Plex Sans"
    readonly property string monoFont: "JetBrains Mono"

    // No page toolbar chrome — the page draws its own Nova header.
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    // -------------------------------------------------------------------------
    // Reusable card: accent bar + title + body + monospace command box + honest
    // note. The button NEVER runs anything: display + clipboard only (v0).
    // RTL-safe: pure Layouts, no left/right anchors — mirrors with the locale.
    // -------------------------------------------------------------------------
    component CompatCard: Rectangle {
        id: card

        property string titleText
        property string bodyText
        property string command: ""
        property string noteText: ""
        property color accent: root.novaBlue

        radius: 14
        color: root.novaSurface
        border.width: cardHover.hovered ? 2 : 1
        border.color: cardHover.hovered ? root.novaBlue : root.novaEdge

        implicitHeight: cardInner.implicitHeight + 36
        implicitWidth: 320

        HoverHandler { id: cardHover }

        ColumnLayout {
            id: cardInner
            anchors.fill: parent
            anchors.margins: 18
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    implicitWidth: 5
                    implicitHeight: 22
                    radius: 2.5
                    color: card.accent
                }

                Text {
                    text: card.titleText
                    color: root.novaText
                    font.family: root.uiFont
                    font.pixelSize: 17
                    font.bold: true
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Text {
                text: card.bodyText
                color: root.novaMuted
                font.family: root.uiFont
                font.pixelSize: 13
                wrapMode: Text.Wrap
                lineHeight: 1.25
                Layout.fillWidth: true
            }

            // --- command box (monospace, selectable, copy-to-clipboard) -----
            Rectangle {
                visible: card.command.length > 0
                Layout.fillWidth: true
                radius: 8
                color: root.novaRaised
                border.width: 1
                border.color: root.novaEdge
                implicitHeight: cmdCol.implicitHeight + 22

                ColumnLayout {
                    id: cmdCol
                    anchors.fill: parent
                    anchors.margins: 11
                    spacing: 7

                    Text {
                        text: "انسخ ونفّذ في Konsole | Copy & run in Konsole"
                        color: root.novaCyan
                        font.family: root.uiFont
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    TextEdit {
                        id: cmdEdit
                        text: card.command
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
                            id: copyBtn
                            text: "📋 نسخ الأمر | Copy"
                            leftPadding: 14
                            rightPadding: 14
                            topPadding: 7
                            bottomPadding: 7
                            contentItem: Text {
                                text: copyBtn.text
                                color: "#FFFFFF"
                                font.family: root.uiFont
                                font.pixelSize: 12
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: 8
                                color: copyBtn.down ? Qt.darker(root.novaBlue, 1.25)
                                     : copyBtn.hovered ? Qt.lighter(root.novaBlue, 1.12)
                                     : root.novaBlue
                            }
                            onClicked: {
                                cmdEdit.selectAll()
                                cmdEdit.copy()
                                cmdEdit.deselect()
                                copiedTag.opacity = 1
                                copiedTimer.restart()
                            }
                        }

                        Text {
                            id: copiedTag
                            text: "✓ نُسخ إلى الحافظة | Copied"
                            color: root.novaCyan
                            font.family: root.uiFont
                            font.pixelSize: 12
                            opacity: 0
                            Behavior on opacity { NumberAnimation { duration: 180 } }
                        }

                        Item { Layout.fillWidth: true }

                        Timer {
                            id: copiedTimer
                            interval: 2000
                            onTriggered: copiedTag.opacity = 0
                        }
                    }
                }
            }

            Text {
                visible: card.noteText.length > 0
                text: card.noteText
                color: root.novaMuted
                opacity: 0.85
                font.family: root.uiFont
                font.pixelSize: 11
                wrapMode: Text.Wrap
                lineHeight: 1.2
                Layout.fillWidth: true
            }

            Item { Layout.fillHeight: true }   // pin content to top on tall rows
        }
    }

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        background: Rectangle { color: root.novaBg }

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
                        text: "مركز التوافق | Compatibility Hub"
                        color: root.novaText
                        font.family: root.uiFont
                        font.pixelSize: 20
                        font.bold: true
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "أربع بوابات صادقة: Windows وAndroid وiPhone وذكاء محلي | Four honest gateways: Windows, Android, iPhone & local AI"
                        color: root.novaMuted
                        font.family: root.uiFont
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }

            // --- the four cards ----------------------------------------------
            QQC2.ScrollView {
                id: scroller
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

                GridLayout {
                    width: scroller.availableWidth
                    columns: width > 700 ? 2 : 1
                    columnSpacing: 14
                    rowSpacing: 14

                    // (a) Windows apps & games — routes to moos-setup
                    CompatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaBlue
                        titleText: "🎮 ألعاب وبرامج Windows | Windows apps & games"
                        bodyText: "ألعابك تعمل عبر Steam + Proton، وبرامج Windows عبر Bottles (Wine). أمر واحد في Konsole يثبّت الحزمة كاملة مع Lutris. | Games run via Steam + Proton, Windows programs via Bottles (Wine). One Konsole command installs the full set, Lutris included."
                        command: "moos-setup"
                        noteText: "⚠ صدق أولاً: ألعاب anti-cheat التنافسية (Valorant وأشباهها) لا تعمل على Linux — تحقق من protondb.com قبل الشراء. | Honesty first: competitive anti-cheat titles (Valorant & co.) do not run on Linux — check protondb.com before buying."
                    }

                    // (b) Android via Waydroid — opt-in, commands from
                    // MOOS_COMPATIBILITY_PLAN.md §4.2 (flags verified against
                    // docs.waydro.id: init -s {VANILLA|FOSS|GAPPS}, default VANILLA)
                    CompatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaCyan
                        titleText: "🤖 تطبيقات Android | Android apps"
                        bodyText: "Waydroid يشغّل Android 13 (LineageOS) في حاوية أصلية — اختياري بالكامل، لا شيء يعمل قبل أن تفعّله بنفسك. المتجر المقترح: F-Droid. | Waydroid runs Android 13 (LineageOS) in a native container — fully opt-in, nothing runs until you enable it yourself. Suggested store: F-Droid."
                        command: "sudo waydroid init -s VANILLA\nsudo systemctl enable --now waydroid-container.service\nwaydroid show-full-ui"
                        noteText: "⚠ حدود صادقة: الكاميرا والمايكروفون لا يعملان، تطبيقات البنوك (Play Integrity) لن تعمل أبداً، ولا يوجد Google Play — إضافته خيار متقدم على مسؤوليتك. | Honest limits: no camera/mic, banking apps (Play Integrity) will never work, and there is no Google Play — adding it is an advanced opt-in at your own risk."
                    }

                    // (c) iPhone Companion — KDE Connect is PREINSTALLED on
                    // Kinoite (kde-connect is a default package of the Fedora 44
                    // comps group kde-desktop — verified 2026-07-10), so this
                    // card explains pairing instead of installing.
                    CompatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaViolet
                        titleText: "📱 مرافق iPhone | iPhone Companion"
                        bodyText: "تطبيقات iOS لا تعمل على Linux — قيد من Apple لا من MoOS. المتاح فعلاً: KDE Connect (مثبّت مسبقاً) للإشعارات والملفات والحافظة. ثبّت KDE Connect على iPhone من App Store، اتصل بنفس شبكة Wi-Fi، ثم افتح: | iOS apps cannot run on Linux — Apple's restriction, not MoOS. What genuinely works: KDE Connect (preinstalled) for notifications, files and clipboard. Install KDE Connect on the iPhone from the App Store, join the same Wi-Fi, then open:"
                        command: "kdeconnect-app"
                        noteText: "مرآة شاشة iPhone عبر UxPlay (AirPlay) تصل في تحديث قادم. | UxPlay (AirPlay) screen mirroring arrives in a later update."
                    }

                    // (d) Mo AI — local assistant (RamaLama backend)
                    CompatCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        accent: root.novaBlue
                        titleText: "🧠 Mo AI — الذكاء المحلي | Local AI"
                        bodyText: "مساعد MoOS يعمل محلياً عبر RamaLama — النموذج على جهازك وبياناتك لا تغادره. الأمر الأول يجهّز النموذج، والثاني يبدأ المحادثة. | The MoOS assistant runs locally via RamaLama — the model lives on your machine and your data never leaves it. The first command prepares the model, the second starts the chat."
                        command: "moai-start\nmoai"
                        noteText: "إن لم يكن الأمر متوفراً بعد فهو يصل مع تحديث Mo AI القادم — انظر MOOS_AI_ASSISTANT_PLAN. | If the command is not available yet, it ships with the upcoming Mo AI update — see MOOS_AI_ASSISTANT_PLAN."
                    }
                }
            }

            // --- footer -------------------------------------------------------
            Text {
                text: "طبقات صادقة، لا وعود كاذبة — MoOS | Honest layers, no false promises"
                color: root.novaMuted
                opacity: 0.7
                font.family: root.uiFont
                font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
        }
    }
}

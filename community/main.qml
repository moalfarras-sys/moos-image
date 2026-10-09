import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Kirigami.ApplicationWindow {
    id: root
    width: 1040
    height: 760
    minimumWidth: 560
    minimumHeight: 520
    visible: true
    title: local("مجتمع MoOS", "MoOS Community")
    readonly property var s: community.snapshot
    readonly property bool rtl: MoUI.Locale.rtl
    property int section: 0
    property string pictureTarget: "report"
    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true
    function local(ar, en) { return MoUI.Locale.local(ar, en) }
    function stateLabel(value) {
        var names = {
            "received": local("مستلم", "Received"),
            "triage": local("قيد الفحص", "Under review"),
            "testing": local("إصلاح قيد الاختبار", "Fix being tested"),
            "released": local("صدر الإصلاح", "Fix released"),
            "closed": local("مغلق", "Closed")
        }
        return names[value] || ""
    }

    component Ink: QQC2.Label {
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        color: Kirigami.Theme.textColor
        // Logical start; inherited LayoutMirroring supplies the RTL direction.
        horizontalAlignment: Text.AlignLeft
    }
    component QuietInk: Ink { color: Qt.alpha(Kirigami.Theme.textColor, 0.78) }
    component SurfaceDialog: QQC2.Dialog {
        id: surface
        // Popups can resolve the controls palette separately from Kirigami's
        // ink. Use the same theme roles for both sides, including private
        // review profiles that have no platform palette provider.
        background: Rectangle {
            color: Kirigami.Theme.backgroundColor
            radius: MoUI.Tokens.radiusCard
            border.width: 1
            border.color: Qt.alpha(Kirigami.Theme.textColor, 0.22)
        }
        header: Ink {
            objectName: "conversationHeader"
            // User-supplied report titles must never trigger AutoText/image URLs.
            text: surface.title
            visible: surface.title !== ""
            wrapMode: Text.NoWrap
            elide: Text.ElideRight
            font.bold: true
            padding: 12
        }
    }
    // The installed Breeze mobile toolbar types its target as TextInput,
    // while TextArea is TextEdit. Use Qt's public Basic template for this
    // multiline field, with the same MoOS palette and focus roles; no vendor fork.
    component WriteArea: Basic.TextArea {
        textFormat: TextEdit.PlainText
        wrapMode: TextEdit.Wrap
        horizontalAlignment: Text.AlignLeft
        color: Kirigami.Theme.textColor
        placeholderTextColor: Qt.alpha(Kirigami.Theme.textColor, 0.78)
        selectionColor: Kirigami.Theme.highlightColor
        selectedTextColor: Kirigami.Theme.highlightedTextColor
        padding: 12
        background: Rectangle {
            color: Kirigami.Theme.backgroundColor
            radius: MoUI.Tokens.radiusControl
            border.width: parent.activeFocus ? 2 : 1
            border.color: parent.activeFocus ? Kirigami.Theme.focusColor : Qt.alpha(Kirigami.Theme.textColor, 0.22)
        }
    }
    component Panel: Rectangle {
        radius: MoUI.Tokens.radiusCard
        color: Kirigami.Theme.alternateBackgroundColor
        border.width: 1
        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.22)
    }
    function persistReport() {
        if (editor.opened) community.saveReportDraft(reportTitle.text, reportBody.text, kind.currentIndex, makePublic.checked)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16
        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            Kirigami.Icon { source: "moos-logo"; Layout.preferredWidth: 48; Layout.preferredHeight: 48 }
            ColumnLayout {
                Layout.fillWidth: true
                Ink { text: root.local("نطوّر MoOS معك", "Build MoOS with us"); font.pixelSize: 28; font.bold: true; Layout.fillWidth: true }
                QuietInk { text: root.local("مشكلة تُحلّ. فكرة تُحدث فرقًا. ومعك نتابع النتيجة.", "Report a problem, share an idea, and follow the result."); Layout.fillWidth: true }
            }
            MoUI.Button { label: root.local("تحديث", "Refresh"); enabled: !root.s.busy; onClicked: community.refresh() }
            MoUI.Button { visible: root.s.signedIn; label: root.local("خروج", "Sign out"); onClicked: community.logout() }
        }

        Panel {
            Layout.fillWidth: true
            implicitHeight: infoColumn.implicitHeight + 24
            ColumnLayout {
                id: infoColumn
                anchors.fill: parent; anchors.margins: 12; spacing: 6
                Ink { Layout.fillWidth: true; font.bold: true; text: root.s.signedIn ? root.s.displayName : root.local("محادثاتك خاصة بك وبفريق التطوير", "Your conversations are private to you and the development team") }
                QuietInk { Layout.fillWidth: true; text: root.local("الاقتراح العام ينشر الفكرة الأولى فقط. الردود والصور تبقى خاصة.", "A public suggestion shares only your original idea. Replies and pictures stay private.") }
            }
        }

        QQC2.TabBar {
            id: tabs
            Layout.fillWidth: true
            currentIndex: root.section
            onCurrentIndexChanged: root.section = currentIndex
            QQC2.TabButton { text: root.local("بلاغاتي", "My conversations"); implicitHeight: 44 }
            QQC2.TabButton { text: root.local("اقتراحات عامة", "Public suggestions"); implicitHeight: 44 }
            QQC2.TabButton { text: root.local("الإشعارات", "Notifications"); implicitHeight: 44 }
        }

        Panel {
            Layout.fillWidth: true
            visible: root.s.status !== ""
            implicitHeight: statusRow.implicitHeight + 24
            RowLayout {
                id: statusRow
                anchors.fill: parent; anchors.margins: 12
                QQC2.BusyIndicator { running: root.s.busy; visible: running; Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
                Ink { Layout.fillWidth: true; text: root.s.status; color: root.s.error ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor }
                MoUI.Button { visible: root.s.pending > 0; enabled: !root.s.busy; label: root.local("أعد الإرسال", "Retry sending"); onClicked: community.retryPending() }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.section
            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 16
                    Panel {
                        visible: !root.s.signedIn
                        Layout.fillWidth: true
                        implicitHeight: loginColumn.implicitHeight + 32
                        ColumnLayout {
                            id: loginColumn
                            anchors.fill: parent; anchors.margins: 16; spacing: 12
                            Ink { text: root.local("مساحة واحدة لمتابعة طلباتك", "One place to follow your requests"); font.pixelSize: 20; font.bold: true }
                            QuietInk { text: root.local("سجّل الدخول لإرسال بلاغ خاص أو اقتراح تطوير.", "Sign in to send a private report or a suggestion."); Layout.fillWidth: true }
                            QQC2.TextField { id: username; Layout.fillWidth: true; implicitHeight: 44; placeholderText: root.local("اسم الدخول · حروف لاتينية وأرقام و _", "Sign-in name · letters, numbers and _"); maximumLength: 32; Accessible.name: placeholderText }
                            QQC2.TextField { id: password; Layout.fillWidth: true; implicitHeight: 44; placeholderText: root.local("كلمة المرور · 12 حرفًا على الأقل", "Password · at least 12 characters"); echoMode: TextInput.Password; maximumLength: 128; Accessible.name: root.local("كلمة المرور", "Password") }
                            RowLayout {
                                MoUI.Button { primary: true; label: root.local("دخول", "Sign in"); enabled: !root.s.busy && username.text.length >= 3 && password.text.length >= 12; onClicked: { community.login(username.text, password.text); password.text = "" } }
                                MoUI.Button { label: root.local("حساب جديد", "Create account"); enabled: root.s.registrationOpen && !root.s.busy; onClicked: registration.open() }
                            }
                        }
                    }

                    RowLayout {
                        visible: root.s.signedIn
                        Layout.fillWidth: true
                        Ink { text: root.local("محادثاتك", "Your conversations"); font.pixelSize: 20; font.bold: true; Layout.fillWidth: true }
                        QuietInk { visible: root.s.pending > 0; text: root.local("مسودات تنتظر الإرسال: ", "Pending drafts: ") + root.s.pending }
                        MoUI.Button { objectName: "newReport"; primary: true; label: root.local("مشكلة أو فكرة جديدة", "New report or idea"); onClicked: editor.open() }
                    }
                    QQC2.ScrollView {
                        id: pendingScroll
                        contentWidth: availableWidth
                        visible: root.s.signedIn && root.s.pending > 0
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(160, pendingColumn.implicitHeight)
                        clip: true
                        ColumnLayout {
                            id: pendingColumn
                            width: pendingScroll.availableWidth
                            Repeater {
                                model: root.s.drafts
                                delegate: RowLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    QuietInk { text: modelData.title || root.local("صورة تنتظر الإرسال", "Picture pending"); Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
                                    MoUI.Button { label: root.local("أعد الإرسال", "Retry"); enabled: !root.s.busy; onClicked: community.retry(modelData.id) }
                                    MoUI.Button { label: root.local("حذف المسودة", "Discard draft"); enabled: !root.s.busy; onClicked: { discardDraft.identity = modelData.id; discardDraft.open() } }
                                }
                            }
                        }
                    }

                    QQC2.ScrollView {
                        id: threadsScroll
                        contentWidth: availableWidth
                        visible: root.s.signedIn
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        ColumnLayout {
                            width: threadsScroll.availableWidth
                            spacing: 12
                            QuietInk { visible: root.s.threads.length === 0; text: root.local("ابدأ بأول بلاغ أو فكرة. سنجمع محادثاتك هنا.", "Start your first report or idea. Your conversations appear here."); Layout.fillWidth: true }
                            Repeater {
                                model: root.s.threads
                                delegate: Panel {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    implicitHeight: threadColumn.implicitHeight + 24
                                    ColumnLayout {
                                        id: threadColumn
                                        anchors.fill: parent; anchors.margins: 12
                                        Ink { text: modelData.title; font.bold: true; Layout.fillWidth: true }
                                        RowLayout {
                                            QuietInk { text: root.stateLabel(modelData.state); Layout.fillWidth: true }
                                            MoUI.Button { label: root.local("افتح المحادثة", "Open conversation"); onClicked: { community.selectThread(modelData.id); conversation.open() } }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Item { visible: !root.s.signedIn; Layout.fillHeight: true }
                }
            }

            QQC2.ScrollView {
                id: publicScroll
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                    width: publicScroll.availableWidth; spacing: 12
                    QuietInk { visible: root.s.suggestions.length === 0; text: root.local("لا توجد اقتراحات منشورة بعد.", "No public suggestions yet."); Layout.fillWidth: true }
                    Repeater {
                        model: root.s.suggestions
                        delegate: Panel {
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: proposal.implicitHeight + 32
                            ColumnLayout {
                                id: proposal
                                anchors.fill: parent; anchors.margins: 16; spacing: 8
                                Ink { text: modelData.title; font.pixelSize: 20; font.bold: true; Layout.fillWidth: true }
                                Ink { text: modelData.proposal; Layout.fillWidth: true }
                                QuietInk { text: modelData.display_name + " · " + root.stateLabel(modelData.state); Layout.fillWidth: true }
                                MoUI.Button { visible: root.s.role === "maintainer" && root.s.signedIn; label: root.local("إخفاء الاقتراح العام", "Hide public suggestion"); onClicked: community.hideSuggestion(modelData.id) }
                            }
                        }
                    }
                }
            }

            QQC2.ScrollView {
                id: notificationsScroll
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                    width: notificationsScroll.availableWidth; spacing: 12
                    QuietInk { visible: !root.s.signedIn; text: root.local("سجّل الدخول لقراءة ردود الفريق وتحديثات بلاغاتك.", "Sign in to read replies and report updates."); Layout.fillWidth: true }
                    QuietInk { visible: root.s.signedIn && root.s.notifications.length === 0; text: root.local("لا توجد إشعارات جديدة.", "No new notifications."); Layout.fillWidth: true }
                    Repeater {
                        model: root.s.notifications
                        delegate: Panel {
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: notification.implicitHeight + 24
                            RowLayout {
                                id: notification
                                anchors.fill: parent; anchors.margins: 12
                                Ink { Layout.fillWidth: true; text: modelData.event === "released" ? root.local("صدر إصلاح مرتبط ببلاغك. افتح المحادثة لمعرفة الإصدار.", "A fix for your report was released. Open the conversation for its version.") : root.local("رد أو تحديث جديد على بلاغك.", "A new reply or status update on your report.") }
                                MoUI.Button { label: modelData.seen ? root.local("افتح", "Open") : root.local("اقرأ", "Read"); onClicked: { community.markSeen(modelData.id); community.selectThread(modelData.thread); conversation.open() } }
                            }
                        }
                    }
                }
            }
        }

        QuietInk { Layout.fillWidth: true; text: root.local("صدور الإصلاح يختلف عن تثبيته على جهازك. نعرض ما تؤكده الخدمة فقط.", "A released fix and an installed update are different. We show verified service state."); font.pixelSize: 12 }
    }

    SurfaceDialog {
        id: registration
        title: root.local("حسابك في مجتمع MoOS", "Your MoOS Community account")
        modal: true
        anchors.centerIn: parent
        width: Math.min(480, root.width - 48)
        ColumnLayout {
            width: parent.width; spacing: 12
            QQC2.TextField { id: newName; Layout.fillWidth: true; implicitHeight: 44; placeholderText: root.local("اسمك المعروض", "Display name"); maximumLength: 60; Accessible.name: placeholderText }
            QQC2.TextField { id: newUser; Layout.fillWidth: true; implicitHeight: 44; placeholderText: root.local("اسم الدخول", "Sign-in name"); maximumLength: 32; Accessible.name: placeholderText }
            QQC2.TextField { id: newPassword; Layout.fillWidth: true; implicitHeight: 44; placeholderText: root.local("كلمة مرور جديدة · 12 حرفًا على الأقل", "New password · at least 12 characters"); echoMode: TextInput.Password; maximumLength: 128; Accessible.name: root.local("كلمة مرور جديدة", "New password") }
            QuietInk { Layout.fillWidth: true; text: root.local("اسمك المعروض يظهر إذا اخترت نشر اقتراح عام. كلمات المرور لا تُحفظ في التطبيق.", "Your display name appears if you publish a suggestion. The app does not store passwords.") }
            RowLayout {
                MoUI.Button { primary: true; label: root.local("أنشئ الحساب", "Create account"); enabled: newName.text.trim().length > 0 && newUser.text.length >= 3 && newPassword.text.length >= 12; onClicked: { community.register(newUser.text, newPassword.text, newName.text); newPassword.text = ""; registration.close() } }
                MoUI.Button { label: root.local("إلغاء", "Cancel"); onClicked: { newPassword.text = ""; registration.close() } }
            }
        }
    }

    SurfaceDialog {
        id: editor
        objectName: "reportEditor"
        title: root.local("مشكلة أو فكرة جديدة", "New report or idea")
        modal: true
        anchors.centerIn: parent
        width: Math.min(640, root.width - 48)
        height: Math.min(680, root.height - 48)
        onAboutToShow: {
            const d = root.s.composer
            reportTitle.text = d.title || ""
            reportBody.text = d.body || ""
            kind.currentIndex = d.kind || 0
            makePublic.checked = d.public === true
        }
        contentItem: QQC2.ScrollView {
            id: editorScroll
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
            width: editorScroll.availableWidth; spacing: 12
            QQC2.ComboBox { id: kind; objectName: "reportKind"; Layout.fillWidth: true; implicitHeight: 44; model: [root.local("مشكلة أريد حلّها", "Report a problem"), root.local("فكرة لتطوير النظام", "Suggest an improvement")]; Accessible.name: root.local("نوع الطلب", "Request type"); onCurrentIndexChanged: root.persistReport() }
            QQC2.TextField { id: reportTitle; objectName: "reportTitle"; Layout.fillWidth: true; implicitHeight: 44; placeholderText: root.local("عنوان واضح", "A clear title"); maximumLength: 160; Accessible.name: placeholderText; onTextChanged: root.persistReport() }
            QQC2.ScrollView { Layout.fillWidth: true; Layout.preferredHeight: 150
                WriteArea { id: reportBody; objectName: "reportBody"; placeholderText: root.local("ماذا حدث؟ ماذا كنت تتوقع؟ أو كيف ستساعدنا فكرتك؟", "What happened, what did you expect, or how would your idea help?"); Accessible.name: root.local("وصف الطلب", "Request details"); onTextChanged: root.persistReport() }
            }
            QQC2.CheckBox { id: makePublic; objectName: "reportConsent"; visible: kind.currentIndex === 1; text: root.local("أنشر الفكرة الأولى كاقتراح عام باسمي المعروض", "Publish the original idea with my display name"); onVisibleChanged: if (!visible) checked = false; onCheckedChanged: root.persistReport() }
            QuietInk { visible: makePublic.checked; Layout.fillWidth: true; text: root.local("العنوان والوصف سيظهران للجميع. المحادثة والصورة تبقيان خاصتين.", "The title and description become public. The conversation and image stay private.") }
            RowLayout {
                MoUI.Button { label: root.local("أرفق صورة", "Attach a picture"); onClicked: { root.pictureTarget = "report"; picturePicker.open() } }
                MoUI.Button { visible: root.s.picture !== ""; label: root.local("أزل الصورة", "Remove picture"); onClicked: community.clearPicture("report") }
            }
            Image { visible: root.s.picture !== ""; source: root.s.picture; fillMode: Image.PreserveAspectFit; Layout.fillWidth: true; Layout.preferredHeight: visible ? 100 : 0 }
            QuietInk { visible: root.s.picture !== ""; Layout.fillWidth: true; text: root.local("راجع الصورة قبل الإرسال وتأكد أنها لا تحتوي معلومات خاصة.", "Review the picture before sending and check it contains no private information.") }
            }
        }
        footer: RowLayout {
                spacing: 12
                Item { Layout.fillWidth: true }
                MoUI.Button { objectName: "sendReport"; primary: true; label: root.local("أرسل", "Send"); enabled: reportTitle.text.trim().length >= 3 && reportBody.text.trim().length >= 5 && reportBody.text.length <= 8000 && !root.s.busy; onClicked: { editor.close(); community.createThread(reportTitle.text, reportBody.text, kind.currentIndex === 0 ? "problem" : "suggestion", makePublic.checked) } }
                MoUI.Button { label: root.local("إلغاء", "Cancel"); onClicked: editor.close() }
        }
    }

    FileDialog {
        id: picturePicker
        title: root.local("اختر صورة للمراجعة قبل الإرسال", "Choose a picture to review before sending")
        nameFilters: ["PNG (*.png)", "JPEG (*.jpg *.jpeg)", "WebP (*.webp)"]
        onAccepted: community.choosePicture(selectedFile.toString(), root.pictureTarget)
    }

    SurfaceDialog {
        id: conversation
        objectName: "conversation"
        title: root.s.selectedTitle || root.local("المحادثة الخاصة", "Private conversation")
        modal: true
        anchors.centerIn: parent
        width: Math.min(720, root.width - 32)
        height: Math.min(640, root.height - 48)
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Ink { objectName: "conversationState"; text: root.stateLabel(root.s.selectedState); font.bold: true; Layout.fillWidth: true }
            Ink { visible: root.s.status !== ""; text: root.s.status; Layout.fillWidth: true; color: root.s.error ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor }
            QuietInk { visible: root.s.release.version !== undefined; text: root.local("الإصدار المعتمد: ", "Verified release: ") + (root.s.release.version || "") + " · " + (root.s.release.edition || ""); Layout.fillWidth: true }
            QQC2.ScrollView {
                id: conversationScroll
                contentWidth: availableWidth
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                ColumnLayout {
                    width: conversationScroll.availableWidth; spacing: 12
                    Repeater {
                        model: root.s.messages
                        delegate: Panel {
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: messageColumn.implicitHeight + 24
                            ColumnLayout {
                                id: messageColumn
                                anchors.fill: parent; anchors.margins: 12; spacing: 8
                                QuietInk { text: modelData.display_name + " · " + (modelData.role === "maintainer" ? root.local("فريق التطوير", "Development team") : root.local("المستخدم", "Member")); Layout.fillWidth: true }
                                Ink { objectName: "messageBody"; text: modelData.body; Layout.fillWidth: true }
                            }
                        }
                    }
                    MoUI.Button { visible: root.s.hasMore; label: root.local("اعرض الرسائل التالية", "Load more messages"); enabled: !root.s.busy; onClicked: community.moreMessages() }
                    Repeater {
                        model: root.s.images
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            MoUI.Button { visible: !modelData.source; label: root.local("اعرض الصورة الخاصة", "View private picture"); enabled: !root.s.busy; onClicked: community.loadImage(modelData.id) }
                            Image { visible: !!modelData.source; source: modelData.source || ""; fillMode: Image.PreserveAspectFit; Layout.fillWidth: true; Layout.preferredHeight: visible ? 180 : 0 }
                        }
                    }
                }
            }
            RowLayout {
                visible: root.s.role === "maintainer"
                MoUI.Button { label: root.local("قيد الفحص", "Under review"); onClicked: community.markState("triage") }
                MoUI.Button { label: root.local("إصلاح قيد الاختبار", "Fix being tested"); onClicked: community.markState("testing") }
            }
            WriteArea { id: reply; objectName: "replyArea"; text: root.s.replyDraft; Layout.fillWidth: true; Layout.preferredHeight: 80; placeholderText: root.local("اكتب ردًا خاصًا…", "Write a private reply…"); Accessible.name: root.local("الرد الخاص", "Private reply"); onTextChanged: if (conversation.opened) community.saveReplyDraft(text) }
            Image { visible: root.s.replyPicture !== ""; source: root.s.replyPicture; fillMode: Image.PreserveAspectFit; Layout.fillWidth: true; Layout.preferredHeight: visible ? 90 : 0 }
            RowLayout {
                MoUI.Button { label: root.local("أرفق صورة", "Attach a picture"); onClicked: { root.pictureTarget = "reply"; picturePicker.open() } }
                MoUI.Button { visible: root.s.replyPicture !== ""; label: root.local("أزل الصورة", "Remove picture"); onClicked: community.clearPicture("reply") }
                Item { Layout.fillWidth: true }
                MoUI.Button { label: root.local("حذف المحادثة", "Delete conversation"); enabled: !root.s.busy; onClicked: deleteThread.open() }
            }
            RowLayout {
                MoUI.Button { primary: true; label: root.local("أرسل الرد", "Send reply"); enabled: reply.text.trim().length > 0 && reply.text.length <= 8000 && !root.s.busy; onClicked: community.sendMessage(reply.text) }
                MoUI.Button { label: root.local("إغلاق", "Close"); onClicked: conversation.close() }
            }
        }
    }
    SurfaceDialog {
        id: deleteThread
        title: root.local("حذف المحادثة؟", "Delete conversation?")
        modal: true; anchors.centerIn: parent; width: Math.min(460, root.width - 48)
        ColumnLayout {
            width: parent.width
            Ink { text: root.local("سيُحذف هذا البلاغ وردوده وصوره من الخدمة نهائيًا.", "This report, its replies and pictures will be permanently deleted from the service."); Layout.fillWidth: true }
            RowLayout {
                MoUI.Button { label: root.local("إلغاء", "Cancel"); onClicked: deleteThread.close() }
                MoUI.Button { label: root.local("احذف", "Delete"); onClicked: { community.deleteConversation(); deleteThread.close(); conversation.close() } }
            }
        }
    }
    SurfaceDialog {
        id: discardDraft
        property string identity: ""
        title: root.local("حذف المسودة؟", "Discard draft?")
        modal: true; anchors.centerIn: parent; width: Math.min(460, root.width - 48)
        ColumnLayout {
            width: parent.width
            Ink { text: root.local("تُحذف نسخة الإرسال المحلية فقط. قد تكون الخدمة قد استلمتها إذا انقطع الرد.", "Only the local retry draft is discarded. The service may already have received it if its reply was interrupted."); Layout.fillWidth: true }
            RowLayout {
                MoUI.Button { label: root.local("إلغاء", "Cancel"); onClicked: discardDraft.close() }
                MoUI.Button { label: root.local("احذف المسودة", "Discard"); onClicked: { community.discardDraft(discardDraft.identity); discardDraft.close() } }
            }
        }
    }
}

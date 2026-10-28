// SPDX-License-Identifier: GPL-2.0-or-later
// Push the native catalogue into the KCM's existing page stack. This keeps
// navigation, modality and lifetime with System Settings, including its
// QWidget/QtQuick host; there is no second top-level window or web store.
import QtQuick
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami
import org.kde.newstuff as NewStuff
import org.moos.ui as MoUI

KCM.AbstractKCM {
    id: root
    required property string libraryConfig
    property bool installedOnly: false
    property bool initialFilterApplied: false
    title: MoUI.Locale.rtl ? "مكتبة المظهر" : "Appearance library"
    framedView: false
    // KNewStuff's child pages use these two native host-context names.
    // Expose the embedded owner, not the outer QWidget's offscreen window.
    readonly property var pageStack: catalogue.pageStack
    function applicationWindow() { return catalogue }
    function revalidate() {
        if (onlinePage && onlinePage.engine) {
            if (!initialFilterApplied) {
                // These are the native Page's own All/Installed filters.
                onlinePage.engine.filter = installedOnly ? 1 : 0
                initialFilterApplied = true
            }
            onlinePage.engine.revalidateCacheEntries()
        }
    }
    Component.onCompleted: Qt.callLater(root.revalidate)
    onVisibleChanged: if (visible) Qt.callLater(root.revalidate)
    // Give the native pages their ApplicationItem and PageRow context for
    // previews, questions and notifications. No separate Window or window-
    // attached drawer is created inside System Settings' QWidget host.
    Kirigami.ApplicationItem {
        id: catalogue
        anchors.fill: parent
        pageStack.defaultColumnWidth: pageStack.width
        pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.Auto
        pageStack.initialPage: NewStuff.Page {
            id: onlinePage
            configFile: root.libraryConfig
            showUploadAction: false
            // Preserve the native warning level with clear local wording;
            // the upstream rich-text Arabic joins the OS name to its words.
            header: Kirigami.InlineMessage {
                readonly property bool riskyContent: onlinePage.engine.contentWarningType === NewStuff.Engine.Executables
                visible: onlinePage.engine.busyState !== NewStuff.Engine.Initializing
                type: riskyContent ? Kirigami.MessageType.Warning : Kirigami.MessageType.Information
                position: Kirigami.InlineMessage.Position.Header
                text: riskyContent
                    ? (MoUI.Locale.rtl ? "قد تحتوي إضافات المستخدمين على شيفرة قابلة للتنفيذ. لم تفحصها MoOS من ناحية الأمان أو الاستقرار أو الجودة."
                                       : "Community additions may contain executable code. MoOS has not reviewed their safety, stability or quality.")
                    : (MoUI.Locale.rtl ? "هذا محتوى يقدّمه المستخدمون. لم تفحصه MoOS من حيث العمل أو الجودة."
                                       : "This content is provided by the community. MoOS has not reviewed its functionality or quality.")
            }
        }
    }
    Connections {
        target: onlinePage.engine
        function onEntryEvent(entry, event) {
            if (event === NewStuff.Entry.StatusChangedEvent || event === NewStuff.Entry.AdoptedEvent)
                kcm.refresh()
        }
    }
    Connections {
        target: catalogue.pageStack
        function onCurrentIndexChanged() {
            if (catalogue.pageStack.currentIndex === 0)
                Qt.callLater(root.revalidate)
        }
    }
}

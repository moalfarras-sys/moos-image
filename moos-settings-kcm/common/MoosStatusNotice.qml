// SPDX-License-Identifier: GPL-2.0-or-later
// The honest line above every MoOS page: reading, or why nothing measured is shown.
// The backend rejects a partial, foreign or stale status document whole, so a page
// either shows measured facts or this notice, never defaults dressed as facts.
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Kirigami.InlineMessage {
    id: notice

    // The module (the `kcm` object of the page).
    property var backend: null
    readonly property bool reading: !!backend && backend.loading && !backend.statusValid
    readonly property bool failed: !!backend && !backend.loading && !backend.statusValid

    function reason(code) {
        switch (code) {
        case "stale":
            return MoUI.Locale.local("آخر حالة محفوظة للجهاز قديمة جداً لعرضها.",
                                     "The last saved device status is too old to show.")
        case "helper":
            return MoUI.Locale.local("لم يتمكن MoOS من قراءة حالة الجهاز.",
                                     "MoOS could not read the device status.")
        case "no-runtime":
            return MoUI.Locale.local("لا تملك هذه الجلسة مجلداً خاصاً لحالة الجهاز.",
                                     "This session has no private folder for the device status.")
        case "invalid":
            return MoUI.Locale.local("وصلت حالة الجهاز ناقصة، فلم تُعرض.",
                                     "The device status arrived incomplete, so it is not shown.")
        }
        return MoUI.Locale.local("حالة الجهاز غير متاحة بعد.", "The device status is not available yet.")
    }

    Layout.fillWidth: true
    visible: reading || failed
    type: failed ? Kirigami.MessageType.Warning : Kirigami.MessageType.Information
    text: reading ? MoUI.Locale.local("جارٍ قراءة حالة الجهاز…", "Reading device status…")
                  : reason(backend ? backend.statusError : "")
    actions: [
        Kirigami.Action {
            text: MoUI.Locale.local("أعد المحاولة", "Try again")
            icon.name: "view-refresh"
            visible: notice.failed
            onTriggered: notice.backend.refresh()
        }
    ]
}

// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

MoUI.Surface {
    id: card
    required property var backend
    readonly property var wallet: backend.status.wallet || ({})
    readonly property bool known: backend.statusValid && wallet.known === true
    property bool busy: false
    property string errorText: ""
    implicitHeight: body.implicitHeight + MoUI.Tokens.space3 * 2
    function t(ar, en) { return MoUI.Locale.local(ar, en) }
    function request(wanted) {
        if (busy || (wanted && (!known || wallet.available !== true))
                || (!wanted && !known && wallet.available !== true)) return
        busy = true
        errorText = ""
        if (!backend.runFixed(wanted ? "wallet-on" : "wallet-off", "")) {
            busy = false
            errorText = t("تعذّر تغيير المحفظة. حاول مجددًا.", "Could not change the wallet. Try again.")
        }
    }
    Connections {
        target: card.backend
        function onJobFinished(id, exitCode, output) {
            if (id !== "wallet-on" && id !== "wallet-off") return
            card.busy = false
            card.errorText = exitCode === 0 ? "" : card.t(
                "تعذّر تأكيد تغيير المحفظة. راجع حالتها وحاول مجددًا.",
                "The wallet change could not be confirmed. Check its state and try again.")
            card.backend.refresh()
        }
    }
    ColumnLayout {
        id: body
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: MoUI.Tokens.space3 }
        spacing: MoUI.Tokens.space2
        MoosSwitchRow {
            id: walletRow
            Layout.fillWidth: true
            font.pixelSize: MoUI.Tokens.typeBody
            background: MoUI.Surface {
                interactive: true
                hovered: walletRow.hovered
                pressed: walletRow.pressed
                selected: walletRow.activeFocus
            }
            objectName: "moosWalletSwitch"
            text: card.t("محفظة كلمات المرور", "Password wallet")
            glyph: "lock"
            on: card.known && card.wallet.enabled === true
            enabled: card.known && !card.busy && (card.wallet.available === true || card.wallet.active === true)
            description: card.busy ? card.t("جارٍ تغيير المحفظة…", "Changing wallet…")
                : !card.known ? card.t("تعذّر قراءة حالة المحفظة", "Wallet state is unavailable")
                : card.wallet.enabled === true && card.wallet.ready !== true
                    ? card.t("مفعّلة، لكن خدماتها غير جاهزة. أوقفها ثم فعّلها للمحاولة مجددًا.",
                             "Enabled, but its services are not ready. Switch off and on to retry.")
                : card.wallet.enabled !== true && card.wallet.active === true
                    ? card.t("التفضيل متوقف، لكن خدمة المحفظة ما زالت تعمل. اضغط إيقاف المحفظة.",
                             "The preference is off, but a wallet service is still running. Choose Turn wallet off.")
                : card.wallet.enabled === true
                    ? card.t("مفعّلة. قد تطلب التطبيقات كلمة مرور المحفظة لحفظ بيانات الدخول.",
                             "On. Apps may ask for the wallet password to save sign-in details.")
                    : card.t("متوقفة. لن تبدأ مطالبات المحفظة، وتبقى محتوياتها المحفوظة كما هي.",
                             "Off. Wallet prompts are stopped and saved contents are kept.")
            onRequested: function(wanted) { card.request(wanted) }
        }
        Controls.Button {
            visible: (!card.known && card.wallet.available === true)
                || (card.wallet.active === true && card.wallet.enabled !== true)
            enabled: !card.busy
            text: card.t("إيقاف المحفظة", "Turn wallet off")
            onClicked: card.request(false)
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: card.errorText.length > 0
            type: Kirigami.MessageType.Error
            text: card.errorText
        }
    }
}

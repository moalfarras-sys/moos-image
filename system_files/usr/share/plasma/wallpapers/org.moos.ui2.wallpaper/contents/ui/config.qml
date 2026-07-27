// The Desktop Settings page for the MoOS scene: right-click the desktop →
// "Configure Desktop and Wallpaper" → Wallpaper.
//
// WHY THIS FILE HAS TO EXIST
//   All five stock Plasma wallpaper plugins ship one; this package shipped none.
//   The scene has three things it can be told — which image, how much motion,
//   dashboard or no dashboard — and with no config.qml the settings dialog
//   offered the user NOTHING for any of them. The keys were reachable only from
//   `moos-theme` on the command line or by hand-editing appletsrc, and a
//   wallpaper whose own settings page is blank does not read as "configured
//   elsewhere", it reads as broken.
//
// THE CONTRACT
//   Plasma's wallpaper config host loads contents/ui/config.qml, binds every
//   `cfg_<Key>` property here to the config key of the same name in
//   contents/config/main.xml, and writes them back on Apply. The root must be a
//   Kirigami.FormLayout twinned with the host's own layout, or the labels do not
//   line up with the rest of the dialog. `parentLayout` is supplied by the host —
//   it is deliberately NOT declared here, exactly as org.kde.color does it;
//   declaring it would shadow the host's value with an empty local one.
//
// No pragma and no Kirigami.Theme colours: this page is a system-settings form
// and must look like every other one. The MoOS visual language belongs on the
// desktop, not inside KDE's own dialog chrome.
import QtQuick
// StandardPaths is a QtCore singleton, NOT something QtQuick.Dialogs brings in
// with FileDialog. Copying the folder-defaulting idiom out of
// org.kde.tiled/contents/ui/config.qml copies its missing import with it —
// that file resolves StandardPaths nowhere either, and the only symptom is one
// "ReferenceError: StandardPaths is not defined" in the journal and a file
// dialog that opens wherever it feels like. Verified against qml-qt6: without
// this line the binding below throws, with it the picker opens in Pictures.
import QtCore
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.FormLayout {
    id: root

    twinFormLayouts: parentLayout
    property alias formLayout: root

    property string cfg_Image
    property int cfg_MotionMode
    property bool cfg_AmbientMotion
    // An ALIAS, not a plain property, and that difference matters. A control that
    // owns exactly one value should BE that value: `checked: root.cfg_X` looks
    // equivalent and is a trap, because the first click makes QtQuick.Controls
    // assign `checked` imperatively, which DESTROYS the binding — after that the
    // box no longer follows the key, so the dialog's own "Defaults" button moves
    // the setting without moving the tick. An alias is two-way and cannot rot.
    // This is the same shape org.kde.color (cfg_Color) and org.kde.image
    // (cfg_Blur) use.
    property alias cfg_ShowDashboard: dashboardBox.checked

    // -1 is main.xml's "nobody has chosen a level on this desktop yet" sentinel,
    // and an unregistered key (a plasmashell still holding the pre-MotionMode
    // main.xml) reads back as neither 0, 1 nor 2 either. In both cases the honest
    // answer comes from the legacy Boolean, so the dialog opens on the level the
    // desktop is ACTUALLY running rather than on a default it is not.
    readonly property int effectiveMotionMode:
        (root.cfg_MotionMode === 0 || root.cfg_MotionMode === 1
         || root.cfg_MotionMode === 2)
            ? root.cfg_MotionMode
            : (root.cfg_AmbientMotion ? 1 : 0)

    // Write BOTH keys in one go, exactly as `moos-theme motion` does. The Boolean
    // is MotionMode's backward-compatible mirror (0 ↔ false, 1 and 2 ↔ true) and
    // is still what an older moos-theme, an older greeter and every installed
    // desktop's existing config understand. Letting the two disagree is how a
    // desktop ends up reporting "gentle" to the Theme Picker while behaving as
    // "still".
    function selectMotion(level) {
        root.cfg_MotionMode = level
        root.cfg_AmbientMotion = level > 0
    }

    QQC2.Button {
        Kirigami.FormData.label: "الخلفية  ·  Image:"
        text: "اختر صورة | Choose Image…"
        onClicked: imageDialog.open()
    }

    QQC2.Label {
        Layout.maximumWidth: Kirigami.Units.gridUnit * 22
        text: root.cfg_Image === ""
              ? "يتبع ثيم MoOS الحالي | Following the active MoOS theme"
              : root.cfg_Image
        elide: Text.ElideMiddle
        opacity: 0.7
    }

    QQC2.Button {
        // Empty is not "no wallpaper", it is the scene's documented "follow the
        // active palette" state — the one moos-theme restores when it hands the
        // desktop a theme. Without a way back to it, one trip through this dialog
        // would pin the desktop to a single file and silently break theme
        // switching for good.
        text: "عد إلى ثيم MoOS | Follow the MoOS theme"
        enabled: root.cfg_Image !== ""
        onClicked: root.cfg_Image = ""
    }

    Item { Kirigami.FormData.isSection: true }

    // A ComboBox and not three RadioButtons, for a reason that is not cosmetic.
    // RadioButtons here would each need `checked: <expression>`, and the first
    // click assigns `checked` imperatively and destroys that binding — from then
    // on the button no longer tracks the key, and because MotionMode is derived
    // from TWO keys the group can end up showing two ticks or none. One control
    // owning one index has no such state to desynchronise.
    //
    // currentIndex is still assigned imperatively rather than bound, which is the
    // idiom org.kde.image uses for exactly this reason, with an explicit re-sync
    // so an outside change (the dialog's "Defaults" button, or moos-theme writing
    // while the dialog is open) still moves the control.
    QQC2.ComboBox {
        id: motionBox
        Kirigami.FormData.label: "الحركة  ·  Motion:"
        // The same three words the MoOS Theme Picker uses, in the same order, so
        // the two places a user can change this cannot disagree.
        model: ["ساكن | Still", "هادئ | Gentle", "حيّ | Alive"]
        onActivated: root.selectMotion(motionBox.currentIndex)
        Component.onCompleted: motionBox.currentIndex = root.effectiveMotionMode
    }

    Connections {
        target: root
        function onEffectiveMotionModeChanged() {
            motionBox.currentIndex = root.effectiveMotionMode
        }
    }

    QQC2.Label {
        Layout.maximumWidth: Kirigami.Units.gridUnit * 22
        text: "ساكن يوقف كل حركة متكررة. هادئ هو الوضع الافتراضي الهادئ. حيّ يضيف لمعان البطاقات ونبض المؤشرات.\n"
              + "Still stops every looping animation. Gentle is the calm default. "
              + "Alive adds the card sheen and the system beacon's pulse."
        wrapMode: Text.WordWrap
        opacity: 0.7
    }

    Item { Kirigami.FormData.isSection: true }

    QQC2.CheckBox {
        id: dashboardBox
        Kirigami.FormData.label: "اللوحة  ·  Dashboard:"
        text: "اعرض لوحة MoOS | Show the MoOS dashboard"
        // No `checked:` binding and no onToggled — cfg_ShowDashboard is an alias
        // onto this very property, so the host reads and writes it directly.
    }

    QQC2.Label {
        Layout.maximumWidth: Kirigami.Units.gridUnit * 22
        // This is the measured number from the cloud edition's tuning, and it is
        // the whole reason the switch is offered rather than hidden: on a machine
        // with no GPU the bento is genuinely expensive, and a user on such a
        // machine deserves to know what turning it off buys them.
        text: "الساعة والطقس وحالة الجهاز أسفل يسار سطح المكتب.\n"
              + "The clock, weather and device health, below your desktop icons. "
              + "On a machine with no GPU this is the most expensive thing the "
              + "desktop draws."
        wrapMode: Text.WordWrap
        opacity: 0.7
    }

    FileDialog {
        id: imageDialog
        title: "اختر صورة الخلفية | Choose a wallpaper image"
        currentFolder: {
            // Wallpapers first, home as the fallback — the same order
            // org.kde.tiled uses, so the picker opens where a user expects.
            let paths = StandardPaths.standardLocations(StandardPaths.PicturesLocation)
            if (!paths.length) {
                paths = StandardPaths.standardLocations(StandardPaths.HomeLocation)
            }
            return paths[0]
        }
        fileMode: FileDialog.OpenFile
        options: FileDialog.ReadOnly
        nameFilters: ["Images (*.jpg *.jpeg *.png *.webp *.avif)"]
        // The scene's resolveImage() strips a file:// prefix itself and matches
        // on the extension, so the dialog's URL can be handed over as-is.
        onAccepted: root.cfg_Image = selectedFile
    }
}

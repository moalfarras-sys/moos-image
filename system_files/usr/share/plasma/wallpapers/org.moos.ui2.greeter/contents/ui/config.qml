// KDE's WallpaperConfig binds cfg_* to the real greeter configuration and
// commits it through its existing KAuth helper. Opening this page writes nothing.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Kirigami.FormLayout {
    id: root
    twinFormLayouts: parentLayout
    property alias formLayout: root
    property var configDialog
    property string cfg_Image
    property string cfg_ImageDefault
    property bool cfg_AmbientMotionDefault
    property alias cfg_AmbientMotion: motion.checked
    readonly property bool rtl: Qt.locale().name.toLowerCase().indexOf("ar") === 0
    readonly property var looks: Object.keys(MoUI.SessionAppearance.wallpapers)
    readonly property string desktopLook: MoUI.SessionAppearance.configuredLook()
    readonly property var familyNames: ({
        "ui2": ["غرافيت", "Graphite"], "nova": ["نوفا", "Nova"],
        "amethyst": ["أميثيست", "Amethyst"], "bloom": ["بلوم", "Bloom"],
        "midnight": ["منتصف الليل", "Midnight"], "aurora": ["أورورا", "Aurora"],
        "gaming": ["أرينا", "Arena"], "dev": ["فورج", "Forge"],
        "study": ["سكولار", "Scholar"]
    })

    function tr(ar, en) { return rtl ? ar : en; }
    function imageForLook(look) {
        // Greeter assets must be globally installed. A scoped development
        // XDG_DATA_DIRS must never persist a private checkout path for login.
        const relative = MoUI.SessionAppearance.wallpapers[look];
        return relative ? "/usr/share/" + relative : "";
    }
    function labelForLook(look) {
        const parts = look.split(".");
        const family = parts.length < 4 || parts[3] === "light" ? "ui2" : parts[3];
        const names = familyNames[family];
        return "MoOS " + (names ? names[rtl ? 0 : 1] : family)
            + (look.endsWith(".light") ? tr(" — فاتح", " — Light") : tr(" — داكن", " — Dark"));
    }
    function selectedIndex() {
        const value = String(cfg_Image || "").replace(/^file:\/\//, "").replace(/\/+$/, "");
        if (value === "") { return looks.indexOf("org.moos.ui2"); }
        return looks.findIndex(look => {
            const image = imageForLook(look);
            return value === image || value === image.split("/contents/")[0];
        });
    }
    function syncSelection() { lookPicker.currentIndex = selectedIndex(); }
    onCfg_ImageChanged: syncSelection()
    Component.onCompleted: {
        syncSelection();
        console.info("MOOS_LOGIN_APPEARANCE_READY", Qt.resolvedUrl("config.qml"), looks.length);
    }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 32
        spacing: Kirigami.Units.smallSpacing
        Kirigami.FormData.label: root.tr("الخلفية الافتراضية:", "Default background:")

        QQC2.ComboBox {
            id: lookPicker
            objectName: "moosLoginLookPicker"
            Layout.fillWidth: true
            model: root.looks.map(look => root.labelForLook(look))
            displayText: currentIndex >= 0 ? currentText : root.tr("صورة مخصّصة", "Custom image")
            Accessible.name: root.tr("مظهر شاشة الدخول", "Login screen appearance")
            onActivated: root.cfg_Image = root.imageForLook(root.looks[currentIndex])
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.round(width * 9 / 16)
            color: Kirigami.Theme.backgroundColor
            radius: Kirigami.Units.smallSpacing
            border.color: Kirigami.Theme.disabledTextColor
            clip: true
            Image {
                anchors.fill: parent
                anchors.margins: 1
                source: MoUI.SessionAppearance.imageUrl(root.selectedIndex() >= 0
                    ? root.imageForLook(root.looks[root.selectedIndex()]) : root.cfg_Image)
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 960
                Accessible.role: Accessible.Graphic
                Accessible.name: root.tr("معاينة مشهد الدخول", "Login scene preview")
            }
        }
        QQC2.Button {
            objectName: "moosLoginUseDesktopLook"
            text: root.tr("استخدم خلفية الثيم الحالي", "Use current theme wallpaper")
            icon.name: "preferences-desktop-theme-global"
            enabled: root.imageForLook(root.desktopLook) !== ""
            onClicked: root.cfg_Image = root.imageForLook(root.desktopLook)
        }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: root.tr("تظهر هذه الخلفية قبل اختيار الحساب. بعد اختياره، تتبع شاشة الدخول ثيمه وخلفيته تلقائيًا. لا تُحفظ الخلفية الافتراضية حتى تضغط «طبّق».",
                          "This background appears before account selection. After selection, login automatically follows that account’s theme and wallpaper. The default background is saved when you press Apply.")
            color: Kirigami.Theme.textColor
        }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: root.tr("يمكنك ضبط الألوان والخط والمؤشر الافتراضيين للجهاز عبر مزامنة الإعدادات في صفحة شاشة الدخول.",
                          "Settings sync on the login screen page sets the device’s default colors, font and cursor.")
            color: Kirigami.Theme.textColor
        }
    }

    QQC2.CheckBox {
        id: motion
        text: root.tr("انتقال قصير عند ظهور الشعار", "Brief logo entrance")
    }
}

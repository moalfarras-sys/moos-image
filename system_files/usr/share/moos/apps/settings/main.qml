// MoOS Command Center — the first-party control surface for the whole system.
//
// This is intentionally not a skin around Plasma's settings grid.  It gives the
// user one MoOS overview, one search surface and one coherent command lane, then
// hands each detailed operation to a fixed, real KCM or first-party MoOS app.
// Pure QML never executes a command: every launch crosses moos-open's audited
// fixed-argv allowlist.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../ui" as MoOSUi
import "../ui/SymbolCatalog.js" as MoOSSymbols

QQC2.ApplicationWindow {
    id: win

    visible: true
    width: Math.min(1360, Screen.desktopAvailableWidth * 0.94)
    height: Math.min(860, Screen.desktopAvailableHeight * 0.94)
    minimumWidth: Math.min(1040, Screen.desktopAvailableWidth * 0.94)
    minimumHeight: Math.min(680, Screen.desktopAvailableHeight * 0.94)
    title: win.local("مركز قيادة MoOS", "MoOS Command Center")
    color: canvas

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.View

    readonly property bool rtl: Qt.application.layoutDirection === Qt.RightToLeft
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property real fontScale: Qt.application.font.pointSize > 0
                                      ? Qt.application.font.pointSize / 10 : 1
    function fs(size) { return Math.round(size * fontScale) }
    function typePx(size) { return design.typeSize(size, fontScale) }
    function local(ar, en) { return rtl ? ar : en }

    MoOSUi.Tokens { id: design }

    readonly property color canvas: Kirigami.Theme.backgroundColor
    readonly property color surface: Kirigami.Theme.alternateBackgroundColor
    readonly property color raised: Qt.tint(
        canvas,
        colorLuma(canvas) > 0.5 ? Qt.rgba(0, 0, 0, 0.055)
                                : Qt.rgba(1, 1, 1, 0.075)
    )
    readonly property color raisedStrong: Qt.tint(
        canvas,
        colorLuma(canvas) > 0.5 ? Qt.rgba(0, 0, 0, 0.10)
                                : Qt.rgba(1, 1, 1, 0.13)
    )
    readonly property color textColor: Kirigami.Theme.textColor
    // DisabledText is intentionally faint and measured too pale over the
    // light Tidal hero.  Secondary copy is still functional information, so
    // derive a 72% ink role from the active foreground instead of borrowing a
    // disabled-control role; this stays legible on every light/dark palette.
    readonly property color mutedColor: Qt.rgba(textColor.r, textColor.g, textColor.b, 0.72)
    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property color accentText: Kirigami.Theme.highlightedTextColor
    readonly property color linkColor: Kirigami.Theme.linkColor
    readonly property color positiveColor: Kirigami.Theme.positiveTextColor
    readonly property color warningColor: Kirigami.Theme.neutralTextColor
    readonly property color dangerColor: Kirigami.Theme.negativeTextColor
    readonly property color outline: Qt.rgba(textColor.r, textColor.g, textColor.b, 0.14)
    readonly property color faintOutline: Qt.rgba(textColor.r, textColor.g, textColor.b, 0.075)

    function colorLuma(value) {
        var c = Qt.color(value)
        return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
    }

    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true

    property string activeSection: "home"
    property string searchQuery: ""
    property bool statusLoaded: false
    property string statusError: ""
    property int statusSerial: 0
    property var status: ({
        schema: 1,
        product: "MoOS",
        hostname: "MoOS",
        kernel: "—",
        cpu: local("جهاز MoOS", "MoOS device"),
        generatedAt: 0,
        uptimeSeconds: 0,
        storage: { total: "—", free: "—", percent: 0 },
        memory: { total: "—", used: "—", percent: 0 },
        network: { connected: false, full: false, label: "" },
        bluetooth: { available: false, powered: false },
        audio: { available: false, volume: 0, muted: false },
        battery: { available: false, percent: 0, state: "" },
        deployment: {
            version: "—", digest: "", signed: false,
            staged: false, stagedVersion: "", rollback: 0
        }
    })

    readonly property var sections: [
        {
            id: "home", glyph: "orbit",
            ar: "نظرة عامة", en: "Overview",
            descAr: "حالة جهازك ومفاتيح الوصول السريع",
            descEn: "Device state and essential commands",
            heroAr: "هذا جهازك، في لمحة.", heroEn: "Your device, in one glance.",
            heroDescAr: "الحالة الحية وما يحتاج انتباهك الآن",
            heroDescEn: "Live state and what needs your attention now"
        },
        {
            id: "appearance", glyph: "ui",
            ar: "المظهر", en: "Appearance",
            descAr: "الهوية، العرض، الخطوط والحركة",
            descEn: "Identity, display, type and motion",
            heroAr: "اجعل MoOS لك.", heroEn: "Make MoOS yours.",
            heroDescAr: "هوية Liquid Glass متكاملة من اللوحة إلى مساحة العمل",
            heroDescEn: "One Liquid Glass identity, from palette to workspace"
        },
        {
            id: "connectivity", glyph: "network",
            ar: "الاتصال", en: "Connectivity",
            descAr: "الشبكات والأجهزة القريبة",
            descEn: "Networks and nearby devices",
            heroAr: "كل شيء متصل، بوضوح.", heroEn: "Everything connected, clearly.",
            heroDescAr: "شبكاتك وأجهزتك القريبة في مسار واحد",
            heroDescEn: "Your networks and nearby devices in one lane"
        },
        {
            id: "devices", glyph: "keyboard",
            ar: "الأجهزة", en: "Devices",
            descAr: "الصوت، الإدخال والشاشات",
            descEn: "Audio, input and displays",
            heroAr: "شاشتك. صوتك. إيقاعك.", heroEn: "Your screen. Your sound. Your rhythm.",
            heroDescAr: "اضبط كل نقطة تماس بينك وبين الجهاز",
            heroDescEn: "Shape every point where you meet your device"
        },
        {
            id: "apps", glyph: "boxes",
            ar: "التطبيقات", en: "Apps",
            descAr: "المتجر، الأذونات والافتراضيات",
            descEn: "Store, permissions and defaults",
            heroAr: "تطبيقاتك، بشروطك.", heroEn: "Apps, on your terms.",
            heroDescAr: "اكتشف وثبّت وحدّد الوصول من مكان واحد",
            heroDescEn: "Discover, install and decide access in one place"
        },
        {
            id: "privacy", glyph: "shield",
            ar: "الخصوصية", en: "Privacy",
            descAr: "القفل والبيانات والوصول",
            descEn: "Lock, data and access",
            heroAr: "الوصول بقرارك.", heroEn: "Access, by your rules.",
            heroDescAr: "خصوصيتك مرئية، مفهومة، وتحت سيطرتك",
            heroDescEn: "Privacy that is visible, legible and under your control"
        },
        {
            id: "system", glyph: "system",
            ar: "النظام", en: "System",
            descAr: "التحديث، الحسابات ومعلومات الجهاز",
            descEn: "Updates, accounts and device facts",
            heroAr: "موثّق من الأساس.", heroEn: "Verified by design.",
            heroDescAr: "صورة ذرّية موقّعة ومعلومات جهاز يمكن الوثوق بها",
            heroDescEn: "A signed atomic image and device facts you can trust"
        },
        {
            id: "recovery", glyph: "repair",
            ar: "الاستعادة", en: "Recovery",
            descAr: "الرجوع الآمن وتشخيص الأداء",
            descEn: "Safe rollback and diagnostics",
            heroAr: "ارجع بثقة.", heroEn: "Return with confidence.",
            heroDescAr: "نسخة سليمة محفوظة حين تحتاجها، وملفاتك تبقى مكانها",
            heroDescEn: "A known-good image when you need it, with your files untouched"
        }
    ]

    // Every route below is a literal member of moos-open's fixed allowlist.
    // Titles and summaries carry both languages for search, but only the active
    // locale is ever rendered.
    readonly property var commands: [
        { section: "appearance", route: "moos://settings/themes", glyph: "diamond",
          ar: "هوية MoOS", en: "MoOS identity",
          descAr: "غيّر لوحة Liquid Glass والخلفية معاً",
          descEn: "Change the Liquid Glass palette and wallpaper together",
          tagAr: "موصى به", tagEn: "Curated" },
        { section: "appearance", route: "moos://settings/display", glyph: "monitor",
          ar: "الشاشات", en: "Displays",
          descAr: "الدقة، القياس، الاتجاه ومعدل التحديث",
          descEn: "Resolution, scale, orientation and refresh rate" },
        { section: "appearance", route: "moos://settings/night-light", glyph: "moon",
          ar: "الضوء الليلي", en: "Night light",
          descAr: "حرارة لون أهدأ حسب الوقت",
          descEn: "A calmer colour temperature on your schedule" },
        { section: "appearance", route: "moos://settings/fonts", glyph: "pen",
          ar: "الخطوط", en: "Typography",
          descAr: "حجم ووضوح النص في النظام كله",
          descEn: "Text size and legibility across the system" },
        { section: "appearance", route: "moos://settings/wallpaper", glyph: "spark",
          ar: "مساحة العمل", en: "Desktop canvas",
          descAr: "الخلفية وتكوين سطح المكتب",
          descEn: "Wallpaper and desktop composition" },
        { section: "appearance", route: "moos://settings/accessibility", glyph: "target",
          ar: "إمكانية الوصول", en: "Accessibility",
          descAr: "الرؤية، لوحة المفاتيح ومساعدة التفاعل",
          descEn: "Vision, keyboard and interaction assistance" },

        { section: "connectivity", route: "moos://settings/network", glyph: "network",
          ar: "الشبكة والواي فاي", en: "Network & Wi-Fi",
          descAr: "الاتصالات النشطة والشبكات المحفوظة",
          descEn: "Active connections and remembered networks" },
        { section: "connectivity", route: "moos://settings/bluetooth", glyph: "bluetooth",
          ar: "بلوتوث", en: "Bluetooth",
          descAr: "اقتران الأجهزة القريبة وإدارتها",
          descEn: "Pair and manage nearby devices" },
        { section: "connectivity", route: "moos://settings/hotspot", glyph: "wave",
          ar: "نقطة اتصال", en: "Mobile hotspot",
          descAr: "شارك اتصال هذا الجهاز عند الحاجة",
          descEn: "Share this device's connection when needed" },
        { section: "connectivity", route: "moos://settings/accounts", glyph: "identity",
          ar: "الحسابات المتصلة", en: "Connected accounts",
          descAr: "خدماتك وحساباتك على الإنترنت",
          descEn: "Your online services and accounts" },

        { section: "devices", route: "moos://settings/audio", glyph: "audio",
          ar: "الصوت", en: "Sound",
          descAr: "المخارج والمداخل ومستويات الصوت",
          descEn: "Outputs, inputs and volume levels" },
        { section: "devices", route: "moos://settings/keyboard", glyph: "keyboard",
          ar: "لوحة المفاتيح", en: "Keyboard",
          descAr: "التخطيطات، التكرار والاختصارات",
          descEn: "Layouts, repeat and keyboard behaviour" },
        { section: "devices", route: "moos://settings/mouse", glyph: "mouse",
          ar: "الفأرة", en: "Mouse",
          descAr: "المؤشر، السرعة والتمرير",
          descEn: "Pointer, speed and scrolling" },
        { section: "devices", route: "moos://settings/touchpad", glyph: "target",
          ar: "لوحة اللمس", en: "Touchpad",
          descAr: "الإيماءات والنقر والتمرير",
          descEn: "Gestures, tapping and scrolling" },
        { section: "devices", route: "moos://settings/printers", glyph: "document",
          ar: "الطابعات", en: "Printers",
          descAr: "إضافة الطابعات وقوائم الانتظار",
          descEn: "Add printers and manage queues" },
        { section: "devices", route: "moos://settings/usb", glyph: "usb",
          ar: "أجهزة USB", en: "USB devices",
          descAr: "معلومات الأجهزة المتصلة",
          descEn: "Inspect connected hardware" },

        { section: "apps", route: "moos://settings/store", glyph: "boxes",
          ar: "Mo Store", en: "Mo Store",
          descAr: "اكتشف تطبيقات موثوقة وثبّتها",
          descEn: "Discover and install trusted applications",
          tagAr: "MoOS", tagEn: "MoOS" },
        { section: "apps", route: "moos://settings/permissions", glyph: "lock",
          ar: "أذونات التطبيقات", en: "App permissions",
          descAr: "تحكّم بما تستطيع التطبيقات الوصول إليه",
          descEn: "Control what installed applications can access" },
        { section: "apps", route: "moos://settings/default-apps", glyph: "star",
          ar: "التطبيقات الافتراضية", en: "Default apps",
          descAr: "اختر التطبيق لكل نوع من المهام",
          descEn: "Choose the app for each kind of task" },
        { section: "apps", route: "moos://settings/autostart", glyph: "bolt",
          ar: "بدء التشغيل", en: "Autostart",
          descAr: "ما يبدأ تلقائياً مع جلستك",
          descEn: "What starts automatically with your session" },
        { section: "apps", route: "moos://settings/notifications", glyph: "chat",
          ar: "الإشعارات", en: "Notifications",
          descAr: "الأصوات والأولوية ووضع عدم الإزعاج",
          descEn: "Sounds, priority and do-not-disturb behaviour" },

        { section: "privacy", route: "moos://settings/lock", glyph: "lock",
          ar: "القفل والحماية", en: "Lock & protection",
          descAr: "وقت القفل وسلوك شاشة الحماية",
          descEn: "Lock timing and protection-screen behaviour" },
        { section: "privacy", route: "moos://settings/permissions", glyph: "shield",
          ar: "وصول التطبيقات", en: "Application access",
          descAr: "راجع الحساسات والملفات التي تصل إليها التطبيقات",
          descEn: "Review sensors and files available to apps" },
        { section: "privacy", route: "moos://settings/file-search", glyph: "search",
          ar: "بحث الملفات", en: "File search",
          descAr: "حدّد ما يدخل في فهرس البحث المحلي",
          descEn: "Choose what enters the local search index" },
        { section: "privacy", route: "moos://settings/telemetry", glyph: "report",
          ar: "مشاركة البيانات", en: "Data sharing",
          descAr: "راجع خيارات الملاحظات والقياس",
          descEn: "Review feedback and measurement preferences" },

        { section: "system", route: "moos://settings/update", glyph: "safe-update",
          ar: "تحديث MoOS", en: "Update MoOS",
          descAr: "تحديث ذرّي موقّع مع رجوع محفوظ",
          descEn: "Signed atomic update with a preserved rollback",
          tagAr: "آمن", tagEn: "Atomic" },
        { section: "system", route: "moos://settings/about", glyph: "identity",
          ar: "حول هذا الجهاز", en: "About this device",
          descAr: "إصدار النظام والعتاد ومعلومات الدعم",
          descEn: "System version, hardware and support details" },
        { section: "system", route: "moos://settings/users", glyph: "identity",
          ar: "المستخدمون", en: "Users",
          descAr: "الحسابات المحلية وصور المستخدمين",
          descEn: "Local accounts and profile pictures" },
        { section: "system", route: "moos://settings/time", glyph: "orbit",
          ar: "الوقت والمنطقة", en: "Time & region",
          descAr: "المنطقة الزمنية والساعة والتنسيقات",
          descEn: "Time zone, clock and regional formats" },
        { section: "system", route: "moos://settings/storage", glyph: "storage",
          ar: "التخزين", en: "Storage",
          descAr: "الأقراص والأقسام والمساحة المتاحة",
          descEn: "Disks, partitions and available space" },
        { section: "system", route: "moos://settings/energy", glyph: "bolt",
          ar: "الطاقة", en: "Energy",
          descAr: "الأداء، السكون واستهلاك الطاقة",
          descEn: "Performance, sleep and energy use" },

        { section: "recovery", route: "moos://settings/recovery", glyph: "repair",
          ar: "استعادة MoOS", en: "MoOS Recovery",
          descAr: "ارجع إلى نسخة سليمة من دون لمس ملفاتك",
          descEn: "Return to a known-good system without touching your files",
          tagAr: "محمي", tagEn: "Protected" },
        { section: "recovery", route: "moos://settings/firmware-security", glyph: "shield",
          ar: "أمان العتاد", en: "Firmware security",
          descAr: "حالة الإقلاع والبرامج الثابتة",
          descEn: "Boot and firmware security posture" },
        { section: "recovery", route: "moos://settings/system-monitor", glyph: "wave",
          ar: "مراقبة النظام", en: "System monitor",
          descAr: "الأداء والعمليات والموارد لحظة بلحظة",
          descEn: "Live performance, processes and resources" },
        { section: "recovery", route: "moos://settings/update", glyph: "refresh",
          ar: "صورة النظام التالية", en: "Next system image",
          descAr: "تحقق من التحديث الموقّع وجهّزه بأمان",
          descEn: "Check and safely stage the next signed image" }
    ]

    readonly property var activeSectionData: {
        for (var i = 0; i < sections.length; ++i)
            if (sections[i].id === activeSection)
                return sections[i]
        return sections[0]
    }

    readonly property var visibleCommands: {
        var result = []
        var needle = searchQuery.trim().toLocaleLowerCase()
        for (var i = 0; i < commands.length; ++i) {
            var item = commands[i]
            var haystack = [
                item.ar, item.en, item.descAr, item.descEn, item.section
            ].join(" ").toLocaleLowerCase()
            if (needle !== "" ? haystack.indexOf(needle) >= 0
                              : item.section === activeSection)
                result.push(item)
        }
        return result
    }

    readonly property string statusUrl: argValue("--status=")

    function argValue(prefix) {
        var args = Qt.application.arguments
        for (var i = 0; i < args.length; ++i)
            if (args[i].indexOf(prefix) === 0)
                return args[i].substring(prefix.length)
        return ""
    }

    function openRoute(route) {
        if (String(route).indexOf("moos://settings/") !== 0)
            return
        Qt.openUrlExternally(route)
    }

    function selectSection(sectionId) {
        searchQuery = ""
        activeSection = sectionId
        contentFlick.contentY = 0
    }

    function uptimeLabel(seconds) {
        var value = Math.max(0, Number(seconds) || 0)
        var days = Math.floor(value / 86400)
        var hours = Math.floor((value % 86400) / 3600)
        if (days > 0)
            return rtl ? days + " ي " + hours + " س" : days + "d " + hours + "h"
        var minutes = Math.max(1, Math.floor(value / 60))
        return rtl ? hours + " س " + (minutes % 60) + " د"
                   : hours + "h " + (minutes % 60) + "m"
    }

    function loadStatus() {
        if (!statusUrl)
            return
        var request = new XMLHttpRequest()
        request.open("GET", statusUrl)
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE)
                return
            if (request.status === 0 || (request.status >= 200 && request.status < 300)) {
                try {
                    var parsed = JSON.parse(request.responseText)
                    if (parsed.schema === 1 && parsed.product === "MoOS") {
                        win.status = parsed
                        win.statusLoaded = true
                        win.statusError = ""
                        win.statusSerial++
                    }
                } catch (error) {
                    win.statusError = String(error)
                }
            }
        }
        request.send()
    }

    Component.onCompleted: {
        var requestedSection = argValue("--section=")
        for (var i = 0; i < sections.length; ++i) {
            if (sections[i].id === requestedSection) {
                activeSection = requestedSection
                break
            }
        }
        loadStatus()
    }
    Timer {
        interval: 1800
        repeat: true
        running: win.visible
        onTriggered: win.loadStatus()
    }

    component FocusRing: MoOSUi.FocusRing {
        accentColor: win.accent
    }

    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: searchField.forceActiveFocus()
    }
    Shortcut {
        sequence: "Ctrl+R"
        onActivated: win.loadStatus()
    }
    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (win.searchQuery !== "") {
                win.searchQuery = ""
                searchField.text = ""
            } else if (win.activeSection !== "home") {
                win.selectSection("home")
            } else {
                win.close()
            }
        }
    }

    component StatusCapsule: Rectangle {
        id: capsule
        required property string glyph
        required property string label
        property string detail: ""
        property color statusColor: win.accent
        property bool active: true

        implicitHeight: win.fs(54)
        implicitWidth: capsuleRow.implicitWidth + design.space5 * 2
        radius: design.radiusCard
        color: Qt.rgba(win.textColor.r, win.textColor.g, win.textColor.b, 0.065)
        border.width: 1
        border.color: Qt.rgba(statusColor.r, statusColor.g, statusColor.b, active ? 0.34 : 0.14)

        RowLayout {
            id: capsuleRow
            anchors.fill: parent
            anchors.leftMargin: design.space4
            anchors.rightMargin: design.space4
            spacing: design.space3

            Rectangle {
                Layout.preferredWidth: win.fs(30)
                Layout.preferredHeight: win.fs(30)
                radius: 10
                color: Qt.rgba(capsule.statusColor.r, capsule.statusColor.g,
                               capsule.statusColor.b, capsule.active ? 0.18 : 0.08)

                MoOSUi.SymbolIcon {
                    anchors.centerIn: parent
                    width: 17
                    height: 17
                    symbol: MoOSSymbols.resolve(capsule.glyph)
                    foreground: capsule.active ? capsule.statusColor : win.mutedColor
                }
            }

            ColumnLayout {
                spacing: 1

                Text {
                    text: capsule.label
                    color: win.textColor
                    font.pixelSize: win.typePx(design.typeSecondary)
                    font.weight: Font.DemiBold
                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                    Layout.maximumWidth: 180
                    elide: Text.ElideRight
                }
                Text {
                    visible: capsule.detail !== ""
                    text: capsule.detail
                    color: win.mutedColor
                    font.pixelSize: win.typePx(design.typeCaption)
                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                    Layout.maximumWidth: 180
                    elide: Text.ElideRight
                }
            }
        }
    }

    component NavButton: QQC2.AbstractButton {
        id: navControl
        required property var sectionData
        readonly property bool selected: win.activeSection === sectionData.id
                                         && win.searchQuery === ""

        Layout.fillWidth: true
        implicitHeight: win.fs(48)
        hoverEnabled: true
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: win.local(sectionData.ar, sectionData.en)
        onClicked: win.selectSection(sectionData.id)

        background: Rectangle {
            radius: design.radiusControl
            color: navControl.selected
                   ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                   : navControl.hovered
                     ? Qt.rgba(win.textColor.r, win.textColor.g, win.textColor.b, 0.065)
                     : "transparent"
            border.width: navControl.selected ? 1 : 0
            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.35)

            Behavior on color {
                ColorAnimation {
                    duration: win.motionEnabled ? design.motionFast : 0
                }
            }
        }

        contentItem: RowLayout {
            spacing: design.space3

            Rectangle {
                Layout.preferredWidth: win.fs(34)
                Layout.preferredHeight: win.fs(34)
                radius: 11
                color: navControl.selected
                       ? win.accent
                       : Qt.rgba(win.textColor.r, win.textColor.g, win.textColor.b, 0.06)

                MoOSUi.SymbolIcon {
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    symbol: MoOSSymbols.resolve(navControl.sectionData.glyph)
                    foreground: navControl.selected ? win.accentText : win.textColor
                }
            }

            Text {
                Layout.fillWidth: true
                text: win.local(navControl.sectionData.ar, navControl.sectionData.en)
                color: win.textColor
                font.pixelSize: win.typePx(design.typeBody)
                font.weight: navControl.selected ? Font.DemiBold : Font.Medium
                horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                elide: Text.ElideRight
            }

            Rectangle {
                visible: navControl.selected
                Layout.preferredWidth: win.fs(5)
                Layout.preferredHeight: win.fs(18)
                radius: 3
                color: win.accent
            }
        }

        FocusRing {
            anchors.fill: navControl
            accentColor: win.accent
            controlRadius: design.radiusControl
        }
    }

    component MetricTile: Rectangle {
        id: metric
        required property string glyph
        required property string label
        required property string value
        property real progress: -1
        property color tone: win.accent

        implicitHeight: win.fs(112)
        radius: design.radiusCard
        color: win.surface
        border.width: 1
        border.color: win.faintOutline

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: design.space4
            spacing: design.space2

            RowLayout {
                Layout.fillWidth: true
                spacing: design.space2

                MoOSUi.SymbolIcon {
                    Layout.preferredWidth: win.fs(18)
                    Layout.preferredHeight: win.fs(18)
                    symbol: MoOSSymbols.resolve(metric.glyph)
                    foreground: metric.tone
                }
                Text {
                    Layout.fillWidth: true
                    text: metric.label
                    color: win.mutedColor
                    font.pixelSize: win.typePx(design.typeCaption)
                    font.weight: Font.DemiBold
                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                    elide: Text.ElideRight
                }
            }

            Text {
                Layout.fillWidth: true
                text: metric.value
                color: win.textColor
                font.pixelSize: win.typePx(design.typeTitle)
                font.weight: Font.DemiBold
                horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                elide: Text.ElideRight
            }

            Rectangle {
                visible: metric.progress >= 0
                Layout.fillWidth: true
                Layout.preferredHeight: win.fs(4)
                radius: 2
                color: Qt.rgba(win.textColor.r, win.textColor.g, win.textColor.b, 0.08)

                Rectangle {
                    width: parent.width * Math.max(0, Math.min(1, metric.progress))
                    height: parent.height
                    radius: parent.radius
                    color: metric.tone

                    Behavior on width {
                        NumberAnimation {
                            duration: win.motionEnabled ? design.motionGeometry : 0
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            }
        }
    }

    component CommandRow: QQC2.AbstractButton {
        id: commandControl
        required property var commandData

        Layout.fillWidth: true
        implicitHeight: win.fs(88)
        hoverEnabled: true
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: win.local(commandData.ar, commandData.en)
        Accessible.description: win.local(commandData.descAr, commandData.descEn)
        onClicked: win.openRoute(commandData.route)
        scale: down ? 0.992 : 1

        Behavior on scale {
            NumberAnimation {
                duration: win.motionEnabled ? design.motionFast : 0
                easing.type: Easing.OutCubic
            }
        }

        background: Rectangle {
            radius: design.radiusCard
            color: commandControl.hovered ? win.raisedStrong : win.surface
            border.width: 1
            border.color: commandControl.hovered
                          ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.36)
                          : win.faintOutline

            Rectangle {
                // One physical start edge is enough: LayoutMirroring moves this
                // edge to the right in RTL.  Anchoring both sides makes QML
                // ignore `width` and turns a 4 px hover cue into a full-row
                // accent slab over the command copy.
                anchors.left: parent.left
                anchors.leftMargin: -1
                anchors.verticalCenter: parent.verticalCenter
                width: commandControl.hovered ? 4 : 0
                height: 38
                radius: 2
                color: win.accent

                Behavior on width {
                    NumberAnimation {
                        duration: win.motionEnabled ? design.motionFast : 0
                    }
                }
            }

            Behavior on color {
                ColorAnimation {
                    duration: win.motionEnabled ? design.motionFast : 0
                }
            }
            Behavior on border.color {
                ColorAnimation {
                    duration: win.motionEnabled ? design.motionFast : 0
                }
            }
        }

        contentItem: RowLayout {
            spacing: design.space4

            Rectangle {
                Layout.preferredWidth: win.fs(52)
                Layout.preferredHeight: win.fs(52)
                radius: design.radiusControl
                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b,
                               commandControl.hovered ? 0.19 : 0.11)

                MoOSUi.SymbolIcon {
                    anchors.centerIn: parent
                    width: 24
                    height: 24
                    symbol: MoOSSymbols.resolve(commandControl.commandData.glyph)
                    foreground: win.accent
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: design.space2

                    Text {
                        Layout.fillWidth: true
                        text: win.local(commandControl.commandData.ar,
                                        commandControl.commandData.en)
                        color: win.textColor
                        font.pixelSize: win.typePx(design.typeLabel)
                        font.weight: Font.DemiBold
                        horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        visible: Boolean(commandControl.commandData.tagAr)
                        implicitWidth: commandTag.implicitWidth + design.space3
                        implicitHeight: win.fs(24)
                        radius: 12
                        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)

                        Text {
                            id: commandTag
                            anchors.centerIn: parent
                            text: win.local(commandControl.commandData.tagAr || "",
                                            commandControl.commandData.tagEn || "")
                            color: win.accent
                            font.pixelSize: win.typePx(design.typeCaption)
                            font.weight: Font.DemiBold
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: win.local(commandControl.commandData.descAr,
                                    commandControl.commandData.descEn)
                    color: win.mutedColor
                    font.pixelSize: win.typePx(design.typeSecondary)
                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                Layout.preferredWidth: win.fs(36)
                Layout.preferredHeight: win.fs(36)
                radius: 18
                color: commandControl.hovered
                       ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                       : "transparent"

                MoOSUi.SymbolIcon {
                    anchors.centerIn: parent
                    width: 17
                    height: 17
                    symbol: MoOSSymbols.resolve("arrow")
                    foreground: commandControl.hovered ? win.accent : win.mutedColor
                }
            }
        }

        FocusRing {
            anchors.fill: commandControl
            accentColor: win.accent
            controlRadius: design.radiusCard
        }
    }

    // Very low-alpha light fields make the canvas feel spatial without turning
    // an always-open settings window into a blur or shader workload.
    Rectangle {
        width: Math.min(win.width * 0.46, 660)
        height: width
        radius: width / 2
        x: win.rtl ? -width * 0.34 : win.width - width * 0.66
        y: -height * 0.48
        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.055)
        Accessible.ignored: true
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: design.space5
        spacing: design.space5

        Rectangle {
            Layout.preferredWidth: win.fs(252)
            Layout.fillHeight: true
            radius: design.radiusPanel
            color: win.surface
            border.width: 1
            border.color: win.faintOutline

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: design.space4
                spacing: design.space3

                RowLayout {
                    Layout.fillWidth: true
                    Layout.bottomMargin: design.space3
                    spacing: design.space3

                    Rectangle {
                        Layout.preferredWidth: win.fs(48)
                        Layout.preferredHeight: win.fs(48)
                        radius: design.radiusCard
                        color: win.accent

                        MoOSUi.SymbolIcon {
                            anchors.centerIn: parent
                            width: 26
                            height: 26
                            symbol: MoOSSymbols.resolve("orbit")
                            foreground: win.accentText
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Text {
                            text: "MoOS"
                            color: win.textColor
                            font.pixelSize: win.typePx(design.typeTitle)
                            font.weight: Font.Bold
                        }
                        Text {
                            text: win.local("مركز القيادة", "COMMAND CENTER")
                            color: win.accent
                            font.pixelSize: win.typePx(design.typeCaption)
                            font.weight: Font.DemiBold
                            font.letterSpacing: win.rtl ? 0 : 1.1
                        }
                    }
                }

                Repeater {
                    model: win.sections
                    delegate: NavButton {
                        required property var modelData
                        sectionData: modelData
                    }
                }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: win.fs(108)
                    radius: design.radiusCard
                    color: win.raised
                    border.width: 1
                    border.color: win.outline

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: design.space3
                        spacing: design.space2

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: design.space2
                            MoOSUi.SymbolIcon {
                                Layout.preferredWidth: win.fs(18)
                                Layout.preferredHeight: win.fs(18)
                                symbol: MoOSSymbols.resolve(
                                    win.status.deployment.signed ? "shield" : "warning"
                                )
                                foreground: win.status.deployment.signed
                                            ? win.positiveColor : win.warningColor
                            }
                            Text {
                                Layout.fillWidth: true
                                text: win.status.deployment.signed
                                      ? win.local("صورة نظام موثّقة", "Verified system image")
                                      : win.local("جارٍ التحقق", "Verification pending")
                                color: win.textColor
                                font.pixelSize: win.typePx(design.typeSecondary)
                                font.weight: Font.DemiBold
                                horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                                elide: Text.ElideRight
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: win.local(
                                "نسخ الرجوع المحفوظة: " + win.status.deployment.rollback,
                                "Safe rollbacks: " + win.status.deployment.rollback
                            )
                            color: win.mutedColor
                            font.pixelSize: win.typePx(design.typeCaption)
                            horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: win.fs(3)
                            radius: 2
                            color: Qt.rgba(win.textColor.r, win.textColor.g, win.textColor.b, 0.08)
                            Rectangle {
                                width: parent.width
                                height: parent.height
                                radius: parent.radius
                                color: win.status.deployment.signed
                                       ? win.positiveColor : win.warningColor
                                opacity: win.statusLoaded ? 1 : 0.25
                            }
                        }
                    }
                }

                MoOSUi.Button {
                    Layout.fillWidth: true
                    label: win.local("كل إعدادات النظام", "All system settings")
                    iconName: MoOSSymbols.resolve("external")
                    surfaceColor: win.raised
                    accentColor: win.accent
                    textColor: win.textColor
                    accentForegroundColor: win.accentText
                    fontPixelSize: win.typePx(design.typeSecondary)
                    onClicked: win.openRoute("moos://settings/full")
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: design.space4

            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: win.fs(52)
                spacing: design.space4

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    Text {
                        Layout.fillWidth: true
                        text: win.searchQuery !== ""
                              ? win.local("نتائج البحث", "Search results")
                              : win.local(win.activeSectionData.ar, win.activeSectionData.en)
                        color: win.textColor
                        font.pixelSize: win.typePx(design.typeHeadline)
                        font.weight: Font.DemiBold
                        horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: win.searchQuery !== ""
                              ? win.local(
                                    win.visibleCommands.length + " نتيجة ضمن مركز القيادة",
                                    win.visibleCommands.length + " commands across MoOS"
                                )
                              : win.local(win.activeSectionData.descAr,
                                          win.activeSectionData.descEn)
                        color: win.mutedColor
                        font.pixelSize: win.typePx(design.typeCaption)
                        horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                        elide: Text.ElideRight
                    }
                }

                QQC2.TextField {
                    id: searchField
                    Layout.preferredWidth: Math.min(340, win.width * 0.27)
                    Layout.preferredHeight: win.fs(44)
                    leftPadding: win.rtl ? design.space4 : 46
                    rightPadding: win.rtl ? 46 : design.space4
                    placeholderText: win.local("ابحث في النظام…", "Search the system…")
                    text: win.searchQuery
                    color: win.textColor
                    placeholderTextColor: win.mutedColor
                    selectionColor: win.accent
                    selectedTextColor: win.accentText
                    font.pixelSize: win.typePx(design.typeSecondary)
                    activeFocusOnTab: true
                    Accessible.name: placeholderText
                    onTextEdited: win.searchQuery = text

                    background: Rectangle {
                        radius: design.radiusControl
                        color: win.surface
                        border.width: searchField.activeFocus ? 2 : 1
                        border.color: searchField.activeFocus ? win.accent : win.outline
                    }

                    MoOSUi.SymbolIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: win.rtl ? undefined : parent.left
                        anchors.leftMargin: design.space4
                        anchors.right: win.rtl ? parent.right : undefined
                        anchors.rightMargin: design.space4
                        width: 18
                        height: 18
                        symbol: MoOSSymbols.resolve("search")
                        foreground: searchField.activeFocus ? win.accent : win.mutedColor
                    }

                    FocusRing {
                        anchors.fill: searchField
                        controlRadius: design.radiusControl
                    }
                }
            }

            Flickable {
                id: contentFlick
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: contentColumn.implicitHeight + design.space5
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

                QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                Column {
                    id: contentColumn
                    width: contentFlick.width - (contentFlick.contentHeight > contentFlick.height ? 12 : 0)
                    spacing: design.space4

                    Rectangle {
                        id: hero
                        visible: win.activeSection === "home" && win.searchQuery === ""
                        width: parent.width
                        height: visible ? 312 : 0
                        radius: 30
                        color: win.raisedStrong
                        border.width: 1
                        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.28)
                        clip: true

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: design.space6
                            spacing: design.space6

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: design.space3

                                Rectangle {
                                    implicitWidth: heroEyebrow.implicitWidth + design.space4
                                    implicitHeight: win.fs(28)
                                    radius: 14
                                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                                    Text {
                                        id: heroEyebrow
                                        anchors.centerIn: parent
                                        text: win.statusLoaded
                                              ? win.local("النظام حيّ الآن", "LIVE SYSTEM")
                                              : win.local("جارٍ قراءة الجهاز", "READING DEVICE")
                                        color: win.accent
                                        font.pixelSize: win.typePx(design.typeCaption)
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: win.rtl ? 0 : 1.0
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: win.local("هذا جهازك، في لمحة.", "Your device, in one glance.")
                                    color: win.textColor
                                    font.pixelSize: win.typePx(design.typeDisplay)
                                    font.weight: Font.Bold
                                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                                    wrapMode: Text.WordWrap
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: win.local(
                                        "MoOS " + win.status.deployment.version
                                        + " • " + win.status.hostname,
                                        "MoOS " + win.status.deployment.version
                                        + " • " + win.status.hostname
                                    )
                                    color: win.mutedColor
                                    font.pixelSize: win.typePx(design.typeBody)
                                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: win.status.cpu
                                    color: win.mutedColor
                                    font.pixelSize: win.typePx(design.typeCaption)
                                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                                    elide: Text.ElideRight
                                }

                                Item { Layout.fillHeight: true }

                                RowLayout {
                                    spacing: design.space3
                                    MoOSUi.Button {
                                        label: win.local("تحديث MoOS", "Update MoOS")
                                        iconName: MoOSSymbols.resolve("safe-update")
                                        primary: true
                                        surfaceColor: win.surface
                                        accentColor: win.accent
                                        textColor: win.textColor
                                        accentForegroundColor: win.accentText
                                        fontPixelSize: win.typePx(design.typeSecondary)
                                        onClicked: win.openRoute("moos://settings/update")
                                    }
                                    MoOSUi.Button {
                                        label: win.local("تفاصيل الجهاز", "Device details")
                                        iconName: MoOSSymbols.resolve("external")
                                        surfaceColor: win.surface
                                        accentColor: win.accent
                                        textColor: win.textColor
                                        accentForegroundColor: win.accentText
                                        fontPixelSize: win.typePx(design.typeSecondary)
                                        onClicked: win.openRoute("moos://settings/about")
                                    }
                                }
                            }

                            Item {
                                Layout.preferredWidth: Math.min(260, hero.width * 0.29)
                                Layout.fillHeight: true

                                Rectangle {
                                    id: orbitOuter
                                    width: Math.min(parent.width, parent.height) * 0.82
                                    height: width
                                    anchors.centerIn: parent
                                    radius: width / 2
                                    color: Qt.rgba(win.canvas.r, win.canvas.g, win.canvas.b, 0.34)
                                    border.width: 1
                                    border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.34)
                                    scale: 1

                                    SequentialAnimation {
                                        running: hero.visible && win.motionEnabled
                                        loops: 1
                                        NumberAnimation {
                                            target: orbitOuter
                                            property: "scale"
                                            from: 0.88
                                            to: 1
                                            duration: design.motionPage
                                            easing.type: Easing.OutBack
                                        }
                                    }

                                    Rectangle {
                                        width: parent.width * 0.67
                                        height: width
                                        anchors.centerIn: parent
                                        radius: width / 2
                                        color: "transparent"
                                        border.width: 1
                                        border.color: Qt.rgba(win.textColor.r, win.textColor.g,
                                                             win.textColor.b, 0.13)
                                    }
                                    Rectangle {
                                        width: parent.width * 0.37
                                        height: width
                                        anchors.centerIn: parent
                                        radius: width / 2
                                        color: win.accent

                                        MoOSUi.SymbolIcon {
                                            anchors.centerIn: parent
                                            width: parent.width * 0.47
                                            height: width
                                            symbol: MoOSSymbols.resolve("system")
                                            foreground: win.accentText
                                        }
                                    }

                                    Repeater {
                                        model: [
                                            { x: 0.48, y: 0.04, color: win.linkColor },
                                            { x: 0.87, y: 0.65, color: win.accent },
                                            { x: 0.12, y: 0.70, color: win.warningColor }
                                        ]
                                        delegate: Rectangle {
                                            required property var modelData
                                            width: 18
                                            height: 18
                                            radius: 9
                                            x: orbitOuter.width * modelData.x - width / 2
                                            y: orbitOuter.height * modelData.y - height / 2
                                            color: modelData.color
                                            border.width: 4
                                            border.color: hero.color
                                        }
                                    }
                                }

                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: design.space3
                                    implicitWidth: orbitLabel.implicitWidth + design.space4
                                    implicitHeight: win.fs(30)
                                    radius: 15
                                    color: win.surface
                                    border.width: 1
                                    border.color: win.outline

                                    Text {
                                        id: orbitLabel
                                        anchors.centerIn: parent
                                        text: win.status.deployment.signed
                                              ? win.local("موقّع ومحمي", "SIGNED & PROTECTED")
                                              : win.local("جاري التحقق", "VERIFYING")
                                        color: win.status.deployment.signed
                                               ? win.positiveColor : win.warningColor
                                        font.pixelSize: win.typePx(design.typeCaption)
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: win.rtl ? 0 : 0.8
                                    }
                                }
                            }
                        }
                    }

                    Flow {
                        visible: win.activeSection === "home" && win.searchQuery === ""
                        width: parent.width
                        height: visible ? implicitHeight : win.fs(0)
                        spacing: design.space3

                        StatusCapsule {
                            glyph: "network"
                            label: win.status.network.connected
                                   ? win.local("متصل", "Online")
                                   : win.local("غير متصل", "Offline")
                            detail: win.status.network.label
                            statusColor: win.status.network.connected
                                         ? win.positiveColor : win.warningColor
                            active: win.status.network.connected
                        }
                        StatusCapsule {
                            glyph: "bluetooth"
                            label: win.status.bluetooth.powered
                                   ? win.local("بلوتوث يعمل", "Bluetooth on")
                                   : win.local("بلوتوث متوقف", "Bluetooth off")
                            detail: win.status.bluetooth.available
                                    ? win.local("جاهز للأجهزة", "Ready for devices")
                                    : win.local("غير متاح", "Not available")
                            statusColor: win.linkColor
                            active: win.status.bluetooth.powered
                        }
                        StatusCapsule {
                            glyph: "shield"
                            label: win.status.deployment.signed
                                   ? win.local("صورة موثّقة", "Verified image")
                                   : win.local("جارٍ التحقق", "Checking image")
                            detail: win.status.deployment.digest
                            statusColor: win.positiveColor
                            active: win.status.deployment.signed
                        }
                        StatusCapsule {
                            glyph: win.status.battery.available ? "bolt" : "repair"
                            label: win.status.battery.available
                                   ? win.status.battery.percent + "%"
                                   : win.local("رجوع جاهز", "Rollback ready")
                            detail: win.status.battery.available
                                    ? win.local("طاقة الجهاز", "Device battery")
                                    : win.local(
                                          win.status.deployment.rollback + " نسخة محفوظة",
                                          win.status.deployment.rollback + " safe image"
                                      )
                            statusColor: win.accent
                            active: win.status.battery.available
                                    || win.status.deployment.rollback > 0
                        }
                    }

                    RowLayout {
                        visible: win.activeSection === "home" && win.searchQuery === ""
                        width: parent.width
                        height: visible ? implicitHeight : win.fs(0)
                        spacing: design.space3

                        MetricTile {
                            Layout.fillWidth: true
                            glyph: "storage"
                            label: win.local("المساحة المتاحة", "Storage free")
                            value: win.status.storage.free
                            progress: Number(win.status.storage.percent) / 100
                            tone: Number(win.status.storage.percent) > 88
                                  ? win.dangerColor : win.accent
                        }
                        MetricTile {
                            Layout.fillWidth: true
                            glyph: "memory"
                            label: win.local("الذاكرة المستخدمة", "Memory in use")
                            value: win.status.memory.used
                            progress: Number(win.status.memory.percent) / 100
                            tone: win.linkColor
                        }
                        MetricTile {
                            Layout.fillWidth: true
                            glyph: "audio"
                            label: win.local("الصوت", "Sound")
                            value: win.status.audio.available
                                   ? (win.status.audio.muted
                                      ? win.local("صامت", "Muted")
                                      : win.status.audio.volume + "%")
                                   : "—"
                            progress: win.status.audio.available
                                      ? Number(win.status.audio.volume) / 100 : -1
                            tone: win.warningColor
                        }
                        MetricTile {
                            Layout.fillWidth: true
                            glyph: "orbit"
                            label: win.local("مدة التشغيل", "Uptime")
                            value: win.uptimeLabel(win.status.uptimeSeconds)
                            progress: -1
                            tone: win.positiveColor
                        }
                    }

                    ColumnLayout {
                        visible: win.activeSection === "home" && win.searchQuery === ""
                        width: parent.width
                        height: visible ? implicitHeight : win.fs(0)
                        spacing: design.space3

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                Layout.fillWidth: true
                                text: win.local("محاور النظام", "System lanes")
                                color: win.textColor
                                font.pixelSize: win.typePx(design.typeTitle)
                                font.weight: Font.DemiBold
                                horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                            }
                            Text {
                                text: win.local("اختر محوراً لتشكيله", "Choose a lane to shape it")
                                color: win.mutedColor
                                font.pixelSize: win.typePx(design.typeCaption)
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: win.fs(102)
                            radius: design.radiusCard
                            color: win.surface
                            border.width: 1
                            border.color: win.faintOutline

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: design.space2
                                spacing: 0

                                Repeater {
                                    model: win.sections.slice(1)
                                    delegate: QQC2.AbstractButton {
                                        id: laneButton
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        hoverEnabled: true
                                        activeFocusOnTab: true
                                        Accessible.role: Accessible.Button
                                        Accessible.name: win.local(modelData.ar, modelData.en)
                                        onClicked: win.selectSection(modelData.id)

                                        background: Rectangle {
                                            radius: design.radiusControl
                                            color: laneButton.hovered
                                                   ? Qt.rgba(win.accent.r, win.accent.g,
                                                             win.accent.b, 0.13)
                                                   : "transparent"
                                        }
                                        contentItem: ColumnLayout {
                                            spacing: design.space2
                                            MoOSUi.SymbolIcon {
                                                Layout.alignment: Qt.AlignHCenter
                                                Layout.preferredWidth: win.fs(24)
                                                Layout.preferredHeight: win.fs(24)
                                                symbol: MoOSSymbols.resolve(laneButton.modelData.glyph)
                                                foreground: laneButton.hovered
                                                            ? win.accent : win.textColor
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: win.local(laneButton.modelData.ar,
                                                                laneButton.modelData.en)
                                                color: win.textColor
                                                font.pixelSize: win.typePx(design.typeCaption)
                                                font.weight: Font.DemiBold
                                                horizontalAlignment: Text.AlignHCenter
                                                elide: Text.ElideRight
                                            }
                                        }
                                        FocusRing {
                                            anchors.fill: laneButton
                                            accentColor: win.accent
                                            controlRadius: design.radiusControl
                                        }
                                    }
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        visible: win.activeSection !== "home" || win.searchQuery !== ""
                        width: parent.width
                        height: visible ? implicitHeight : win.fs(0)
                        spacing: design.space3

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: win.fs(132)
                            radius: design.radiusPanel
                            color: win.raised
                            border.width: 1
                            border.color: win.outline

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: design.space5
                                spacing: design.space4

                                Rectangle {
                                    Layout.preferredWidth: win.fs(72)
                                    Layout.preferredHeight: win.fs(72)
                                    radius: 24
                                    color: Qt.rgba(win.accent.r, win.accent.g,
                                                   win.accent.b, 0.15)
                                    border.width: 1
                                    border.color: Qt.rgba(win.accent.r, win.accent.g,
                                                         win.accent.b, 0.28)
                                    MoOSUi.SymbolIcon {
                                        anchors.centerIn: parent
                                        width: 34
                                        height: 34
                                        symbol: MoOSSymbols.resolve(
                                            win.searchQuery !== ""
                                            ? "search" : win.activeSectionData.glyph
                                        )
                                        foreground: win.accent
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: design.space2
                                    Text {
                                        Layout.fillWidth: true
                                        text: win.searchQuery !== ""
                                              ? win.local("ابحث. افتح. تحكّم.", "Find. Open. Shape.")
                                              : win.local(win.activeSectionData.heroAr,
                                                          win.activeSectionData.heroEn)
                                        color: win.textColor
                                        font.pixelSize: win.typePx(design.typeHeadline)
                                        font.weight: Font.DemiBold
                                        horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: win.searchQuery !== ""
                                              ? win.local(
                                                    "نتائج من كل محاور MoOS، بلا قوائم مخفية.",
                                                    "Commands across every MoOS lane, with no hidden maze."
                                                )
                                              : win.local(win.activeSectionData.heroDescAr,
                                                          win.activeSectionData.heroDescEn)
                                        color: win.mutedColor
                                        font.pixelSize: win.typePx(design.typeBody)
                                        horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }

                        Repeater {
                            model: win.visibleCommands
                            delegate: CommandRow {
                                required property var modelData
                                commandData: modelData
                            }
                        }

                        Rectangle {
                            visible: win.visibleCommands.length === 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: win.fs(190)
                            radius: design.radiusPanel
                            color: win.surface
                            border.width: 1
                            border.color: win.faintOutline

                            ColumnLayout {
                                anchors.centerIn: parent
                                width: Math.min(parent.width - design.space6 * 2, 460)
                                spacing: design.space3
                                MoOSUi.SymbolIcon {
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.preferredWidth: win.fs(38)
                                    Layout.preferredHeight: win.fs(38)
                                    symbol: MoOSSymbols.resolve("search")
                                    foreground: win.mutedColor
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: win.local("لا توجد أوامر مطابقة", "No matching commands")
                                    color: win.textColor
                                    font.pixelSize: win.typePx(design.typeTitle)
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: win.local(
                                        "جرّب كلمة أبسط مثل «الشبكة» أو «الشاشة».",
                                        "Try a broader term such as “network” or “display”."
                                    )
                                    color: win.mutedColor
                                    font.pixelSize: win.typePx(design.typeSecondary)
                                    horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

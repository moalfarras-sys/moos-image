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
import org.moos.ui as MoUI

QQC2.ApplicationWindow {
    id: win

    visible: true
    width: Math.min(design.commandCenterWidth, Screen.desktopAvailableWidth * 0.94)
    height: Math.min(design.commandCenterHeight, Screen.desktopAvailableHeight * 0.94)
    minimumWidth: Math.min(design.commandCenterMinimumWidth,
                           Screen.desktopAvailableWidth * 0.94)
    minimumHeight: Math.min(design.commandCenterMinimumHeight,
                            Screen.desktopAvailableHeight * 0.94)
    title: win.local("إعدادات MoOS", "MoOS Settings")
    color: canvas

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.View

    // ONE authority (org.moos.ui Locale). This read
    // Qt.application.layoutDirection, which follows an installed TRANSLATOR
    // and not the locale — MoOS ships bilingual QML strings rather than Qt
    // catalogues, so it is LeftToRight even at LANG=ar_SA.UTF-8. Proven with
    // a QML probe on the live session: locale RTL true, application RTL false.
    // The whole Command Center therefore rendered in English on an
    // Arabic-first OS while the launcher beside it was correctly Arabic.
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property real fontScale: Qt.application.font.pointSize > 0
                                      ? Qt.application.font.pointSize / 10 : 1
    function fs(size) { return Math.round(size * fontScale) }
    function typePx(size) { return design.typeSize(size, fontScale) }
    function local(ar, en) { return rtl ? ar : en }

    readonly property var design: MoUI.Tokens

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
    onSearchQueryChanged: {
        searchField.text = searchQuery
        contentFlick.contentY = 0
    }
    property bool statusLoaded: false
    property string statusError: ""
    property int statusSerial: 0
    property bool statusBusy: false
    property string launchError: ""
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
        destinations: {},
        network: { known: false, connectivity: "unknown", connected: false, full: false, label: "" },
        bluetooth: { available: false, powered: false },
        audio: { available: false, volume: 0, muted: false },
        battery: { available: false, percent: 0, state: "" },
        deployment: {
            version: "—", digest: "", signed: false, known: false,
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
            heroAr: "حالة النظام وتفضيلاتك.", heroEn: "System state and preferences.",
            heroDescAr: "التحديثات والحسابات واللغة ومعلومات الجهاز",
            heroDescEn: "Updates, accounts, language and device information"
        },
        {
            id: "recovery", glyph: "repair",
            ar: "الاستعادة", en: "Recovery",
            descAr: "الرجوع الآمن وتشخيص الأداء",
            descEn: "Safe rollback and diagnostics",
            heroAr: "ارجع بثقة.", heroEn: "Return with confidence.",
            heroDescAr: "راجع النسخ المحفوظة وخيارات الاستعادة المتاحة",
            heroDescEn: "Review saved deployments and available recovery options"
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
          ar: "التاريخ والوقت", en: "Date & time",
          descAr: "المنطقة الزمنية والساعة التلقائية",
          descEn: "Time zone and automatic clock" },
        { section: "system", route: "moos://settings/region", glyph: "identity",
          ar: "اللغة والمنطقة", en: "Language & region",
          descAr: "لغة النظام وتنسيقات الأرقام والتاريخ",
          descEn: "System language, number and date formats" },
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
          tagAr: "", tagEn: "" },
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
                item.ar, item.en, item.descAr, item.descEn, item.section, item.route.substring(16)
            ].join(" ").toLocaleLowerCase()
            if (needle !== "" ? haystack.indexOf(needle) >= 0
                              : item.section === activeSection)
                result.push(item)
        }
        return result
    }

    readonly property string statusUrl: argValue("--status=")

    function argValue(prefix, suppliedArguments) {
        var args = suppliedArguments || Qt.application.arguments
        for (var i = 0; i < args.length; ++i)
            if (args[i].indexOf(prefix) === 0)
                return args[i].substring(prefix.length)
        return ""
    }

    // moos-qml-shell keeps one Command Center process. A second launcher
    // action must navigate that live window, not read the first process's
    // immutable Qt.application.arguments and reopen the old page.
    function activateRequested(arguments) {
        var requestedSection = argValue("--section=", arguments)
        for (var i = 0; i < sections.length; ++i) {
            if (sections[i].id === requestedSection) {
                selectSection(requestedSection)
                return
            }
        }
    }

    function routeAvailable(route) {
        return statusLoaded && status.destinations[String(route).substring(16)] === true
    }

    function routeReason(route) {
        if (!statusLoaded)
            return statusError || local("جارٍ قراءة الإعدادات…", "Reading settings…")
        return routeAvailable(route) ? "" : local(
            "هذه الإعدادات غير مثبتة على هذا الجهاز", "These settings are not installed on this device")
    }

    readonly property string imageLabel: !statusLoaded || !status.deployment.known
        ? local("حالة التوقيع غير متاحة", "Signature status unavailable")
        : status.deployment.signed ? local("صورة نظام موقّعة", "Signed system image")
        : local("صورة نظام غير موثّقة", "Unverified system image")

    readonly property string networkLabel: !statusLoaded || !status.network.known
        ? local("حالة الشبكة غير متاحة", "Network status unavailable")
        : !status.network.connected ? local("غير متصل", "Offline")
        : status.network.full ? local("متصل بالإنترنت", "Online")
        : status.network.connectivity === "portal" ? local("يلزم تسجيل الدخول", "Sign-in required")
        : local("الإنترنت غير مؤكد", "Internet not confirmed")

    readonly property string bluetoothLabel: !statusLoaded
        ? local("حالة بلوتوث غير متاحة", "Bluetooth status unavailable")
        : !status.bluetooth.available ? local("بلوتوث غير متاح", "Bluetooth unavailable")
        : status.bluetooth.powered ? local("بلوتوث يعمل", "Bluetooth on")
        : local("بلوتوث متوقف", "Bluetooth off")

    readonly property string rollbackLabel: !statusLoaded || !status.deployment.known
        ? local("حالة الاستعادة غير متاحة", "Recovery status unavailable")
        : status.deployment.rollback > 0 ? local("نسخة رجوع متاحة", "Rollback available")
        : local("لا توجد نسخة رجوع", "No rollback saved")

    function isolated(value) { return "\u2068" + value + "\u2069" }

    function commandDetail(item) {
        var reason = routeReason(item.route)
        if (reason) return reason
        switch (item.route) {
        case "moos://settings/network": return networkLabel + (status.network.label ? " · " + isolated(status.network.label) : "")
        case "moos://settings/bluetooth": return bluetoothLabel
        case "moos://settings/audio": return !status.audio.available ? local("لا يوجد مخرج صوت متاح", "No audio output available")
            : status.audio.muted ? local("الصوت مكتوم", "Output muted") : local("مستوى الصوت: ", "Output volume: ") + isolated(status.audio.volume + "%")
        case "moos://settings/storage": return isolated(status.storage.free) + local(" متاحة من ", " free of ") + isolated(status.storage.total)
        case "moos://settings/about": return isolated("MoOS " + isolated(status.deployment.version)) + " · " + isolated(status.hostname)
        case "moos://settings/recovery": return rollbackLabel
        case "moos://settings/update": return status.deployment.staged
            ? local("جاهز لإعادة التشغيل: ", "Ready to restart: ") + isolated(status.deployment.stagedVersion)
            : local("الإصدار المثبت: ", "Installed version: ") + isolated(status.deployment.version)
        }
        return local(item.descAr, item.descEn)
    }

    function openRoute(route) {
        if (String(route).indexOf("moos://settings/") !== 0 || !routeAvailable(route))
            return
        launchError = Qt.openUrlExternally(route) ? "" : local(
            "تعذّر فتح الإعدادات. حاول مرة أخرى.", "Could not open settings. Try again.")
    }

    function selectSection(sectionId) {
        searchQuery = ""
        launchError = ""
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

    function statusFailure() {
        statusLoaded = false
        statusError = local("تعذّرت قراءة حالة الجهاز. ستتم إعادة المحاولة تلقائياً.",
                            "Device status is unavailable. Retrying automatically.")
    }

    function acceptStatus(parsed) {
        // A matching schema alone is not a usable document. Reject partial and
        // stale snapshots before any binding can present their defaults as facts.
        var age = Date.now() / 1000 - (parsed && parsed.generatedAt)
        if (!parsed || parsed.schema !== 1 || parsed.product !== "MoOS"
                || !Number.isFinite(age) || age < -5 || age > 45)
            return false
        var objects = ["deployment", "network", "bluetooth", "audio", "battery", "storage", "memory", "destinations"]
        for (var i = 0; i < objects.length; ++i)
            if (!parsed[objects[i]] || typeof parsed[objects[i]] !== "object") return false
        var shape = {
            deployment: {known: "boolean", signed: "boolean", staged: "boolean", rollback: "number", version: "string", stagedVersion: "string", digest: "string"},
            network: {known: "boolean", connected: "boolean", full: "boolean", connectivity: "string", label: "string"},
            audio: {available: "boolean", muted: "boolean", volume: "number"},
            bluetooth: {available: "boolean", powered: "boolean"},
            battery: {available: "boolean", percent: "number", state: "string"},
            memory: {used: "string", total: "string", percent: "number"},
            storage: {free: "string", total: "string", percent: "number"}
        }
        for (var group in shape)
            for (var key in shape[group])
                if (typeof parsed[group][key] !== shape[group][key]) return false
        for (var field of ["hostname", "kernel", "cpu"])
            if (typeof parsed[field] !== "string") return false
        if (typeof parsed.uptimeSeconds !== "number") return false
        if (typeof parsed.deployment.known !== "boolean" || typeof parsed.network.known !== "boolean")
            return false
        status = parsed
        statusLoaded = true
        statusError = ""
        statusSerial++
        return true
    }

    function loadStatus() {
        if (statusBusy) return
        if (!statusUrl) { statusFailure(); return }
        statusBusy = true
        var request = new XMLHttpRequest()
        request.open("GET", statusUrl)
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) return
            win.statusBusy = false
            try {
                if ((request.status !== 0 && (request.status < 200 || request.status >= 300))
                        || !win.acceptStatus(JSON.parse(request.responseText))) win.statusFailure()
            } catch (error) { win.statusFailure() }
        }
        request.send()
    }

    Component.onCompleted: {
        activateRequested(Qt.application.arguments)
        loadStatus()
    }
    Timer {
        interval: 1800
        repeat: true
        running: win.visible
        onTriggered: win.loadStatus()
    }

    component FocusRing: MoUI.FocusRing {
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
            } else if (win.activeSection !== "home") {
                win.selectSection("home")
            } else {
                win.close()
            }
        }
    }

    component StatusCapsule: MoUI.Surface {
        id: capsule
        required property string glyph
        required property string label
        property string detail: ""
        property color statusColor: win.accent
        property bool active: true

        implicitHeight: win.fs(54)
        implicitWidth: capsuleRow.implicitWidth + design.space5 * 2
        radius: design.radiusCard
        surfaceColor: Qt.rgba(win.textColor.r, win.textColor.g,
                              win.textColor.b, 0.065)
        inkColor: win.textColor
        accentColor: statusColor
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
                radius: design.radiusSmall
                color: Qt.rgba(capsule.statusColor.r, capsule.statusColor.g,
                               capsule.statusColor.b, capsule.active ? 0.18 : 0.08)

                MoUI.SymbolIcon {
                    anchors.centerIn: parent
                    width: 17
                    height: 17
                    symbol: MoUI.SymbolCatalog.resolve(capsule.glyph)
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
                    horizontalAlignment: Text.AlignLeft
                    Layout.maximumWidth: 180
                    elide: Text.ElideRight
                }
                Text {
                    visible: capsule.detail !== ""
                    text: capsule.detail
                    color: win.mutedColor
                    font.pixelSize: win.typePx(design.typeCaption)
                    horizontalAlignment: Text.AlignLeft
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
                radius: design.radiusControl
                color: navControl.selected
                       ? win.accent
                       : Qt.rgba(win.textColor.r, win.textColor.g, win.textColor.b, 0.06)

                MoUI.SymbolIcon {
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    symbol: MoUI.SymbolCatalog.resolve(navControl.sectionData.glyph)
                    foreground: navControl.selected ? win.accentText : win.textColor
                }
            }

            Text {
                Layout.fillWidth: true
                text: win.local(navControl.sectionData.ar, navControl.sectionData.en)
                color: win.textColor
                font.pixelSize: win.typePx(design.typeBody)
                font.weight: navControl.selected ? Font.DemiBold : Font.Medium
                horizontalAlignment: Text.AlignLeft
                elide: Text.ElideRight
            }

            Rectangle {
                visible: navControl.selected
                Layout.preferredWidth: win.fs(5)
                Layout.preferredHeight: win.fs(18)
                radius: width / 2
                color: win.accent
            }
        }

        FocusRing {
            anchors.fill: navControl
            accentColor: win.accent
            controlRadius: design.radiusControl
        }
    }

    component MetricTile: MoUI.Surface {
        id: metric
        required property string glyph
        required property string label
        required property string value
        property real progress: -1
        property color tone: win.accent

        implicitHeight: win.fs(112)
        radius: design.radiusCard
        surfaceColor: win.surface
        inkColor: win.textColor
        accentColor: tone
        border.color: win.faintOutline

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: design.space4
            spacing: design.space2

            RowLayout {
                Layout.fillWidth: true
                spacing: design.space2

                MoUI.SymbolIcon {
                    Layout.preferredWidth: win.fs(18)
                    Layout.preferredHeight: win.fs(18)
                    symbol: MoUI.SymbolCatalog.resolve(metric.glyph)
                    foreground: metric.tone
                }
                Text {
                    Layout.fillWidth: true
                    text: metric.label
                    color: win.mutedColor
                    font.pixelSize: win.typePx(design.typeCaption)
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignLeft
                    elide: Text.ElideRight
                }
            }

            Text {
                Layout.fillWidth: true
                text: metric.value
                color: win.textColor
                font.pixelSize: win.typePx(design.typeTitle)
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignLeft
                elide: Text.ElideRight
            }

            Rectangle {
                visible: metric.progress >= 0
                Layout.fillWidth: true
                Layout.preferredHeight: win.fs(4)
                radius: height / 2
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
        leftPadding: design.space4
        rightPadding: design.space4
        onActiveFocusChanged: {
            if (!activeFocus) return
            var top = mapToItem(contentColumn, 0, 0).y
            if (top < contentFlick.contentY) contentFlick.contentY = top
            else if (top + height > contentFlick.contentY + contentFlick.height)
                contentFlick.contentY = top + height - contentFlick.height
        }
        hoverEnabled: true
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: win.local(commandData.ar, commandData.en)
        enabled: win.routeAvailable(commandData.route)
        Accessible.description: win.commandDetail(commandData)
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
                radius: width / 2
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

                MoUI.SymbolIcon {
                    anchors.centerIn: parent
                    width: 24
                    height: 24
                    symbol: MoUI.SymbolCatalog.resolve(commandControl.commandData.glyph)
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
                        horizontalAlignment: Text.AlignLeft
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        visible: Boolean(commandControl.commandData.tagAr)
                        implicitWidth: commandTag.implicitWidth + design.space3
                        implicitHeight: win.fs(24)
                        radius: height / 2
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
                    text: win.commandDetail(commandControl.commandData)
                    color: win.mutedColor
                    font.pixelSize: win.typePx(design.typeSecondary)
                    horizontalAlignment: Text.AlignLeft
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                Layout.preferredWidth: win.fs(36)
                Layout.preferredHeight: win.fs(36)
                radius: width / 2
                color: commandControl.hovered
                       ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                       : "transparent"

                MoUI.SymbolIcon {
                    anchors.centerIn: parent
                    width: 17
                    height: 17
                    symbol: MoUI.SymbolCatalog.resolve(commandControl.enabled ? "external" : "lock")
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

        MoUI.GlassSurface {
            Layout.preferredWidth: win.fs(design.commandCenterSidebarWidth)
            Layout.fillHeight: true
            surfaceColor: win.surface
            inkColor: win.textColor
            accentColor: win.accent
            floating: true
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

                        MoUI.SymbolIcon {
                            anchors.centerIn: parent
                            width: 26
                            height: 26
                            symbol: MoUI.SymbolCatalog.resolve("orbit")
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
                            text: win.local("الإعدادات", "SETTINGS")
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
                            MoUI.SymbolIcon {
                                Layout.preferredWidth: win.fs(18)
                                Layout.preferredHeight: win.fs(18)
                                symbol: MoUI.SymbolCatalog.resolve(
                                    win.status.deployment.signed ? "shield" : "warning"
                                )
                                foreground: win.statusLoaded && win.status.deployment.signed
                                            ? win.positiveColor : win.warningColor
                            }
                            Text {
                                Layout.fillWidth: true
                                text: win.imageLabel
                                color: win.textColor
                                font.pixelSize: win.typePx(design.typeSecondary)
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignLeft
                                elide: Text.ElideRight
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: win.rollbackLabel
                            color: win.mutedColor
                            font.pixelSize: win.typePx(design.typeCaption)
                            horizontalAlignment: Text.AlignLeft
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: win.fs(3)
                            radius: height / 2
                            color: Qt.rgba(win.textColor.r, win.textColor.g, win.textColor.b, 0.08)
                            Rectangle {
                                width: parent.width
                                height: parent.height
                                radius: parent.radius
                                color: win.statusLoaded && win.status.deployment.signed
                                       ? win.positiveColor : win.warningColor
                                opacity: win.statusLoaded ? 1 : 0.25
                            }
                        }
                    }
                }

                MoUI.Button {
                    Layout.fillWidth: true
                    label: win.local("كل إعدادات النظام", "All system settings")
                    iconName: MoUI.SymbolCatalog.resolve("external")
                    surfaceColor: win.raised
                    accentColor: win.accent
                    textColor: win.textColor
                    accentForegroundColor: win.accentText
                    fontPixelSize: win.typePx(design.typeSecondary)
                    enabled: win.routeAvailable("moos://settings/full")
                    visible: !win.statusLoaded || enabled
                    Accessible.description: win.routeReason("moos://settings/full")
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
                        horizontalAlignment: Text.AlignLeft
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: win.searchQuery !== ""
                              ? win.local(
                                    win.visibleCommands.length + " نتيجة في الإعدادات",
                                    win.visibleCommands.length + " settings found"
                                )
                              : win.local(win.activeSectionData.descAr,
                                          win.activeSectionData.descEn)
                        color: win.mutedColor
                        font.pixelSize: win.typePx(design.typeCaption)
                        horizontalAlignment: Text.AlignLeft
                        elide: Text.ElideRight
                    }
                }

                QQC2.TextField {
                    id: searchField
                    objectName: "settingsSearch"
                    horizontalAlignment: Text.AlignLeft
                    Layout.preferredWidth: Math.min(340, win.width * 0.27)
                    Layout.preferredHeight: win.fs(44)
                    leftPadding: win.rtl ? design.space4 : 46
                    rightPadding: win.rtl ? 46 : design.space4
                    placeholderText: win.local("ابحث في النظام…", "Search the system…")
                    color: win.textColor
                    placeholderTextColor: win.mutedColor
                    selectionColor: win.accent
                    selectedTextColor: win.accentText
                    font.pixelSize: win.typePx(design.typeSecondary)
                    activeFocusOnTab: true
                    Accessible.name: placeholderText
                    onTextEdited: { win.searchQuery = text; contentFlick.contentY = 0 }

                    background: Rectangle {
                        radius: design.radiusControl
                        color: win.surface
                        border.width: searchField.activeFocus ? 2 : 1
                        border.color: searchField.activeFocus ? win.accent : win.outline
                    }

                    MoUI.SymbolIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: design.space4
                        width: 18
                        height: 18
                        symbol: MoUI.SymbolCatalog.resolve("search")
                        foreground: searchField.activeFocus ? win.accent : win.mutedColor
                    }

                    FocusRing {
                        anchors.fill: searchField
                        controlRadius: design.radiusControl
                    }
                }
            }

            MoUI.Surface {
                visible: !win.statusLoaded || win.launchError !== ""
                Layout.fillWidth: true
                implicitHeight: noticeRow.implicitHeight + design.space4 * 2
                surfaceColor: win.raised
                inkColor: win.textColor
                accentColor: win.warningColor
                radius: design.radiusCard
                RowLayout {
                    id: noticeRow
                    anchors.fill: parent
                    anchors.margins: design.space4
                    Text {
                        Layout.fillWidth: true
                        text: win.launchError || win.statusError || win.local("جارٍ قراءة حالة الجهاز…", "Reading device status…")
                        color: win.textColor
                        font.pixelSize: win.typePx(design.typeSecondary)
                        horizontalAlignment: Text.AlignLeft
                        wrapMode: Text.WordWrap
                    }
                    MoUI.Button {
                        label: win.local("إعادة المحاولة", "Retry")
                        enabled: !win.statusBusy
                        onClicked: { win.launchError = ""; win.loadStatus() }
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

                    MoUI.GlassSurface {
                        id: hero
                        visible: win.activeSection === "home" && win.searchQuery === ""
                        width: parent.width
                        height: visible ? win.fs(design.commandCenterHeroHeight) : 0
                        radius: design.radiusDialog
                        surfaceColor: win.raisedStrong
                        inkColor: win.textColor
                        accentColor: win.accent
                        floating: true
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
                                    radius: height / 2
                                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                                    Text {
                                        id: heroEyebrow
                                        anchors.centerIn: parent
                                        text: win.statusError ? win.local("الحالة غير متاحة", "STATUS UNAVAILABLE")
                                              : win.statusLoaded
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
                                    horizontalAlignment: Text.AlignLeft
                                    wrapMode: Text.WordWrap
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: !win.statusLoaded ? "MoOS" : win.local(
                                        "MoOS " + win.status.deployment.version
                                        + " • " + win.status.hostname,
                                        "MoOS " + win.status.deployment.version
                                        + " • " + win.status.hostname
                                    )
                                    color: win.mutedColor
                                    font.pixelSize: win.typePx(design.typeBody)
                                    horizontalAlignment: Text.AlignLeft
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: !win.statusLoaded ? "—" : win.status.cpu === "MoOS device"
                                          ? win.local("جهاز MoOS", "MoOS device") : win.status.cpu
                                    color: win.mutedColor
                                    font.pixelSize: win.typePx(design.typeCaption)
                                    horizontalAlignment: Text.AlignLeft
                                    elide: Text.ElideRight
                                }

                                Item { Layout.fillHeight: true }

                                RowLayout {
                                    spacing: design.space3
                                    MoUI.Button {
                                        label: win.local("تحديث MoOS", "Update MoOS")
                                        iconName: MoUI.SymbolCatalog.resolve("safe-update")
                                        primary: true
                                        surfaceColor: win.surface
                                        accentColor: win.accent
                                        textColor: win.textColor
                                        accentForegroundColor: win.accentText
                                        fontPixelSize: win.typePx(design.typeSecondary)
                                        enabled: win.routeAvailable("moos://settings/update")
                    visible: !win.statusLoaded || enabled
                    Accessible.description: win.routeReason("moos://settings/update")
                    onClicked: win.openRoute("moos://settings/update")
                                    }
                                    MoUI.Button {
                                        label: win.local("تفاصيل الجهاز", "Device details")
                                        iconName: MoUI.SymbolCatalog.resolve("external")
                                        surfaceColor: win.surface
                                        accentColor: win.accent
                                        textColor: win.textColor
                                        accentForegroundColor: win.accentText
                                        fontPixelSize: win.typePx(design.typeSecondary)
                                        enabled: win.routeAvailable("moos://settings/about")
                    visible: !win.statusLoaded || enabled
                    Accessible.description: win.routeReason("moos://settings/about")
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

                                        MoUI.SymbolIcon {
                                            anchors.centerIn: parent
                                            width: parent.width * 0.47
                                            height: width
                                            symbol: MoUI.SymbolCatalog.resolve("system")
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
                                    radius: height / 2
                                    color: win.surface
                                    border.width: 1
                                    border.color: win.outline

                                    Text {
                                        id: orbitLabel
                                        anchors.centerIn: parent
                                        text: win.imageLabel
                                        color: win.statusLoaded && win.status.deployment.signed
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
                            label: win.networkLabel
                            detail: win.statusLoaded ? win.status.network.label : ""
                            statusColor: win.statusLoaded && win.status.network.full
                                         ? win.positiveColor : win.warningColor
                            active: win.statusLoaded && win.status.network.full
                        }
                        StatusCapsule {
                            glyph: "bluetooth"
                            label: win.bluetoothLabel
                            detail: !win.statusLoaded ? "" : win.status.bluetooth.available
                                    ? win.local("جاهز للأجهزة", "Ready for devices")
                                    : win.local("غير متاح", "Not available")
                            statusColor: win.linkColor
                            active: win.statusLoaded && win.status.bluetooth.powered
                        }
                        StatusCapsule {
                            glyph: "shield"
                            label: win.imageLabel
                            detail: win.statusLoaded ? win.status.deployment.digest : ""
                            statusColor: win.statusLoaded && win.status.deployment.signed ? win.positiveColor : win.warningColor
                            active: win.statusLoaded && win.status.deployment.signed
                        }
                        StatusCapsule {
                            glyph: win.status.battery.available ? "bolt" : "repair"
                            label: win.statusLoaded && win.status.battery.available
                                   ? win.status.battery.percent + "%"
                                   : win.rollbackLabel
                            detail: !win.statusLoaded ? "" : win.status.battery.available
                                    ? win.local("طاقة الجهاز", "Device battery")
                                    : win.local(
                                          win.status.deployment.rollback + " نسخة محفوظة",
                                          win.status.deployment.rollback + " saved"
                                      )
                            statusColor: win.accent
                            active: win.statusLoaded && (win.status.battery.available
                                    || win.status.deployment.rollback > 0)
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
                            value: win.statusLoaded ? win.status.storage.free : "—"
                            progress: win.statusLoaded ? 1 - Number(win.status.storage.percent) / 100 : -1
                            tone: Number(win.status.storage.percent) > 88
                                  ? win.dangerColor : win.accent
                        }
                        MetricTile {
                            Layout.fillWidth: true
                            glyph: "memory"
                            label: win.local("الذاكرة المستخدمة", "Memory in use")
                            value: win.statusLoaded ? win.status.memory.used : "—"
                            progress: win.statusLoaded ? Number(win.status.memory.percent) / 100 : -1
                            tone: win.linkColor
                        }
                        MetricTile {
                            Layout.fillWidth: true
                            glyph: "audio"
                            label: win.local("الصوت", "Sound")
                            value: win.statusLoaded && win.status.audio.available
                                   ? (win.status.audio.muted
                                      ? win.local("صامت", "Muted")
                                      : win.status.audio.volume + "%")
                                   : "—"
                            progress: win.statusLoaded && win.status.audio.available
                                      ? Number(win.status.audio.volume) / 100 : -1
                            tone: win.warningColor
                        }
                        MetricTile {
                            Layout.fillWidth: true
                            glyph: "orbit"
                            label: win.local("مدة التشغيل", "Uptime")
                            value: win.statusLoaded ? win.uptimeLabel(win.status.uptimeSeconds) : "—"
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
                                text: win.local("فئات الإعدادات", "Settings categories")
                                color: win.textColor
                                font.pixelSize: win.typePx(design.typeTitle)
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignLeft
                            }
                            Text {
                                text: win.local("اختر الإعدادات التي تريد تغييرها", "Choose what to configure")
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
                                            MoUI.SymbolIcon {
                                                Layout.alignment: Qt.AlignHCenter
                                                Layout.preferredWidth: win.fs(24)
                                                Layout.preferredHeight: win.fs(24)
                                                symbol: MoUI.SymbolCatalog.resolve(laneButton.modelData.glyph)
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

                        MoUI.GlassSurface {
                            Layout.fillWidth: true
                            Layout.preferredHeight: win.fs(132)
                            radius: design.radiusPanel
                            surfaceColor: win.raised
                            inkColor: win.textColor
                            accentColor: win.accent
                            floating: true
                            border.color: win.outline

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: design.space5
                                spacing: design.space4

                                Rectangle {
                                    Layout.preferredWidth: win.fs(72)
                                    Layout.preferredHeight: win.fs(72)
                                    radius: design.radiusPanel
                                    color: Qt.rgba(win.accent.r, win.accent.g,
                                                   win.accent.b, 0.15)
                                    border.width: 1
                                    border.color: Qt.rgba(win.accent.r, win.accent.g,
                                                         win.accent.b, 0.28)
                                    MoUI.SymbolIcon {
                                        anchors.centerIn: parent
                                        width: 34
                                        height: 34
                                        symbol: MoUI.SymbolCatalog.resolve(
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
                                              ? win.local("ابحث عن إعداداتك.", "Find your settings.")
                                              : win.local(win.activeSectionData.heroAr,
                                                          win.activeSectionData.heroEn)
                                        color: win.textColor
                                        font.pixelSize: win.typePx(design.typeHeadline)
                                        font.weight: Font.DemiBold
                                        horizontalAlignment: Text.AlignLeft
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: win.searchQuery !== ""
                                              ? win.local(
                                                    "افتح الإعدادات المطابقة لبحثك.",
                                                    "Open the settings that match your search."
                                                )
                                              : win.local(win.activeSectionData.heroDescAr,
                                                          win.activeSectionData.heroDescEn)
                                        color: win.mutedColor
                                        font.pixelSize: win.typePx(design.typeBody)
                                        horizontalAlignment: Text.AlignLeft
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
                                MoUI.SymbolIcon {
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.preferredWidth: win.fs(38)
                                    Layout.preferredHeight: win.fs(38)
                                    symbol: MoUI.SymbolCatalog.resolve("search")
                                    foreground: win.mutedColor
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: win.local("لا توجد إعدادات مطابقة", "No matching settings")
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

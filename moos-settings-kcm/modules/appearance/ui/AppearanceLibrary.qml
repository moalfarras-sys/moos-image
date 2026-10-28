// SPDX-License-Identifier: GPL-2.0-or-later
// KDE owns catalogue policy, previews, package transactions and native apply.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.kde.kcmutils as KCM
import org.kde.newstuff as NewStuff
import org.moos.ui as MoUI

KCM.SimpleKCM {
    id: root
    title: t("مكتبة المظهر", "Appearance library")
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property real cardWidth: Kirigami.Units.gridUnit * 44
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                Kirigami.Theme.textColor.b, 0.72)
    property string routeError: ""
    function t(ar, en) { return rtl ? ar : en }
    function nativeAvailable(token) {
        return !kcm.statusValid || (kcm.status.destinations || {})[token] !== false
    }
    function open(route) {
        routeError = kcm.openRoute(route) ? "" : t("تعذّر فتح هذه الصفحة.", "Could not open that page.")
    }
    // Compile the native child at module load; instantiate its engine only on
    // an explicit Online action. Native KCM push owns the actual page lifetime.
    readonly property Component onlinePage: KdeOnline { libraryConfig: "" }
    function browse(config, savedOnly) {
        var page = onlinePage.createObject(root, { libraryConfig: config, installedOnly: savedOnly === true })
        if (page)
            kcm.push(page)
        else
            routeError = t("تعذّر فتح المكتبة عبر الإنترنت.", "Could not open the online library.")
    }
    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true
    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing
        MoosRouteNotice {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            message: root.routeError
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            Kirigami.Heading {
                Layout.fillWidth: true
                level: 2
                text: root.t("مظهرك، بطريقتك", "Make it yours")
                wrapMode: Text.WordWrap
            }
            Controls.Label {
                Layout.fillWidth: true
                text: root.t("استخدم أزرار الإدارة لعرض الموجود، أو «من الإنترنت» للمعاينة والتنزيل. تبقى الإضافات محفوظة لحسابك ويمكن إزالتها من المكتبة نفسها.",
                             "Manage your existing items, or choose Online to preview and download. Additions are saved for your account and can be removed in the same library.")
                color: root.secondaryInk
                wrapMode: Text.WordWrap
            }
        }
        // Installed choices stay with their native KCM; Online opens that same
        // category's KNewStuff preview/install/remove UI, without another store.
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("مكتبة المظهر", "Appearance library")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            KdeLibraryRow {
                glyph: "grid"
                text: root.t("أدوات سطح المكتب", "Desktop widgets")
                description: root.t("نزّل الأدوات، ثم أضفها ورتّبها من معرض أدوات سطح المكتب.",
                                    "Download widgets, then add and arrange them in the desktop widget gallery.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("widgets")
                enabled: root.nativeAvailable("desktop")
                onManageInstalled: root.open("moos://settings/desktop")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "ui"
                text: root.t("السمة العامة", "Global theme")
                description: root.t("عاين السمات المثبتة أو احفظ مظهرك الحالي كثيم جديد.",
                                    "Preview installed themes or save your current appearance as a new theme.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("themes")
                enabled: root.nativeAvailable("global-theme")
                onManageInstalled: root.open("moos://settings/global-theme")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "image"
                text: root.t("الخلفيات", "Wallpapers")
                description: root.t("اعرض الصور التي نزّلتها من المكتبة، أو عاين صورًا جديدة.",
                                    "Browse images you downloaded from the library, or preview new ones.")
                rtl: root.rtl
                installedLabel: root.t("المحفوظة", "Saved")
                libraryConfig: kcm.appearanceLibraryConfig("wallpapers")
                enabled: root.nativeAvailable("wallpaper-library")
                onManageInstalled: {
                    if (libraryConfig !== "" && NewStuff.Settings.allowedByKiosk)
                        root.browse(libraryConfig, true)
                    else
                        root.open("moos://settings/wallpaper-library")
                }
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "grid"
                text: root.t("نمط سطح المكتب", "Desktop style")
                description: root.t("خامة اللوحات والقوائم وأدوات سطح المكتب.",
                                    "The appearance of panels, menus and desktop widgets.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("plasma-styles")
                enabled: root.nativeAvailable("desktop-style")
                onManageInstalled: root.open("moos://settings/desktop-style")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "gem"
                text: root.t("الألوان", "Colors")
                description: root.t("مخطط الألوان ولون التمييز.", "The colour scheme and the accent colour.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("colors")
                enabled: root.nativeAvailable("colors")
                onManageInstalled: root.open("moos://settings/colors")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "grid"
                text: root.t("الأيقونات", "Icons")
                description: root.t("سمة الأيقونات وأحجامها.", "The icon theme and icon sizes.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("icons")
                enabled: root.nativeAvailable("icons")
                onManageInstalled: root.open("moos://settings/icons")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "mouse"
                text: root.t("المؤشر", "Cursors")
                description: root.t("شكل المؤشر وحجمه.", "The pointer's shape and size.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("cursors")
                enabled: root.nativeAvailable("cursors")
                onManageInstalled: root.open("moos://settings/cursors")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "system"
                text: root.t("إطار النوافذ", "Window decorations")
                description: root.t("شريط عنوان النوافذ وأزراره.", "Window title bars and their buttons.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("decorations")
                enabled: root.nativeAvailable("window-decoration")
                onManageInstalled: root.open("moos://settings/window-decoration")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "document"
                text: root.t("الخطوط", "Fonts")
                description: root.t("خطوط الواجهة والنصوص وأحجامها.", "Interface and text fonts, and their sizes.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("fonts")
                directDownloadEnabled: false
                libraryRoute: root.nativeAvailable("font-library") && libraryConfig !== "" ? "moos://settings/font-library" : ""
                enabled: root.nativeAvailable("fonts")
                onManageInstalled: root.open("moos://settings/fonts")
                onOpenLibraryRoute: route => root.open(route)
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "wave"
                text: root.t("تأثيرات سطح المكتب", "Desktop effects")
                description: root.t("معاينة تأثيرات النوافذ وتفعيل ما يناسب جهازك.",
                                    "Preview window effects and enable those suited to your device.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("effects")
                enabled: root.nativeAvailable("effects")
                onManageInstalled: root.open("moos://settings/effects")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "ui"
                text: root.t("التبديل بين النوافذ", "Window switcher")
                description: root.t("شكل معاينة النوافذ عند التنقل بينها.",
                                    "How window previews appear while switching between applications.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("switchers")
                enabled: root.nativeAvailable("task-switcher")
                onManageInstalled: root.open("moos://settings/task-switcher")
                onBrowseOnline: config => root.browse(config)
            }
            FormCard.FormDelegateSeparator {}
            KdeLibraryRow {
                glyph: "system"
                text: root.t("إضافات مدير النوافذ", "Window manager extensions")
                description: root.t("إضافات لتنظيم النوافذ وطريقة استخدامها.",
                                    "Extensions for arranging windows and working with them.")
                rtl: root.rtl
                libraryConfig: kcm.appearanceLibraryConfig("scripts")
                enabled: root.nativeAvailable("window-scripts")
                onManageInstalled: root.open("moos://settings/window-scripts")
                onBrowseOnline: config => root.browse(config)
            }
        }

    }
}

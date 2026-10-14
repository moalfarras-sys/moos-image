pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — Sources: where Mo Store's apps come from and the specialist engines
// behind it.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Flickable {
    id: sourcesFlick
    required property var win
    readonly property var design: win.design
    anchors.fill: parent
    visible: win.page === "sources"
    contentWidth: width
    contentHeight: sourceBody.implicitHeight + 50
    clip: true
    Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(sourcesFlick, event)
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    ColumnLayout {
        id: sourceBody
        x: 26
        width: parent.width - 52
        spacing: 17
        Item { Layout.preferredHeight: win.fs(4) }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: win.fs(142)
            radius: win.fs(25)
            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.11)
            border.width: 1
            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.3)
            RowLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 17
                Rectangle {
                    Layout.preferredWidth: win.fs(70)
                    Layout.preferredHeight: win.fs(70)
                    radius: win.fs(23)
                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                    Glyph { win: sourcesFlick.win; anchors.centerIn: parent; width: 34; height: 34; name: "orbit"; tint: win.accent }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: design.space1
                    Text {
                        text: win.rtl ? "مصادر متعددة، تجربة واحدة." : "Many sources. One coherent store."
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(23)
                        font.bold: true
                    }
                    Text {
                        Layout.fillWidth: true
                        text: win.rtl
                            ? "Mo Store يوحّد البيانات والإدارة، ويُبقي المحركات المتخصصة متاحة عند الحاجة من دون تكرار المتاجر في القائمة."
                            : "Mo Store unifies discovery and management while keeping specialist engines available without duplicate storefronts."
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(11)
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: win.width > 1120 ? 2 : 1
            columnSpacing: 13
            rowSpacing: 13
            Repeater {
                model: [
                    {
                        id: "flathub", glyph: "shield",
                        ar: "Flathub · المصدر الأساسي", en: "Flathub · Primary source",
                        ar2: win.hasFlatpakCatalog()
                            ? "آلاف التطبيقات المعزولة، فهرس محلي، وأيقونات وبيانات AppStream حقيقية."
                            : "الكتالوج الأساسي فقط متاح الآن؛ اتصل بالإنترنت لتحديث فهرس التطبيقات الكامل.",
                        en2: win.hasFlatpakCatalog()
                            ? "Thousands of sandboxed apps with a local AppStream catalogue and real metadata."
                            : "Only the essential catalogue is available; connect to refresh the full app index.",
                        stateAr: win.hasFlatpakCatalog() ? "مدمج" : "يحتاج تحديثًا",
                        stateEn: win.hasFlatpakCatalog() ? "Integrated" : "Refresh needed",
                        action: win.hasFlatpakCatalog() ? "" : "refresh"
                    },
                    {
                        id: "bazaar", glyph: "grid",
                        ar: "Bazaar · كتالوج تطبيقات إضافي", en: "Bazaar · Additional app catalogue",
                        ar2: "واجهة متقدمة للكتالوج والحسابات والمفضلة. تبقى مخفية من قائمة النظام كي يظل Mo Store المتجر الوحيد.",
                        en2: "An advanced catalogue, account and favourites engine, kept out of the menu so Mo Store stays the one storefront.",
                        stateAr: "اختياري", stateEn: "Optional", action: "bazaar"
                    },
                    {
                        id: "discover", glyph: "monitor",
                        ar: "محرّك تحديثات النظام", en: "System update engine",
                        ar2: "للتحديثات والبرامج الثابتة وإضافات سطح المكتب. لا يفتح تثبيت حزم نظام عشوائية.",
                        en2: "For updates, firmware and desktop add-ons — never arbitrary host packages.",
                        stateAr: "متاح", stateEn: "Available", action: "discover"
                    },
                    {
                        id: "appimage", glyph: "external",
                        ar: "تنزيلات الناشر · مصادر خارجية", en: "Publisher downloads · External sources",
                        ar2: "يُسمح فقط بروابط الناشر الرسمية والوصفات المراجعة. لا تثبيت صامت لملفات غير موقّعة.",
                        en2: "Only reviewed recipes and official publisher links — never silent unverified executables.",
                        stateAr: "مقيّد بأمان", stateEn: "Safety restricted", action: ""
                    },
                    {
                        id: "permissions", glyph: "lock",
                        ar: "Flatseal · إدارة الصلاحيات", en: "Flatseal · Permissions",
                        ar2: "راجع وصول التطبيقات للملفات والكاميرا والميكروفون والشبكة.",
                        en2: "Review app access to files, camera, microphone and the network.",
                        stateAr: "أداة موصى بها", stateEn: "Recommended tool", action: "permissions"
                    },
                    {
                        id: "developer", glyph: "code",
                        ar: "أدوات المطور", en: "Developer tools",
                        ar2: "أدوات npm المراجعة تظهر بوضوح كمصدر متقدم؛ لا taps ولا أوامر shell حرة.",
                        en2: "Reviewed npm tools are clearly marked as advanced; their package scripts run only after explicit approval.",
                        stateAr: "مراجعة مطلوبة", stateEn: "Review required", action: ""
                    }
                ]
                delegate: Rectangle {
                    id: sourceCard
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.fs(168)
                    radius: win.fs(22)
                    color: sourceHover.hovered
                        ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.96)
                        : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.77)
                    border.width: 1
                    border.color: sourceHover.hovered ? win.accent : win.outline
                    HoverHandler { id: sourceHover }
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: design.space2
                        RowLayout {
                            Layout.fillWidth: true
                            Rectangle {
                                Layout.preferredWidth: win.fs(46)
                                Layout.preferredHeight: win.fs(46)
                                radius: design.radiusCard
                                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.13)
                                Glyph { win: sourcesFlick.win; anchors.centerIn: parent; width: 24; height: 24; name: sourceCard.modelData.glyph; tint: win.accent }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Text {
                                    text: win.rtl ? sourceCard.modelData.ar : sourceCard.modelData.en
                                    color: win.txt
                                    font.family: win.uiFont
                                    font.pixelSize: win.typePx(14)
                                    font.bold: true
                                }
                                Text {
                                    text: win.rtl ? sourceCard.modelData.stateAr : sourceCard.modelData.stateEn
                                    color: win.accent
                                    font.family: win.uiFont
                                    font.pixelSize: win.typePx(10)
                                    font.bold: true
                                }
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: win.rtl ? sourceCard.modelData.ar2 : sourceCard.modelData.en2
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(10)
                            wrapMode: Text.WordWrap
                            maximumLineCount: 3
                            elide: Text.ElideRight
                        }
                        Item { Layout.fillHeight: true }
                        ActionButton {
                            win: sourcesFlick.win
                            visible: sourceCard.modelData.action !== ""
                            enabled: !win.jobIsActive()
                            label: sourceCard.modelData.action === "permissions"
                                ? win.isInstalled(win.appById("com.github.tchx84.Flatseal"))
                                    ? (win.rtl ? "افتح الأداة" : "Open tool")
                                    : (win.rtl ? "ثبّت الأداة" : "Install tool")
                                : sourceCard.modelData.action === "refresh"
                                    ? (win.rtl ? "حدّث الفهرس" : "Refresh catalogue")
                                : sourceCard.modelData.action === "bazaar"
                                    && !win.isInstalled(win.appById("io.github.kolunmi.Bazaar"))
                                    ? (win.rtl ? "ثبّت المحرك وافتحه" : "Install & open engine")
                                : (win.rtl ? "فتح المحرك" : "Open engine")
                            glyphName: sourceCard.modelData.action === "permissions"
                                && !win.isInstalled(win.appById("com.github.tchx84.Flatseal"))
                                || sourceCard.modelData.action === "bazaar"
                                    && !win.isInstalled(win.appById("io.github.kolunmi.Bazaar"))
                                ? "download" : "external"
                            triggered: function() {
                                win.openSourceEngine(sourceCard.modelData.action)
                            }
                        }
                    }
                }
            }
        }
    }
}

pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — an app's page. A band in the app's own colour carries its picture, its name, who
// made it, where it comes from and its actions (Get · Open · Update, with the job's progress in the
// button; Remove… and Permissions… once it is installed). Under it: the facts that decide whether
// to install it (works here?, size, version, age rating, licence, Arabic, source), its screenshots
// whole and never cropped, what it is, what is new, what it may do and how safe that is, the
// publisher's links, more from the same developer and similar apps.
//
// It shows win.selectedApp; main.qml's openDetails() fills it and reads the app's details
// document. Back is the header's arrow, Escape, Backspace or Alt+Left.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: appPage
    required property var win
    readonly property var design: win.design
    readonly property var app: win.selectedApp
    readonly property var details: win.selectedDetails
    readonly property real padding: appPage.width > win.fs(1000) ? design.space6 : design.space5
    readonly property string kind: win.appKind(appPage.app)
    readonly property bool installed: win.isInstalled(appPage.app)
    readonly property var compat: win.compatOf(appPage.app)
    readonly property color brand: win.appColour(appPage.app)
    readonly property color base: win.plateColour(appPage.brand)
    readonly property color ink: win.inkOn(appPage.base)
    readonly property bool inkIsLight: win.luminanceOf(appPage.ink) > 0.5
    property bool moreDescription: false

    anchors.fill: parent
    visible: win.page === "app" && appPage.app !== null
    transform: pageEnter.shift
    PageEnter { id: pageEnter; win: appPage.win; target: appPage }

    Connections {
        target: appPage.win
        function onSelectedAppChanged() {
            detailFlick.contentY = 0
            appPage.moreDescription = false
        }
    }

    // ── what the page shows, computed once per app ──
    readonly property var release: appPage.details && appPage.details.releases && appPage.details.releases.length
                                   ? appPage.details.releases[0] : null
    readonly property var shots: appPage.details && appPage.details.screenshots ? appPage.details.screenshots : []
    readonly property var links: {
        var urls = appPage.details && appPage.details.urls ? appPage.details.urls : ({})
        var out = []
        var spec = [
            { key: "homepage",   ar: "موقع التطبيق",    en: "Website",           glyph: "external" },
            { key: "help",       ar: "المساعدة",        en: "Help",              glyph: "help" },
            { key: "donation",   ar: "ادعم المطوّر",     en: "Support the developer", glyph: "heart" },
            { key: "bugtracker", ar: "أبلغ عن مشكلة",   en: "Report a problem",  glyph: "report" }
        ]
        for (var i = 0; i < spec.length; ++i)
            if (appPage.win.isSafeLink(urls[spec[i].key]))
                out.push({ url: urls[spec[i].key], ar: spec[i].ar, en: spec[i].en, glyph: spec[i].glyph })
        if (out.length === 0 && appPage.app && appPage.app.install && appPage.win.isSafeLink(appPage.app.install.url))
            out.push({ url: appPage.app.install.url, ar: "موقع الناشر", en: "Publisher's website", glyph: "external" })
        return out
    }
    readonly property var fromDeveloper: {
        var app = appPage.app
        var who = app && app.developer ? ("" + app.developer).toLowerCase() : ""
        var out = []
        if (who === "") return out
        var order = appPage.win.browseOrder
        for (var i = 0; i < order.length && out.length < 12; ++i)
            if (order[i] !== app && ("" + (order[i].developer || "")).toLowerCase() === who) out.push(order[i])
        return out
    }
    readonly property var similar: {
        var app = appPage.app
        var out = []
        if (!app) return out
        var order = appPage.win.browseOrder
        for (var pass = 0; pass < 2 && out.length < 12; ++pass) {
            for (var i = 0; i < order.length && out.length < 12; ++i) {
                var other = order[i]
                if (other === app || other.cat !== app.cat || out.indexOf(other) >= 0) continue
                if (appPage.fromDeveloper.indexOf(other) >= 0) continue
                if (pass === 0 && other.family !== app.family) continue
                out.push(other)
            }
        }
        return out
    }
    readonly property int arabicShare: appPage.details && appPage.details.languages
                                       && appPage.details.languages.ar !== undefined
                                       ? Number(appPage.details.languages.ar) : -1
    readonly property bool knowsLanguages: appPage.details && appPage.details.languages
                                           && Object.keys(appPage.details.languages).length > 0
    readonly property var fact: appPage.win.factOf(appPage.app)
    readonly property real downloadBytes: {
        var fact = appPage.fact
        if (fact && fact.download > 0) return fact.download
        var install = appPage.app && appPage.app.install
        if (install && install.downloads && install.downloads[appPage.win.machineArch])
            return Number(install.downloads[appPage.win.machineArch].size || 0)
        if (install && install.size) return Number(install.size)
        return 0
    }
    readonly property var tiles: {
        var app = appPage.app
        if (!app) return []
        var win = appPage.win
        var out = []
        if (appPage.compat.known)
            out.push({ caption: win.local("على هذا الجهاز", "On this PC"), value: win.compatTitle(appPage.compat.verdict),
                       detail: appPage.compat.reasons.length ? win.compatReasonText(appPage.compat.reasons[0]) : "",
                       glyph: appPage.compat.verdict === "blocked" ? "danger" : appPage.compat.verdict === "warn" ? "warning" : "check",
                       tone: appPage.compat.verdict === "blocked" ? win.dangerInk : appPage.compat.verdict === "warn" ? win.warningInk : win.positiveInk })
        if (appPage.downloadBytes > 0 || (appPage.fact && appPage.fact.installed > 0))
            out.push({ caption: win.local("الحجم", "Size"),
                       value: appPage.downloadBytes > 0 ? win.sizeText(appPage.downloadBytes) : win.sizeText(appPage.fact.installed),
                       detail: appPage.fact && appPage.fact.installed > 0
                               ? win.local("بعد التثبيت ", "Installed ") + win.sizeText(appPage.fact.installed) : win.local("للتنزيل", "To download"),
                       glyph: "download", tone: win.accent })
        // The version on this computer when it is installed, the newest one otherwise; the date only
        // belongs to the release it names, and an update says what it brings.
        var installedVersion = win.isInstalled(app) ? "" + (app.installed_version || "") : ""
        var pending = win.updateFor(app)
        var target = !pending ? "" : pending.kind === "pin" ? "" + (pending.version || "") : "" + (app.version || "")
        var version = installedVersion || (appPage.release ? "" + appPage.release.version : "") || "" + (app.version || "")
        if (version !== "") {
            var versionDetail = ""
            if (target !== "" && target !== version)
                versionDetail = win.local("يتوفر الإصدار ", "Version ") + win.ltr(target) + win.local("", " is out")
            else if (appPage.release && appPage.release.date && "" + appPage.release.version === version)
                versionDetail = win.dateText(appPage.release.date)
            out.push({ caption: win.local("الإصدار", "Version"), value: win.ltr(version),
                       detail: versionDetail, glyph: "refresh", tone: win.accent })
        }
        if (app.content_rating !== undefined && app.content_rating !== null)
            out.push({ caption: win.local("العمر", "Age"), value: win.contentRatingText(app.content_rating),
                       detail: "", glyph: "user", tone: win.accent })
        var licence = win.licenceKind(app)
        if (licence !== "unknown")
            out.push({ caption: win.local("الترخيص", "Licence"),
                       value: licence === "free" ? win.local("حر ومجاني", "Free") : win.local("مملوك", "Proprietary"),
                       detail: licence === "free" ? win.local("مفتوح المصدر", "Open source") : "",
                       glyph: "document", tone: win.accent })
        if (appPage.knowsLanguages)
            out.push({ caption: win.local("اللغة", "Language"),
                       value: appPage.arabicShare >= 50 ? win.local("واجهة عربية", "Arabic interface")
                            : appPage.arabicShare > 0 ? win.local("عربية جزئيًا", "Partly in Arabic")
                            : win.local("لا عربية بعد", "Not in Arabic yet"),
                       detail: appPage.arabicShare > 0 ? win.ltr(Math.round(appPage.arabicShare) + "%") : "",
                       glyph: "chat", tone: appPage.arabicShare >= 50 ? win.positiveInk : win.accent })
        if (appPage.kind === "webapp") {
            out.push({ caption: win.local("يفتح في", "Opens in"), value: win.local("نافذته الخاصة", "Its own window"),
                       detail: win.local("بعيدًا عن متصفحك", "Apart from your browser"), glyph: "system", tone: win.accent })
            var identity = app.install && app.install.identity ? app.install.identity : []
            var names = { "google": "Google", "microsoft": "Microsoft", "apple": "Apple", "github": "GitHub" }
            var accounts = []
            for (var a = 0; a < identity.length; ++a) if (names[identity[a]]) accounts.push(names[identity[a]])
            if (accounts.length)
                out.push({ caption: win.local("الدخول بحساب", "Sign in with"), value: win.ltr(accounts.join(" · ")),
                           detail: "", glyph: "user", tone: win.accent })
        }
        out.push({ caption: win.local("المصدر", "Source"), value: win.kindLabel(appPage.kind),
                   detail: app.verified === true ? win.local("ناشر موثّق", "Verified publisher") : "",
                   glyph: win.kindGlyph(appPage.kind), tone: win.accent })
        return out
    }

    Flickable {
        id: detailFlick
        objectName: "detailFlick"
        anchors.fill: parent
        contentWidth: width
        contentHeight: detailBody.implicitHeight + appPage.design.space6 * 2 + appPage.win.footClearance
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(detailFlick, event)
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: detailBody
            x: appPage.padding
            y: appPage.design.space2
            width: detailFlick.width - appPage.padding * 2
            spacing: appPage.design.space5

            // ── the band ──
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: bandContent.implicitHeight + appPage.design.space6 * 2
                SoftShadow { win: appPage.win; radius: appPage.design.radiusPanel; strength: 1.5; lift: appPage.design.space3 }
                Rectangle {
                    id: band
                    anchors.fill: parent
                    radius: appPage.design.radiusPanel
                    clip: true
                    gradient: Gradient {
                        GradientStop { position: 0; color: appPage.inkIsLight ? appPage.base : Qt.lighter(appPage.base, 1.08) }
                        GradientStop { position: 1; color: appPage.inkIsLight ? Qt.darker(appPage.base, 1.35) : appPage.base }
                    }
                    Repeater {
                        model: 3
                        delegate: Rectangle {
                            required property int index
                            width: band.height * (1.5 + index * 0.55)
                            height: width
                            radius: width / 2
                            x: appPage.win.rtl ? -width * 0.42 : band.width - width * 0.58
                            y: -height * 0.18
                            color: index === 0 ? appPage.win.tint(appPage.ink, 0.06) : "transparent"
                            border.width: Math.max(1, appPage.win.fs(1.5))
                            border.color: appPage.win.tint(appPage.ink, 0.15 - index * 0.04)
                        }
                    }
                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "transparent"
                        border.width: 1
                        border.color: appPage.win.tint(appPage.ink, 0.14)
                    }
                }
                RowLayout {
                    id: bandContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: appPage.design.space6
                    anchors.rightMargin: appPage.design.space6
                    spacing: appPage.design.space5

                    Item {
                        Layout.preferredWidth: appPage.win.fs(128)
                        Layout.preferredHeight: appPage.win.fs(128)
                        Layout.alignment: Qt.AlignTop
                        AppIcon {
                            win: appPage.win
                            anchors.fill: parent
                            app: appPage.app
                            size: appPage.win.fs(128)
                            lifted: true
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: appPage.design.space2
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: appPage.win.localName(appPage.app)
                            color: appPage.ink
                            font.family: appPage.win.uiFont
                            font.pixelSize: appPage.win.typePx(32)
                            font.weight: Font.Bold
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                            Accessible.role: Accessible.Heading
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: appPage.design.space2
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.maximumWidth: detailBody.width * 0.5
                                text: appPage.win.publisherLine(appPage.app)
                                color: appPage.win.tint(appPage.ink, 0.86)
                                font.family: appPage.win.uiFont
                                font.pixelSize: appPage.win.typePx(15)
                                elide: Text.ElideRight
                            }
                            Rectangle {
                                visible: appPage.app !== null && appPage.app.verified === true
                                Layout.preferredHeight: appPage.win.fs(24)
                                Layout.preferredWidth: verifiedRow.implicitWidth + appPage.design.space3 * 2
                                radius: height / 2
                                color: appPage.win.tint(appPage.ink, 0.18)
                                RowLayout {
                                    id: verifiedRow
                                    anchors.centerIn: parent
                                    spacing: appPage.design.space1
                                    Glyph { win: appPage.win; name: "check"; tint: appPage.ink; Layout.preferredWidth: appPage.win.fs(13); Layout.preferredHeight: appPage.win.fs(13) }
                                    Text {
                                        text: appPage.win.local("موثّق", "Verified")
                                        color: appPage.ink
                                        font.family: appPage.win.uiFont
                                        font.pixelSize: appPage.win.typePx(12)
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }
                            Item { Layout.fillWidth: true }
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            visible: text !== ""
                            text: appPage.win.systemManagedOnly(appPage.app)
                                ? appPage.win.local("مثبّت لكل مستخدمي هذا الجهاز، فيُدار مع النظام", "Installed for everyone on this computer, so it is managed with the system")
                                : appPage.installed && appPage.app && appPage.app.installed_version
                                    ? appPage.win.local("مثبّت · الإصدار ", "Installed · version ") + appPage.win.ltr(appPage.app.installed_version)
                                    : appPage.installed ? appPage.win.local("مثبّت على هذا الجهاز", "Installed on this computer") : ""
                            color: appPage.win.tint(appPage.ink, 0.74)
                            font.family: appPage.win.uiFont
                            font.pixelSize: appPage.win.typePx(13)
                            elide: Text.ElideRight
                        }
                        RowLayout {
                            Layout.topMargin: appPage.design.space2
                            spacing: appPage.design.space3
                            ProgressButton {
                                win: appPage.win
                                app: appPage.app
                                large: true
                                prominent: true
                                onColour: true
                                colourInk: appPage.ink
                                colourBase: appPage.base
                            }
                            ActionButton {
                                win: appPage.win
                                visible: appPage.installed && appPage.win.canChangePermissions(appPage.app)
                                pill: true
                                implicitHeight: appPage.win.fs(44)
                                label: appPage.win.local("الأذونات…", "Permissions…")
                                glyphName: "lock"
                                surfaceColor: appPage.win.tint(appPage.ink, 0.16)
                                textColor: appPage.ink
                                outlineColor: appPage.win.tint(appPage.ink, 0.32)
                                accentColor: appPage.ink
                                triggered: function() { appPage.win.openPermissions(appPage.app) }
                            }
                            ActionButton {
                                win: appPage.win
                                visible: win.canRemove(win.selectedApp)
                                enabled: !win.jobIsActive()
                                pill: true
                                implicitHeight: appPage.win.fs(44)
                                label: appPage.win.local("إزالة…", "Remove…")
                                glyphName: "trash"
                                surfaceColor: appPage.win.tint(appPage.ink, 0.16)
                                textColor: appPage.ink
                                outlineColor: appPage.win.tint(appPage.ink, 0.32)
                                accentColor: appPage.ink
                                triggered: function() { appPage.win.openRemove(appPage.app) }
                            }
                        }
                    }
                }
            }

            // ── the facts ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: tileFlow.implicitHeight + appPage.design.space2 * 2
                visible: appPage.tiles.length > 0
                radius: appPage.design.radiusCard + 2
                color: appPage.win.cardColor
                border.width: 1
                border.color: appPage.win.cardBorder
                Flow {
                    id: tileFlow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    // As many to a row as fit their words, in rows of even length (seven on a narrow
                    // window is four and three, never six and a lonely one).
                    readonly property int fits: Math.max(1, Math.floor(width / appPage.win.fs(150)))
                    readonly property int rows: Math.max(1, Math.ceil(appPage.tiles.length / tileFlow.fits))
                    readonly property int perRow: Math.max(1, Math.ceil(appPage.tiles.length / tileFlow.rows))
                    Repeater {
                        model: appPage.tiles
                        delegate: Item {
                            id: tileCell
                            required property var modelData
                            required property int index
                            width: tileFlow.width / tileFlow.perRow
                            height: appPage.win.fs(92)
                            InfoTile {
                                win: appPage.win
                                anchors.fill: parent
                                caption: tileCell.modelData.caption
                                value: tileCell.modelData.value
                                detail: tileCell.modelData.detail
                                glyph: tileCell.modelData.glyph
                                tone: tileCell.modelData.tone
                            }
                            Rectangle {
                                visible: (tileCell.index + 1) % tileFlow.perRow !== 0
                                         && tileCell.index !== appPage.tiles.length - 1
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: 1
                                height: parent.height * 0.56
                                color: appPage.win.cardBorder
                            }
                        }
                    }
                }
            }

            // ── screenshots ──
            ScreenshotStrip {
                win: appPage.win
                Layout.fillWidth: true
                shots: appPage.shots
                loading: appPage.win.detailsState === "loading"
                visible: appPage.shots.length > 0 || appPage.win.detailsState === "loading"
            }

            // ── what it is ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: appPage.design.space3
                Text {
                    Layout.fillWidth: true
                    text: win.localSummary(win.selectedApp)
                    textFormat: Text.PlainText
                    color: appPage.win.txt
                    font.family: appPage.win.uiFont
                    font.pixelSize: appPage.win.typePx(20)
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }
                Item {
                    id: descriptionBox
                    Layout.fillWidth: true
                    // Long descriptions open at six lines with a fade and a "More"; the text itself is
                    // always whole: it is clipped by this box, never cut short.
                    readonly property real fullHeight: descriptionText.implicitHeight
                    readonly property real shortHeight: descriptionText.font.pixelSize * 1.35 * 6
                    readonly property bool long: descriptionBox.fullHeight > descriptionBox.shortHeight + appPage.design.space4
                    visible: descriptionText.text !== "" && descriptionText.text !== win.localSummary(win.selectedApp)
                    Layout.preferredHeight: appPage.moreDescription || !descriptionBox.long
                                            ? descriptionBox.fullHeight : descriptionBox.shortHeight
                    clip: true
                    Behavior on Layout.preferredHeight {
                        NumberAnimation { duration: appPage.win.motionEnabled ? appPage.design.motionGeometry : 0; easing.type: Easing.OutCubic }
                    }
                    Text {
                        id: descriptionText
                        width: parent.width
                        text: win.localDescription(win.selectedApp)
                        textFormat: Text.PlainText
                        color: appPage.win.txt2
                        font.family: appPage.win.uiFont
                        font.pixelSize: appPage.win.typePx(14)
                        wrapMode: Text.WordWrap
                        lineHeight: 1.35
                    }
                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: appPage.win.fs(48)
                        visible: descriptionBox.long && !appPage.moreDescription
                        gradient: Gradient {
                            GradientStop { position: 0; color: appPage.win.tint(appPage.win.canvas, 0) }
                            GradientStop { position: 1; color: appPage.win.canvas }
                        }
                    }
                }
                ActionButton {
                    win: appPage.win
                    visible: descriptionBox.visible && descriptionBox.long
                    compact: true
                    pill: true
                    label: appPage.moreDescription ? appPage.win.local("أقل", "Less") : appPage.win.local("المزيد", "More")
                    triggered: function() { appPage.moreDescription = !appPage.moreDescription }
                }
            }

            // ── what is new, and what it may do ──
            GridLayout {
                Layout.fillWidth: true
                columns: detailBody.width > appPage.win.fs(860) ? 2 : 1
                columnSpacing: appPage.design.space4
                rowSpacing: appPage.design.space4

                // What's new.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredHeight: newsColumn.implicitHeight + appPage.design.space5 * 2
                    radius: appPage.design.radiusCard + 2
                    color: appPage.win.cardColor
                    border.width: 1
                    border.color: appPage.win.cardBorder
                    ColumnLayout {
                        id: newsColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: appPage.design.space5
                        spacing: appPage.design.space3
                        SectionHeader {
                            win: appPage.win
                            Layout.fillWidth: true
                            title: appPage.win.local("ما الجديد", "What's new")
                            subtitle: appPage.release
                                ? appPage.win.local("الإصدار ", "Version ") + appPage.win.ltr(appPage.release.version || "")
                                  + (appPage.release.date ? "  ·  " + appPage.win.dateText(appPage.release.date) : "")
                                : ""
                            glyph: "spark"
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: !appPage.release
                                ? (appPage.win.detailsState === "loading" ? appPage.win.local("يُقرأ…", "Reading…")
                                   : appPage.kind === "webapp" || appPage.kind === "web"
                                     ? appPage.win.local("تطبيقات الويب هي دائمًا أحدث ما نشره الناشر على موقعه.",
                                                         "A web app is always the latest version its publisher runs on their site.")
                                   : appPage.app && appPage.app.install && appPage.app.install.version
                                     ? (appPage.win.rtl ? "الإصدار " + appPage.win.ltr(appPage.app.install.version) + "، كما نشره ناشره، ويطابق بصمته."
                                                        : "Version " + appPage.app.install.version + ", as its publisher released it, matched to its fingerprint.")
                                   : appPage.win.local("لا يعرف المتجر سجل إصدارات هذا التطبيق بعد.", "The Store does not know this app's release history yet."))
                                : (appPage.release.notes && appPage.release.notes !== ""
                                   ? appPage.release.notes
                                   : appPage.win.local("لم ينشر المطوّر ملاحظات لهذا الإصدار.", "The developer published no notes for this version."))
                            textFormat: Text.PlainText
                            color: appPage.win.txt2
                            font.family: appPage.win.uiFont
                            font.pixelSize: appPage.win.typePx(13)
                            wrapMode: Text.WordWrap
                            lineHeight: 1.3
                            maximumLineCount: 10
                            elide: Text.ElideRight
                        }
                        Repeater {
                            model: appPage.details && appPage.details.releases ? appPage.details.releases.slice(1, 3) : []
                            delegate: RowLayout {
                                id: earlier
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: appPage.design.space2
                                Rectangle {
                                    Layout.preferredWidth: appPage.win.fs(6)
                                    Layout.preferredHeight: appPage.win.fs(6)
                                    radius: width / 2
                                    color: appPage.win.txt2
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: appPage.win.local("الإصدار ", "Version ") + appPage.win.ltr(earlier.modelData.version || "")
                                          + (earlier.modelData.date ? "  ·  " + appPage.win.dateText(earlier.modelData.date) : "")
                                    color: appPage.win.txt2
                                    font.family: appPage.win.uiFont
                                    font.pixelSize: appPage.win.typePx(12)
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                // Permissions and safety.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredHeight: safetyColumn.implicitHeight + appPage.design.space5 * 2
                    radius: appPage.design.radiusCard + 2
                    color: appPage.win.cardColor
                    border.width: 1
                    border.color: appPage.win.cardBorder
                    ColumnLayout {
                        id: safetyColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: appPage.design.space5
                        spacing: appPage.design.space3
                        SectionHeader {
                            win: appPage.win
                            Layout.fillWidth: true
                            title: appPage.win.local("الأذونات والأمان", "Permissions and safety")
                            glyph: "shield"
                        }
                        SafetyLabel { win: appPage.win; Layout.fillWidth: true; app: appPage.app }
                        // An app from outside the sandboxed catalogue is reviewed before it installs,
                        // and the page says so before the button is pressed (once it is installed
                        // the note has nothing left to warn about). The OR-chain is `undefined` for
                        // an app with no recipe; `!!` keeps the binding a boolean.
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: reviewNote.implicitHeight + appPage.design.space3 * 2
                            visible: win.selectedApp !== null && !!(win.selectedApp.requires_review === true
                                                                    || (win.selectedApp.install
                                                                        && win.selectedApp.install.requires_review === true)
                                                                    || (win.selectedApp.install && win.selectedApp.install.kind === "npm"))
                                     && !appPage.win.isInstalled(win.selectedApp)
                            radius: appPage.design.radiusControl
                            color: appPage.win.tint(appPage.win.warningInk, appPage.win.lightScheme ? 0.10 : 0.12)
                            Text {
                                id: reviewNote
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.margins: appPage.design.space3
                                text: appPage.win.local("يأتي من خارج الكتالوج المعزول، فيعرض عليك المتجر مصدره وطريقة تثبيته قبل أن يبدأ.",
                                                        "It comes from outside the sandboxed catalogue, so the Store shows you its source and how it installs before anything starts.")
                                color: appPage.win.txt
                                font.family: appPage.win.uiFont
                                font.pixelSize: appPage.win.typePx(12)
                                wrapMode: Text.WordWrap
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: win.selectedApp !== null && !!win.selectedApp.license
                            text: appPage.win.local("الترخيص: ", "Licence: ")
                                  + appPage.win.ltr(win.selectedApp && win.selectedApp.license ? "" + win.selectedApp.license : "")
                            color: appPage.win.txt2
                            font.family: appPage.win.uiFont
                            font.pixelSize: appPage.win.typePx(12)
                            wrapMode: Text.WordWrap
                        }
                        Repeater {
                            model: appPage.win.permissionRowsFor(appPage.app)
                            delegate: PermissionRow {
                                required property var modelData
                                win: appPage.win
                                Layout.fillWidth: true
                                key: modelData.key
                                allowed: modelData.allowed
                                ask: modelData.ask
                                requested: modelData.requested === true
                                mode: "info"
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: text !== ""
                            text: appPage.win.permissionState === "loading" ? appPage.win.local("تُقرأ الأذونات…", "Reading its permissions…")
                                : appPage.win.permissionState === "unsupported" ? appPage.win.needsUpdateText
                                // Full access and Android's own settings are already the safety line above;
                                // only "not installed" (the backend found no app) adds something.
                                : appPage.win.permissionState === "ready" && appPage.win.permissionDoc
                                  && appPage.win.permissionDoc.note_key === "not_installed"
                                    ? appPage.win.permissionNoteText(appPage.win.permissionDoc.note_key)
                                : appPage.win.permissionState === "facts" && appPage.kind === "flatpak" && !appPage.fact
                                    ? appPage.win.local("سيعرض المتجر ما يطلبه بعد قراءة الكتالوج.", "The Store shows what it asks for once the catalogue is read.")
                                : ""
                            color: appPage.win.txt2
                            font.family: appPage.win.uiFont
                            font.pixelSize: appPage.win.typePx(12)
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: appPage.app !== null && !!appPage.app.compat
                                     && (appPage.app.compat.reasons || []).indexOf("not_verified") >= 0
                            text: appPage.win.compatReasonText("not_verified")
                            color: appPage.win.warningInk
                            font.family: appPage.win.uiFont
                            font.pixelSize: appPage.win.typePx(12)
                            wrapMode: Text.WordWrap
                        }
                        ActionButton {
                            win: appPage.win
                            visible: appPage.win.canChangePermissions(appPage.app)
                            pill: true
                            compact: true
                            label: appPage.win.local("غيّر الأذونات…", "Change permissions…")
                            glyphName: "settings"
                            triggered: function() { appPage.win.openPermissions(appPage.app) }
                        }
                    }
                }
            }

            // ── works here? the reasons, in words ──
            Rectangle {
                Layout.fillWidth: true
                visible: appPage.compat.known && appPage.compat.reasons.length + appPage.compat.notes.length > 0
                Layout.preferredHeight: compatColumn.implicitHeight + appPage.design.space5 * 2
                radius: appPage.design.radiusCard + 2
                color: appPage.win.cardColor
                border.width: 1
                border.color: appPage.win.cardBorder
                ColumnLayout {
                    id: compatColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: appPage.design.space5
                    spacing: appPage.design.space3
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: appPage.design.space3
                        Text {
                            Layout.fillWidth: true
                            text: appPage.win.local("على هذا الجهاز", "On this PC")
                            color: appPage.win.txt
                            font.family: appPage.win.uiFont
                            font.pixelSize: appPage.win.typePx(20)
                            font.weight: Font.Bold
                        }
                        CompatBadge { win: appPage.win; app: appPage.app }
                    }
                    Repeater {
                        model: appPage.compat.reasons.concat(appPage.compat.notes)
                        delegate: RowLayout {
                            id: reasonRow
                            required property var modelData
                            readonly property bool note: appPage.compat.notes.indexOf(reasonRow.modelData) >= 0
                            Layout.fillWidth: true
                            spacing: appPage.design.space3
                            Glyph {
                                win: appPage.win
                                name: reasonRow.note ? "about" : appPage.compat.verdict === "blocked" ? "danger" : "warning"
                                tint: reasonRow.note ? appPage.win.txt2
                                    : appPage.compat.verdict === "blocked" ? appPage.win.dangerInk : appPage.win.warningInk
                                Layout.preferredWidth: appPage.win.fs(16)
                                Layout.preferredHeight: appPage.win.fs(16)
                            }
                            Text {
                                Layout.fillWidth: true
                                text: appPage.win.compatReasonText(reasonRow.modelData)
                                color: appPage.win.txt
                                font.family: appPage.win.uiFont
                                font.pixelSize: appPage.win.typePx(14)
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            // ── the publisher's links ──
            Flow {
                Layout.fillWidth: true
                spacing: appPage.design.space2
                visible: appPage.links.length > 0
                Repeater {
                    model: appPage.links
                    delegate: ActionButton {
                        id: linkButton
                        required property var modelData
                        win: appPage.win
                        pill: true
                        compact: true
                        label: appPage.win.rtl ? linkButton.modelData.ar : linkButton.modelData.en
                        glyphName: linkButton.modelData.glyph
                        Accessible.description: linkButton.modelData.url
                        triggered: function() { appPage.win.openLink(linkButton.modelData.url) }
                    }
                }
            }

            // ── more from the developer, and similar apps ──
            CollectionRow {
                win: appPage.win
                Layout.fillWidth: true
                visible: appPage.fromDeveloper.length > 0
                canSeeAll: false
                bleed: appPage.padding
                collection: ({ id: "developer", glyph: "user", apps: appPage.fromDeveloper,
                               ar: "المزيد من " + (appPage.app && appPage.app.developer ? appPage.app.developer : ""),
                               en: "More from " + (appPage.app && appPage.app.developer ? appPage.app.developer : "") })
            }
            CollectionRow {
                win: appPage.win
                Layout.fillWidth: true
                visible: appPage.similar.length > 0
                canSeeAll: false
                bleed: appPage.padding
                collection: ({ id: "similar", glyph: "grid", apps: appPage.similar,
                               ar: "تطبيقات مشابهة", en: "Similar apps" })
            }
        }
    }
}

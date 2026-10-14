pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — Settings: automatic app updates; whether app pictures may load from the internet;
// whether this computer is ready for Windows programs and Android apps (with the existing one-time
// setups); where apps come from, said honestly; adding an app from a file; the catalogue itself;
// and, under Advanced, the optional second catalogue.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: settingsPage
    required property var win
    readonly property var design: win.design
    readonly property real padding: settingsPage.width > win.fs(1000) ? design.space6 : design.space5
    readonly property var engines: win.indexEngines
    readonly property bool hasWindows: settingsPage.engines === null || settingsPage.engines === undefined
                                       || settingsPage.engines.indexOf("windows") >= 0
    readonly property bool hasAndroid: settingsPage.engines === null || settingsPage.engines === undefined
                                       || settingsPage.engines.indexOf("android") >= 0
    readonly property var windowsState: win.machine && win.machine.windows ? win.machine.windows : null
    readonly property var androidState: win.machine && win.machine.android ? win.machine.android : null

    anchors.fill: parent
    visible: win.page === "settings"
    transform: pageEnter.shift
    PageEnter { id: pageEnter; win: settingsPage.win; target: settingsPage }

    Flickable {
        id: settingsFlick
        objectName: "settingsFlick"
        anchors.fill: parent
        contentWidth: width
        contentHeight: settingsBody.implicitHeight + settingsPage.design.space6 * 2 + settingsPage.win.footClearance
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(settingsFlick, event)
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: settingsBody
            x: Math.max(settingsPage.padding, (settingsFlick.width - width) / 2)
            y: settingsPage.design.space2
            width: Math.min(settingsFlick.width - settingsPage.padding * 2, settingsPage.win.fs(980))
            spacing: settingsPage.design.space5

            // ── updates ──
            SettingsGroup {
                win: settingsPage.win
                Layout.fillWidth: true
                title: settingsPage.win.local("التحديثات", "Updates")
                AutoUpdateRow { win: settingsPage.win; Layout.fillWidth: true }
            }

            // ── pictures ──
            SettingsGroup {
                win: settingsPage.win
                Layout.fillWidth: true
                title: settingsPage.win.local("الصور", "Pictures")
                RowLayout {
                    Layout.fillWidth: true
                    spacing: settingsPage.design.space4
                    Rectangle {
                        Layout.preferredWidth: settingsPage.win.fs(40)
                        Layout.preferredHeight: settingsPage.win.fs(40)
                        radius: settingsPage.design.radiusControl
                        color: settingsPage.win.tint(settingsPage.win.accent, settingsPage.win.lightScheme ? 0.14 : 0.18)
                        Glyph {
                            win: settingsPage.win
                            anchors.centerIn: parent
                            width: settingsPage.win.fs(20)
                            height: width
                            name: "image"
                            tint: settingsPage.win.accent
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: settingsPage.win.local("حمّل صور التطبيقات من الإنترنت", "Load app pictures from the internet")
                            color: settingsPage.win.txt
                            font.family: settingsPage.win.uiFont
                            font.pixelSize: settingsPage.win.typePx(15)
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: settingsPage.win.remotePictures
                                ? settingsPage.win.local("لقطات الشاشة وبعض الأيقونات تأتي من مواقع الناشرين عند فتح صفحة تطبيق، فيعرف ذلك الموقع أنك فتحتها.",
                                                         "Screenshots and some icons come from publishers' sites when you open an app's page, so that site learns you opened it.")
                                : settingsPage.win.local("متوقف: لا يحمّل المتجر أي صورة من الإنترنت، وتبقى صفحات التطبيقات نصًا وأيقونات محلية.",
                                                         "Off: the Store loads no picture from the internet; app pages keep their words and local icons.")
                            color: settingsPage.win.txt2
                            font.family: settingsPage.win.uiFont
                            font.pixelSize: settingsPage.win.typePx(13)
                            wrapMode: Text.WordWrap
                        }
                    }
                    Rectangle {
                        id: pictureTrack
                        Layout.preferredWidth: settingsPage.win.fs(52)
                        Layout.preferredHeight: settingsPage.win.fs(30)
                        radius: height / 2
                        color: settingsPage.win.remotePictures ? settingsPage.win.accent
                             : settingsPage.win.tint(settingsPage.win.txt, settingsPage.win.lightScheme ? 0.18 : 0.22)
                        activeFocusOnTab: true
                        Accessible.role: Accessible.CheckBox
                        Accessible.name: settingsPage.win.local("حمّل صور التطبيقات من الإنترنت", "Load app pictures from the internet")
                        Accessible.checkable: true
                        Accessible.checked: settingsPage.win.remotePictures
                        Accessible.onToggleAction: settingsPage.win.setRemotePictures(!settingsPage.win.remotePictures)
                        Accessible.onPressAction: settingsPage.win.setRemotePictures(!settingsPage.win.remotePictures)
                        Keys.onSpacePressed: settingsPage.win.setRemotePictures(!settingsPage.win.remotePictures)
                        Keys.onReturnPressed: settingsPage.win.setRemotePictures(!settingsPage.win.remotePictures)
                        FocusRing { win: settingsPage.win }
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: settingsPage.win.setRemotePictures(!settingsPage.win.remotePictures) }
                        Behavior on color { ColorAnimation { duration: settingsPage.win.motionEnabled ? settingsPage.design.motionFast : 0 } }
                        Rectangle {
                            width: pictureTrack.height - 6
                            height: width
                            radius: width / 2
                            y: 3
                            x: settingsPage.win.remotePictures !== settingsPage.win.rtl ? pictureTrack.width - width - 3 : 3
                            color: settingsPage.win.remotePictures ? settingsPage.win.accentText : settingsPage.win.canvas
                            Behavior on x { NumberAnimation { duration: settingsPage.win.motionEnabled ? settingsPage.design.motionPress : 0; easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }

            // ── this computer ──
            SettingsGroup {
                win: settingsPage.win
                Layout.fillWidth: true
                title: settingsPage.win.local("هذا الجهاز", "This computer")
                ReadinessRow {
                    win: settingsPage.win
                    Layout.fillWidth: true
                    glyph: "system"
                    title: settingsPage.win.local("برامج ويندوز", "Windows programs")
                    available: settingsPage.hasWindows
                    ready: settingsPage.windowsState ? settingsPage.windowsState.ready === true : settingsPage.hasWindows
                    known: settingsPage.windowsState !== null || !settingsPage.hasWindows
                    line: !settingsPage.hasWindows
                        ? settingsPage.win.local("لا يتضمن هذا الإصدار من MoOS ما يشغّل برامج ويندوز على هذا النوع من الحواسيب.",
                                                 "This edition of MoOS has nothing to run Windows programs on this kind of computer.")
                        : settingsPage.windowsState && settingsPage.windowsState.ready === true
                          ? (settingsPage.windowsState.x86_32 === true
                             ? settingsPage.win.local("جاهز. كل برنامج يحصل على مساحته الخاصة، ويُنزَّل من ناشره.",
                                                      "Ready. Each program gets a space of its own and comes from its publisher.")
                             : settingsPage.win.local("جاهز لبرامج 64-بت. كل برنامج يحصل على مساحته الخاصة، ويُنزَّل من ناشره.",
                                                      "Ready for 64-bit programs. Each gets a space of its own and comes from its publisher."))
                          : settingsPage.win.local("يحتاج إعدادًا لمرة واحدة قبل أول برنامج.", "Needs a one-time setup before the first program.")
                    action: settingsPage.windowsState && settingsPage.windowsState.ready === false ? "setup-windows" : ""
                }
                ReadinessRow {
                    win: settingsPage.win
                    Layout.fillWidth: true
                    glyph: "phone"
                    title: settingsPage.win.local("تطبيقات أندرويد", "Android apps")
                    available: settingsPage.hasAndroid
                    ready: settingsPage.androidState ? settingsPage.androidState.ready === true && settingsPage.androidState.initialized !== false
                                                     : settingsPage.hasAndroid
                    known: settingsPage.androidState !== null || !settingsPage.hasAndroid
                    line: !settingsPage.hasAndroid
                        ? settingsPage.win.local("لا يتضمن هذا الإصدار من MoOS ما يشغّل تطبيقات أندرويد على هذا النوع من الحواسيب.",
                                                 "This edition of MoOS has nothing to run Android apps on this kind of computer.")
                        : settingsPage.androidState && settingsPage.androidState.initialized === false
                          ? settingsPage.win.local("تحتاج إعدادًا لمرة واحدة (تنزيل يزيد على 2 غيغابايت).", "Needs a one-time setup (a download of over 2 GB).")
                        : settingsPage.androidState && settingsPage.androidState.graphics === "software"
                          ? settingsPage.win.local("جاهزة، لكنها ترسم هنا دون تسريع رسومي، فقد تبطؤ الألعاب.",
                                                   "Ready, but they draw without graphics acceleration here, so games may be slow.")
                        : settingsPage.win.local("جاهزة. تعمل بجانب برامجك الأخرى، ويدير أندرويد أذوناتها.",
                                                 "Ready. They run beside your other programs, and Android manages their permissions.")
                    action: settingsPage.androidState && settingsPage.androidState.initialized === false ? "setup-android" : ""
                }
            }

            // ── where apps come from ──
            SettingsGroup {
                win: settingsPage.win
                Layout.fillWidth: true
                title: settingsPage.win.local("من أين تأتي التطبيقات", "Where apps come from")
                Repeater {
                    model: [
                        { glyph: "cube", ar: "تطبيقات لينكس", en: "Linux apps",
                          ar2: "من كتالوج التطبيقات المفتوح، كل تطبيق في عزله الخاص. «موثّق» يعني أن الكتالوج تحقّق من ناشره.",
                          en2: "From the open app catalogue, each in a sandbox of its own. \"Verified\" means the catalogue checked who publishes it." },
                        { glyph: "globe", ar: "تطبيقات الويب", en: "Web apps",
                          ar2: "مواقع الناشرين نفسها، كل واحد في نافذته الخاصة بعيدًا عن متصفحك، ويسألك قبل الكاميرا والميكروفون.",
                          en2: "The publishers' own sites, each in a window of its own apart from your browser, asking before the camera or microphone." },
                        { glyph: "system", ar: "برامج ويندوز", en: "Windows programs",
                          ar2: "تُنزَّل من ناشريها وتُطابق بصمة راجعها MoOS، ثم تعمل باسمك بوصول كامل إلى ملفاتك.",
                          en2: "Downloaded from their publishers and matched to a fingerprint MoOS reviewed; they then run as you, with full access to your files." },
                        { glyph: "phone", ar: "تطبيقات أندرويد", en: "Android apps",
                          ar2: "ملفات موثّقة تعمل في مساحة أندرويد على هذا الجهاز.",
                          en2: "Verified files that run in the Android space on this computer." },
                        { glyph: "download", ar: "من مواقع الناشرين", en: "From publishers' websites",
                          ar2: "برامج لينكس يوزّعها ناشروها بأنفسهم. تُطابق بصمتها ثم تعمل باسمك خارج العزل.",
                          en2: "Linux programs their publishers distribute themselves. Their fingerprint is matched, then they run as you, outside the sandbox." },
                        { glyph: "folder", ar: "ما تضيفه من ملف", en: "What you add from a file",
                          ar2: "يفحص MoOS الملف ويسألك قبل أي تثبيت، ولا يحتاج ذلك صلاحيات المسؤول.",
                          en2: "MoOS inspects the file and asks you before installing anything, without administrator rights." }
                    ]
                    delegate: RowLayout {
                        id: sourceRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: settingsPage.design.space4
                        Rectangle {
                            Layout.preferredWidth: settingsPage.win.fs(36)
                            Layout.preferredHeight: settingsPage.win.fs(36)
                            Layout.alignment: Qt.AlignTop
                            radius: width / 2
                            color: settingsPage.win.tint(settingsPage.win.txt, settingsPage.win.lightScheme ? 0.06 : 0.08)
                            Glyph {
                                win: settingsPage.win
                                anchors.centerIn: parent
                                width: settingsPage.win.fs(18)
                                height: width
                                name: sourceRow.modelData.glyph
                                tint: settingsPage.win.txt
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: settingsPage.win.localName(sourceRow.modelData)
                                color: settingsPage.win.txt
                                font.family: settingsPage.win.uiFont
                                font.pixelSize: settingsPage.win.typePx(14)
                                font.weight: Font.DemiBold
                            }
                            Text {
                                Layout.fillWidth: true
                                text: settingsPage.win.rtl ? sourceRow.modelData.ar2 : sourceRow.modelData.en2
                                color: settingsPage.win.txt2
                                font.family: settingsPage.win.uiFont
                                font.pixelSize: settingsPage.win.typePx(13)
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            // ── add an app from a file ──
            SettingsGroup {
                win: settingsPage.win
                Layout.fillWidth: true
                title: settingsPage.win.local("أضف تطبيقًا من ملف", "Add an app from a file")
                Text {
                    Layout.fillWidth: true
                    text: settingsPage.win.local("اختر ملفًا نزّلته، أو أفلته على نافذة المتجر. يفحص MoOS نوعه ويسألك قبل أي تثبيت.",
                                                 "Choose a file you downloaded, or drop it on the Store's window. MoOS inspects what it is and asks before installing anything.")
                    color: settingsPage.win.txt2
                    font.family: settingsPage.win.uiFont
                    font.pixelSize: settingsPage.win.typePx(13)
                    wrapMode: Text.WordWrap
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: settingsPage.design.space2
                    ActionButton {
                        win: settingsPage.win
                        pill: true
                        primary: true
                        label: settingsPage.win.local("اختر ملفًا…", "Choose a file…")
                        glyphName: "upload"
                        enabled: !settingsPage.win.jobIsActive()
                        triggered: function() { settingsPage.win.openApplicationPicker() }
                    }
                    Repeater {
                        model: settingsPage.win.engineCapabilities
                        delegate: ActionButton {
                            id: capability
                            required property var modelData
                            win: settingsPage.win
                            pill: true
                            label: capability.modelData.label
                            glyphName: capability.modelData.id === "windows" ? "system"
                                     : capability.modelData.id === "android" ? "phone" : "cube"
                            enabled: !settingsPage.win.jobIsActive()
                            Accessible.description: settingsPage.win.local("اختر ملفًا من هذا النوع لإضافته", "Choose a file of this kind to add")
                            triggered: function() { settingsPage.win.openPickerFor(capability.modelData) }
                        }
                    }
                }
            }

            // ── the catalogue ──
            SettingsGroup {
                win: settingsPage.win
                Layout.fillWidth: true
                title: settingsPage.win.local("الكتالوج", "The catalogue")
                Text {
                    Layout.fillWidth: true
                    text: {
                        var parts = []
                        parts.push(settingsPage.win.indexReady
                            ? (settingsPage.win.hasFlatpakCatalog()
                               ? settingsPage.win.local("الكتالوج الكامل جاهز", "The full catalogue is ready")
                               : settingsPage.win.local("الكتالوج الأساسي فقط؛ اتصل بالإنترنت لتحديثه", "The essential catalogue only; connect to the internet to refresh it"))
                            : settingsPage.win.local("يُجهَّز الكتالوج…", "The catalogue is being prepared…"))
                        parts.push(settingsPage.win.appsCountText(settingsPage.win.browseOrder.length))
                        var when = settingsPage.win.agoText(settingsPage.win.indexGeneratedAt)
                        if (when !== "") parts.push(settingsPage.win.local("حُدِّث ", "updated ") + when)
                        return parts.join("  ·  ")
                    }
                    color: settingsPage.win.txt2
                    font.family: settingsPage.win.uiFont
                    font.pixelSize: settingsPage.win.typePx(13)
                    wrapMode: Text.WordWrap
                }
                ActionButton {
                    win: settingsPage.win
                    visible: settingsPage.win.indexReady && !settingsPage.win.hasFlatpakCatalog()
                    pill: true
                    label: settingsPage.win.rtl ? "حدّث الفهرس" : "Refresh catalogue"
                    glyphName: "refresh"
                    enabled: !settingsPage.win.jobIsActive()
                    triggered: function() { settingsPage.win.openSourceEngine("refresh") }
                }
            }

            // ── advanced ──
            SettingsGroup {
                win: settingsPage.win
                Layout.fillWidth: true
                title: settingsPage.win.local("متقدم", "Advanced")
                RowLayout {
                    Layout.fillWidth: true
                    spacing: settingsPage.design.space4
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: settingsPage.win.local("كتالوج إضافي اختياري", "Optional additional catalogue")
                            color: settingsPage.win.txt
                            font.family: settingsPage.win.uiFont
                            font.pixelSize: settingsPage.win.typePx(14)
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: settingsPage.win.local("واجهة ثانية لكتالوج تطبيقات لينكس، بحسابات ومفضلة. تبقى خارج قائمة التطبيقات كي يظل متجر MoOS المتجر الوحيد، وأول فتح لها يثبّتها.",
                                                         "A second view of the Linux app catalogue, with accounts and favourites. It stays out of the app menu so Mo Store remains the one store, and opening it the first time installs it.")
                            color: settingsPage.win.txt2
                            font.family: settingsPage.win.uiFont
                            font.pixelSize: settingsPage.win.typePx(13)
                            wrapMode: Text.WordWrap
                        }
                    }
                    ActionButton {
                        win: settingsPage.win
                        pill: true
                        enabled: !settingsPage.win.jobIsActive()
                        label: !settingsPage.win.isInstalled(settingsPage.win.appById("io.github.kolunmi.Bazaar"))
                            ? (settingsPage.win.rtl ? "ثبّت المحرك وافتحه" : "Install & open engine")
                            : (settingsPage.win.rtl ? "فتح المحرك" : "Open engine")
                        glyphName: settingsPage.win.isInstalled(settingsPage.win.appById("io.github.kolunmi.Bazaar")) ? "external" : "download"
                        triggered: function() { settingsPage.win.openSourceEngine("bazaar") }
                    }
                }
            }
        }
    }
}

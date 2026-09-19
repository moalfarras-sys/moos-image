import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

// Executable design reference, never a system-settings or device-control window.
// All interactions are local samples. Use scripts/review/design-studio.py.
//
// THE RULE THIS FILE LIVES BY: a reference may not simulate what it documents.
// Four things in the first version of this window did, and each one taught the
// opposite of the contract:
//
//   * it set `fillOpacity` on every GlassSurface itself, which bypassed
//     Tokens.glassFill() — the ONLY consumer of Tokens.blurActive — so the one
//     code path the material actually takes was the one path never exercised;
//   * it derived layout direction from a command-line flag instead of
//     MoUI.Locale, the shipped singleton the contract names as the source;
//   * it invented `Qt.alpha(ink, 0.76)` for muted ink where production uses
//     Tokens.mutedOpacity;
//   * it carried a local `calm` switch in place of the shipped motion gate,
//     `Kirigami.Units.longDuration > 1`.
//
// Everything below reads the shipped tokens and singletons. Where the studio
// shows a system state it READS it; the only things it toggles are its own
// preview surfaces.
QQC2.ApplicationWindow {
    id: studio
    visible: true
    width: Number(argument("width", "1440"))
    // A capture must show the whole reference. At the requested size the sections
    // below the fold were cut off the PNG, so in capture mode the window grows to
    // the height the content actually needs and the grab gets all of it.
    height: capturing ? Math.max(requestedHeight, Math.ceil(requiredHeight))
                      : requestedHeight
    title: local("مختبر تصميم MoOS", "MoOS Design Studio")
    color: Kirigami.Theme.backgroundColor

    readonly property var design: MoUI.Tokens
    readonly property int requestedHeight: Number(argument("height", "960"))
    readonly property bool capturing: argument("capture", "") !== ""

    // Layout direction comes from the shipped singleton, never from this window.
    // MoUI.Locale reads Qt.locale().textDirection, which follows the session's
    // LANG; the --language flag only tells the harness which locale to start in,
    // and disagreeing with the singleton is reported rather than obeyed.
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property string requestedLanguage: argument("language", MoUI.Locale.language)

    readonly property color ink: Kirigami.Theme.textColor
    // The shipped secondary-ink alpha. A studio that invents its own number hides
    // whatever contrast the real one produces.
    readonly property color muted: Qt.alpha(ink, design.mutedOpacity)
    readonly property color accent: Kirigami.Theme.highlightColor

    // The real gate every shipped MoOS surface uses. Kirigami floors longDuration
    // at 1 (not 0) when the owner disables animations, so the comparison is `> 1`.
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property bool calm: !motionEnabled

    // The one thing the studio may toggle: its own preview surfaces. `floating` is
    // a GlassSurface property, so the density still comes out of Tokens.glassFill().
    property bool floatingSurfaces: false
    property int selectedLayout: 0
    property string feedback: local("اختر ترتيبًا لتجربة المعاينة", "Choose a layout to explore the preview")

    readonly property int pageMargin: width < 900 ? design.space4 : design.space7
    readonly property real requiredHeight:
        pageMargin * 2 + header.implicitHeight + design.space5 + page.implicitHeight

    function local(ar, en) { return MoUI.Locale.local(ar, en) }
    function argument(name, fallback) {
        const prefix = "--" + name + "="
        for (let value of Qt.application.arguments)
            if (value.indexOf(prefix) === 0) return value.substring(prefix.length)
        return fallback
    }

    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true

    Component.onCompleted: {
        if (requestedLanguage !== MoUI.Locale.language)
            console.warn("DESIGN_STUDIO_LOCALE_MISMATCH requested=" + requestedLanguage
                         + " locale=" + MoUI.Locale.language + " rtl=" + MoUI.Locale.rtl
                         + " — direction follows MoUI.Locale; set LANG to change it")
        console.log("DESIGN_STUDIO_STATE locale=" + MoUI.Locale.language
                    + " rtl=" + MoUI.Locale.rtl
                    + " blurActive=" + design.blurActive
                    + " longDuration=" + Kirigami.Units.longDuration
                    + " motionEnabled=" + motionEnabled)
    }

    component Copy: Text {
        color: studio.ink
        font.family: design.interfaceFamily
        font.pixelSize: design.typeBody
        wrapMode: Text.WordWrap
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }

    // A glass surface exactly as a shipped MoOS surface declares one: depth and
    // `floating` in, Tokens.glassFill() decides the density. Nothing here assigns
    // fillOpacity, because that assignment is what disconnected the studio from
    // the blur policy in the first place.
    component Sample: MoUI.GlassSurface {
        depth: design.glassLevelPanel
        surfaceColor: Kirigami.Theme.backgroundColor
        floating: studio.floatingSurfaces
        radius: design.radiusPanel
    }

    // Qt Quick Controls' Switch measures 20 px tall with a 36×18 indicator, which
    // is half the 40×40 minimum the visual contract states. MoUI ships no switch,
    // so the control keeps its stock look and gets the contract's hit target.
    component Toggle: QQC2.Switch {
        implicitHeight: design.targetCompact
        font.family: design.interfaceFamily
        font.pixelSize: design.typeBody
        Accessible.name: text
    }

    Item {
        id: canvas
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.tint(studio.color, Qt.alpha(studio.accent, 0.12)) }
                GradientStop { position: 0.6; color: studio.color }
                GradientStop { position: 1; color: Qt.tint(studio.color, Qt.alpha(studio.accent, 0.06)) }
            }
        }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: studio.pageMargin
            spacing: design.space5
            RowLayout {
                id: header
                Layout.fillWidth: true
                spacing: design.space4
                Image {
                    id: logo
                    source: "../../system_files/usr/share/moos/moos-logo.png"
                    Layout.preferredWidth: 48; Layout.preferredHeight: 48
                    sourceSize: Qt.size(192, 192)
                    fillMode: Image.PreserveAspectFit
                    Accessible.name: "MoOS"
                }
                ColumnLayout {
                    spacing: 0
                    Copy { text: "MoOS UI"; font.pixelSize: design.typeTitle; font.weight: Font.DemiBold }
                    Copy { text: studio.local("نظام واحد. لغة واحدة.", "One system. One visual language."); color: studio.muted }
                }
                Item { Layout.fillWidth: true }
                Copy {
                    text: studio.local("مرجع تفاعلي • بيانات توضيحية", "Interactive reference • sample data")
                    color: studio.muted
                    Layout.maximumWidth: 250
                    horizontalAlignment: Text.AlignRight
                }
            }
            Flickable {
                id: scroll
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true
                contentWidth: width; contentHeight: page.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                ColumnLayout {
                    id: page
                    width: scroll.width
                    spacing: design.space5
                    RowLayout {
                        Layout.fillWidth: true
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: design.space2
                            Copy {
                                text: studio.local("مساحة لعملك. هدوء لتفكيرك.", "Room to work. Space to think.")
                                font.pixelSize: scroll.width < 900 ? design.typeDisplay : design.typeHero
                                font.weight: Font.DemiBold
                                Layout.fillWidth: true
                            }
                            Copy {
                                text: studio.local("وضوح في كل طبقة، وحركة تستجيب لك.", "Clarity at every depth. Motion that responds to you.")
                                color: studio.muted; font.pixelSize: design.typeTitle
                                Layout.fillWidth: true
                            }
                        }
                    }
                    Sample {
                        Layout.fillWidth: true
                        implicitHeight: workspaceColumn.implicitHeight + design.space6 * 2
                        ColumnLayout {
                            id: workspaceColumn
                            anchors.fill: parent; anchors.margins: design.space6
                            spacing: design.space4
                            RowLayout {
                                Layout.fillWidth: true
                                Copy { text: studio.local("مساحة العمل", "Workspace"); font.pixelSize: design.typeTitle; font.weight: Font.DemiBold }
                                Item { Layout.fillWidth: true }
                                Copy { text: studio.local("معاينة الترتيب", "Arrangement preview"); color: studio.muted }
                            }
                            Rectangle {
                                id: workspacePreview
                                Layout.fillWidth: true; Layout.preferredHeight: Math.min(260, scroll.width * 0.24)
                                radius: design.radiusCard
                                color: Qt.tint(studio.color, Qt.alpha(studio.accent, 0.09))
                                border.color: Qt.alpha(studio.ink, 0.12)
                                // Static composition, finite geometry changes only on selection.
                                //
                                // Each tile states where its LEADING edge sits and the row
                                // flips that to the trailing edge when the layout mirrors.
                                // Raw `x:` arithmetic is invisible to LayoutMirroring, which
                                // is why the Arabic arrangement preview used to read
                                // left-to-right while every label beside it was mirrored.
                                Repeater {
                                    model: 3
                                    Rectangle {
                                        id: tile
                                        required property int index
                                        readonly property real gap: 12
                                        readonly property real usable: workspacePreview.width - 48
                                        readonly property bool mainAndTwo: studio.selectedLayout === 1
                                        readonly property real leading:
                                            12 + (mainAndTwo ? (index === 0 ? 0 : usable * 0.6 + gap)
                                                             : index * (usable / 3 + gap))
                                        x: workspacePreview.LayoutMirroring.enabled
                                           ? workspacePreview.width - leading - width : leading
                                        y: mainAndTwo && index === 2 ? workspacePreview.height / 2 + 6 : 12
                                        width: mainAndTwo ? (index === 0 ? usable * 0.6 : usable * 0.4 + gap) : usable / 3
                                        height: mainAndTwo && index > 0 ? (workspacePreview.height - 36) / 2 : workspacePreview.height - 24
                                        radius: design.radiusControl
                                        color: index === 0 ? Qt.tint(studio.color, Qt.alpha(studio.accent, 0.2)) : studio.color
                                        border.color: index === 0 ? studio.accent : Qt.alpha(studio.ink, 0.2)
                                        // The shipped durations already collapse to 0 when the
                                        // owner has animations off (Tokens.scaled floors there),
                                        // so the preview falls still with the rest of the system.
                                        Behavior on x { NumberAnimation { duration: design.motionGeometry; easing.type: Easing.OutCubic } }
                                        Behavior on y { NumberAnimation { duration: design.motionGeometry; easing.type: Easing.OutCubic } }
                                        Behavior on width { NumberAnimation { duration: design.motionGeometry; easing.type: Easing.OutCubic } }
                                        Behavior on height { NumberAnimation { duration: design.motionGeometry; easing.type: Easing.OutCubic } }
                                        Copy {
                                            anchors.centerIn: parent
                                            text: ["Mo AI", studio.local("المستندات", "Documents"), "MoPlayer"][tile.index]
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                }
                            }
                            Flow {
                                Layout.fillWidth: true
                                spacing: design.space3
                                MoUI.Button {
                                    label: studio.local("ثلاث مساحات", "Three columns"); primary: studio.selectedLayout === 0
                                    onClicked: { studio.selectedLayout = 0; studio.feedback = studio.local("معاينة: ثلاث مساحات متساوية", "Preview: three equal workspaces") }
                                }
                                MoUI.Button {
                                    label: studio.local("تركيز ومساحتان", "Focus + two"); primary: studio.selectedLayout === 1
                                    onClicked: { studio.selectedLayout = 1; studio.feedback = studio.local("معاينة: مساحة رئيسية ومساحتان جانبيتان", "Preview: one main workspace and two companions") }
                                }
                            }
                            Copy { Layout.fillWidth: true; text: studio.feedback; color: studio.muted }
                        }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: scroll.width < 900 ? 1 : 2
                        columnSpacing: design.space5; rowSpacing: design.space5
                        Sample {
                            Layout.fillWidth: true; Layout.preferredHeight: materialColumn.implicitHeight + 48
                            ColumnLayout {
                                id: materialColumn
                                anchors.fill: parent; anchors.margins: design.space5
                                spacing: design.space3
                                Copy { text: studio.local("المادة والوضوح", "Material & clarity"); font.pixelSize: design.typeTitle; font.weight: Font.DemiBold }
                                Copy { Layout.fillWidth: true; text: studio.local("لونك هو الهوية. الكثافة تحمي القراءة.", "Colour carries identity. Density protects readability."); color: studio.muted }
                                Toggle {
                                    text: studio.local("أسطح طافية في المعاينة", "Floating preview surfaces")
                                    checked: studio.floatingSurfaces
                                    onToggled: studio.floatingSurfaces = checked
                                }
                                Copy {
                                    Layout.fillWidth: true
                                    color: studio.muted
                                    font.pixelSize: design.typeSecondary
                                    text: studio.local(
                                        design.blurActive
                                            ? "الضبابية مفعّلة: glassFill() يعيد الكثافة المصمّمة نفسها لكل عمق (0.220)، والحافة واللمعة هما ما يحملان التدرّج."
                                            : "لا ضبابية: glassFill() يزيد الكثافة مع العمق، فتظهر الأربع درجات أدناه.",
                                        design.blurActive
                                            ? "Blur is on: glassFill() returns the same designed density at every depth (0.220); the rim and the specular carry the hierarchy."
                                            : "No blur: glassFill() adds body with depth — the four steps below.")
                                }
                                // Aurora Glass, four depths, over something worth hiding.
                                //
                                // These four tiles used to sit on a surface of their own
                                // colour, and compositing colour C over colour C is C at
                                // every alpha: measured (194,228,225)/(194,229,225)/
                                // (194,228,225)/(194,228,225), a 1.0000 contrast ratio
                                // across four different densities. Density is a property
                                // of what shows THROUGH, so the strip is laid over a
                                // high-frequency plate and the four levels separate for
                                // the same reason they do over a real wallpaper.
                                Rectangle {
                                    id: depthPlate
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 104
                                    radius: design.radiusCard
                                    clip: true
                                    color: Qt.darker(studio.accent, 2.2)
                                    Row {
                                        anchors.fill: parent
                                        Repeater {
                                            model: 28
                                            Rectangle {
                                                required property int index
                                                width: depthPlate.width / 28
                                                height: depthPlate.height
                                                color: index % 2 === 0 ? studio.accent
                                                                       : Qt.darker(studio.accent, 2.6)
                                            }
                                        }
                                    }
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: design.space2
                                        spacing: design.space2
                                        Repeater {
                                            model: [
                                                { token: "glassLevelScene", level: design.glassLevelScene },
                                                { token: "glassLevelPanel", level: design.glassLevelPanel },
                                                { token: "glassLevelPopover", level: design.glassLevelPopover },
                                                { token: "glassLevelDialog", level: design.glassLevelDialog },
                                            ]
                                            Sample {
                                                id: depthTile
                                                required property var modelData
                                                depth: modelData.level
                                                radius: design.radiusControl
                                                Layout.fillWidth: true; Layout.fillHeight: true
                                                ColumnLayout {
                                                    anchors.centerIn: parent
                                                    width: parent.width - design.space2
                                                    spacing: 0
                                                    Copy {
                                                        Layout.fillWidth: true
                                                        text: depthTile.modelData.token
                                                        font.pixelSize: design.typeCaption
                                                        font.weight: Font.DemiBold
                                                        horizontalAlignment: Text.AlignHCenter
                                                        elide: Text.ElideRight
                                                    }
                                                    Copy {
                                                        Layout.fillWidth: true
                                                        text: depthTile.fillOpacity.toFixed(3)
                                                        color: studio.muted
                                                        font.pixelSize: design.typeCaption
                                                        horizontalAlignment: Text.AlignHCenter
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Sample {
                            Layout.fillWidth: true; Layout.preferredHeight: motionColumn.implicitHeight + 48
                            ColumnLayout {
                                id: motionColumn
                                anchors.fill: parent; anchors.margins: design.space5
                                spacing: design.space3
                                Copy { text: studio.local("الحركة والاستجابة", "Motion & response"); font.pixelSize: design.typeTitle; font.weight: Font.DemiBold }
                                Copy { Layout.fillWidth: true; text: studio.local("استجابة قصيرة، ثم سكون كامل.", "A brief response, then complete stillness."); color: studio.muted }
                                // Reduced motion is READ, never simulated. The owner's
                                // [KDE] AnimationDurationFactor reaches QML only through
                                // Kirigami.Units.longDuration, which is floored at 1 with
                                // animations off — so the gate is `> 1`, and this row
                                // reports whatever it currently says.
                                Sample {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: motionState.implicitHeight + design.space4 * 2
                                    depth: design.glassLevelScene
                                    radius: design.radiusControl
                                    ColumnLayout {
                                        id: motionState
                                        anchors.fill: parent; anchors.margins: design.space4
                                        spacing: design.space1
                                        Copy {
                                            Layout.fillWidth: true
                                            font.weight: Font.DemiBold
                                            text: studio.local(
                                                studio.motionEnabled ? "الحركة مفعّلة في هذه الجلسة"
                                                                     : "الحركة مُعطَّلة في هذه الجلسة",
                                                studio.motionEnabled ? "Motion is on in this session"
                                                                     : "Motion is off in this session")
                                        }
                                        Copy {
                                            Layout.fillWidth: true
                                            color: studio.muted
                                            font.pixelSize: design.typeSecondary
                                            text: "Kirigami.Units.longDuration = " + Kirigami.Units.longDuration
                                                  + "  ·  Tokens.motionGeometry = " + design.motionGeometry + " ms"
                                        }
                                        Copy {
                                            Layout.fillWidth: true
                                            color: studio.muted
                                            font.pixelSize: design.typeSecondary
                                            text: studio.local(
                                                "المصدر: [KDE] AnimationDurationFactor في kdeglobals — إعداد المالك، لا مفتاح في هذه النافذة.",
                                                "Source: [KDE] AnimationDurationFactor in kdeglobals — the owner's setting, not a switch in this window.")
                                        }
                                    }
                                }
                                Flow {
                                    Layout.fillWidth: true; spacing: design.space3
                                    MoUI.Button { label: studio.local("جرّب الاستجابة", "Try feedback"); primary: true; onClicked: studio.feedback = studio.local("استجابت المعاينة. لم تتغير إعدادات الجهاز.", "Preview responded. Device settings were unchanged.") }
                                    MoUI.Button { label: studio.local("غير متاح", "Unavailable"); enabled: false }
                                }
                            }
                        }
                    }
                    Copy {
                        Layout.fillWidth: true; color: studio.muted
                        text: studio.local(
                            "الأسطح والأزرار والرموز من مصدر MoOS نفسه (org.moos.ui). المفاتيح من Qt Quick Controls بهدف لمس 40 بكسل كما يفرض العقد. المعاينة لا ترتّب نوافذك ولا تغيّر إعداداتك.",
                            "Surfaces, buttons and tokens come from the MoOS source (org.moos.ui). The switches are Qt Quick Controls, given the contract's 40 px target. This preview does not arrange your windows or change your settings.")
                    }
                }
            }
        }
    }

    // Readiness, not a guess.
    //
    // The capture used to fire on a flat 1200 ms timer, which is a bet rather than
    // a signal: a slow font or image load produced a blank or half-drawn PNG that
    // passed every check the runner made. The scene reports when it has actually
    // been rendered (`frameSwapped`), the logo reports when it has finished
    // loading, and the page reports a settled implicit height; the grab waits for
    // all three to hold still, and says so in the log either way.
    property int framesRendered: 0
    onFrameSwapped: studio.framesRendered++

    Timer {
        id: readiness
        interval: 100
        repeat: true
        running: studio.capturing
        property int ticks: 0
        property real lastHeight: -1
        readonly property int deadline: 80   // 8 s, then grab anyway and report it
        onTriggered: {
            const settledHeight = page.implicitHeight
            const ready = studio.framesRendered > 0
                       && logo.status !== Image.Loading
                       && settledHeight > 0
                       && settledHeight === lastHeight
            lastHeight = settledHeight
            ticks++
            if (!ready && ticks < deadline) return
            running = false
            console.log("DESIGN_STUDIO_READY", ready, "ticks=" + ticks,
                        "frames=" + studio.framesRendered, "height=" + settledHeight)
            canvas.grabToImage(function(result) {
                const saved = result.saveToFile(studio.argument("capture", ""))
                console.log("DESIGN_STUDIO_CAPTURE", saved, canvas.width, canvas.height)
                Qt.exit(saved && ready ? 0 : 1)
            })
        }
    }
}

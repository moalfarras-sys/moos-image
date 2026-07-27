pragma ComponentBehavior: Bound

/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS Theme Picker — a real, working chooser for the 16 MoOS Global Themes.
    The theme LIST is discovered from the installed look-and-feel packages (the
    source of truth), not a hardcoded table; each card previews the theme's own
    wallpaper + accent, and applying runs `moos-theme apply-lnf <id>` which is
    the atomic, undo-safe switch (save-previous + revert-on-failure). The picker
    itself is Kirigami.Theme-driven, so it wears whichever theme is active.
*/
import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

Kirigami.ApplicationWindow {
    id: root
    title: "MoOS Themes"
    width: Math.min(Kirigami.Units.gridUnit * 72,
                    Screen.desktopAvailableWidth * 0.90)
    height: Math.min(Kirigami.Units.gridUnit * 46,
                     Screen.desktopAvailableHeight * 0.88)
    minimumWidth: Math.min(Kirigami.Units.gridUnit * 34,
                           Screen.desktopAvailableWidth * 0.90)
    minimumHeight: Math.min(Kirigami.Units.gridUnit * 26,
                            Screen.desktopAvailableHeight * 0.88)
    color: Kirigami.Theme.backgroundColor
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property bool lightSurface:
        Kirigami.Theme.backgroundColor.hslLightness > 0.55
    readonly property string currentQuery:
        "kreadconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage"
    readonly property string currentMotionQuery: "moos-theme motion"
    // The supplement seam. Reading LookAndFeelPackage back proves only the one
    // value plasma-apply-lookandfeel is guaranteed to get right — it says
    // nothing about the four things moos-theme exists to carry (the desktop
    // scene, Konsole, GTK and the lock screen), so "verified" was verifying the
    // part that never breaks while a switch that left Firefox dark on a light
    // desktop still reported success. GTK's light/dark bit is the supplement
    // this window can predict on its own: every MoOS light sibling is its dark
    // id + ".light", which is exactly the rule moos-theme's load_profile uses to
    // pick prefer-light/prefer-dark. Literal command — nothing is concatenated
    // into it, like every other command this window runs.
    readonly property string supplementQuery:
        "gsettings get org.gnome.desktop.interface color-scheme"
    property string currentLnf: ""
    property string currentMotion: ""
    property bool busy: false
    property string pendingThemeCommand: ""
    property string pendingExpectedLnf: ""
    property string pendingMotionCommand: ""
    property string pendingExpectedMotion: ""
    property string pendingExpectedColorScheme: ""
    property string pendingVerb: ""
    property bool awaitingReadback: false
    property bool awaitingMotionReadback: false
    property bool awaitingSupplementReadback: false
    property bool operationTimedOut: false
    property string operationMessage: ""
    property bool operationFailed: false
    readonly property bool operationPending:
        pendingThemeCommand.length > 0 || awaitingReadback
        || pendingMotionCommand.length > 0 || awaitingMotionReadback
        || awaitingSupplementReadback

    // Queries and mutations deliberately use separate executable sources.
    // Plasma's executable engine publishes stdout/stderr + exit status only
    // when the process really exits; that completion event is the transaction
    // boundary for a theme switch.
    P5Support.DataSource {
        id: queryExec
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            root.handleQueryResult(source, data || {})
            disconnectSource(source)
        }
        function run(cmd) {
            if (connectedSources.indexOf(cmd) < 0)
                connectSource(cmd)
        }
    }

    P5Support.DataSource {
        id: themeExec
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            root.handleThemeResult(source, data || {})
            disconnectSource(source)
        }
        function run(cmd) {
            if (connectedSources.indexOf(cmd) < 0)
                connectSource(cmd)
        }
    }

    function normalExit(data) {
        return Number(data["exit code"]) === 0
            && Number(data["exit status"]) === 0;
    }

    function resultDetail(data) {
        let detail = String(data["stderr"] || "").trim();
        if (!detail)
            detail = String(data["stdout"] || "").trim();
        if (!detail)
            return "";
        const firstLine = detail.split("\n")[0];
        return firstLine.length > 220
            ? firstLine.substring(0, 217) + "…"
            : firstLine;
    }

    function clearOperationState() {
        pendingThemeCommand = "";
        pendingExpectedLnf = "";
        pendingMotionCommand = "";
        pendingExpectedMotion = "";
        pendingExpectedColorScheme = "";
        pendingVerb = "";
        awaitingReadback = false;
        awaitingMotionReadback = false;
        awaitingSupplementReadback = false;
        operationTimedOut = false;
        busy = false;
    }

    function failOperation(message) {
        operationTimeout.stop();
        clearOperationState();
        operationFailed = true;
        operationMessage = message;
    }

    function handleQueryResult(cmd, data) {
        const out = String(data["stdout"] || "");
        if (cmd.indexOf("look-and-feel/org.moos.ui2") >= 0 && cmd.indexOf("metadata.json") >= 0) {
            if (!normalExit(data)) {
                operationFailed = true;
                operationMessage = "تعذّر تحميل قائمة الثيمات | Could not load themes";
                return;
            }
            themesModel.clear();
            const lines = out.split("\n");
            for (let i = 0; i < lines.length; ++i) {
                const line = lines[i].trim();
                if (!line) continue;
                const parts = line.split("|");
                const id = parts[0];
                const name = parts.length > 1 && parts[1] ? parts[1] : id;
                themesModel.append({ lnf: id, name: name, isLight: id.endsWith(".light") });
            }
            root.refreshCurrent();
        } else if (cmd === currentMotionQuery) {
            const activeMotion = out.trim();
            const validMotion = /^(?:still|gentle|alive)$/.test(activeMotion);
            if (!awaitingMotionReadback) {
                if (normalExit(data) && validMotion) {
                    currentMotion = activeMotion;
                } else {
                    operationFailed = true;
                    operationMessage =
                        "تعذّرت قراءة حركة الخلفية | Could not read wallpaper motion";
                }
                return;
            }

            operationTimeout.stop();
            if (!normalExit(data) || !validMotion) {
                const detail = resultDetail(data);
                failOperation("اكتمل الضبط لكن تعذّر التحقق من حركة الخلفية"
                              + " | Motion changed, but verification failed"
                              + (detail ? ": " + detail : ""));
                return;
            }

            currentMotion = activeMotion;
            if (activeMotion !== pendingExpectedMotion) {
                const expected = pendingExpectedMotion;
                failOperation("لم تطابق الحركة الفعلية الاختيار"
                              + " | Active motion differs"
                              + ": " + activeMotion + " ≠ " + expected);
                return;
            }

            const wasLate = operationTimedOut;
            clearOperationState();
            operationFailed = false;
            operationMessage = wasLate
                ? "اكتمل ضبط الحركة بعد انتظار أطول وتم التحقق منه"
                  + " | Motion completed late and was verified"
                : "تم ضبط حركة الخلفية والتحقق منها"
                  + " | Wallpaper motion applied and verified";
        } else if (cmd === currentQuery) {
            const activeLnf = out.trim();
            if (!awaitingReadback) {
                if (normalExit(data) && activeLnf)
                    currentLnf = activeLnf;
                return;
            }

            operationTimeout.stop();
            if (!normalExit(data) || !activeLnf) {
                const detail = resultDetail(data);
                failOperation("اكتمل التبديل لكن تعذّر التحقق من الثيم"
                              + " | Theme changed, but verification failed"
                              + (detail ? ": " + detail : ""));
                return;
            }

            currentLnf = activeLnf;
            if (pendingExpectedLnf && activeLnf !== pendingExpectedLnf) {
                const expected = pendingExpectedLnf;
                failOperation("لم يطابق الثيم الفعلي الاختيار | Active theme differs"
                              + ": " + activeLnf + " ≠ " + expected);
                return;
            }

            // The Global Theme landed. That is the half of the switch KDE does;
            // now prove a supplement followed, because that is the half MoOS
            // does and the only half that can quietly not happen. Expected value
            // comes from the theme Plasma actually reports, so it is right for
            // undo (which has no expected id) as well as for an apply.
            pendingExpectedColorScheme =
                activeLnf.endsWith(".light") ? "prefer-light" : "prefer-dark";
            awaitingReadback = false;
            awaitingSupplementReadback = true;
            busy = true;
            operationTimeout.restart();
            refreshSupplement();
        } else if (cmd === supplementQuery) {
            if (!awaitingSupplementReadback)
                return;

            operationTimeout.stop();
            // gsettings prints its strings quoted: 'prefer-dark'.
            const activeScheme = out.trim().replace(/^'|'$/g, "");
            if (!normalExit(data) || !activeScheme) {
                const detail = resultDetail(data);
                failOperation("طُبّق الثيم لكن تعذّر التحقق من مكمّلاته"
                              + " | Theme applied, but its supplements could not be verified"
                              + (detail ? ": " + detail : ""));
                return;
            }
            if (activeScheme !== pendingExpectedColorScheme) {
                const expectedScheme = pendingExpectedColorScheme;
                failOperation("طُبّق الثيم ولم تتبعه مكمّلاته"
                              + " | Theme applied, but its supplements did not follow"
                              + ": " + activeScheme + " ≠ " + expectedScheme);
                return;
            }

            const wasLate = operationTimedOut;
            const wasUndo = pendingVerb === "undo";
            clearOperationState();
            operationFailed = false;
            operationMessage = wasLate
                ? "اكتمل التبديل بعد انتظار أطول وتم التحقق منه"
                  + " | Theme completed late and was verified"
                : (wasUndo
                    ? "تم التراجع والتحقق من الثيم | Undo complete and verified"
                    : "تم تطبيق الثيم والتحقق منه | Theme applied and verified");
        }
    }

    function handleThemeResult(cmd, data) {
        if (cmd === pendingMotionCommand) {
            operationTimeout.stop();
            pendingMotionCommand = "";
            if (!normalExit(data)) {
                const detail = resultDetail(data);
                failOperation("تعذّر ضبط حركة الخلفية | Motion change failed"
                              + (detail ? ": " + detail : ""));
                return;
            }

            // A successful mutation is only provisional. Query the live scenes
            // after moos-theme exits and highlight a choice only on exact match.
            awaitingMotionReadback = true;
            busy = true;
            operationTimeout.restart();
            refreshMotion();
            return;
        }

        if (cmd !== pendingThemeCommand)
            return;

        operationTimeout.stop();
        pendingThemeCommand = "";
        if (!normalExit(data)) {
            const detail = resultDetail(data);
            failOperation("تعذّر تطبيق الثيم | Theme switch failed"
                          + (detail ? ": " + detail : ""));
            return;
        }

        // A zero exit is necessary but not sufficient: read back Plasma's live
        // selection only after moos-theme has fully exited.
        awaitingReadback = true;
        busy = true;
        operationTimeout.restart();
        refreshCurrent();
    }

    function refreshThemes() {
        queryExec.run('for d in /usr/share/plasma/look-and-feel/org.moos.ui2*; do id=$(basename "$d"); nm=$(sed -n \'s/.*"Name"[^"]*"\\([^"]*\\)".*/\\1/p\' "$d/metadata.json" | head -1); echo "$id|$nm"; done');
    }
    function refreshCurrent() {
        queryExec.run(currentQuery);
    }
    function refreshMotion() {
        queryExec.run(currentMotionQuery);
    }
    function refreshSupplement() {
        queryExec.run(supplementQuery);
    }
    function beginThemeOperation(cmd, expectedLnf, verb) {
        if (operationPending)
            return;
        pendingThemeCommand = cmd;
        pendingExpectedLnf = expectedLnf;
        pendingVerb = verb;
        awaitingReadback = false;
        operationTimedOut = false;
        operationMessage = "";
        operationFailed = false;
        busy = true;
        operationTimeout.restart();
        themeExec.run(cmd);
    }
    function applyTheme(lnf) {
        if (!/^org\.moos\.ui2(?:\.[a-z0-9]+)*$/.test(lnf)) {
            failOperation("معرّف ثيم غير صالح | Invalid theme identifier");
            return;
        }
        beginThemeOperation("moos-theme apply-lnf " + lnf, lnf, "apply");
    }
    function undo() {
        beginThemeOperation("moos-theme undo", "", "undo");
    }
    // Put the three motion highlights back under the live value. A checkable
    // QQC2.Button writes its OWN `checked` on the press, before onClicked runs,
    // so without this the footer showed the user's REQUEST as though it were the
    // desktop's STATE. Measured on Qt 6.7 with these exact bindings (offscreen
    // qml-qt6, in both the default and the org.kde.desktop style): click "Still"
    // while the live value is "gentle" and the Still button lights while Gentle
    // stays lit too — two of three pressed, one of them advertising a mode the
    // desktop never took. There is no exclusivity group to prevent that, and
    // none is wanted: root.currentMotion is a single string, so the model
    // already permits exactly one, and a group would be a second source of truth
    // to keep in step. The value only ever moves on a VERIFIED readback, and a
    // motion write that fails or is reverted never moves it — which is precisely
    // when the old behaviour lied and kept lying, because nothing else would
    // have re-evaluated those bindings. Re-asserting them here restores the
    // truth inside the same event, before the frame is drawn.
    function restoreMotionHighlights() {
        motionStill.checked = Qt.binding(() => root.currentMotion === "still");
        motionGentle.checked = Qt.binding(() => root.currentMotion === "gentle");
        motionAlive.checked = Qt.binding(() => root.currentMotion === "alive");
    }
    function setMotion(mode) {
        restoreMotionHighlights();
        if (operationPending)
            return;

        // Keep all executable-engine commands literal. No model value or other
        // mutable string is ever concatenated into a shell command.
        let cmd = "";
        switch (mode) {
        case "still":
            cmd = "moos-theme motion still";
            break;
        case "gentle":
            cmd = "moos-theme motion gentle";
            break;
        case "alive":
            cmd = "moos-theme motion alive";
            break;
        default:
            failOperation("خيار حركة غير صالح | Invalid motion choice");
            return;
        }

        pendingMotionCommand = cmd;
        pendingExpectedMotion = mode;
        operationTimedOut = false;
        operationMessage = "";
        operationFailed = false;
        busy = true;
        operationTimeout.restart();
        themeExec.run(cmd);
    }

    // Do not terminate moos-theme on timeout: killing the atomic apply script
    // halfway through could leave a mixed desktop. The UI stops spinning,
    // reports the delay, keeps competing choices locked, and consumes the real
    // completion event when it eventually arrives. Readback is safe to cancel.
    Timer {
        id: operationTimeout
        interval: 30000
        repeat: false
        onTriggered: {
            if (root.pendingThemeCommand || root.pendingMotionCommand) {
                root.operationTimedOut = true;
                root.busy = false;
                root.operationFailed = true;
                root.operationMessage =
                    "استغرقت العملية أكثر من 30 ثانية؛ ما زالت تعمل بأمان"
                    + " | The change is still finishing safely";
            } else if (root.awaitingReadback || root.awaitingMotionReadback
                       || root.awaitingSupplementReadback) {
                // Release exactly the query that is in flight. Connecting a
                // source is what starts the process, so leaving a hung one
                // connected means the next readback never starts.
                queryExec.disconnectSource(
                    root.awaitingMotionReadback ? root.currentMotionQuery
                    : (root.awaitingSupplementReadback ? root.supplementQuery
                                                       : root.currentQuery));
                root.failOperation(
                    "انتهت مهلة التحقق | Verification timed out");
            }
        }
    }

    ListModel { id: themesModel }
    Component.onCompleted: {
        refreshThemes()
        refreshMotion()
    }

    // ── header ──────────────────────────────────────────────────────────────
    header: QQC2.ToolBar {
        background: Rectangle {
            color: Qt.rgba(Kirigami.Theme.alternateBackgroundColor.r,
                           Kirigami.Theme.alternateBackgroundColor.g,
                           Kirigami.Theme.alternateBackgroundColor.b,
                           root.lightSurface ? 0.92 : 0.82)
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.22)
            }
        }
        contentItem: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon { source: "preferences-desktop-theme-global"; implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: implicitWidth }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Kirigami.Heading { level: 3; text: "ثيمات MoOS  ·  MoOS Themes"; elide: Text.ElideRight }
                QQC2.Label {
                    text: root.busy
                        ? "…يُطبّق | applying"
                        : (root.operationPending
                            ? "…بانتظار اكتمال العملية | waiting for completion"
                            : root.currentActiveName())
                    opacity: 0.7; font.pointSize: Kirigami.Theme.smallFont.pointSize; elide: Text.ElideRight
                }
            }
            QQC2.Button {
                text: "تراجع | Undo"
                icon.name: "edit-undo"
                enabled: !root.operationPending
                onClicked: root.undo()
            }
        }
    }

    // ── live wallpaper motion policy ───────────────────────────────────────
    footer: QQC2.ToolBar {
        leftPadding: Kirigami.Units.largeSpacing
        rightPadding: Kirigami.Units.largeSpacing
        topPadding: Kirigami.Units.smallSpacing
        bottomPadding: Kirigami.Units.smallSpacing
        background: Rectangle {
            color: Qt.rgba(Kirigami.Theme.alternateBackgroundColor.r,
                           Kirigami.Theme.alternateBackgroundColor.g,
                           Kirigami.Theme.alternateBackgroundColor.b,
                           root.lightSurface ? 0.96 : 0.88)
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: Qt.rgba(root.accent.r, root.accent.g,
                               root.accent.b, 0.34)
            }
        }
        contentItem: RowLayout {
            spacing: Kirigami.Units.largeSpacing

            Kirigami.Icon {
                source: "preferences-desktop-effects"
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: implicitWidth
                color: root.accent
            }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                QQC2.Label {
                    text: "حركة الخلفية  ·  Wallpaper motion"
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                QQC2.Label {
                    text: "اختر مستوى الهدوء والحيوية  ·  Choose the energy level"
                    opacity: 0.66
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    elide: Text.ElideRight
                }
            }

            // The three are checkable because that is the only strong
            // "this one is on" the desktop style draws (org.kde.desktop's
            // Button hands `checkable && checked` to the QStyle; `highlighted`
            // there is only a focus ring). What they must NOT do is light
            // themselves — see restoreMotionHighlights(), which every click
            // goes through.
            QQC2.Button {
                id: motionStill
                text: "ساكن | Still"
                checkable: true
                checked: root.currentMotion === "still"
                enabled: !root.operationPending
                onClicked: root.setMotion("still")
            }
            QQC2.Button {
                id: motionGentle
                text: "هادئ | Gentle"
                checkable: true
                checked: root.currentMotion === "gentle"
                enabled: !root.operationPending
                onClicked: root.setMotion("gentle")
            }
            QQC2.Button {
                id: motionAlive
                text: "حيّ | Alive"
                checkable: true
                checked: root.currentMotion === "alive"
                enabled: !root.operationPending
                onClicked: root.setMotion("alive")
            }
        }
    }

    function currentActiveName() {
        for (let i = 0; i < themesModel.count; ++i) {
            if (themesModel.get(i).lnf === root.currentLnf) return "المُطبّق | Active:  " + themesModel.get(i).name;
        }
        return root.currentLnf;
    }

    // A restrained palette wash behind the cards. It stays on inexpensive
    // gradients: the real frost is provided by the desktop theme's KWin blur
    // mask, while this window remains light with all 16 previews visible.
    Rectangle {
        anchors.fill: parent
        z: -1
        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: Qt.lighter(Kirigami.Theme.backgroundColor,
                                  root.lightSurface ? 1.02 : 1.08)
            }
            GradientStop {
                position: 0.58
                color: Kirigami.Theme.backgroundColor
            }
            GradientStop {
                position: 1.0
                color: Qt.tint(
                    Kirigami.Theme.backgroundColor,
                    Qt.rgba(root.accent.r, root.accent.g, root.accent.b,
                            root.lightSurface ? 0.08 : 0.11))
            }
        }
    }

    Kirigami.InlineMessage {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Kirigami.Units.largeSpacing
        z: 10
        visible: root.operationMessage.length > 0
        text: root.operationMessage
        type: root.operationFailed
            ? Kirigami.MessageType.Error
            : Kirigami.MessageType.Positive
        actions: [
            Kirigami.Action {
                text: "إغلاق | Dismiss"
                icon.name: "dialog-close"
                onTriggered: root.operationMessage = ""
            }
        ]
    }

    // ── the grid of theme cards ─────────────────────────────────────────────
    QQC2.ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        background: null
        GridView {
            id: grid
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            cellWidth: Math.floor(width / Math.max(1, Math.floor(width / (Kirigami.Units.gridUnit * 15))))
            cellHeight: Kirigami.Units.gridUnit * 12
            model: themesModel
            clip: true

            delegate: Item {
                id: themeCard
                width: grid.cellWidth
                height: grid.cellHeight
                required property string lnf
                required property string name
                required property bool isLight
                readonly property bool isActive: lnf === root.currentLnf

                QQC2.AbstractButton {
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.smallSpacing
                    hoverEnabled: true
                    padding: Math.max(2, Math.round(Kirigami.Units.smallSpacing / 2))
                    id: cardButton
                    enabled: !root.operationPending
                    onClicked: root.applyTheme(themeCard.lnf)
                    scale: down ? 0.98 : (hovered ? 1.02 : 1.0)
                    Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }

                    background: Rectangle {
                        radius: Kirigami.Units.gridUnit * 0.6
                        color: "transparent"
                        gradient: Gradient {
                            GradientStop {
                                position: 0.0
                                color: Qt.rgba(
                                    Kirigami.Theme.alternateBackgroundColor.r,
                                    Kirigami.Theme.alternateBackgroundColor.g,
                                    Kirigami.Theme.alternateBackgroundColor.b,
                                    root.lightSurface ? 0.94 : 0.84)
                            }
                            GradientStop {
                                position: 1.0
                                color: Qt.rgba(
                                    Kirigami.Theme.backgroundColor.r,
                                    Kirigami.Theme.backgroundColor.g,
                                    Kirigami.Theme.backgroundColor.b,
                                    root.lightSurface ? 0.88 : 0.74)
                            }
                        }
                        border.width: themeCard.isActive ? 2 : (cardButton.hovered ? 1.5 : 1)
                        border.color: themeCard.isActive || cardButton.hovered
                            ? root.accent
                            : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.14)
                        Behavior on border.color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.leftMargin: parent.radius
                            anchors.rightMargin: parent.radius
                            height: 1
                            color: Qt.rgba(
                                Kirigami.Theme.highlightedTextColor.r,
                                Kirigami.Theme.highlightedTextColor.g,
                                Kirigami.Theme.highlightedTextColor.b,
                                root.lightSurface ? 0.34 : 0.20)
                        }
                    }
                    contentItem: ColumnLayout {
                        spacing: 0
                        // wallpaper preview
                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            Image {
                                anchors.fill: parent
                                source: "file:///usr/share/plasma/look-and-feel/" + themeCard.lnf + "/contents/previews/fullscreenpreview.jpg"
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: false
                                smooth: true
                                mipmap: true
                                // Decode only the physical pixels this card can
                                // display. This stays crisp at 4K/200% without
                                // holding sixteen full-HD frames in memory.
                                sourceSize: Qt.size(
                                    Math.max(64, Math.round(width * Screen.devicePixelRatio)),
                                    Math.max(64, Math.round(height * Screen.devicePixelRatio)))
                            }
                            // active check badge
                            Rectangle {
                                visible: themeCard.isActive
                                anchors { top: parent.top; right: parent.right; margins: Kirigami.Units.smallSpacing }
                                width: Kirigami.Units.iconSizes.medium; height: width; radius: width / 2
                                color: root.accent
                                Kirigami.Icon {
                                    anchors.centerIn: parent
                                    source: "checkmark"
                                    color: Kirigami.Theme.highlightedTextColor
                                    width: Kirigami.Units.iconSizes.small
                                    height: width
                                }
                            }
                        }
                        // caption row
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.margins: Kirigami.Units.smallSpacing
                            spacing: Kirigami.Units.smallSpacing
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: themeCard.name
                                elide: Text.ElideRight
                                font.weight: Font.DemiBold
                                color: Kirigami.Theme.textColor
                            }
                            Kirigami.Icon {
                                source: themeCard.isLight ? "weather-clear" : "weather-clear-night"
                                implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                                opacity: 0.7
                            }
                        }
                    }
                }
            }
        }
    }

    // gentle busy veil
    Rectangle {
        anchors.fill: parent
        visible: root.busy
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.35)
        QQC2.BusyIndicator { anchors.centerIn: parent; running: root.busy }
    }
}

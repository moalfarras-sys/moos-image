// The full MoOS Launcher surface. All colours come from Kirigami.Theme; the
// Plasma dialog behind this item supplies the family-specific glass and blur.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PC3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami

Item {
    id: view

    required property var launcher
    required property var searchModel
    required property var applicationsModel
    required property var favoritesModel
    required property var recentUsageModel
    required property var placesModel
    required property var sessionModel
    required property var menuEditor

    readonly property bool rtl: launcher.rtl
    readonly property bool searching: launcher.searchQuery.trim().length > 0
    property string queuedSearchRun: ""
    property date now: new Date()
    property bool entranceReady: false

    // Tidal Horizon shell tokens. QML uses logical pixels, so these values
    // retain the same optical rhythm at 100–275% display scale.
    readonly property string uiFontFamily: Qt.application.font.family
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 20
    readonly property int space6: 24
    readonly property int radiusS: 8
    readonly property int radiusM: 12
    readonly property int radiusL: 16
    readonly property int radiusXL: 24
    readonly property int targetSize: 40
    readonly property int typeCaption: 11
    readonly property int typeSecondary: 13
    readonly property int typeBody: 14
    readonly property int typeEmphasis: 15
    readonly property int typeSubheading: 18
    readonly property int typeTitle: 20
    readonly property int motionFast: Kirigami.Units.longDuration > 1 ? 120 : 0
    readonly property int motionMedium: Kirigami.Units.longDuration > 1 ? 240 : 0

    implicitWidth: Kirigami.Units.gridUnit * 44
    implicitHeight: Kirigami.Units.gridUnit * 32
    // The Command Canvas deliberately owns more breathing room than a menu.
    // At the reference 225% scale this remains inside a 4K work area while
    // preserving real 40 px targets and the calm four-column app rhythm.
    Layout.minimumWidth: implicitWidth
    Layout.minimumHeight: implicitHeight

    // entranceReady drives both the panel's own fade+scale and the staggered
    // tile reveal below. It is reset when the launcher closes so the entrance
    // plays on EVERY open — bound once at construction it fires a single time
    // per session and the motion is effectively invisible.
    Connections {
        target: view.launcher
        function onExpandedChanged() {
            if (view.launcher.expanded) {
                Qt.callLater(() => view.entranceReady = true);
            } else {
                view.entranceReady = false;
            }
        }
    }

    Component.onCompleted: {
        Qt.callLater(() => view.entranceReady = true);
        // A build-only proof that plasmawindowed constructed this component,
        // not merely the compact panel button.  It is silent in a real session.
        if (view.launcher.smokeFullRepresentation) {
            console.info("MOOS_LAUNCHER_FULL_READY size="
                + Math.round(view.implicitWidth) + "x"
                + Math.round(view.implicitHeight));
        }
    }

    function local(arabic, english) {
        return view.rtl ? arabic : english;
    }

    function greeting() {
        const hour = view.now.getHours();
        if (hour < 12) {
            return view.local("صباح هادئ", "Good morning");
        }
        if (hour < 18) {
            return view.local("مساء منتج", "Good afternoon");
        }
        return view.local("مساء هادئ", "Good evening");
    }

    function latinNumerals(text) {
        let out = "";
        for (let i = 0; i < text.length; ++i) {
            const code = text.charCodeAt(i);
            if (code >= 0x0660 && code <= 0x0669) {
                out += String.fromCharCode(code - 0x0660 + 0x30);
            } else if (code >= 0x06F0 && code <= 0x06F9) {
                out += String.fromCharCode(code - 0x06F0 + 0x30);
            } else {
                out += text[i];
            }
        }
        return out;
    }

    function shortDate() {
        const formatted = view.rtl
            ? Qt.locale("ar").toString(view.now, "dddd، d MMMM")
            : Qt.locale("en").toString(view.now, "dddd · d MMMM");
        return view.latinNumerals(formatted);
    }

    function sessionIcon(actionId) {
        // Every id maps to the glyph a user would guess it means. "logout" once
        // wore the external-link box and "switch-user" the identity spark --
        // both read as mystery buttons on the real 4K session.
        const icons = {
            "lock-screen": "moos-lock-symbolic",
            "switch-user": "moos-user-symbolic",
            "logout": "moos-logout-symbolic",
            "suspend": "moos-moon-symbolic",
            "hibernate": "moos-moon-symbolic",
            "reboot": "moos-refresh-symbolic",
            "shutdown": "moos-power-symbolic"
        };
        return icons[String(actionId)] || "moos-power-symbolic";
    }

    function focusSearch() {
        searchInput.forceActiveFocus();
        searchInput.selectAll();
    }

    function setSearchCursor(position) {
        searchInput.forceActiveFocus();
        searchInput.cursorPosition = Math.max(0, Math.min(position, searchInput.length));
    }

    function runCurrentSearchResult() {
        if (view.searchModel.querying || searchResults.count < 1
                || searchResults.currentIndex < 0) {
            view.queuedSearchRun = view.launcher.searchQuery;
            return;
        }
        view.queuedSearchRun = "";
        view.launcher.runSearchResult(searchResults.currentIndex);
    }

    function runQueuedSearchResult() {
        if (view.queuedSearchRun.length > 0
                && view.queuedSearchRun === view.launcher.searchQuery
                && !view.searchModel.querying && searchResults.count > 0) {
            searchResults.currentIndex = 0;
            view.queuedSearchRun = "";
            Qt.callLater(() => view.launcher.runSearchResult(0));
        }
    }

    Keys.onEscapePressed: event => {
        if (launcher.searchQuery.length > 0) {
            launcher.searchQuery = "";
            focusSearch();
        } else {
            launcher.closeLauncher();
        }
        event.accepted = true;
    }

    Keys.onPressed: event => {
        if (!searchInput.activeFocus && event.text.length > 0
                && !/[\x00-\x1F\x7F]/.test(event.text)) {
            searchInput.forceActiveFocus();
            searchInput.insert(searchInput.cursorPosition, event.text);
            event.accepted = true;
        }
    }

    Connections {
        target: view.searchModel

        function resetSearchSelection() {
            searchResults.currentIndex = searchResults.count > 0 ? 0 : -1;
            if (view.queuedSearchRun.length > 0
                    && view.queuedSearchRun !== view.launcher.searchQuery) {
                view.queuedSearchRun = "";
            }
        }

        function onQueryStringChanged() { resetSearchSelection(); }
        function onModelReset() { resetSearchSelection(); }
        function onRowsInserted() { view.runQueuedSearchResult(); }
        function onDataChanged() { view.runQueuedSearchResult(); }
        function onQueryingChanged() {
            if (!view.searchModel.querying) {
                view.runQueuedSearchResult();
            }
        }
    }

    // One wake-up per minute is enough for the context deck. The canvas never
    // pays for a seconds ticker or an idle animation.
    Timer {
        interval: 60000 - (view.now.getSeconds() * 1000 + view.now.getMilliseconds())
        running: view.visible
        repeat: true
        onTriggered: {
            view.now = new Date();
            interval = 60000 - (view.now.getSeconds() * 1000 + view.now.getMilliseconds());
        }
    }

    // One material layer, one KWin shadow. The stepped top-right and bottom-left
    // shelves are the Tidal Cut silhouette: recognizable before any copy or
    // icon is read, and still entirely semantic-theme driven.
    Shape {
        anchors.fill: parent
        containsMode: Shape.FillContains

        ShapePath {
            strokeWidth: 1
            strokeColor: Qt.alpha(Kirigami.Theme.textColor, 0.16)
            fillColor: Qt.alpha(Kirigami.Theme.backgroundColor, 0.86)
            joinStyle: ShapePath.RoundJoin
            capStyle: ShapePath.RoundCap
            startX: view.radiusXL
            startY: 0
            PathLine { x: view.width - 172; y: 0 }
            PathQuad {
                x: view.width - 148; y: view.space6
                controlX: view.width - 154; controlY: 0
            }
            PathLine { x: view.width - view.radiusXL; y: view.space6 }
            PathQuad {
                x: view.width; y: view.space6 + view.radiusXL
                controlX: view.width; controlY: view.space6
            }
            PathLine { x: view.width; y: view.height - view.radiusXL }
            PathQuad {
                x: view.width - view.radiusXL; y: view.height
                controlX: view.width; controlY: view.height
            }
            PathLine { x: 116; y: view.height }
            PathQuad {
                x: 92; y: view.height - view.space6
                controlX: 98; controlY: view.height
            }
            PathLine { x: view.radiusXL; y: view.height - view.space6 }
            PathQuad {
                x: 0; y: view.height - view.space6 - view.radiusXL
                controlX: 0; controlY: view.height - view.space6
            }
            PathLine { x: 0; y: view.radiusXL }
            PathQuad {
                x: view.radiusXL; y: 0
                controlX: 0; controlY: 0
            }
        }
    }

    // The Tidal Cut signature: a horizon that deliberately stops short, then
    // resumes as a bright marker. No Canvas/shader and no perpetual motion.
    Row {
        anchors {
            top: parent.top
            left: parent.left
            leftMargin: view.radiusXL
            topMargin: 1
        }
        height: 2
        spacing: view.space2

        Rectangle {
            width: Math.round(view.width * 0.23)
            height: 2
            radius: 1
            color: Kirigami.Theme.highlightColor
            opacity: 0.92
        }
        Rectangle {
            width: view.space2
            height: 2
            radius: 1
            color: Kirigami.Theme.highlightColor
            opacity: 0.38
        }
    }

    Rectangle {
        anchors {
            right: parent.right
            top: parent.top
            rightMargin: view.radiusXL
            topMargin: view.space6 + 2
        }
        width: 2
        height: view.space6
        radius: 1
        color: Kirigami.Theme.highlightColor
        opacity: 0.64
    }

    ColumnLayout {
        id: commandCanvas
        anchors.fill: parent
        anchors.margins: view.space5
        spacing: view.space2
        opacity: view.entranceReady ? 1 : 0
        scale: view.entranceReady ? 1 : 0.985
        transformOrigin: Item.Center
        Behavior on opacity {
            NumberAnimation {
                duration: view.motionMedium
                easing.type: Easing.OutCubic
            }
        }
        Behavior on scale {
            NumberAnimation {
                duration: view.motionMedium
                easing.type: Easing.OutCubic
            }
        }

        // ── Context deck: identity, the day and the local-first promise ─────
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            spacing: view.space4
            // No explicit layoutDirection anywhere in this file: plasmashell runs
            // this popup with LayoutMirroring enabled+inherited on RTL sessions, and
            // mirroring INVERTS an explicit Qt.RightToLeft back to visual LTR. The
            // fifteen rows that declared it rendered backwards; the rows that never
            // mentioned it were correct the whole time. Mirroring is the one system.

            Item {
                Layout.preferredWidth: 44
                Layout.preferredHeight: width

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width
                    height: width
                    radius: view.radiusM
                    // Rim scale (THEME_REV 32): the plate is told by its fill;
                    // the edge is a hint, not an outline. 0.54 drew a hard box
                    // around the mark at rest, every time the launcher opened.
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.16)
                    border.width: 1
                    border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.24)
                }

                Image {
                    anchors.centerIn: parent
                    width: parent.width * 0.76
                    height: width
                    source: "file:///usr/share/moos/moos-logo.png"
                    sourceSize: Qt.size(width * 2, height * 2)
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                Text {
                    text: "MoOS"
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeSubheading
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.4
                }
                Text {
                    text: view.greeting()
                    color: Kirigami.Theme.disabledTextColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeSecondary
                }
            }

            Item { Layout.fillWidth: true }

            RowLayout {
                id: privacyRow
                spacing: view.space2

                Rectangle {
                    Layout.preferredWidth: 7
                    Layout.preferredHeight: 7
                    radius: width / 2
                    color: Kirigami.Theme.positiveTextColor
                }
                Text {
                    text: view.local("محلي وخاص", "LOCAL · PRIVATE")
                    color: Kirigami.Theme.disabledTextColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeCaption
                    font.weight: Font.DemiBold
                    font.letterSpacing: view.rtl ? 0 : 0.9
                }
            }

            Rectangle {
                Layout.preferredWidth: 1
                Layout.preferredHeight: 36
                color: Qt.alpha(Kirigami.Theme.textColor, 0.14)
            }

            ColumnLayout {
                Layout.minimumWidth: 138
                spacing: -1

                Text {
                    Layout.fillWidth: true
                    text: Qt.formatTime(view.now, "HH:mm")
                    horizontalAlignment: view.rtl ? Text.AlignRight : Text.AlignLeft
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeTitle
                    font.weight: Font.DemiBold
                    font.features: ({ "tnum": 1 })
                }
                Text {
                    Layout.fillWidth: true
                    text: view.shortDate()
                    horizontalAlignment: view.rtl ? Text.AlignRight : Text.AlignLeft
                    color: Kirigami.Theme.disabledTextColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeCaption
                    elide: Text.ElideRight
                }
            }
        }

        // ── The command field is the hero, not another menu search box ──────
        Rectangle {
            Layout.fillWidth: true
            Layout.leftMargin: view.space1
            Layout.rightMargin: view.space1
            Layout.preferredHeight: 56
            radius: view.radiusL
            color: Qt.alpha(Kirigami.Theme.backgroundColor,
                searchInput.activeFocus ? 0.96 : 0.78)
            border.width: 1
            border.color: searchInput.activeFocus
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.82)
                : Qt.alpha(Kirigami.Theme.textColor, 0.16)

            Behavior on color { ColorAnimation { duration: view.motionFast } }
            Behavior on border.color { ColorAnimation { duration: view.motionFast } }

            Row {
                anchors {
                    left: parent.left
                    bottom: parent.bottom
                    leftMargin: view.radiusL
                }
                height: 2
                spacing: view.space1

                Rectangle {
                    width: searchInput.activeFocus ? 72 : 36
                    height: 2
                    radius: 1
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.92
                    Behavior on width {
                        NumberAnimation {
                            duration: view.motionMedium
                            easing.type: Easing.OutCubic
                        }
                    }
                }
                Rectangle {
                    width: view.space2
                    height: 2
                    radius: 1
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.32
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: view.space4
                anchors.rightMargin: view.space3
                spacing: view.space4

                Kirigami.Icon {
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 20
                    source: "moos-search-symbolic"
                    color: searchInput.activeFocus
                        ? Kirigami.Theme.highlightColor
                        : Kirigami.Theme.textColor
                    opacity: searchInput.activeFocus ? 1 : 0.72
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    TextInput {
                        id: searchInput
                        anchors.fill: parent
                        verticalAlignment: TextInput.AlignVCenter
                        horizontalAlignment: view.rtl ? TextInput.AlignRight : TextInput.AlignLeft
                        text: view.launcher.searchQuery
                        color: Kirigami.Theme.textColor
                        selectionColor: Kirigami.Theme.highlightColor
                        selectedTextColor: Kirigami.Theme.highlightedTextColor
                        font.family: view.uiFontFamily
                        font.pixelSize: view.typeBody
                        font.weight: Font.Medium
                        selectByMouse: true
                        clip: true
                        inputMethodHints: Qt.ImhNoPredictiveText
                        Accessible.name: view.local(
                            "البحث في التطبيقات والملفات والإعدادات",
                            "Search apps, files and settings")

                        onTextEdited: view.launcher.searchQuery = text
                        onAccepted: view.runCurrentSearchResult()
                        Keys.onDownPressed: event => {
                            if (searchResults.count > 0) {
                                searchResults.currentIndex = Math.max(0, searchResults.currentIndex);
                                searchResults.forceActiveFocus();
                            }
                            event.accepted = true;
                        }

                        Text {
                            anchors.fill: parent
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: view.rtl ? Text.AlignRight : Text.AlignLeft
                            text: view.local(
                                "اكتب أمراً، افتح تطبيقاً، أو اعثر على ملف…",
                                "Run a command, open an app, or find a file…")
                            visible: searchInput.text.length === 0
                            color: Kirigami.Theme.disabledTextColor
                            font: searchInput.font
                            elide: Text.ElideRight
                        }
                    }
                }

                PC3.BusyIndicator {
                    Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                    Layout.preferredHeight: width
                    running: view.searching && view.searchModel.querying
                    visible: running
                }

                PC3.ToolButton {
                    visible: view.launcher.searchQuery.length > 0
                    Layout.minimumWidth: view.targetSize
                    Layout.minimumHeight: view.targetSize
                    icon.name: "moos-close-symbolic"
                    text: view.local("مسح", "Clear")
                    display: PC3.AbstractButton.IconOnly
                    onClicked: {
                        view.launcher.searchQuery = "";
                        view.focusSearch();
                    }
                    PC3.ToolTip.text: text
                    PC3.ToolTip.visible: hovered && text.length > 0
                    PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
                }

                Text {
                    visible: view.launcher.searchQuery.length === 0
                    text: "META"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeCaption
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }
            }
        }

        // ── Navigation + page content ───────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: view.space4

            ColumnLayout {
                readonly property real fixedWidth: 140

                Layout.fillWidth: false
                Layout.minimumWidth: fixedWidth
                Layout.preferredWidth: fixedWidth
                Layout.maximumWidth: fixedWidth
                Layout.fillHeight: true
                spacing: view.space2

                NavButton {
                    page: 0
                    iconName: "moos-home-symbolic"
                    label: view.local("الرئيسية", "Home")
                }
                NavButton {
                    page: 1
                    iconName: "moos-grid-symbolic"
                    label: view.local("التطبيقات", "Applications")
                }
                NavButton {
                    page: 2
                    iconName: "moos-document-symbolic"
                    label: view.local("الأماكن", "Places")
                }
                NavButton {
                    page: 3
                    iconName: "moos-settings-symbolic"
                    label: view.local("تخصيص", "Customize")
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: view.space3
                    Layout.rightMargin: view.space3
                    spacing: view.space2

                    Rectangle {
                        Layout.preferredWidth: 7
                        Layout.preferredHeight: 7
                        radius: width / 2
                        color: Kirigami.Theme.positiveTextColor
                    }
                    Text {
                        Layout.fillWidth: true
                        text: view.local("فهرس محلي", "LOCAL INDEX")
                        color: Kirigami.Theme.disabledTextColor
                        font.family: view.uiFontFamily
                        font.pixelSize: view.typeCaption
                        font.weight: Font.DemiBold
                        font.letterSpacing: view.rtl ? 0 : 0.8
                    }
                }
            }

            Rectangle {
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                color: Qt.alpha(Kirigami.Theme.textColor, 0.10)
            }

            StackLayout {
                id: pages
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: view.searching ? 4 : view.launcher.activePage

                // ── Home: favourites first, recent second ──────────────────
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: view.space3

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumHeight: 64
                            Layout.preferredHeight: 64
                            Layout.maximumHeight: 64
                            spacing: view.space3

                            CommandCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredWidth: 240
                                featured: true
                                iconName: "moos-ai-symbolic"
                                eyebrow: view.local("مساحة ذكية", "INTELLIGENCE")
                                title: view.local("ابدأ مع Mo AI", "Create with Mo AI")
                                onActivated: view.launcher.openDesktop("org.moos.moai.desktop")
                            }
                            CommandCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredWidth: 180
                                iconName: "moos-install-symbolic"
                                eyebrow: view.local("اكتشف", "DISCOVER")
                                title: view.local("متجر MoOS", "MoOS Store")
                                onActivated: view.launcher.openDesktop("org.moos.store.desktop")
                            }
                            CommandCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredWidth: 180
                                iconName: "moos-settings-symbolic"
                                eyebrow: view.local("تحكم", "CONTROL")
                                title: view.local("إعدادات النظام", "System Settings")
                                onActivated: view.launcher.openDesktop("systemsettings.desktop")
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true

                            SectionTitle {
                                Layout.fillWidth: true
                                compact: true
                                title: view.local("مدارك", "Your orbit")
                                subtitle: view.local(
                                    "أقرب تطبيقاتك في متناولك",
                                    "What matters, always within reach")
                            }

                            PC3.Button {
                                Layout.minimumHeight: view.targetSize
                                text: view.launcher.editMode
                                    ? view.local("تم", "Done")
                                    : view.local("تخصيص", "Customize")
                                icon.name: view.launcher.editMode
                                    ? "moos-check-symbolic"
                                    : "moos-pen-symbolic"
                                flat: true
                                checkable: true
                                checked: view.launcher.editMode
                                onClicked: view.launcher.editMode = !view.launcher.editMode
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            GridView {
                                id: favoritesGrid
                                anchors.fill: parent
                                clip: true
                                boundsBehavior: Flickable.StopAtBounds
                                model: view.favoritesModel
                                cellWidth: Math.max(1, Math.floor(width / 4))
                                cellHeight: Plasmoid.configuration.compactTiles
                                    ? 82
                                    : 96
                                keyNavigationWraps: true
                                QQC2.ScrollBar.vertical: QQC2.ScrollBar {
                                    policy: QQC2.ScrollBar.AsNeeded
                                    // Position indicator only: an interactive
                                    // bar's ~21px hit area overlays the
                                    // trailing column's tiles and steals their
                                    // hover-revealed pin button. Wheel, keys
                                    // and touch flicks still scroll the grid.
                                    interactive: false
                                    implicitWidth: 5
                                }

                                delegate: AppTile {
                                    width: GridView.view.cellWidth - view.space1
                                    height: GridView.view.cellHeight - view.space1
                                    sourceModel: view.favoritesModel
                                    favoriteSurface: true
                                }
                            }

                            ColumnLayout {
                                anchors.centerIn: parent
                                width: parent.width * 0.72
                                visible: view.favoritesModel.count === 0
                                spacing: view.space2

                                Item {
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.preferredWidth: 104
                                    Layout.preferredHeight: 104

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: view.radiusXL
                                        color: Qt.alpha(Kirigami.Theme.highlightColor, 0.075)
                                        border.width: 1
                                        border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.24)
                                        rotation: 6
                                    }
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 82
                                        height: 82
                                        radius: view.radiusL
                                        color: Qt.alpha(Kirigami.Theme.backgroundColor, 0.62)
                                        border.width: 1
                                        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.10)
                                        rotation: -5
                                    }
                                    Kirigami.Icon {
                                        anchors.centerIn: parent
                                        width: 72
                                        height: 72
                                        source: "moos-orbit-symbolic"
                                        color: Kirigami.Theme.highlightColor
                                        opacity: 0.42
                                    }
                                    Kirigami.Icon {
                                        anchors.centerIn: parent
                                        width: 40
                                        height: 40
                                        source: "moos-star-symbolic"
                                        color: Kirigami.Theme.textColor
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: view.local(
                                        "اصنع مدارك الخاص",
                                        "Build your own orbit")
                                    horizontalAlignment: Text.AlignHCenter
                                    color: Kirigami.Theme.textColor
                                    font.family: view.uiFontFamily
                                    font.pixelSize: view.typeTitle
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: view.local(
                                        "ثبّت تطبيقاتك المهمة لتبقى في قلب مساحة MoOS",
                                        "Pin what matters and keep it at the heart of MoOS")
                                    horizontalAlignment: Text.AlignHCenter
                                    color: Kirigami.Theme.disabledTextColor
                                    font.family: view.uiFontFamily
                                    font.pixelSize: view.typeSecondary
                                    wrapMode: Text.WordWrap
                                }
                                PC3.Button {
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.minimumHeight: view.targetSize
                                    text: view.local("استكشف التطبيقات", "Explore applications")
                                    icon.name: "moos-grid-symbolic"
                                    onClicked: view.launcher.activePage = 1
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: false
                            Layout.preferredHeight: visible ? Kirigami.Units.gridUnit * 6.6 : 0
                            Layout.minimumHeight: Layout.preferredHeight
                            Layout.maximumHeight: Layout.preferredHeight
                            visible: Plasmoid.configuration.showRecent && view.recentUsageModel.count > 0
                            spacing: view.space2

                            SectionTitle {
                                Layout.fillWidth: true
                                compact: true
                                title: view.local("الأخيرة", "Recent")
                                subtitle: view.local("ارجع لما كنت تعمل عليه", "Pick up where you left off")
                            }

                            ListView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                orientation: ListView.Horizontal
                                spacing: view.space2
                                clip: true
                                boundsBehavior: Flickable.StopAtBounds
                                model: view.recentUsageModel

                                delegate: RecentTile {
                                    width: 156
                                    height: ListView.view.height - view.space2
                                    sourceModel: view.recentUsageModel
                                }
                            }
                        }
                    }
                }

                // ── Applications: complete catalogue with direct pinning ───
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: view.space3

                        RowLayout {
                            Layout.fillWidth: true

                            SectionTitle {
                                Layout.fillWidth: true
                                title: view.local("كل التطبيقات", "All applications")
                                subtitle: view.local(
                                    "افتح تطبيقاً أو ثبته في الرئيسية",
                                    "Open an app or pin it to Home")
                            }

                            PC3.ToolButton {
                                Layout.minimumWidth: view.targetSize
                                Layout.minimumHeight: view.targetSize
                                text: view.local("تحرير قائمة التطبيقات", "Edit application menu")
                                icon.name: "moos-pen-symbolic"
                                display: PC3.AbstractButton.IconOnly
                                onClicked: view.menuEditor.runMenuEditor()
                                PC3.ToolTip.text: text
                                PC3.ToolTip.visible: hovered && text.length > 0
                                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
                            }

                            PC3.ToolButton {
                                Layout.minimumWidth: view.targetSize
                                Layout.minimumHeight: view.targetSize
                                text: Plasmoid.configuration.compactTiles
                                    ? view.local("عرض مريح", "Comfortable view")
                                    : view.local("عرض مضغوط", "Compact view")
                                icon.name: Plasmoid.configuration.compactTiles
                                    ? "moos-document-symbolic"
                                    : "moos-grid-symbolic"
                                display: PC3.AbstractButton.IconOnly
                                onClicked: Plasmoid.configuration.compactTiles = !Plasmoid.configuration.compactTiles
                                PC3.ToolTip.text: text
                                PC3.ToolTip.visible: hovered && text.length > 0
                                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
                            }
                        }

                        GridView {
                            id: applicationsGrid
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            model: view.applicationsModel
                            cellWidth: Math.max(1, Math.floor(width / 4))
                            cellHeight: Plasmoid.configuration.compactTiles
                                ? 82
                                : 96
                            keyNavigationWraps: true
                            QQC2.ScrollBar.vertical: QQC2.ScrollBar {
                                policy: QQC2.ScrollBar.AsNeeded
                                // Same indicator-only contract as the pinned
                                // grid above: never steal trailing-tile input.
                                interactive: false
                                implicitWidth: 5
                            }

                            delegate: AppTile {
                                width: GridView.view.cellWidth - view.space1
                                height: GridView.view.cellHeight - view.space1
                                sourceModel: view.applicationsModel
                                favoriteSurface: false
                            }
                        }
                    }
                }

                // ── Places and devices ─────────────────────────────────────
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: view.space3

                        SectionTitle {
                            Layout.fillWidth: true
                            title: view.local("الأماكن والملفات", "Places & files")
                            subtitle: view.local(
                                "مجلداتك وأقراصك في مكان واحد",
                                "Your folders and storage in one place")
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: scopeCallout.implicitHeight + view.space4
                            radius: view.radiusM
                            color: Qt.alpha(Kirigami.Theme.highlightColor, 0.075)
                            border.width: 1
                            border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.22)

                            RowLayout {
                                id: scopeCallout
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: view.space4
                                anchors.rightMargin: view.space4
                                spacing: view.space3

                                Kirigami.Icon {
                                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                                    Layout.preferredHeight: width
                                    source: "moos-search-symbolic"
                                    color: Kirigami.Theme.highlightColor
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        Layout.fillWidth: true
                                        text: view.local("بحث الملفات يعمل داخل مجلدك الشخصي", "File search covers your home folder")
                                        color: Kirigami.Theme.textColor
                                        font.family: view.uiFontFamily
                                        font.pixelSize: view.typeBody
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: view.local("الملفات المخفية مستثناة لحماية الخصوصية والأداء", "Hidden files stay private and out of the index")
                                        color: Kirigami.Theme.disabledTextColor
                                        font.family: view.uiFontFamily
                                        font.pixelSize: view.typeCaption
                                        elide: Text.ElideRight
                                    }
                                }
                                PC3.Button {
                                    Layout.minimumHeight: view.targetSize
                                    text: view.local("إدارة المواقع", "Manage locations")
                                    icon.name: "moos-settings-symbolic"
                                    onClicked: view.launcher.openDesktop("kcm_baloofile.desktop")
                                }
                            }
                        }

                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: view.space2
                            boundsBehavior: Flickable.StopAtBounds
                            model: view.placesModel

                            delegate: PlaceRow {
                                width: ListView.view.width
                                sourceModel: view.placesModel
                            }
                        }
                    }
                }

                // ── Customisation: visible controls, no mystery config keys ─
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    Flickable {
                        anchors.fill: parent
                        contentWidth: width
                        contentHeight: customizeColumn.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        ColumnLayout {
                            id: customizeColumn
                            width: parent.width
                            spacing: view.space4

                            SectionTitle {
                                Layout.fillWidth: true
                                title: view.local("اجعلها لك", "Make it yours")
                                subtitle: view.local(
                                    "كل تغيير يبقى محفوظاً بعد إعادة التشغيل",
                                    "Every choice persists across restarts")
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: favoritesControl.implicitHeight + view.space6
                                radius: view.radiusM
                                color: Qt.alpha(Kirigami.Theme.textColor, 0.05)
                                border.width: 1
                                border.color: Qt.alpha(Kirigami.Theme.textColor, 0.11)

                                RowLayout {
                                    id: favoritesControl
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.leftMargin: view.space4
                                    anchors.rightMargin: view.space4
                                    spacing: view.space4

                                    Kirigami.Icon {
                                        Layout.preferredWidth: Kirigami.Units.iconSizes.large
                                        Layout.preferredHeight: width
                                        source: "moos-star-symbolic"
                                        color: Kirigami.Theme.highlightColor
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1
                                        Text {
                                            text: view.local("التطبيقات المثبتة", "Pinned applications")
                                            color: Kirigami.Theme.textColor
                                            font.family: view.uiFontFamily
                                            font.pixelSize: view.typeBody
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: view.local(
                                                "أضف بالنجمة، ثم رتّب أو احذف من الرئيسية",
                                                "Star apps, then reorder or remove them on Home")
                                            color: Kirigami.Theme.disabledTextColor
                                            font.family: view.uiFontFamily
                                            font.pixelSize: view.typeCaption
                                            elide: Text.ElideRight
                                        }
                                    }
                                    PC3.Button {
                                        Layout.minimumHeight: view.targetSize
                                        text: view.local("ترتيب الآن", "Arrange now")
                                        icon.name: "moos-pen-symbolic"
                                        onClicked: {
                                            view.launcher.activePage = 0;
                                            view.launcher.editMode = true;
                                        }
                                    }
                                    PC3.Button {
                                        Layout.minimumHeight: view.targetSize
                                        text: view.local("استعادة الافتراضي", "Restore defaults")
                                        icon.name: "moos-refresh-symbolic"
                                        flat: true
                                        onClicked: view.launcher.restoreFavorites()
                                    }
                                }
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                rowSpacing: view.space3
                                columnSpacing: view.space3

                                SettingCard {
                                    iconName: "moos-refresh-symbolic"
                                    title: view.local("العناصر الأخيرة", "Recent items")
                                    description: view.local("أظهر ما استخدمته مؤخراً في الرئيسية", "Show recently used items on Home")
                                    checked: Plasmoid.configuration.showRecent
                                    onToggled: checked => Plasmoid.configuration.showRecent = checked
                                }
                                SettingCard {
                                    iconName: "moos-grid-symbolic"
                                    title: view.local("بطاقات مضغوطة", "Compact tiles")
                                    description: view.local("اعرض تطبيقات أكثر في نفس المساحة", "Fit more apps in the same space")
                                    checked: Plasmoid.configuration.compactTiles
                                    onToggled: checked => Plasmoid.configuration.compactTiles = checked
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: view.space3

                                PC3.Button {
                                    Layout.fillWidth: true
                                    Layout.minimumHeight: view.targetSize
                                    text: view.local("إعدادات مزودي البحث", "Search providers")
                                    icon.name: "moos-search-symbolic"
                                    onClicked: view.launcher.openDesktop("kcm_plasmasearch.desktop")
                                }
                                PC3.Button {
                                    Layout.fillWidth: true
                                    Layout.minimumHeight: view.targetSize
                                    text: view.local("مواقع بحث الملفات", "File search locations")
                                    icon.name: "moos-document-symbolic"
                                    onClicked: view.launcher.openDesktop("kcm_baloofile.desktop")
                                }
                                PC3.Button {
                                    Layout.fillWidth: true
                                    Layout.minimumHeight: view.targetSize
                                    text: view.local("تحرير قائمة التطبيقات", "Edit application menu")
                                    icon.name: "moos-pen-symbolic"
                                    onClicked: view.menuEditor.runMenuEditor()
                                }
                            }
                        }
                    }
                }

                // ── Search results overlay all normal pages ─────────────────
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: view.space2

                        RowLayout {
                            Layout.fillWidth: true

                            SectionTitle {
                                Layout.fillWidth: true
                                title: view.local("نتائج البحث", "Search results")
                                subtitle: view.local(
                                    "تطبيقات، إعدادات، ملفات، مجلدات وأدوات",
                                    "Apps, settings, files, folders and tools")
                            }
                            Text {
                                text: searchResults.count.toString()
                                color: Kirigami.Theme.highlightColor
                                font.family: view.uiFontFamily
                                font.pixelSize: view.typeSecondary
                                font.weight: Font.DemiBold
                            }
                        }

                        ListView {
                            id: searchResults
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: view.space1
                            boundsBehavior: Flickable.StopAtBounds
                            keyNavigationWraps: true
                            currentIndex: -1
                            model: view.searchModel
                            activeFocusOnTab: true
                            Accessible.role: Accessible.List
                            Accessible.name: view.local("نتائج البحث", "Search results")
                            section.property: "category"
                            section.criteria: ViewSection.FullString

                            onCountChanged: {
                                if (count < 1) {
                                    currentIndex = -1;
                                } else if (currentIndex < 0 || currentIndex >= count) {
                                    currentIndex = 0;
                                }
                                view.runQueuedSearchResult();
                            }

                            section.delegate: Text {
                                required property string section
                                width: ListView.view.width
                                height: Kirigami.Units.gridUnit * 1.75
                                verticalAlignment: Text.AlignBottom
                                leftPadding: Kirigami.Units.mediumSpacing
                                rightPadding: Kirigami.Units.mediumSpacing
                                bottomPadding: Kirigami.Units.smallSpacing
                                text: section
                                textFormat: Text.PlainText
                                horizontalAlignment: view.rtl ? Text.AlignRight : Text.AlignLeft
                                color: Kirigami.Theme.highlightColor
                                font.family: view.uiFontFamily
                                font.pixelSize: view.typeCaption
                                font.weight: Font.DemiBold
                            }

                            delegate: SearchResultRow {
                                width: ListView.view.width
                            }

                            Keys.onReturnPressed: event => {
                                view.runCurrentSearchResult();
                                event.accepted = true;
                            }
                            Keys.onEnterPressed: event => {
                                view.runCurrentSearchResult();
                                event.accepted = true;
                            }
                            Keys.onUpPressed: event => {
                                if (currentIndex <= 0) {
                                    view.focusSearch();
                                } else {
                                    decrementCurrentIndex();
                                }
                                event.accepted = true;
                            }
                        }

                        PlasmaExtras.PlaceholderMessage {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: searchResults.count === 0 && !view.searchModel.querying
                            iconName: "moos-search-symbolic"
                            text: view.local("لا توجد نتيجة", "No result found")
                            explanation: view.local(
                                "جرّب اسماً آخر أو راجع مواقع البحث",
                                "Try another name or review search locations")
                            helpfulAction: Kirigami.Action {
                                text: view.local("إعدادات البحث", "Search settings")
                                icon.name: "moos-settings-symbolic"
                                onTriggered: view.launcher.openDesktop("kcm_plasmasearch.desktop")
                            }
                        }
                    }
                }
            }
        }

        // ── Quiet session edge: no duplicate destinations or nested strip ──
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: view.space2
            Layout.rightMargin: view.space2
            Layout.preferredHeight: view.targetSize
            spacing: view.space1

            Kirigami.Icon {
                Layout.preferredWidth: 18
                Layout.preferredHeight: 18
                source: "moos-shield-symbolic"
                color: Kirigami.Theme.positiveTextColor
            }
            Text {
                text: view.local("جلسة محلية موثوقة", "TRUSTED LOCAL SESSION")
                color: Kirigami.Theme.disabledTextColor
                font.family: view.uiFontFamily
                font.pixelSize: view.typeCaption
                font.weight: Font.DemiBold
                font.letterSpacing: view.rtl ? 0 : 0.6
            }

            Item { Layout.fillWidth: true }

            PC3.ToolButton {
                Layout.minimumWidth: view.targetSize
                Layout.minimumHeight: view.targetSize
                text: view.local("ثيمات MoOS", "MoOS Themes")
                icon.name: "moos-ui-symbolic"
                display: PC3.AbstractButton.IconOnly
                onClicked: view.launcher.openDesktop("org.moos.themepicker.desktop")
                PC3.ToolTip.text: text
                PC3.ToolTip.visible: hovered && text.length > 0
                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
            }

            Rectangle {
                Layout.preferredWidth: 1
                Layout.preferredHeight: 22
                color: Qt.alpha(Kirigami.Theme.textColor, 0.14)
            }

            Repeater {
                model: view.sessionModel

                PC3.ToolButton {
                    required property int index
                    required property var model

                    readonly property bool shown: [
                        "lock-screen", "switch-user", "logout", "suspend",
                        "hibernate", "reboot", "shutdown"
                    ]
                        .indexOf(String(model.favoriteId)) >= 0

                    visible: shown
                    Layout.minimumWidth: shown ? view.targetSize : 0
                    Layout.preferredWidth: shown ? Math.max(view.targetSize, implicitWidth) : 0
                    Layout.maximumWidth: shown ? Math.max(view.targetSize, implicitWidth) : 0
                    Layout.minimumHeight: shown ? view.targetSize : 0
                    text: model.display
                    icon.name: view.sessionIcon(model.favoriteId)
                    display: PC3.AbstractButton.IconOnly
                    onClicked: view.launcher.triggerEntry(view.sessionModel, index)
                    PC3.ToolTip.text: text
                    PC3.ToolTip.visible: hovered && text.length > 0
                    PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
                }
            }
        }
    }

    // ── Reusable pieces ─────────────────────────────────────────────────────
    component SectionTitle: ColumnLayout {
        id: sectionTitle
        property string title: ""
        property string subtitle: ""
        property bool compact: false
        spacing: compact ? 0 : view.space1

        Text {
            Layout.fillWidth: true
            text: sectionTitle.title
            textFormat: Text.PlainText
            horizontalAlignment: view.rtl ? Text.AlignRight : Text.AlignLeft
            color: Kirigami.Theme.textColor
            font.family: view.uiFontFamily
            font.pixelSize: sectionTitle.compact ? view.typeEmphasis : view.typeTitle
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            text: sectionTitle.subtitle
            textFormat: Text.PlainText
            horizontalAlignment: view.rtl ? Text.AlignRight : Text.AlignLeft
            visible: text.length > 0
            color: Kirigami.Theme.disabledTextColor
            font.family: view.uiFontFamily
            font.pixelSize: sectionTitle.compact ? view.typeCaption : view.typeSecondary
            elide: Text.ElideRight
        }
    }

    component NavButton: PC3.ItemDelegate {
        id: nav
        required property int page
        property string iconName: ""
        property string label: ""

        Layout.fillWidth: true
        Layout.minimumHeight: 42
        Layout.preferredHeight: 42
        hoverEnabled: true
        Accessible.name: label
        Accessible.role: Accessible.Button
        onClicked: {
            view.launcher.searchQuery = "";
            view.launcher.activePage = page;
        }

        background: Rectangle {
            radius: view.radiusM
            color: view.launcher.activePage === nav.page && !view.searching
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.11)
                : Qt.alpha(Kirigami.Theme.textColor,
                    nav.hovered || nav.activeFocus ? 0.065 : 0.0)
            border.width: nav.activeFocus ? 2 : 0
            border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.78)
            Behavior on color { ColorAnimation { duration: view.motionFast } }

            Rectangle {
                width: 3
                height: parent.height * 0.44
                radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                // Logical start: plasmashell's inherited LayoutMirroring turns
                // this left anchor into the right edge in an RTL session.
                anchors.left: parent.left
                color: Kirigami.Theme.highlightColor
                opacity: view.launcher.activePage === nav.page && !view.searching ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: view.motionFast } }
            }
        }

        contentItem: RowLayout {
            spacing: view.space3

            Kirigami.Icon {
                Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                Layout.preferredHeight: width
                source: nav.iconName
                color: view.launcher.activePage === nav.page && !view.searching
                    ? Kirigami.Theme.highlightColor
                    : Kirigami.Theme.textColor
            }
            Text {
                Layout.fillWidth: true
                text: nav.label
                textFormat: Text.PlainText
                horizontalAlignment: view.rtl ? Text.AlignRight : Text.AlignLeft
                color: Kirigami.Theme.textColor
                font.family: view.uiFontFamily
                font.pixelSize: view.typeSecondary
                font.weight: view.launcher.activePage === nav.page ? Font.DemiBold : Font.Medium
                elide: Text.ElideRight
            }
        }
    }

    component AppTile: PC3.ItemDelegate {
        id: tile
        required property int index
        required property var model
        required property var sourceModel
        property bool favoriteSurface: false

        // The staggered reveal. Each tile arrives a beat after the one before
        // it, so the grid assembles instead of appearing — the difference
        // between a menu and a surface that was built for you.
        //
        // Cost is deliberately near zero: opacity and y only, no shaders and no
        // per-frame work once settled. The delay is CAPPED at 11 steps so a
        // large catalogue cannot turn the entrance into a queue, and the whole
        // thing collapses to an instant 1.0 when motion is off — the gate is
        // named in full rather than through view.motionMedium so it is legible
        // to the reader and to verify_user_experience.
        readonly property int revealDelay:
            Kirigami.Units.longDuration > 1 ? Math.min(tile.index, 11) * 24 : 0
        opacity: view.entranceReady ? 1 : 0
        transform: Translate {
            y: view.entranceReady ? 0 : 6
            Behavior on y {
                SequentialAnimation {
                    PauseAnimation { duration: tile.revealDelay }
                    NumberAnimation {
                        duration: view.motionMedium
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }
        Behavior on opacity {
            SequentialAnimation {
                PauseAnimation { duration: tile.revealDelay }
                NumberAnimation {
                    duration: view.motionMedium
                    easing.type: Easing.OutCubic
                }
            }
        }

        enabled: model.disabled !== true
        hoverEnabled: true
        Accessible.name: String(model.display || "")
        Accessible.role: Accessible.Button
        scale: down ? 0.985 : 1.0
        function activate() { view.launcher.triggerEntry(sourceModel, index); }
        onClicked: activate()
        Keys.onReturnPressed: event => { tile.activate(); event.accepted = true; }
        Keys.onEnterPressed: event => { tile.activate(); event.accepted = true; }
        Keys.onSpacePressed: event => { tile.activate(); event.accepted = true; }

        Behavior on scale {
            NumberAnimation { duration: view.motionFast; easing.type: Easing.OutCubic }
        }

        background: Rectangle {
            radius: view.radiusM
            color: tile.down
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.15)
                : tile.hovered || tile.activeFocus
                    ? Qt.alpha(Kirigami.Theme.highlightColor, 0.085)
                    : "transparent"
            border.width: tile.activeFocus ? 2 : tile.hovered ? 1 : 0
            border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                tile.activeFocus ? 0.82 : 0.34)
            Behavior on color { ColorAnimation { duration: view.motionFast } }
            Behavior on border.color { ColorAnimation { duration: view.motionFast } }
        }

        contentItem: ColumnLayout {
            anchors.margins: view.space1
            spacing: view.space1

            Kirigami.Icon {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Plasmoid.configuration.compactTiles
                    ? Kirigami.Units.iconSizes.medium
                    : 44
                Layout.preferredHeight: width
                source: tile.model.decoration || "moos-cube-symbolic"
                animated: false
            }
            Text {
                Layout.fillWidth: true
                text: String(tile.model.compactName || tile.model.display || "")
                textFormat: Text.PlainText
                color: Kirigami.Theme.textColor
                font.family: view.uiFontFamily
                font.pixelSize: view.typeSecondary
                font.weight: Font.Medium
                horizontalAlignment: Text.AlignHCenter
                maximumLineCount: 1
                elide: Text.ElideRight
            }
        }

        PC3.ToolButton {
            anchors.top: parent.top
            // Logical trailing corner; inherited mirroring moves it left in RTL.
            anchors.right: parent.right
            anchors.margins: view.space1
            width: view.targetSize
            height: view.targetSize
            z: 4
            visible: !tile.favoriteSurface && (tile.hovered || view.launcher.editMode)
                && String(tile.model.favoriteId || "").length > 0
            checkable: true
            checked: view.favoritesModel.isFavorite(String(tile.model.favoriteId || ""))
            icon.name: "moos-star-symbolic"
            text: view.favoritesModel.isFavorite(String(tile.model.favoriteId || ""))
                ? view.local("إزالة من المثبتة", "Unpin")
                : view.local("تثبيت في الرئيسية", "Pin to Home")
            display: PC3.AbstractButton.IconOnly
            onClicked: view.launcher.toggleFavorite(String(tile.model.favoriteId || ""))
            PC3.ToolTip.text: text
            PC3.ToolTip.visible: hovered && text.length > 0
            PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 1
            z: 4
            visible: tile.favoriteSurface && view.launcher.editMode
            spacing: 1

            PC3.ToolButton {
                width: view.targetSize
                height: view.targetSize
                icon.name: view.rtl
                    ? "moos-arrow-symbolic"
                    : "moos-arrow-back-symbolic"
                text: view.local("نقل للخلف", "Move earlier")
                display: PC3.AbstractButton.IconOnly
                enabled: tile.index > 0
                onClicked: view.launcher.moveFavorite(tile.index, tile.index - 1)
                PC3.ToolTip.text: text
                PC3.ToolTip.visible: hovered && text.length > 0
                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
            }
            PC3.ToolButton {
                width: view.targetSize
                height: view.targetSize
                icon.name: "moos-trash-symbolic"
                text: view.local("إزالة", "Remove")
                display: PC3.AbstractButton.IconOnly
                onClicked: view.launcher.toggleFavorite(String(tile.model.favoriteId || ""))
                PC3.ToolTip.text: text
                PC3.ToolTip.visible: hovered && text.length > 0
                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
            }
            PC3.ToolButton {
                width: view.targetSize
                height: view.targetSize
                icon.name: view.rtl
                    ? "moos-arrow-back-symbolic"
                    : "moos-arrow-symbolic"
                text: view.local("نقل للأمام", "Move later")
                display: PC3.AbstractButton.IconOnly
                enabled: tile.index < view.favoritesModel.count - 1
                onClicked: view.launcher.moveFavorite(tile.index, tile.index + 1)
                PC3.ToolTip.text: text
                PC3.ToolTip.visible: hovered && text.length > 0
                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
            }
        }
    }

    component RecentTile: PC3.ItemDelegate {
        id: recent
        required property int index
        required property var model
        required property var sourceModel

        enabled: model.disabled !== true
        hoverEnabled: true
        Accessible.name: String(model.display || "")
        Accessible.description: String(model.description || "")
        Accessible.role: Accessible.Button
        function activate() { view.launcher.triggerEntry(sourceModel, index); }
        onClicked: activate()
        Keys.onReturnPressed: event => { recent.activate(); event.accepted = true; }
        Keys.onEnterPressed: event => { recent.activate(); event.accepted = true; }
        Keys.onSpacePressed: event => { recent.activate(); event.accepted = true; }
        background: Rectangle {
            radius: view.radiusM
            color: recent.hovered || recent.activeFocus
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.085)
                : "transparent"
            border.width: recent.activeFocus ? 2 : recent.hovered ? 1 : 0
            border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                recent.activeFocus ? 0.82 : 0.34)
            // Ease the hover like every sibling row (FavoriteTile/nav/search) —
            // was the one Recent row whose prelight snapped instead of gliding.
            Behavior on color { ColorAnimation { duration: view.motionFast } }
            Behavior on border.color { ColorAnimation { duration: view.motionFast } }
        }
        contentItem: RowLayout {
            spacing: view.space3
            Kirigami.Icon {
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.preferredHeight: width
                source: recent.model.decoration || "moos-document-symbolic"
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Text {
                    Layout.fillWidth: true
                    text: String(recent.model.compactName || recent.model.display || "")
                    textFormat: Text.PlainText
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeSecondary
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: String(recent.model.description || "")
                    textFormat: Text.PlainText
                    color: Kirigami.Theme.disabledTextColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeCaption
                    elide: Text.ElideMiddle
                }
            }
        }
    }

    component PlaceRow: PC3.ItemDelegate {
        id: place
        required property int index
        required property var model
        required property var sourceModel

        height: 52
        enabled: model.disabled !== true
        hoverEnabled: true
        Accessible.name: String(model.display || "")
        Accessible.description: String(model.description || "")
        Accessible.role: Accessible.Button
        function activate() { view.launcher.triggerEntry(sourceModel, index); }
        onClicked: activate()
        Keys.onReturnPressed: event => { place.activate(); event.accepted = true; }
        Keys.onEnterPressed: event => { place.activate(); event.accepted = true; }
        Keys.onSpacePressed: event => { place.activate(); event.accepted = true; }
        background: Rectangle {
            radius: view.radiusM
            color: place.hovered || place.activeFocus
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.085)
                : "transparent"
            border.width: place.activeFocus ? 2 : place.hovered ? 1 : 0
            border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                place.activeFocus ? 0.82 : 0.34)
            // Same eased-hover parity as the Favorite/Recent/nav rows.
            Behavior on color { ColorAnimation { duration: view.motionFast } }
            Behavior on border.color { ColorAnimation { duration: view.motionFast } }
        }
        contentItem: RowLayout {
            spacing: view.space3
            Kirigami.Icon {
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.preferredHeight: width
                source: place.model.decoration || "moos-document-symbolic"
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Text {
                    Layout.fillWidth: true
                    text: String(place.model.compactName || place.model.display || "")
                    textFormat: Text.PlainText
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeBody
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: String(place.model.description || "")
                    textFormat: Text.PlainText
                    color: Kirigami.Theme.disabledTextColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeCaption
                    elide: Text.ElideMiddle
                }
            }
            Kirigami.Icon {
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: width
                source: view.rtl
                    ? "moos-arrow-back-symbolic"
                    : "moos-arrow-symbolic"
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }

    component SearchResultRow: PC3.ItemDelegate {
        id: result
        required property int index
        required property var model

        height: 56
        enabled: model.enabled !== false
        hoverEnabled: true
        Accessible.name: String(model.display || "")
        Accessible.description: String(model.subtext || "")
        Accessible.role: Accessible.ListItem
        onHoveredChanged: {
            if (hovered) {
                result.ListView.view.currentIndex = index;
            }
        }
        onClicked: view.launcher.runSearchResult(index)

        background: Rectangle {
            radius: view.radiusM
            color: result.ListView.isCurrentItem
                ? Qt.alpha(Kirigami.Theme.highlightColor, result.down ? 0.18 : 0.105)
                : result.hovered
                    ? Qt.alpha(Kirigami.Theme.textColor, 0.055)
                    : "transparent"
            border.width: result.activeFocus ? 2
                : result.ListView.isCurrentItem ? 1 : 0
            border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                result.activeFocus ? 0.82 : 0.34)
            Behavior on color { ColorAnimation { duration: view.motionFast } }
        }

        contentItem: RowLayout {
            spacing: view.space3

            Rectangle {
                Layout.preferredWidth: view.targetSize
                Layout.preferredHeight: width
                radius: view.radiusM
                color: Qt.alpha(Kirigami.Theme.highlightColor, 0.10)
                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: Kirigami.Units.iconSizes.medium
                    height: width
                    source: result.model.decoration || "moos-search-symbolic"
                    animated: false
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Text {
                    Layout.fillWidth: true
                    text: String(result.model.display || "")
                    textFormat: Text.PlainText
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeBody
                    font.weight: Font.Medium
                    elide: Text.ElideMiddle
                }
                Text {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: String(result.model.subtext || "")
                    textFormat: Text.PlainText
                    color: Kirigami.Theme.disabledTextColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeCaption
                    elide: Text.ElideMiddle
                }
            }
            Text {
                visible: result.ListView.isCurrentItem
                text: "↵"
                color: Kirigami.Theme.highlightColor
                font.family: view.uiFontFamily
                font.pixelSize: view.typeBody
            }
        }
    }

    component CommandCard: PC3.ItemDelegate {
        id: command
        property string iconName: "moos-spark-symbolic"
        property string eyebrow: ""
        property string title: ""
        property bool featured: false
        signal activated()

        hoverEnabled: true
        Accessible.name: command.title
        Accessible.description: command.eyebrow
        Accessible.role: Accessible.Button
        scale: down ? 0.985 : 1
        onClicked: command.activated()
        Keys.onReturnPressed: event => {
            command.activated();
            event.accepted = true;
        }
        Keys.onEnterPressed: event => {
            command.activated();
            event.accepted = true;
        }
        Keys.onSpacePressed: event => {
            command.activated();
            event.accepted = true;
        }

        Behavior on scale {
            NumberAnimation {
                duration: view.motionFast
                easing.type: Easing.OutCubic
            }
        }

        background: Rectangle {
            radius: view.radiusL
            color: Qt.alpha(command.featured || command.hovered
                ? Kirigami.Theme.highlightColor
                : Kirigami.Theme.textColor,
                command.down ? 0.16
                    : (command.featured ? 0.105 : (command.hovered ? 0.075 : 0.025)))
            border.width: command.activeFocus ? 2 : 1
            border.color: Qt.alpha(command.featured || command.activeFocus
                ? Kirigami.Theme.highlightColor
                : Kirigami.Theme.textColor,
                command.activeFocus ? 0.82 : command.featured ? 0.34 : 0.09)
            Behavior on color { ColorAnimation { duration: view.motionFast } }
            Behavior on border.color { ColorAnimation { duration: view.motionFast } }

            Rectangle {
                anchors {
                    left: parent.left
                    bottom: parent.bottom
                    leftMargin: view.radiusL
                }
                width: command.featured ? 42 : 18
                height: 2
                radius: 1
                color: Kirigami.Theme.highlightColor
                opacity: command.featured || command.hovered ? 0.94 : 0.34
                Behavior on width {
                    NumberAnimation {
                        duration: view.motionMedium
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }

        contentItem: RowLayout {
            spacing: view.space3

            Rectangle {
                Layout.preferredWidth: 38
                Layout.preferredHeight: 38
                radius: view.radiusM
                color: Qt.alpha(Kirigami.Theme.highlightColor,
                    command.featured ? 0.18 : 0.10)

                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: 22
                    height: 22
                    source: command.iconName
                    color: command.featured
                        ? Kirigami.Theme.highlightColor
                        : Kirigami.Theme.textColor
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: -1

                Text {
                    Layout.fillWidth: true
                    text: command.eyebrow
                    color: command.featured
                        ? Kirigami.Theme.highlightColor
                        : Kirigami.Theme.disabledTextColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeCaption
                    font.weight: Font.DemiBold
                    font.letterSpacing: view.rtl ? 0 : 0.7
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: command.title
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeSecondary
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
            }
        }
    }

    component SettingCard: Rectangle {
        id: setting
        property string iconName: "moos-settings-symbolic"
        property string title: ""
        property string description: ""
        property bool checked: false
        signal toggled(bool checked)

        Layout.fillWidth: true
        Layout.preferredHeight: 104
        radius: view.radiusM
        color: Qt.alpha(Kirigami.Theme.textColor, 0.045)
        border.width: 1
        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.10)

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: view.space4
            spacing: view.space2

            RowLayout {
                Layout.fillWidth: true
                Kirigami.Icon {
                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                    Layout.preferredHeight: width
                    source: setting.iconName
                    color: Kirigami.Theme.highlightColor
                }
                Text {
                    Layout.fillWidth: true
                    text: setting.title
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeBody
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                PC3.Switch {
                    checked: setting.checked
                    Accessible.name: setting.title
                    onToggled: setting.toggled(checked)
                }
            }
            Text {
                Layout.fillWidth: true
                text: setting.description
                color: Kirigami.Theme.disabledTextColor
                font.family: view.uiFontFamily
                font.pixelSize: view.typeCaption
                wrapMode: Text.WordWrap
                maximumLineCount: 2
            }
        }
    }
}

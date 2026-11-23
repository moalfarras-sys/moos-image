// The full MoOS Launcher surface. All colours come from Kirigami.Theme; the
// Plasma dialog behind this item supplies the family-specific glass and blur.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQml.Models
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PC3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI
import "code/kicker-tools.js" as KickerTools

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

    // Semantic aliases keep this large shell surface readable while their
    // values come from the one generated MoOS Design Core.
    readonly property var design: MoUI.Tokens
    readonly property string uiFontFamily: Qt.application.font.family
    readonly property int space1: design.space1
    readonly property int space2: design.space2
    readonly property int space3: design.space3
    readonly property int space4: design.space4
    readonly property int space5: design.space5
    readonly property int space6: design.space5
    readonly property int radiusS: design.radiusSmall
    readonly property int radiusM: design.radiusControl
    readonly property int radiusL: design.radiusCard
    readonly property int radiusXL: design.radiusPanel
    readonly property int targetSize: design.targetControl
    readonly property int typeCaption: design.typeCaption
    readonly property int typeSecondary: design.typeSecondary
    readonly property int typeBody: design.typeBody
    readonly property int typeEmphasis: design.typeLabel
    readonly property int typeSubheading: design.typeTitle
    readonly property int typeTitle: design.typeTitle
    readonly property int motionFast: design.duration(
        Kirigami.Units.longDuration > 1, design.motionFast)
    readonly property int motionMedium: design.duration(
        Kirigami.Units.longDuration > 1, design.motionGeometry)
    readonly property bool lightSurface: design.isLight(Kirigami.Theme.backgroundColor)
    readonly property color secondaryInk: Qt.alpha(Kirigami.Theme.textColor, 0.78)

    onVisibleChanged: if (!visible && pages) { pages.settlePage(); }
    onMotionMediumChanged: if (motionMedium === 0 && pages) { pages.settlePage(); }

    // Fit the current work area in logical pixels. Keep the normal wide
    // composition; reflow content instead of scaling text or touch targets.
    readonly property bool immersive: launcher.tabletMode === true
        || (launcher.popupAvailableWidth < 640
            && launcher.popupAvailableHeight > launcher.popupAvailableWidth * 1.12)
    readonly property bool spacious: !immersive
        && launcher.popupAvailableWidth >= 1440 && launcher.popupAvailableHeight >= 780
    implicitWidth: Math.min(immersive ? launcher.popupAvailableWidth - 24
        : spacious ? 1040 : design.dialogWidth,
        Math.max(1, launcher.popupAvailableWidth - 8))
    implicitHeight: Math.min(immersive ? launcher.popupAvailableHeight - 24
        : spacious ? 720 : design.dialogHeight,
        Math.max(1, launcher.popupAvailableHeight - (immersive ? 24 : 64)))
    Layout.minimumWidth: implicitWidth
    Layout.minimumHeight: implicitHeight
    Layout.maximumWidth: implicitWidth
    Layout.maximumHeight: implicitHeight
    readonly property bool compact: width < 640
    readonly property bool narrow: width < 480
    readonly property bool shortLayout: height < 520
    readonly property int touchTarget: design.targetControl
    readonly property int canvasMargin: compact ? space3 : space5

    function appColumns(availableWidth) {
        return Math.max(1, Math.min(8, Math.floor(availableWidth / 112)));
    }
    function favoriteColumns(availableWidth, count) {
        const capacity = view.appColumns(availableWidth);
        const rows = Math.max(1, Math.ceil(Math.max(1, count) / capacity));
        return Math.max(1, Math.min(capacity, Math.ceil(count / rows)));
    }
    function appRowHeight(availableHeight, minimum) {
        const room = Math.max(1, Math.floor(availableHeight));
        const rows = Math.max(1, Math.floor(room / minimum));
        return Math.max(minimum, Math.floor(room / rows));
    }
    function selectCategory(row) {
        const catalogue = view.launcher.appRootModel;
        // Row zero is Kicker's deliberately invisible favorites placeholder.
        // Categories and their children remain native models, including after
        // a Store install refreshes KService. Never build a second app index.
        if (row < 1 || row >= catalogue.count || !catalogue.modelForRow(row)) return;
        view.launcher.appsModelRow = row;
        view.launcher.appFolderPath = [];
        applicationsGrid.currentIndex = 0;
        applicationsGrid.positionViewAtBeginning();
    }
    function focusCategory(row) {
        row = Math.max(1, Math.min(view.launcher.appRootModel.count - 1, row));
        view.selectCategory(row);
        categoryStrip.positionViewAtIndex(row, ListView.Contain);
        Qt.callLater(() => {
            const button = categoryStrip.itemAtIndex(row);
            if (button) button.forceActiveFocus();
        });
    }
    function sessionActionShown(actionId) {
        return ["lock-screen", "switch-user", "logout", "suspend",
                "hibernate", "reboot", "shutdown"].indexOf(String(actionId)) >= 0;
    }

    MovaActionMenu { id: appActions; objectName: "movaAppActions" }
    function openAppActions(tile) {
        if (!tile || tile.index < 0) return;
        const actions = tile.model.hasActionList === true ? tile.model.actionList : [];
        KickerTools.fillActionMenu(i18n, appActions, actions,
            view.favoritesModel, String(tile.model.favoriteId || ""));
        if (tile.favoriteSurface) {
            const extra = Array.from(appActions.actionList || []);
            extra.push({type: "separator"},
                {text: view.local("نقل للخلف", "Move earlier"), actionId: "_mova_move_earlier", enabled: tile.index > 0},
                {text: view.local("نقل للأمام", "Move later"), actionId: "_mova_move_later", enabled: tile.index < view.favoritesModel.count - 1});
            appActions.actionList = extra;
        }
        if (!appActions.actionList || appActions.actionList.length === 0) return;
        appActions.visualParent = tile;
        appActions.delegate = tile;
        appActions.favoriteIdentity = tile.favoriteId;
        appActions.nativeModel = tile.baseModel;
        appActions.open();
    }

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
        // both read as mystery buttons on the real 4K session. Suspend and
        // hibernate once shared the moon: two identical buttons side by side
        // that only a tooltip told apart (A1, 2026-09-18). Hibernate is the one
        // that writes the session to disk, so it wears the disk.
        const icons = {
            "lock-screen": "moos-lock-symbolic",
            "switch-user": "moos-user-symbolic",
            "logout": "moos-logout-symbolic",
            "suspend": "moos-moon-symbolic",
            "hibernate": "moos-storage-symbolic",
            "reboot": "moos-refresh-symbolic",
            "shutdown": "moos-power-symbolic"
        };
        return icons[String(actionId)] || "moos-power-symbolic";
    }

    function focusSearch() {
        searchInput.forceActiveFocus();
        searchInput.selectAll();
    }

    // Move keyboard focus from the search field (or the sidebar) INTO the
    // surface the user is looking at. Every non-search page has one primary
    // interactive region; this is the single owner of "which one". Down from
    // the search field and the logical-forward arrow from a NavButton both
    // land here, so the launcher is fully operable without a pointer.
    function focusActivePageContent() {
        if (view.searching) {
            if (searchResults.count > 0) {
                searchResults.currentIndex = Math.max(0, searchResults.currentIndex);
                searchResults.forceActiveFocus();
            }
            return;
        }
        switch (view.launcher.activePage) {
        case 0:
            if (view.favoritesModel.count > 0) {
                favoritesGrid.currentIndex = Math.max(0, favoritesGrid.currentIndex);
                favoritesGrid.forceActiveFocus();
            } else {
                homeExploreButton.forceActiveFocus();
            }
            break;
        case 1:
            applicationsGrid.currentIndex = Math.max(0, applicationsGrid.currentIndex);
            applicationsGrid.forceActiveFocus();
            break;
        case 2:
            if (placesList.count > 0) {
                placesList.currentIndex = Math.max(0, placesList.currentIndex);
                placesList.forceActiveFocus();
            }
            break;
        case 3:
            customizeArrangeButton.forceActiveFocus();
            break;
        }
    }

    // The NavButton for a page, so a grid/list can hand focus back to the
    // sidebar entry it belongs under (Shift+Tab), not just the last one.
    function navForPage(page) {
        return page === 0 ? navHome
             : page === 2 ? navPlaces
             : page === 3 ? navCustomize
             : navApps;
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

    // Shared by every application tile: one metrics object, not one per tile.
    FontMetrics {
        id: tileLabelMetrics
        font.family: view.uiFontFamily
        font.pixelSize: view.typeSecondary
        font.weight: Font.Medium
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

    // One calm material layer. KWin owns blur and shadow; this item supplies a
    // clean, continuous silhouette with no clipped shelves, wireframe corners or
    // competing outline segments. Semantic colours keep the same MoOS identity
    // in every light/dark family without turning the launcher into neon chrome.
    MoUI.GlassSurface {
        id: canvasGlass
        anchors.fill: parent
        radius: view.radiusXL
        depth: design.glassLevelPopover
        // The complete canvas owns its entrance; do not animate two sheets.
        animateArrival: false
        // Keep the reading plane dense even in Clear mode. Solid/no-blur and
        // live compositor changes follow the same owner as Settings and Search.
        readonly property real readingOpacity: view.lightSurface ? 0.92 : 0.86
        fillOpacity: Math.max(readingOpacity,
            design.glassFill(surfaceColor, depth, readingOpacity))
        border.width: design.borderHairline
        antialiasing: true
    }

    // A still, low-amplitude horizon held inside the material. It connects the
    // Command Canvas to the generated wallpaper family without adding a timer,
    // shader or second shell. The outer Plasma dialog remains the only blur and
    // shadow owner.
    //
    // It rises vertically from the sheet's lower rim and has no edge of its own.
    // The earlier horizontal pill (16% of the height, radius height/2) drew a
    // hard top line and visible gradient columns across the bottom content row
    // on the physical 3840x2160 V3 at scale 2.5.
    Rectangle {
        objectName: "movaHorizon"
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            margins: design.borderHairline
        }
        height: Math.round(view.height * 0.22)
        radius: view.radiusXL
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop {
                position: 1.0
                color: Qt.alpha(Kirigami.Theme.highlightColor,
                    view.lightSurface ? 0.045 : 0.075)
            }
        }
    }

    ColumnLayout {
        id: commandCanvas
        anchors.fill: parent
        anchors.margins: view.canvasMargin
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
            Layout.preferredHeight: view.shortLayout ? 32 : 50
            spacing: view.space4
            // No explicit layoutDirection anywhere in this file: plasmashell runs
            // this popup with LayoutMirroring enabled+inherited on RTL sessions, and
            // mirroring INVERTS an explicit Qt.RightToLeft back to visual LTR. The
            // fifteen rows that declared it rendered backwards; the rows that never
            // mentioned it were correct the whole time. Mirroring is the one system.

            Item {
                Layout.preferredWidth: view.shortLayout ? 32 : 44
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
                    text: "Mova"
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeSubheading
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.4
                }
                Text {
                    text: view.greeting()
                    visible: !view.shortLayout
                    color: view.secondaryInk
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeSecondary
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: 1
                Layout.preferredHeight: 36
                visible: !view.narrow
                color: Qt.alpha(Kirigami.Theme.textColor, 0.14)
            }

            ColumnLayout {
                Layout.minimumWidth: view.narrow ? 80 : 138
                visible: !view.narrow
                spacing: -1

                Text {
                    Layout.fillWidth: true
                    text: Qt.formatTime(view.now, "HH:mm")
                    horizontalAlignment: Text.AlignLeft
                    color: Kirigami.Theme.textColor
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeTitle
                    font.weight: Font.DemiBold
                    font.features: ({ "tnum": 1 })
                }
                Text {
                    Layout.fillWidth: true
                    text: view.shortDate()
                    visible: !view.shortLayout
                    horizontalAlignment: Text.AlignLeft
                    color: view.secondaryInk
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
            // The MoOS corner: the top-trailing corner is square.
            topLeftRadius: LayoutMirroring.enabled ? Math.min(radius, design.radiusSquare) : radius
            topRightRadius: LayoutMirroring.enabled ? radius : Math.min(radius, design.radiusSquare)
            color: Qt.alpha(Kirigami.Theme.backgroundColor,
                searchInput.activeFocus ? 0.96 : 0.78)
            border.width: 1
            border.color: searchInput.activeFocus
                ? Qt.alpha(Kirigami.Theme.textColor, 0.28)
                : Qt.alpha(Kirigami.Theme.textColor, 0.16)

            Behavior on color { ColorAnimation { duration: view.motionFast } }
            Behavior on border.color { ColorAnimation { duration: view.motionFast } }

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
                        horizontalAlignment: TextInput.AlignLeft
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
                        // Down leaves the field for the content the user can
                        // see: the results list while searching, otherwise the
                        // active page's primary grid/list. focusActivePageContent
                        // owns that choice for every route into the surface.
                        Keys.onDownPressed: event => {
                            view.focusActivePageContent();
                            event.accepted = true;
                        }

                        Text {
                            anchors.fill: parent
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignLeft
                            text: view.local(
                                "اكتب أمراً، افتح تطبيقاً، أو اعثر على ملف…",
                                "Run a command, open an app, or find a file…")
                            visible: searchInput.text.length === 0
                            color: view.secondaryInk
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
                    visible: !view.compact && view.launcher.searchQuery.length === 0
                    text: "Esc"
                    color: view.secondaryInk
                    font.family: view.uiFontFamily
                    font.pixelSize: view.typeCaption
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }
            }
        }

        // ── Navigation + page content ───────────────────────────────────────
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: view.compact ? 1 : 3
            columnSpacing: view.space4
            rowSpacing: view.space2

            GridLayout {
                id: navigation
                columns: view.compact ? 4 : 1
                columnSpacing: view.space1
                rowSpacing: view.space2
                Layout.fillWidth: view.compact
                Layout.minimumWidth: view.compact ? 0 : 140
                Layout.preferredWidth: view.compact ? -1 : 140
                Layout.maximumWidth: view.compact ? Infinity : 140
                Layout.fillHeight: !view.compact
                Layout.alignment: Qt.AlignTop

                // Up/Down cycle the four; the ids let each one name its
                // neighbours so the ring wraps without a Repeater (which would
                // cost these explicit, page-bound instances their identity).
                NavButton {
                    id: navHome
                    page: 0
                    iconName: "moos-home-symbolic"
                    label: view.local("الرئيسية", "Home")
                    navUp: navCustomize
                    navDown: navApps
                }
                NavButton {
                    id: navApps
                    page: 1
                    iconName: "moos-grid-symbolic"
                    label: view.local("المكتبة", "Library")
                    navUp: navHome
                    navDown: navPlaces
                }
                NavButton {
                    id: navPlaces
                    page: 2
                    iconName: "moos-document-symbolic"
                    label: view.local("الأماكن", "Places")
                    navUp: navApps
                    navDown: navCustomize
                }
                NavButton {
                    id: navCustomize
                    page: 3
                    iconName: "moos-settings-symbolic"
                    label: view.local("تخصيص", "Customize")
                    navUp: navPlaces
                    navDown: navHome
                }

                Item { visible: !view.compact; Layout.fillHeight: true }

                RowLayout {
                    visible: !view.compact
                    Layout.fillWidth: true
                    Layout.leftMargin: view.space3
                    Layout.rightMargin: view.space3
                    spacing: view.space2

                    Text {
                        Layout.fillWidth: true
                        text: view.local("تنقّل بمفاتيح الأسهم", "Navigate with arrow keys")
                        color: view.secondaryInk
                        font.family: view.uiFontFamily
                        font.pixelSize: view.typeCaption
                        font.weight: Font.DemiBold
                        font.letterSpacing: view.rtl ? 0 : 0.8
                    }
                }
            }

            Rectangle {
                visible: !view.compact
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                color: Qt.alpha(Kirigami.Theme.textColor, 0.10)
            }

            StackLayout {
                id: pages
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: view.searching ? 4 : view.launcher.activePage
                property int previousIndex: 0
                property real arrivalOffset: 0
                readonly property bool pageAnimating: pageTurn.running
                readonly property real pageTranslation: pageShift.x
                transform: Translate { id: pageShift }
                function settlePage() {
                    if (pageTurn) { pageTurn.stop(); }
                    pages.opacity = 1;
                    if (pageShift) { pageShift.x = 0; }
                }
                onCurrentIndexChanged: {
                    const direction = currentIndex >= previousIndex ? 1 : -1;
                    previousIndex = currentIndex;
                    settlePage();
                    if (view.visible && view.launcher.expanded && view.entranceReady
                            && view.motionMedium > 0) {
                        arrivalOffset = (view.rtl ? -1 : 1) * direction * view.space3;
                        pageTurn.restart();
                    }
                }
                ParallelAnimation {
                    id: pageTurn
                    NumberAnimation {
                        target: pages; property: "opacity"; from: 0.88; to: 1
                        duration: view.motionMedium; easing.type: view.design.easeStandard
                    }
                    NumberAnimation {
                        target: pageShift; property: "x"; from: pages.arrivalOffset; to: 0
                        duration: view.motionMedium; easing.type: view.design.easeStandard
                    }
                }

                // ── Home: favourites first, recent second ──────────────────
                Flickable {
                    id: homeScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: width
                    contentHeight: Math.max(height, homeColumn.implicitHeight)
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    QQC2.ScrollBar.vertical: QQC2.ScrollBar { interactive: false }
                    ScrollEdge { flick: homeScroll }

                    function reveal(item) {
                        const point = item.mapToItem(homeColumn, 0, 0);
                        contentY = Math.max(0, Math.min(contentHeight - height,
                            Math.min(point.y, Math.max(contentY, point.y + item.height - height))));
                    }

                    ColumnLayout {
                        id: homeColumn
                        width: homeScroll.width
                        height: Math.max(homeScroll.height, implicitHeight)
                        spacing: view.space3

                        RowLayout {
                            Layout.fillWidth: true

                            SectionTitle {
                                objectName: "launcherPinnedHeading"
                                Layout.fillWidth: true
                                compact: true
                                title: view.local("تطبيقاتك المفضّلة", "Pinned applications")
                                subtitle: view.local(
                                    "مساحتك تبدأ بما تستخدمه",
                                    "Your space starts with what you use")
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
                            Layout.fillHeight: false
                            Layout.preferredHeight: view.favoritesModel.count > 0
                                ? Math.max(1, Math.min(3, Math.ceil(view.favoritesModel.count / Math.max(1, favoritesGrid.columns)))) * favoritesGrid.cellHeight
                                : emptyOrbit.implicitHeight
                            Layout.minimumHeight: Layout.preferredHeight

                            GridView {
                                id: favoritesGrid
                                onActiveFocusChanged: if (activeFocus) homeScroll.reveal(parent)
                                anchors.fill: parent
                                clip: true
                                boundsBehavior: Flickable.StopAtBounds
                                model: view.favoritesModel
                                cellWidth: Math.max(1, Math.floor(width / view.favoriteColumns(width, view.favoritesModel.count)))
                                cellHeight: Plasmoid.configuration.compactTiles
                                    ? 100
                                    : 128
                                keyNavigationWraps: true
                                activeFocusOnTab: true
                                readonly property int columns: Math.max(
                                    1, Math.floor(width / Math.max(1, cellWidth)))
                                // From the top row, Up returns to the search
                                // field — the same contract the results list
                                // already honours. Shift+Tab goes to this
                                // page's sidebar entry, not the last one.
                                KeyNavigation.priority: KeyNavigation.BeforeItem
                                KeyNavigation.backtab: navHome
                                Keys.onUpPressed: event => {
                                    if (currentIndex < columns) {
                                        view.focusSearch();
                                    } else {
                                        moveCurrentIndexUp();
                                    }
                                    event.accepted = true;
                                }
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
                                id: emptyOrbit
                                anchors.centerIn: parent
                                width: parent.width * 0.90
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
                                    color: view.secondaryInk
                                    font.family: view.uiFontFamily
                                    font.pixelSize: view.typeSecondary
                                    wrapMode: Text.WordWrap
                                }
                                PC3.Button {
                                    id: homeExploreButton
                                    onActiveFocusChanged: if (activeFocus) homeScroll.reveal(emptyOrbit)
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.minimumHeight: view.targetSize
                                    text: view.local("استكشف التطبيقات", "Explore applications")
                                    icon.name: "moos-grid-symbolic"
                                    activeFocusOnTab: true
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
                                title: view.local("تابع عملك", "Continue your work")
                                subtitle: view.local("ارجع لما كنت تعمل عليه", "Pick up where you left off")
                            }

                            ListView {
                                id: recentStrip
                                onActiveFocusChanged: if (activeFocus) homeScroll.reveal(parent)
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                orientation: ListView.Horizontal
                                spacing: view.space2
                                clip: true
                                boundsBehavior: Flickable.StopAtBounds
                                keyNavigationWraps: true
                                activeFocusOnTab: true
                                currentIndex: -1
                                model: view.recentUsageModel
                                KeyNavigation.priority: KeyNavigation.BeforeItem
                                KeyNavigation.backtab: navHome

                                Keys.onReturnPressed: event => {
                                    if (currentIndex >= 0) {
                                        view.launcher.triggerEntry(
                                            view.recentUsageModel, currentIndex);
                                    }
                                    event.accepted = true;
                                }
                                Keys.onEnterPressed: event => {
                                    if (currentIndex >= 0) {
                                        view.launcher.triggerEntry(
                                            view.recentUsageModel, currentIndex);
                                    }
                                    event.accepted = true;
                                }

                                delegate: RecentTile {
                                    width: 156
                                    height: ListView.view.height - view.space2
                                    sourceModel: view.recentUsageModel
                                }
                            }
                        }

                        GridLayout {
                            // Size from the command area's actual width after the rail.
                            // Reserve room for the icon and the Arabic command on one line.
                            columns: width >= 4 * 224 + 3 * columnSpacing ? 4 : 2
                            Layout.fillWidth: true
                            // Lay out the shaped caption, title and their padding at native font metrics.
                            Layout.minimumHeight: implicitHeight
                            Layout.maximumHeight: implicitHeight
                            columnSpacing: view.space3
                            rowSpacing: view.space3

                            CommandCard {
                                objectName: "moosHomeOverview"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredWidth: 240
                                featured: true
                                iconName: "moos-grid-symbolic"
                                eyebrow: view.local("مساحة العمل", "WORKSPACE")
                                title: view.narrow ? view.local("النوافذ", "Windows")
                                    : view.local("كل نوافذك", "All your windows")
                                onActivated: view.launcher.openRoute("moos://control/window/overview")
                            }
                            CommandCard {
                                objectName: "moosHomeArrangement"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredWidth: 180
                                iconName: "moos-grid-symbolic"
                                eyebrow: view.local("تنظيم", "ARRANGE")
                                title: view.narrow ? view.local("تقسيم", "Tile")
                                    : view.local("جنبًا إلى جنب", "Side by side")
                                onActivated: view.launcher.openRoute("moos://control/arrange/halves")
                            }
                            CommandCard {
                                objectName: "moosHomeSettings"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredWidth: 180
                                iconName: "moos-settings-symbolic"
                                eyebrow: view.local("تحكم", "CONTROL")
                                title: view.narrow ? view.local("الإعدادات", "Settings")
                                    : view.local("إعدادات MoOS", "MoOS Settings")
                                onActivated: view.launcher.openRoute("moos://settings/overview")
                            }
                            CommandCard {
                                objectName: "moosHomeMira"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredWidth: 180
                                iconName: "moos-ai-symbolic"
                                eyebrow: view.local("مساعدك", "ASSISTANT")
                                title: view.narrow ? view.local("ميرا", "Mira")
                                    : view.local("ابدأ مع ميرا", "Create with Mira")
                                onActivated: view.launcher.openDesktop("org.moos.moai.desktop")
                            }
                        }

                        // Spare viewport height belongs below the sections. Without
                        // it the stretched column shared it out as gaps, leaving a
                        // band of empty glass between "Pinned" and its first row
                        // in portrait/tablet viewports.
                        Item {
                            objectName: "movaHomeTail"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
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
                                title: view.local("مكتبة التطبيقات", "App library")
                                subtitle: view.shortLayout ? "" : view.local("التطبيقات: ", "Applications: ")
                                    + Number(view.applicationsModel ? view.applicationsModel.count : 0)
                                        .toLocaleString(Qt.locale(), "f", 0)
                                    + " · " + view.local("اختر فئة أو ابحث بالأعلى", "Choose a category or search above")
                            }

                            PC3.Button {
                                objectName: "launcherStore"
                                Layout.minimumWidth: view.targetSize
                                Layout.minimumHeight: view.targetSize
                                text: view.local("متجر MoOS", "Mo Store")
                                icon.name: "moos-install-symbolic"
                                display: view.narrow ? PC3.AbstractButton.IconOnly : PC3.AbstractButton.TextBesideIcon
                                onClicked: view.launcher.openDesktop("org.moos.store.desktop")
                                PC3.ToolTip.text: text
                                PC3.ToolTip.visible: hovered && view.narrow
                                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
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

                        ListView {
                            id: categoryStrip
                            objectName: "launcherCategories"
                            Layout.fillWidth: true
                            Layout.preferredHeight: view.touchTarget + view.space1
                            orientation: ListView.Horizontal
                            spacing: view.space2
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            model: view.launcher.appRootModel
                            currentIndex: view.launcher.appsModelRow
                            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                            QQC2.ScrollBar.horizontal: QQC2.ScrollBar { interactive: false }

                            delegate: PC3.ItemDelegate {
                                id: category
                                required property int index
                                required property var model
                                objectName: "launcherCategory" + index
                                visible: index > 0 && model.hasChildren === true
                                width: visible ? Math.max(view.touchTarget, implicitWidth) : 0
                                height: view.touchTarget
                                text: index === 1 ? view.local("الكل", "All") : String(model.display || "")
                                checked: view.launcher.appsModelRow === index
                                hoverEnabled: true
                                activeFocusOnTab: visible
                                Accessible.role: Accessible.PageTab
                                Accessible.name: text
                                Accessible.selected: checked
                                Accessible.onPressAction: category.activate()
                                function activate() {
                                    category.forceActiveFocus();
                                    view.selectCategory(index);
                                }
                                onClicked: activate()
                                Keys.onReturnPressed: event => { activate(); event.accepted = true; }
                                Keys.onEnterPressed: event => { activate(); event.accepted = true; }
                                Keys.onSpacePressed: event => { activate(); event.accepted = true; }
                                Keys.onLeftPressed: event => {
                                    view.focusCategory(index + (view.rtl ? 1 : -1)); event.accepted = true;
                                }
                                Keys.onRightPressed: event => {
                                    view.focusCategory(index + (view.rtl ? -1 : 1)); event.accepted = true;
                                }
                                Keys.onUpPressed: event => { view.focusSearch(); event.accepted = true; }
                                Keys.onDownPressed: event => { view.focusActivePageContent(); event.accepted = true; }
                                background: Rectangle {
                                    radius: view.radiusM
                                    color: category.checked
                                        ? Qt.alpha(Kirigami.Theme.highlightColor, 0.26)
                                        : Qt.alpha(Kirigami.Theme.textColor, category.hovered ? 0.14 : 0.06)
                                    border.width: category.activeFocus ? 2 : 1
                                    border.color: category.activeFocus
                                        ? Kirigami.Theme.highlightColor
                                        : Qt.alpha(Kirigami.Theme.textColor, category.checked ? 0.24 : 0.10)
                                    Behavior on color { ColorAnimation { duration: view.motionFast } }
                                }
                            }
                        }

                        RowLayout {
                            visible: view.launcher.appFolderPath.length > 0
                            Layout.fillWidth: true
                            PC3.ToolButton {
                                objectName: "movaFolderBack"
                                Layout.minimumWidth: view.targetSize; Layout.minimumHeight: view.targetSize
                                icon.name: view.rtl ? "go-next-symbolic" : "go-previous-symbolic"
                                text: view.local("رجوع إلى المجلد السابق", "Back to parent folder")
                                display: PC3.AbstractButton.IconOnly
                                onClicked: view.launcher.leaveAppFolder()
                                PC3.ToolTip { text: parent.text }
                            }
                            PC3.Label {
                                Layout.fillWidth: true
                                text: view.launcher.appFolderPath.map(entry => entry.label).join(" / ")
                                elide: Text.ElideMiddle; textFormat: Text.PlainText
                                font.pixelSize: view.typeSecondary
                            }
                        }

                        GridView {
                            id: applicationsGrid
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            model: view.applicationsModel
                            cellWidth: Math.max(1, Math.floor(width / view.appColumns(width)))
                            cellHeight: view.appRowHeight(height, Plasmoid.configuration.compactTiles ? 100 : 128)
                            snapMode: GridView.SnapToRow
                            keyNavigationWraps: true
                            activeFocusOnTab: true
                            readonly property int columns: Math.max(
                                1, Math.floor(width / Math.max(1, cellWidth)))
                            // Same keyboard contract as the pinned grid: top row
                            // Up -> search field, Shift+Tab -> Applications nav.
                            KeyNavigation.priority: KeyNavigation.BeforeItem
                            KeyNavigation.backtab: navApps
                            Keys.onUpPressed: event => {
                                if (currentIndex < columns) {
                                    view.focusSearch();
                                } else {
                                    moveCurrentIndexUp();
                                }
                                event.accepted = true;
                            }
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

                            GridLayout {
                                columns: view.narrow ? 1 : 3
                                id: scopeCallout
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: view.space4
                                anchors.rightMargin: view.space4
                                rowSpacing: view.space3
                                columnSpacing: view.space3

                                Kirigami.Icon {
                                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                                    Layout.preferredHeight: width
                                    source: "moos-search-symbolic"
                                    visible: !view.narrow
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
                                        color: view.secondaryInk
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
                            id: placesList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: view.space2
                            boundsBehavior: Flickable.StopAtBounds
                            keyNavigationWraps: true
                            activeFocusOnTab: true
                            currentIndex: -1
                            model: view.placesModel
                            KeyNavigation.priority: KeyNavigation.BeforeItem
                            KeyNavigation.backtab: navPlaces

                            // Enter is handled at the view (like the results
                            // list): the delegate carries its own handlers too,
                            // but the view level fires whether or not the row
                            // itself took focus.
                            Keys.onUpPressed: event => {
                                if (currentIndex <= 0) {
                                    view.focusSearch();
                                } else {
                                    decrementCurrentIndex();
                                }
                                event.accepted = true;
                            }
                            Keys.onDownPressed: event => {
                                incrementCurrentIndex();
                                event.accepted = true;
                            }
                            Keys.onReturnPressed: event => {
                                if (currentIndex >= 0) {
                                    view.launcher.triggerEntry(view.placesModel, currentIndex);
                                }
                                event.accepted = true;
                            }
                            Keys.onEnterPressed: event => {
                                if (currentIndex >= 0) {
                                    view.launcher.triggerEntry(view.placesModel, currentIndex);
                                }
                                event.accepted = true;
                            }

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
                        id: customizeScroll
                        anchors.fill: parent
                        contentWidth: width
                        contentHeight: customizeColumn.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollEdge { flick: customizeScroll }

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

                                GridLayout {
                                    columns: view.compact ? 1 : 4
                                    id: favoritesControl
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.leftMargin: view.space4
                                    anchors.rightMargin: view.space4
                                    rowSpacing: view.space4
                                    columnSpacing: view.space4

                                    Kirigami.Icon {
                                        Layout.preferredWidth: Kirigami.Units.iconSizes.large
                                        Layout.preferredHeight: width
                                        source: "moos-star-symbolic"
                                        visible: !view.compact
                                        color: Kirigami.Theme.highlightColor
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1
                                        Text {
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                            text: view.local("التطبيقات المفضّلة", "Pinned applications")
                                            color: Kirigami.Theme.textColor
                                            font.family: view.uiFontFamily
                                            font.pixelSize: view.typeBody
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: view.local(
                                                "أضف بالنجمة، ثم رتّب أو أزل من المفضّلة",
                                                "Star apps, then reorder or unpin them on Home")
                                            color: view.secondaryInk
                                            font.family: view.uiFontFamily
                                            font.pixelSize: view.typeCaption
                                            elide: Text.ElideRight
                                        }
                                    }
                                    PC3.Button {
                                        id: customizeArrangeButton
                                        onActiveFocusChanged: if (activeFocus) customizeScroll.contentY = 0
                                        Layout.minimumHeight: view.targetSize
                                        text: view.local("ترتيب الآن", "Arrange now")
                                        icon.name: "moos-pen-symbolic"
                                        activeFocusOnTab: true
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

                            PC3.Button {
                                objectName: "moosNativeWidgetLibrary"
                                Layout.fillWidth: true
                                Layout.minimumHeight: view.targetSize
                                text: view.local("سطح المكتب والأدوات", "Desktop & widgets")
                                icon.name: MoUI.SymbolCatalog.resolve("grid")
                                onClicked: view.launcher.openRoute("moos://settings/desktop")
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: view.narrow ? 1 : 2
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

                            GridLayout {
                                Layout.fillWidth: true
                                columns: view.compact ? 1 : 3
                                rowSpacing: view.space3
                                columnSpacing: view.space3

                                PC3.Button {
                                    Layout.fillWidth: true
                                    Layout.minimumHeight: view.targetSize
                                    onActiveFocusChanged: if (activeFocus) customizeScroll.contentY = Math.max(
                                        0, customizeScroll.contentHeight - customizeScroll.height)
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
                            KeyNavigation.priority: KeyNavigation.BeforeItem
                            KeyNavigation.backtab: searchInput
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
                                horizontalAlignment: Text.AlignLeft
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
                source: "moos-user-symbolic"
                color: Kirigami.Theme.textColor
            }
            Text {
                Layout.fillWidth: true
                visible: !view.compact
                elide: Text.ElideRight
                text: view.local("خيارات الجلسة", "Session actions")
                color: view.secondaryInk
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
                // The MoOS Themes page lives in MoOS Settings (Appearance).
                onClicked: view.launcher.openRoute("moos://settings/themes")
                PC3.ToolTip.text: text
                PC3.ToolTip.visible: hovered && text.length > 0
                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
            }

            Rectangle {
                Layout.preferredWidth: 1
                Layout.preferredHeight: 22
                color: Qt.alpha(Kirigami.Theme.textColor, 0.14)
            }

            PC3.Button {
                id: sessionMenuButton
                visible: view.compact
                Layout.minimumHeight: view.touchTarget
                text: view.local("الجلسة والطاقة", "Session & power")
                icon.name: "moos-power-symbolic"
                onClicked: sessionMenu.popup()
                QQC2.Menu {
                    id: sessionMenu
                    Instantiator {
                        model: view.sessionModel
                        delegate: QQC2.MenuItem {
                            required property int index
                            required property var model
                            visible: view.sessionActionShown(model.favoriteId)
                            height: visible ? Math.max(implicitHeight, view.touchTarget) : 0
                            text: model.display
                            icon.name: view.sessionIcon(model.favoriteId)
                            onTriggered: view.launcher.triggerEntry(view.sessionModel, index)
                        }
                        onObjectAdded: (index, object) => sessionMenu.insertItem(index, object)
                        onObjectRemoved: (index, object) => sessionMenu.removeItem(object)
                    }
                }
            }

            Repeater {
                model: view.sessionModel

                PC3.ToolButton {
                    required property int index
                    required property var model

                    readonly property bool shown: !view.compact
                        && view.sessionActionShown(model.favoriteId)

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
            horizontalAlignment: Text.AlignLeft
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
            horizontalAlignment: Text.AlignLeft
            visible: text.length > 0
            color: view.secondaryInk
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
        // The two vertical neighbours in the four-button ring.
        property Item navUp: null
        property Item navDown: null

        Layout.fillWidth: true
        Layout.minimumWidth: view.touchTarget
        Layout.minimumHeight: view.touchTarget
        Layout.preferredHeight: view.touchTarget
        leftPadding: view.narrow ? view.space1 : view.space3
        rightPadding: leftPadding
        hoverEnabled: true
        // A keyboard user must be able to Tab to the sidebar and see where the
        // focus sits — the background already draws an activeFocus edge.
        activeFocusOnTab: true
        Accessible.name: label
        Accessible.role: Accessible.PageTab
        Accessible.selectable: true
        Accessible.selected: view.launcher.activePage === nav.page && !view.searching
        Accessible.onPressAction: nav.activate()

        function activate() {
            nav.forceActiveFocus();
            view.launcher.searchQuery = "";
            view.launcher.activePage = page;
        }
        onClicked: nav.activate()

        // Enter/Space switch the page and keep focus here so the user can keep
        // arrowing. The logical-forward arrow (Right in LTR, Left in RTL — and
        // there is nothing on the other side of the sidebar, so both do it)
        // steps into the page content.
        Keys.onReturnPressed: event => { nav.activate(); event.accepted = true; }
        Keys.onEnterPressed: event => { nav.activate(); event.accepted = true; }
        Keys.onSpacePressed: event => { nav.activate(); event.accepted = true; }
        Keys.onUpPressed: event => {
            if (view.compact) { view.focusSearch(); }
            else if (nav.navUp) { nav.navUp.forceActiveFocus(); }
            event.accepted = true;
        }
        Keys.onDownPressed: event => {
            if (view.compact) { view.focusActivePageContent(); }
            else if (nav.navDown) { nav.navDown.forceActiveFocus(); }
            event.accepted = true;
        }
        Keys.onLeftPressed: event => {
            if (view.compact) { (view.rtl ? nav.navDown : nav.navUp).forceActiveFocus(); }
            else { view.focusActivePageContent(); }
            event.accepted = true;
        }
        Keys.onRightPressed: event => {
            if (view.compact) { (view.rtl ? nav.navUp : nav.navDown).forceActiveFocus(); }
            else { view.focusActivePageContent(); }
            event.accepted = true;
        }
        PC3.ToolTip.text: nav.label
        PC3.ToolTip.visible: view.narrow && hovered
        PC3.ToolTip.delay: Kirigami.Units.toolTipDelay

        background: Rectangle {
            radius: view.radiusM
            // AMPLITUDE (see artwork/MOOS_UI2_DESIGN.md). The SELECTED page sat
            // at 0.11 and hover at 0.065 — both inside the 0.05-0.12 band that
            // renders as 5-11 luminance steps, under the ~15 a person needs. The
            // sidebar could not tell you which page you were on. Rows correctly
            // stay transparent at REST; it is the selected state that has to
            // carry, so it does.
            color: view.launcher.activePage === nav.page && !view.searching
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.26)
                : Qt.alpha(Kirigami.Theme.textColor,
                    nav.hovered || nav.activeFocus ? 0.14 : 0.0)
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
            spacing: view.narrow ? 0 : view.space3

            Kirigami.Icon {
                Layout.alignment: view.narrow ? Qt.AlignHCenter : Qt.AlignVCenter
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
                visible: !view.narrow
                textFormat: Text.PlainText
                horizontalAlignment: Text.AlignLeft
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
        objectName: (favoriteSurface ? "movaFavorite_" : "movaApplication_") + index
        readonly property var baseModel: sourceModel
        readonly property string favoriteId: String(model.favoriteId || "")
        readonly property var dragOwner: view.launcher
        property bool dragConsumed: false
        z: favoriteDragProxy.Drag.active ? 2 : 0
        signal interactionConcluded()
        onInteractionConcluded: view.launcher.closeLauncher()

        // The staggered reveal. Each tile arrives a beat after the one before
        // it, so the grid assembles instead of appearing — the difference
        // between a menu and a surface that was built for you.
        //
        // Cost is deliberately near zero: opacity and y only, no shaders and no
        // per-frame work once settled. The delay is CAPPED at five short steps so a
        // large catalogue cannot turn the entrance into a queue, and the whole
        // thing collapses to an instant 1.0 when motion is off — the gate is
        // named in full rather than through view.motionMedium so it is legible
        // to the reader and to verify_user_experience.
        // DelegateModel sets index to -1 briefly while a tile is being
        // detached. Clamp BOTH bounds: capping only the upper end turns that
        // teardown state into a negative PauseAnimation duration and floods
        // the live shell journal every time the launcher model changes.
        readonly property int revealDelay:
            Kirigami.Units.longDuration > 1
                ? Math.max(0, Math.min(tile.index, 5)) * 10
                : 0
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
        Accessible.description: String(model.description || "")
        Accessible.role: Accessible.Button
        function activate() {
            if (tile.Drag.active || favoriteDragProxy.Drag.active || tileDrag.active) return;
            if (model.hasChildren === true && !tile.favoriteSurface) {
                if (view.launcher.enterAppFolder(index, String(model.display || "")))
                    applicationsGrid.currentIndex = 0;
                return;
            }
            view.launcher.triggerEntry(sourceModel, index);
        }
        function movePinned(delta) {
            if (tile.favoriteSurface) view.launcher.moveFavorite(tile.index, tile.index + delta);
        }
        onPressedChanged: if (pressed) dragConsumed = false
        onClicked: {
            if (!dragConsumed) activate();
            dragConsumed = false;
        }
        onPressAndHold: view.openAppActions(tile)
        Keys.onReturnPressed: event => { tile.activate(); event.accepted = true; }
        Keys.onEnterPressed: event => { tile.activate(); event.accepted = true; }
        Keys.onSpacePressed: event => { tile.activate(); event.accepted = true; }
        Keys.onMenuPressed: event => { view.openAppActions(tile); event.accepted = true; }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton
            onPressed: view.openAppActions(tile)
        }
        DragHandler {
            id: tileDrag
            property bool cancelled: false
            target: null
            acceptedDevices: view.launcher.editMode ? PointerDevice.AllDevices
                : PointerDevice.Mouse | PointerDevice.Stylus
            enabled: tile.favoriteId.length > 0 && tile.visible && view.visible
            onCanceled: cancelled = true
            onActiveTranslationChanged: if (active && tile.favoriteSurface) {
                favoriteDragProxy.x = activeTranslation.x;
                favoriteDragProxy.y = activeTranslation.y;
            }
            onActiveChanged: {
                if (active) {
                    cancelled = false;
                    tile.dragConsumed = true;
                    if (tile.favoriteSurface) {
                        favoriteDragProxy.x = 0; favoriteDragProxy.y = 0;
                        favoriteDragProxy.Drag.active = true;
                    } else {
                        tile.contentItem.grabToImage(result => {
                            if (!tileDrag.active || !tile.visible || !view.visible) return;
                            tile.Drag.imageSource = result.url;
                            tile.Drag.active = true;
                        });
                    }
                } else {
                    if (favoriteDragProxy.Drag.active && !cancelled
                            && tile.visible && view.visible && view.launcher.expanded)
                        favoriteDragProxy.Drag.drop();
                    favoriteDragProxy.Drag.active = false;
                    tile.Drag.active = false;
                    favoriteDragProxy.x = 0; favoriteDragProxy.y = 0;
                }
            }
        }
        Item {
            id: favoriteDragProxy
            objectName: "movaFavoriteDragProxy"
            width: tile.width; height: tile.height
            Drag.source: tile
            Drag.hotSpot.x: width / 2; Drag.hotSpot.y: height / 2
            Drag.dragType: Drag.Internal
            Drag.keys: ["org.moos.mova.application"]
            Drag.supportedActions: Qt.MoveAction
            Rectangle {
                anchors.fill: parent; anchors.margins: view.space1
                visible: favoriteDragProxy.Drag.active
                radius: view.radiusL
                // The MoOS corner: the top-trailing corner is square.
                topLeftRadius: LayoutMirroring.enabled ? Math.min(radius, design.radiusSquare) : radius
                topRightRadius: LayoutMirroring.enabled ? radius : Math.min(radius, design.radiusSquare)
                color: Qt.alpha(Kirigami.Theme.backgroundColor, .94)
                border.color: Qt.alpha(Kirigami.Theme.highlightColor, .8)
                border.width: 1
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: view.space2
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: Plasmoid.configuration.compactTiles ? 32 : 52
                        Layout.preferredHeight: width
                        source: tile.model.decoration || "moos-cube-symbolic"
                        animated: false
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: String(tile.model.compactName || tile.model.display || "")
                        font.pixelSize: view.typeSecondary
                        horizontalAlignment: Text.AlignHCenter
                        textFormat: Text.PlainText; elide: Text.ElideRight
                    }
                }
            }
        }
        Drag.dragType: Drag.Automatic
        Drag.source: tile
        Drag.keys: ["org.moos.mova.application"]
        Drag.supportedActions: Qt.CopyAction | Qt.MoveAction
        Drag.mimeData: ({"text/uri-list": [String(tile.model.url || "")]})
        onVisibleChanged: if (!visible) {
            tile.Drag.active = false;
            favoriteDragProxy.Drag.active = false;
        }
        DropArea {
            id: reorderDrop
            objectName: "movaFavoriteDrop"
            anchors.fill: parent
            enabled: tile.favoriteSurface
            keys: ["org.moos.mova.application"]
            onEntered: event => {
                event.accepted = !!event.source && event.source.dragOwner === view.launcher
                    && event.source.favoriteSurface && event.source !== tile;
            }
            onDropped: event => {
                const source = event.source;
                if (!source || source.dragOwner !== view.launcher || !source.favoriteSurface
                        || source === tile || source.index < 0 || tile.index < 0) return;
                view.launcher.moveFavorite(source.index, tile.index);
                event.accept(Qt.MoveAction);
            }
        }

        // EVERY TILE IS A CARD, INCLUDING AT REST.
        //
        // The publisher icon and label identify each application. A surface
        // appears on interaction, leaving the library calm at rest.
        readonly property bool lit: tile.down || tile.hovered || tile.activeFocus
            || reorderDrop.containsDrag
        background: Rectangle {
            objectName: "movaTileCard"
            radius: view.radiusM
            color: tile.down
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.26)
                : tile.lit
                    ? Qt.alpha(Kirigami.Theme.highlightColor, 0.14)
                    : "transparent"
            // Rim scale (THEME_REV 32): keyboard focus is the one state allowed
            // a strong edge. Hover borrows the Control Center's glass card: the
            // same .14 accent tint, a .32 accent hairline and a top sheen.
            border.width: tile.activeFocus ? 2 : tile.lit ? 1 : 0
            border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                tile.activeFocus ? 0.82 : 0.32)
            Behavior on color { ColorAnimation { duration: view.motionFast } }

            Rectangle {
                objectName: "movaTileSheen"
                anchors {
                    left: parent.left
                    right: parent.right
                    top: parent.top
                    margins: parent.border.width
                }
                height: parent.height * 0.5
                radius: Math.max(0, parent.radius - parent.border.width)
                visible: tile.lit
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, view.lightSurface ? 0.10 : 0.06) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            // The lift. A card that only changes colour on hover feels painted;
            // one that rises feels like an object. Transform only — no shadow
            // layer, no shader, nothing per-frame once settled.
            transform: Translate { y: tile.hovered && view.motionFast > 0 ? -2 : 0
                Behavior on y {
                    NumberAnimation { duration: view.motionFast; easing.type: Easing.OutCubic }
                }
            }
        }

        contentItem: ColumnLayout {
            anchors.margins: view.space1
            spacing: view.space1
            opacity: favoriteDragProxy.Drag.active ? .3 : 1
            scale: tileFeedback.value
            MoUI.SpringFeedback {
                id: tileFeedback
                active: tile.visible && view.visible
                targetScale: tile.down ? view.design.pressScale
                    : tile.hovered ? view.design.hoverScale : 1
            }

            // Icon and name travel as one group centred in the cell. Without
            // the two fillers the layout spread its spare height between them,
            // so the name floated far below its icon; the reserved second line
            // keeps every icon of a row on one level whether a name wraps or not.
            Item { Layout.fillHeight: true }
            Kirigami.Icon {
                objectName: "movaAppIcon"
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Plasmoid.configuration.compactTiles
                    ? Kirigami.Units.iconSizes.medium
                    : 60
                Layout.preferredHeight: width
                source: tile.model.decoration || "moos-cube-symbolic"
                animated: false
            }
            Text {
                objectName: "movaAppName"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.ceil(tileLabelMetrics.lineSpacing * 2)
                verticalAlignment: Text.AlignTop
                text: String(tile.model.compactName || tile.model.display || "")
                textFormat: Text.PlainText
                color: Kirigami.Theme.textColor
                font.family: view.uiFontFamily
                font.pixelSize: view.typeSecondary
                font.weight: Font.Medium
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            Item { Layout.fillHeight: true }
        }

        PC3.ToolButton {
            id: tileActionsButton
            objectName: "movaAppActionsButton"
            anchors.top: parent.top
            // Logical trailing corner; inherited mirroring moves it left in RTL.
            anchors.right: parent.right
            anchors.margins: view.space1
            width: view.targetSize
            height: view.targetSize
            z: 4
            visible: (tile.hovered || tile.activeFocus || tileActionsButton.activeFocus || view.launcher.editMode)
                && tile.favoriteId.length > 0
            icon.name: "overflow-menu"
            text: String(tile.model.compactName || tile.model.display || "")
                + " · " + view.local("إجراءات التطبيق", "Application actions")
            activeFocusOnTab: true
            display: PC3.AbstractButton.IconOnly
            onClicked: view.openAppActions(tile)
            PC3.ToolTip.text: text
            PC3.ToolTip.visible: hovered && text.length > 0
            PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
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
            color: recent.hovered || recent.activeFocus || recent.ListView.isCurrentItem
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.085)
                : "transparent"
            border.width: recent.activeFocus ? 2
                : recent.hovered || recent.ListView.isCurrentItem ? 1 : 0
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
                    color: view.secondaryInk
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
            // isCurrentItem is the keyboard selection: the Places list drives
            // currentIndex from the arrow keys, so the row under it must read as
            // chosen even with no pointer and no delegate focus.
            color: place.hovered || place.activeFocus || place.ListView.isCurrentItem
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.085)
                : "transparent"
            border.width: place.activeFocus ? 2
                : place.hovered || place.ListView.isCurrentItem ? 1 : 0
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
                    color: view.secondaryInk
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
                color: view.secondaryInk
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
                    color: view.secondaryInk
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
        onActiveFocusChanged: if (activeFocus) homeScroll.reveal(command)
        property string iconName: "moos-spark-symbolic"
        property string eyebrow: ""
        property string title: ""
        property bool featured: false
        signal activated()

        hoverEnabled: true
        // Inset the content off the card edge. Without this the eyebrow ran
        // flush into the rounded corner and clipped in RTL — "اكتشف" rendered
        // as "كتشف" at 150% (docs/DEVELOPMENT_PLAN.md P2.5: no clipped RTL
        // labels). AppTile already insets its own contentItem the same way.
        leftPadding: view.space4
        rightPadding: view.space4
        topPadding: view.space2
        bottomPadding: view.space2
        Layout.preferredHeight: Math.max(76, implicitContentHeight + topPadding + bottomPadding)
        Accessible.name: command.title
        Accessible.description: command.eyebrow
        Accessible.role: Accessible.Button
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

        // AMPLITUDE (artwork/MOOS_UI2_DESIGN.md). Resting fill was 0.025 /
        // featured 0.105 — both inside the 0.05–0.12 band that renders as 5–11
        // luminance steps. Same contract as AppTile: textColour 0.11 at rest so
        // one value works across all 16 themes; accent only on interaction.
        background: Rectangle {
            radius: view.radiusL
            // The MoOS corner: the top-trailing corner is square.
            topLeftRadius: LayoutMirroring.enabled ? Math.min(radius, design.radiusSquare) : radius
            topRightRadius: LayoutMirroring.enabled ? radius : Math.min(radius, design.radiusSquare)
            color: command.down
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.34)
                : command.hovered || command.activeFocus
                    ? Qt.alpha(Kirigami.Theme.highlightColor, 0.24)
                    : Qt.alpha(Kirigami.Theme.textColor, 0.11)
            // Rim scale (THEME_REV 32): resting ≤0.22; keyboard focus is the
            // only state allowed a stronger edge.
            border.width: command.activeFocus ? 2 : 1
            border.color: Qt.alpha(
                command.activeFocus ? Kirigami.Theme.highlightColor
                                    : Kirigami.Theme.textColor,
                command.activeFocus ? 0.52 : 0.18)
            Behavior on color { ColorAnimation { duration: view.motionFast } }
            Behavior on border.color { ColorAnimation { duration: view.motionFast } }

            transform: Translate {
                y: command.hovered && view.motionFast > 0 ? -2 : 0
                Behavior on y {
                    NumberAnimation {
                        duration: view.motionFast
                        easing.type: Easing.OutCubic
                    }
                }
            }

            Rectangle {
                anchors {
                    left: parent.left
                    bottom: parent.bottom
                    leftMargin: view.radiusL
                }
                width: command.featured || command.hovered ? 42 : 18
                height: 2
                radius: 1
                color: Kirigami.Theme.highlightColor
                opacity: command.featured || command.hovered ? 0.94 : 0.55
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
            scale: command.down ? view.design.pressScale : 1
            Behavior on scale { NumberAnimation { duration: view.motionFast; easing.type: Easing.OutCubic } }

            Item {
                visible: !view.narrow
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32

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
                spacing: view.space1

                Text {
                    Layout.fillWidth: true
                    text: command.eyebrow
                    color: view.secondaryInk
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
                    font.pixelSize: view.typeBody
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
            }
        }
    }

    // A page that continues below the fold says so with a soft edge instead of
    // cutting its last row in half. It belongs to the Flickable itself (not its
    // content), takes no input and fades into the same glass sheet it sits on.
    component ScrollEdge: Rectangle {
        id: edge
        required property Flickable flick
        readonly property bool more: flick.contentHeight - flick.contentY - flick.height > 1
        objectName: "movaScrollEdge"
        parent: flick
        z: 3
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        height: Math.min(48, flick.height * 0.18)
        opacity: more ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: view.motionFast } }
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop {
                position: 1.0
                color: Qt.alpha(canvasGlass.surfaceColor,
                    Math.min(1, canvasGlass.fillOpacity + 0.06))
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
        // Same resting amplitude as AppTile / CommandCard — 0.045 was invisible.
        color: Qt.alpha(Kirigami.Theme.textColor, 0.11)
        border.width: 1
        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.18)

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
                    id: settingSwitch
                    objectName: "movaSettingSwitch"
                    checked: setting.checked
                    Accessible.name: setting.title
                    onToggled: setting.toggled(checked)

                    // The native off groove is a faint ink tint; on this card's
                    // own ink tint it vanished and left only a ring that read as
                    // a radio button. A matching ink track beneath the native
                    // indicator restores the switch silhouette; when checked the
                    // native accent groove covers it completely.
                    Rectangle {
                        objectName: "movaSettingSwitchTrack"
                        z: -1
                        x: settingSwitch.indicator.x
                        y: settingSwitch.indicator.y
                        width: settingSwitch.indicator.width
                        height: settingSwitch.indicator.height
                        radius: height / 2
                        visible: !settingSwitch.checked
                        color: Qt.alpha(Kirigami.Theme.textColor, 0.16)
                        border.width: 1
                        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.34)
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                text: setting.description
                color: view.secondaryInk
                font.family: view.uiFontFamily
                font.pixelSize: view.typeCaption
                wrapMode: Text.WordWrap
                maximumLineCount: 2
            }
        }
    }
}

// MoOS Launcher — one button, one search surface, every local thing.
//
// This applet deliberately keeps the historic org.moos.brand package id so an
// update can replace the existing panel item in place.  It is no longer a
// separate "brand glance" beside Kickoff: it IS MoOS's application launcher.
// Plasma's native models remain the engine underneath the MoOS face:
//
//   * Milou.ResultsModel       applications, settings, indexed files/folders,
//                              places, windows, calculations and every enabled
//                              KRunner provider;
//   * Kicker.RootModel         the installed application catalogue;
//   * KAStatsFavoritesModel    persistent pin/unpin/reorder support;
//   * RecentUsageModel         applications and documents the user actually used;
//   * ComputerModel            places, storage and system locations;
//   * SystemModel              lock, session and power actions.
//
// No query is interpolated into a shell command. Search results and applications
// are launched through their owning Plasma model. Static MoOS destinations use
// applications: URLs. System actions use SystemModel. This keeps the old launch
// path's integration while removing its duplicated UI and broken D-Bus query.
//
// Always-on motion budget: transforms/opacity only; no shaders, MultiEffect,
// Lottie or Canvas. The full launcher follows Kirigami.Theme exclusively so all
// sixteen MoOS UI2 family members remain coherent in dark and light modes.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQml.Models
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.kicker as Kicker
import org.kde.milou as Milou
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "moos-logo"
    // plasmawindowed normally honours the same compact preference as a panel,
    // which used to make the image gate test only this button while the entire
    // launcher stayed lazy and unproven.  This positional argument is accepted
    // only by the explicit build smoke; plasmashell never starts with it.
    readonly property bool smokeFullRepresentation:
        Qt.application.arguments.indexOf("moos-ci-full-representation") >= 0
    preferredRepresentation: root.smokeFullRepresentation
        ? fullRepresentation : compactRepresentation

    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft
    readonly property string uiFontFamily: Qt.application.font.family
    readonly property int motionFast: Kirigami.Units.longDuration > 1
        ? Kirigami.Units.shortDuration : 0
    readonly property int motionMedium: Kirigami.Units.longDuration > 1
        ? Math.round(Kirigami.Units.longDuration * 1.35) : 0
    readonly property var shippedFavorites: [
        "org.moos.moai.desktop",
        "org.moos.store.desktop",
        "preferred://browser",
        "org.moos.moplayer.desktop",
        "org.kde.dolphin.desktop",
        "systemsettings.desktop",
        "org.moos.updater.desktop",
        "org.moos.recovery.desktop"
    ]

    property string searchQuery: ""
    property int activePage: 1
    property bool editMode: false
    property int appsModelRow: 1
    property var favoriteSearchIds: []

    toolTipMainText: "MoOS"
    toolTipSubText: root.rtl
        ? "التطبيقات والملفات والإعدادات"
        : "Apps, files and settings"

    function closeLauncher() {
        root.searchQuery = "";
        root.editMode = false;
        root.expanded = false;
    }

    function openDesktop(desktopId) {
        if (!desktopId || desktopId.length === 0) {
            return;
        }
        const destinations = launcherDestinations.favorites;
        const row = destinations.indexOf(desktopId);
        if (row >= 0 && launcherDestinations.trigger(row, "", null)) {
            closeLauncher();
        }
    }

    function triggerEntry(sourceModel, row) {
        if (sourceModel && row >= 0 && sourceModel.trigger(row, "", null)) {
            closeLauncher();
        }
    }

    function runSearchResult(row) {
        if (row < 0 || row >= searchResults.rowCount()) {
            return;
        }
        if (searchResults.run(searchResults.index(row, 0))) {
            closeLauncher();
        }
    }

    function toggleFavorite(favoriteId) {
        if (!favoriteId || favoriteId.length === 0) {
            return;
        }
        const favorites = root.favoriteModel;
        if (favorites.isFavorite(favoriteId)) {
            favorites.removeFavorite(favoriteId);
        } else {
            favorites.addFavorite(favoriteId);
        }
    }

    function moveFavorite(from, to) {
        const count = root.favoriteModel.count;
        if (from < 0 || to < 0 || from >= count || to >= count || from === to) {
            return;
        }
        root.favoriteModel.moveRow(from, to);
    }

    function restoreFavorites() {
        const favorites = root.favoriteModel;
        const existing = [];
        for (let i = 0; i < favoriteObjects.count; ++i) {
            const object = favoriteObjects.objectAt(i) as FavoriteSnapshot;
            if (object && object.favoriteId) {
                existing.push(object.favoriteId);
            }
        }
        for (let i = existing.length - 1; i >= 0; --i) {
            favorites.removeFavorite(existing[i]);
        }
        for (let i = 0; i < root.shippedFavorites.length; ++i) {
            favorites.addFavorite(root.shippedFavorites[i]);
        }
        root.editMode = true;
        root.activePage = 0;
    }

    function syncFavoriteSearchIds() {
        const ids = [];
        for (let i = 0; i < favoriteObjects.count; ++i) {
            const object = favoriteObjects.objectAt(i) as FavoriteSnapshot;
            if (object && object.favoriteId) {
                ids.push(object.favoriteId);
            }
        }
        root.favoriteSearchIds = ids;
    }

    readonly property Kicker.RootModel appRootModel: Kicker.RootModel {
        id: appRootModel

        autoPopulate: false
        appletInterface: root
        appNameFormat: 0
        flat: true
        sorted: true
        showSeparators: false
        showRootSeparator: false
        showTopLevelItems: true
        showAllApps: true
        showAllAppsCategorized: false
        showRecentApps: false
        showRecentDocs: false
        showRecentFolders: false
        showPowerSession: false
        showFavoritesPlaceholder: true
        highlightNewlyInstalledApps: true

        Component.onCompleted: {
            const favoriteModel = favoritesModel as Kicker.KAStatsFavoritesModel;
            const configuredClient = String(Plasmoid.configuration.favoritesClient || "");
            const client = configuredClient.length > 0
                ? configuredClient
                : "org.moos.launcher.favorites";
            favoriteModel.initForClient(client);

            if (!Plasmoid.configuration.favoritesSeeded) {
                if (favoriteModel.count < 1) {
                    const configured = Array.from(Plasmoid.configuration.favoriteApps || []);
                    favoriteModel.portOldFavorites(configured.length > 0
                        ? configured
                        : root.shippedFavorites);
                }
                Plasmoid.configuration.favoritesClient = client;
                Plasmoid.configuration.favoritesSeeded = true;
            }
            refresh();
        }
    }

    readonly property Kicker.KAStatsFavoritesModel favoriteModel:
        appRootModel.favoritesModel as Kicker.KAStatsFavoritesModel

    component FavoriteSnapshot: QtObject {
        required property string favoriteId
    }

    Instantiator {
        id: favoriteObjects
        model: root.favoriteModel

        delegate: FavoriteSnapshot {}

        onCountChanged: Qt.callLater(root.syncFavoriteSearchIds)
        onObjectAdded: Qt.callLater(root.syncFavoriteSearchIds)
        onObjectRemoved: Qt.callLater(root.syncFavoriteSearchIds)
    }

    Connections {
        target: appRootModel
        function onRefreshed() {
            // modelForRow() is a method call and therefore has no automatic QML
            // dependency. Nudge the binding after KService/KSycoca refreshes.
            root.appsModelRowChanged();
        }
    }

    readonly property var appsModel: appRootModel.modelForRow(appsModelRow)
    readonly property LauncherView launcherView:
        root.fullRepresentationItem as LauncherView

    Milou.ResultsModel {
        id: searchResults
        queryString: root.searchQuery
        favoriteIds: root.favoriteSearchIds
        limit: 36

        onQueryStringChangeRequested: (queryString, cursorPosition) => {
            root.searchQuery = queryString;
            Qt.callLater(() => {
                if (root.launcherView) {
                    root.launcherView.setSearchCursor(cursorPosition);
                }
            });
        }
    }

    Kicker.RecentUsageModel {
        id: recentModel
        favoritesModel: root.favoriteModel
        ordering: 0
    }

    Kicker.ComputerModel {
        id: computerModel
        appletInterface: root
        favoritesModel: root.favoriteModel
        appNameFormat: 0
        systemApplications: [
            "systemsettings.desktop",
            "org.kde.kinfocenter.desktop",
            "org.moos.recovery.desktop"
        ]
    }

    Kicker.SystemModel {
        id: systemModel
    }

    // A model-backed launch path is important here: applications: is an
    // internal Kicker URL, not a registered desktop URL scheme. AppEntry owns
    // desktop-file activation and KCM launch semantics without invoking a shell.
    Kicker.SimpleFavoritesModel {
        id: launcherDestinations
        favorites: [
            "kcm_baloofile.desktop",
            "kcm_plasmasearch.desktop",
            "org.moos.moai.desktop",
            "org.moos.store.desktop",
            "org.moos.themepicker.desktop",
            "systemsettings.desktop"
        ]
    }

    Kicker.ProcessRunner {
        id: processRunner
    }

    onActivePageChanged: {
        if (activePage >= 0 && activePage <= 3) {
            Plasmoid.configuration.defaultPage = activePage;
        }
    }

    onExpandedChanged: {
        if (root.expanded) {
            root.activePage = Math.max(0, Math.min(3,
                Number(Plasmoid.configuration.defaultPage)));
            root.searchQuery = "";
            root.editMode = false;
            recentModel.refresh();
            computerModel.refresh();
            systemModel.refresh();
            Qt.callLater(() => {
                if (root.launcherView) {
                    root.launcherView.focusSearch();
                }
            });
        } else {
            root.searchQuery = "";
            root.editMode = false;
        }
    }

    compactRepresentation: MouseArea {
        id: compact

        // Enough optical width for the 11px functional caption in both
        // languages; the old 2.55 ratio only worked by shrinking it to 7px.
        readonly property int contentWidth: Math.round(height * 3.72)

        implicitWidth: contentWidth
        implicitHeight: Kirigami.Units.gridUnit * 2
        Layout.minimumWidth: contentWidth
        Layout.preferredWidth: contentWidth
        Layout.maximumWidth: contentWidth

        hoverEnabled: true
        activeFocusOnTab: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        cursorShape: Qt.PointingHandCursor
        Accessible.name: root.rtl ? "قائمة MoOS" : "MoOS Launcher"
        Accessible.role: Accessible.Button
        Accessible.pressed: compact.pressed
        Accessible.checked: root.expanded
        Accessible.onPressAction: compact.activate()

        function activate() {
            logoFlourish.restart();
            root.expanded = !root.expanded;
        }

        onPressed: compact.wasExpanded = root.expanded
        onClicked: mouse => {
            logoFlourish.restart();
            if (mouse.button === Qt.MiddleButton) {
                root.activePage = 1;
            }
            root.expanded = !compact.wasExpanded;
        }
        Keys.onReturnPressed: event => { compact.activate(); event.accepted = true; }
        Keys.onEnterPressed: event => { compact.activate(); event.accepted = true; }
        Keys.onSpacePressed: event => { compact.activate(); event.accepted = true; }

        property bool wasExpanded: false

        Rectangle {
            anchors.centerIn: parent
            width: Math.round(compact.contentWidth * 0.96)
            height: Math.round(compact.height * 0.80)
            radius: Math.round(height * 0.32)
            color: Qt.alpha(root.expanded || compact.containsMouse
                ? Kirigami.Theme.highlightColor
                : Kirigami.Theme.textColor,
                compact.pressed ? 0.24
                    : (root.expanded ? 0.17 : (compact.containsMouse ? 0.13 : 0.055)))
            border.width: 1
            border.color: Qt.alpha(root.expanded || compact.containsMouse
                ? Kirigami.Theme.highlightColor
                : Kirigami.Theme.textColor,
                root.expanded ? 0.72 : (compact.containsMouse ? 0.50 : 0.14))
            scale: compact.pressed ? 0.97 : 1.0

            Behavior on color { ColorAnimation { duration: root.motionFast } }
            Behavior on border.color { ColorAnimation { duration: root.motionFast } }
            Behavior on scale {
                NumberAnimation {
                    duration: root.motionFast
                    easing.type: Easing.OutCubic
                }
            }

            Row {
                anchors {
                    left: parent.left
                    top: parent.top
                    leftMargin: parent.radius
                }
                height: 2
                spacing: 5
                Rectangle {
                    width: compact.containsMouse || root.expanded ? 34 : 20
                    height: 2
                    radius: 1
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.92
                    Behavior on width {
                        NumberAnimation {
                            duration: root.motionMedium
                            easing.type: Easing.OutCubic
                        }
                    }
                }
                Rectangle {
                    width: 7
                    height: 2
                    radius: 1
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.34
                }
            }

            Rectangle {
                anchors {
                    right: parent.right
                    bottom: parent.bottom
                    rightMargin: parent.radius * 0.72
                }
                width: root.expanded ? 24 : 10
                height: 2
                radius: 1
                color: Kirigami.Theme.highlightColor
                opacity: root.expanded ? 0.92 : 0.30
                Behavior on width {
                    NumberAnimation {
                        duration: root.motionMedium
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }

        RowLayout {
            anchors.centerIn: parent
            width: Math.round(compact.contentWidth * 0.86)
            height: Math.round(compact.height * 0.68)
            spacing: Math.max(4, Kirigami.Units.smallSpacing)
            // No explicit layoutDirection: plasmashell mirrors this tree on RTL
            // sessions, and mirroring inverts an explicit RightToLeft back to
            // visual LTR — same defect as the fifteen removed in LauncherView.

            Item {
                Layout.preferredWidth: parent.height
                Layout.preferredHeight: parent.height

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.height * 0.92
                    height: width
                    radius: Math.round(width * 0.30)
                    color: Qt.alpha(Kirigami.Theme.highlightColor,
                        root.expanded ? 0.18 : 0.08)
                    border.width: Math.max(1, Math.round(width * 0.035))
                    border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                        root.expanded ? 0.88 : (compact.containsMouse ? 0.72 : 0.34))
                    scale: compact.containsMouse ? 1.05 : 1.0
                    Behavior on scale {
                        NumberAnimation {
                            duration: root.motionFast
                            easing.type: Easing.OutCubic
                        }
                    }
                }

                Image {
                    id: compactLogo
                    anchors.centerIn: parent
                    width: Math.round(parent.height * 0.78)
                    height: width
                    source: "file:///usr/share/moos/moos-logo.png"
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    smooth: true
                    sourceSize: Qt.size(width * 2, height * 2)

                    ParallelAnimation {
                        id: logoFlourish
                        NumberAnimation {
                            target: compactLogo
                            property: "rotation"
                            from: root.rtl ? 10 : -10
                            to: 0
                            duration: root.motionMedium
                            easing.type: Easing.OutBack
                        }
                        NumberAnimation {
                            target: compactLogo
                            property: "scale"
                            from: 0.86
                            to: 1
                            duration: root.motionMedium
                            easing.type: Easing.OutBack
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: -1

                Text {
                    text: "MoOS"
                    color: Kirigami.Theme.textColor
                    font.family: root.uiFontFamily
                    font.pixelSize: Math.max(12, Math.round(compact.height * 0.26))
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.5
                }
                Text {
                    text: root.rtl ? "مساحة الأوامر" : "COMMAND"
                    color: compact.containsMouse || root.expanded
                        ? Kirigami.Theme.highlightColor
                        : Kirigami.Theme.disabledTextColor
                    font.family: root.uiFontFamily
                    // The previous 7px floor disappeared on a dense panel and
                    // made the dock brand look like decorative microcopy.
                    font.pixelSize: Math.max(11, Math.round(compact.height * 0.20))
                    font.weight: Font.DemiBold
                    font.letterSpacing: root.rtl ? 0 : 1.1
                    Behavior on color { ColorAnimation { duration: root.motionFast } }
                }
            }

            Rectangle {
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                radius: Math.round(width * 0.32)
                color: Qt.alpha(Kirigami.Theme.textColor,
                    compact.containsMouse || root.expanded ? 0.10 : 0.045)
                border.width: 1
                border.color: Qt.alpha(Kirigami.Theme.textColor, 0.10)

                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: 17
                    height: 17
                    source: "moos-search-symbolic"
                    color: compact.containsMouse || root.expanded
                        ? Kirigami.Theme.highlightColor
                        : Kirigami.Theme.textColor
                    opacity: compact.containsMouse || root.expanded ? 1.0 : 0.62
                }
            }
        }
    }

    fullRepresentation: LauncherView {
        launcher: root
        searchModel: searchResults
        applicationsModel: root.appsModel
        favoritesModel: root.favoriteModel
        recentUsageModel: recentModel
        placesModel: computerModel
        sessionModel: systemModel
        menuEditor: processRunner
    }

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: root.rtl ? "تحرير التطبيقات…" : "Edit applications…"
            icon.name: "moos-pen-symbolic"
            onTriggered: processRunner.runMenuEditor()
        },
        PlasmaCore.Action {
            text: root.rtl ? "إعدادات البحث…" : "Search settings…"
            icon.name: "moos-search-symbolic"
            onTriggered: root.openDesktop("kcm_plasmasearch.desktop")
        }
    ]

    Component.onCompleted: {
        Plasmoid.activationTogglesExpanded = true;
    }
}

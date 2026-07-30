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
    property int activePage: 0
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

        readonly property int contentWidth: Math.round(height * 2.55)

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
            radius: height / 2
            color: Qt.alpha(compact.containsMouse
                ? Kirigami.Theme.highlightColor
                : Kirigami.Theme.textColor,
                compact.pressed ? 0.22 : (compact.containsMouse ? 0.14 : 0.065))
            border.width: 1
            border.color: Qt.alpha(compact.containsMouse
                ? Kirigami.Theme.highlightColor
                : Kirigami.Theme.textColor,
                compact.containsMouse ? 0.52 : 0.15)
            scale: compact.pressed ? 0.97 : 1.0

            Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
            Behavior on border.color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
            Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
        }

        RowLayout {
            anchors.centerIn: parent
            width: Math.round(compact.contentWidth * 0.80)
            height: Math.round(compact.height * 0.68)
            spacing: Math.max(4, Kirigami.Units.smallSpacing)
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            Item {
                Layout.preferredWidth: parent.height
                Layout.preferredHeight: parent.height

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.height * 0.92
                    height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: Math.max(1, Math.round(width * 0.035))
                    border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                        compact.containsMouse ? 0.78 : 0.34)
                    scale: compact.containsMouse ? 1.05 : 1.0
                    Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
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

                    RotationAnimation {
                        id: logoFlourish
                        target: compactLogo
                        property: "rotation"
                        from: 0
                        to: 360
                        duration: Kirigami.Units.longDuration * 2
                        easing.type: Easing.OutBack
                        onStopped: compactLogo.rotation = 0
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
                    text: root.rtl ? "القائمة" : "LAUNCHER"
                    color: compact.containsMouse
                        ? Kirigami.Theme.highlightColor
                        : Kirigami.Theme.disabledTextColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.max(7, Math.round(compact.height * 0.13))
                    font.weight: Font.DemiBold
                    font.letterSpacing: root.rtl ? 0 : 1.1
                    Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
                }
            }

            Kirigami.Icon {
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: width
                source: "system-search-symbolic"
                color: compact.containsMouse
                    ? Kirigami.Theme.highlightColor
                    : Kirigami.Theme.textColor
                opacity: compact.containsMouse ? 1.0 : 0.58
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
            icon.name: "kmenuedit"
            onTriggered: processRunner.runMenuEditor()
        },
        PlasmaCore.Action {
            text: root.rtl ? "إعدادات البحث…" : "Search settings…"
            icon.name: "preferences-desktop-search"
            onTriggered: root.openDesktop("kcm_plasmasearch.desktop")
        }
    ]

    Component.onCompleted: {
        Plasmoid.activationTogglesExpanded = true;
    }
}

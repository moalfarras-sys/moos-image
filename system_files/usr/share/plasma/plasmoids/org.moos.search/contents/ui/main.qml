pragma ComponentBehavior: Bound
import QtCore
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC3
import org.kde.milou as Milou
import org.kde.plasma.private.kicker as Kicker
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

// MoOS Search — the bar's own results surface.
//
// The first bar search was a TextField that handed the query to KRunner after a typing pause.
// It worked, but it was two surfaces for one intent: the user typed at the bottom of the screen and
// the answers appeared in a separate window at the top, away from their eyes and their pointer.
// MoOS Search now opens ONE focused surface anchored to the bar: the field, live results grouped by
// kind, the action a row will take, and an explicit hand-off to Mo AI.
//
// Results come from Milou.ResultsModel — the same KRunner runners Plasma's own search uses
// (applications, System Settings pages, files, calculator, units, Mo AI's runner). Nothing here
// re-implements a runner, and a result is always executed by the model that produced it.
//
// Focus: a panel does not take keyboard focus. The field therefore lives in the popup, which is a
// real window and receives keys the moment it opens; the bar pill is a button. Clicking it, or
// activating the applet from its keyboard shortcut, opens the surface with the caret already in the
// field. The previous AcceptingInputStatus juggling is no longer needed.
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "moos-search-symbolic"
    preferredRepresentation: compactRepresentation
    activationTogglesExpanded: true
    hideOnWindowDeactivate: true

    readonly property bool rtl: MoUI.Locale.rtl
    readonly property var design: MoUI.Tokens
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property string uiFontFamily: Qt.application.font.family
    // The standalone applet has more vertical room than the bottom-panel
    // Context Island host. SearchView reads this one host-owned geometry token.
    readonly property int searchSurfaceUnits: 28
    readonly property int searchBottomInset: 0
    property string query: ""
    property string queuedRun: ""
    property int queryRevision: 0

    onQueryChanged: {
        ++root.queryRevision;
        root.queuedRun = "";
    }

    function local(arabic, english) { return root.rtl ? arabic : english; }
    function fast() { return root.design.duration(root.motionEnabled, root.design.motionFast); }

    toolTipMainText: root.local("بحث MoOS", "MoOS Search")
    toolTipSubText: root.local("التطبيقات والإعدادات والملفات", "Apps, settings and files")

    Milou.ResultsModel {
        id: results
        queryString: root.query
        limit: 30
        onQueryStringChangeRequested: (queryString, cursorPosition) => {
            root.query = queryString;
        }
        onQueryingChanged: root.runQueued()
    }

    Kicker.RecentUsageModel {
        id: recentApps
        shownItems: Kicker.RecentUsageModel.OnlyApps
        ordering: 0
    }

    onExpandedChanged: {
        if (!root.expanded) {
            root.query = "";
            root.queuedRun = "";
        }
    }

    function openRecent(row) {
        if (row >= 0 && row < recentApps.count && recentApps.trigger(row, "", null)) {
            root.expanded = false;
        }
    }

    function run(row) {
        if (!root.expanded || results.querying || row < 0 || row >= results.rowCount()) {
            return;
        }
        if (results.run(results.index(row, 0))) {
            root.expanded = false;
        }
    }

    // Enter can arrive before the runners have answered the text just typed. Running whatever row
    // is current at that moment would launch the result for an OLDER query, so the request waits for
    // the model to settle on exactly this query and then runs its first row.
    function runCurrent(row) {
        if (!root.expanded || root.query.trim().length === 0) return;
        if (results.querying || results.rowCount() < 1 || row < 0) {
            root.queuedRun = root.query;
            return;
        }
        root.queuedRun = "";
        root.run(row);
    }
    function runQueued() {
        if (root.queuedRun.length > 0 && root.queuedRun === root.query
                && !results.querying && results.rowCount() > 0) {
            const requestedQuery = root.queuedRun;
            const requestedRevision = root.queryRevision;
            Qt.callLater(() => {
                // A popup close, edit or clear/retype can happen before the next event turn.
                // Check again at execution, including revisions for an identical retyped query.
                if (root.expanded && root.query === requestedQuery
                        && root.queryRevision === requestedRevision
                        && root.queuedRun === requestedQuery && !results.querying) {
                    root.queuedRun = "";
                    root.run(0);
                }
            });
        }
    }

    function askMoAI() {
        const question = root.query.trim();
        root.expanded = false;
        Qt.openUrlExternally(question.length > 0
            ? "moos://ai/ask/" + encodeURIComponent(question)
            : "moos://app/moai");
    }

    function openDestination(target) {
        root.expanded = false;
        Qt.openUrlExternally(target);
    }

    // ── The bar button ───────────────────────────────────────────────────────────────────────
    //
    // This used to be a 140–196 px pill carrying the words "ابحث في MoOS | Search MoOS".
    // On the owner's own desk that was the widest thing on the bar and it held nothing: the
    // field it suggests lives in the popup, because a panel cannot take keyboard focus. So the
    // bar paid for a text box that can never be typed into, the bar grew by the width of that
    // promise, and the words repeated what the magnifier already says. Measured on the station
    // on 2026-09-18: the empty pill took as much room as four application icons.
    //
    // It is a button now — one icon, the size of its neighbours — and it opens exactly the same
    // surface. The hint moved into the tooltip and into the popup's own placeholder, where the
    // caret actually is.
    compactRepresentation: Item {
        id: pill
        implicitWidth: root.design.targetControl
        implicitHeight: root.design.targetControl
        Layout.minimumWidth: root.design.targetControl
        Layout.preferredWidth: root.design.targetControl
        Layout.maximumWidth: root.design.targetControl
        Layout.minimumHeight: root.design.targetControl

        LayoutMirroring.enabled: root.rtl
        LayoutMirroring.childrenInherit: true

        Accessible.role: Accessible.Button
        Accessible.name: root.local("فتح بحث MoOS", "Open MoOS Search")
        Accessible.onPressAction: root.expanded = !root.expanded

        MouseArea {
            id: pillArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            // Press-time capture: if this press dismissed the open surface, the release must not
            // read the post-dismiss state and open it again.
            property bool wasExpanded: false
            onPressed: wasExpanded = root.expanded
            onClicked: root.expanded = !wasExpanded
        }

        Rectangle {
            id: pillShell
            anchors.fill: parent
            anchors.topMargin: root.design.space1 + 1
            anchors.bottomMargin: root.design.space1 + 1
            radius: height / 2
            // A slot recessed into the bar, not a bordered text box: a quiet tint of the text
            // colour, with Aurora Glass's own rim at PANEL depth so the button keeps an edge
            // over a bright wallpaper, and a hairline that brightens with attention.
            color: Qt.alpha(Kirigami.Theme.textColor,
                            root.expanded ? 0.14 : (pillArea.containsMouse ? 0.11 : 0.075))
            border.width: root.design.borderHairline
            border.color: root.expanded
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.72)
                : (pillArea.containsMouse
                    ? Qt.alpha(Kirigami.Theme.textColor, 0.20)
                    : root.design.glassEdge(Kirigami.Theme.backgroundColor,
                                            root.design.glassLevelPanel))
            scale: pillFeedback.value
            antialiasing: true
            Behavior on color { ColorAnimation { duration: root.fast() } }
            Behavior on border.color { ColorAnimation { duration: root.fast() } }

            MoUI.SpringFeedback {
                id: pillFeedback
                active: pill.visible
                targetScale: pillArea.pressed ? root.design.pressScale : 1
            }

            Kirigami.Icon {
                anchors.centerIn: parent
                width: 20
                height: 20
                source: "moos-search-symbolic"
                color: root.expanded ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                opacity: root.expanded || pillArea.containsMouse ? 1 : 0.8
            }
        }
    }

    // ── The results surface ──────────────────────────────────────────────────────────────────
    fullRepresentation: SearchView {
        controller: root
        resultModel: results
        recentModel: recentApps
    }
}

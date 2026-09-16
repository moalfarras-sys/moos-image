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
    property string query: ""
    property string queuedRun: ""

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
        if (row < 0 || row >= results.rowCount()) {
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
            root.queuedRun = "";
            Qt.callLater(() => root.run(0));
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

    // ── The bar pill ─────────────────────────────────────────────────────────────────────────
    compactRepresentation: Item {
        id: pill
        implicitWidth: Math.round(Math.min(196, Math.max(140, Screen.width * 0.125)))
        implicitHeight: root.design.targetControl
        Layout.minimumWidth: 140
        Layout.preferredWidth: implicitWidth
        Layout.maximumWidth: 196
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
            // colour, and a hairline that only brightens with attention.
            color: Qt.alpha(Kirigami.Theme.textColor,
                            root.expanded ? 0.14 : (pillArea.containsMouse ? 0.11 : 0.075))
            border.width: root.design.borderHairline
            border.color: root.expanded
                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.72)
                : Qt.alpha(Kirigami.Theme.textColor, pillArea.containsMouse ? 0.20 : 0.10)
            scale: pillFeedback.value
            antialiasing: true
            Behavior on color { ColorAnimation { duration: root.fast() } }
            Behavior on border.color { ColorAnimation { duration: root.fast() } }

            MoUI.SpringFeedback {
                id: pillFeedback
                active: pill.visible
                targetScale: pillArea.pressed ? root.design.pressScale : 1
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: root.design.space3
                anchors.rightMargin: root.design.space3
                spacing: root.design.space2

                Kirigami.Icon {
                    Layout.preferredWidth: 18
                    Layout.preferredHeight: 18
                    source: "moos-search-symbolic"
                    color: root.expanded ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                    opacity: root.expanded || pillArea.containsMouse ? 1 : 0.8
                }
                Text {
                    Layout.fillWidth: true
                    text: root.local("ابحث في MoOS", "Search MoOS")
                    textFormat: Text.PlainText
                    color: Kirigami.Theme.textColor
                    opacity: 0.74
                    font.family: root.uiFontFamily
                    font.pixelSize: root.design.typeSecondary
                    horizontalAlignment: Text.AlignLeft
                    elide: Text.ElideRight
                }
            }
        }
    }

    // ── The results surface ──────────────────────────────────────────────────────────────────
    fullRepresentation: FocusScope {
        id: surface
        Layout.minimumWidth: Kirigami.Units.gridUnit * 24
        Layout.preferredWidth: Kirigami.Units.gridUnit * 30
        Layout.maximumWidth: Kirigami.Units.gridUnit * 34
        Layout.minimumHeight: Kirigami.Units.gridUnit * 16
        Layout.preferredHeight: Kirigami.Units.gridUnit * 28
        Layout.maximumHeight: Kirigami.Units.gridUnit * 32
        focus: true

        LayoutMirroring.enabled: root.rtl
        LayoutMirroring.childrenInherit: true

        readonly property bool hasQuery: root.query.trim().length > 0

        function focusField() {
            field.forceActiveFocus();
            field.cursorPosition = field.text.length;
        }
        function move(step) {
            if (resultList.count < 1) {
                return;
            }
            const next = resultList.currentIndex + step;
            resultList.currentIndex = Math.max(0, Math.min(resultList.count - 1, next));
            resultList.positionViewAtIndex(resultList.currentIndex, ListView.Contain);
        }

        Component.onCompleted: if (root.expanded) Qt.callLater(surface.focusField)
        Connections {
            target: root
            function onExpandedChanged() {
                if (root.expanded) {
                    Qt.callLater(surface.focusField);
                    if (root.motionEnabled) {
                        entrance.value = 0.965;
                        entrance.retarget();
                    }
                }
            }
        }

        // One finite spring for the arrival. It scales the content about its own bottom edge (the
        // side the surface grows from), so nothing travels across the screen; with animations off
        // it is simply there, and it does no work once settled.
        MoUI.SpringFeedback {
            id: entrance
            active: root.expanded
            targetScale: 1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.design.space3
            spacing: root.design.space3
            scale: entrance.value
            opacity: Math.min(1, Math.max(0, (entrance.value - 0.94) / 0.06))
            transformOrigin: Item.Bottom

            // Field ──────────────────────────────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: root.design.targetComfortable + root.design.space1
                radius: root.design.radiusControl + 2
                color: Qt.alpha(Kirigami.Theme.textColor, 0.075)
                border.width: field.activeFocus ? root.design.focusWidth : root.design.borderHairline
                border.color: field.activeFocus
                    ? Qt.alpha(Kirigami.Theme.highlightColor, 0.85)
                    : Qt.alpha(Kirigami.Theme.textColor, 0.12)

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: root.design.space4
                    anchors.rightMargin: root.design.space2
                    spacing: root.design.space3

                    Kirigami.Icon {
                        Layout.preferredWidth: root.design.iconLarge
                        Layout.preferredHeight: root.design.iconLarge
                        source: "moos-search-symbolic"
                        color: Kirigami.Theme.highlightColor
                    }

                    TextInput {
                        id: field
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        verticalAlignment: TextInput.AlignVCenter
                        horizontalAlignment: TextInput.AlignLeft
                        text: root.query
                        color: Kirigami.Theme.textColor
                        selectionColor: Kirigami.Theme.highlightColor
                        selectedTextColor: Kirigami.Theme.highlightedTextColor
                        font.family: root.uiFontFamily
                        font.pixelSize: root.design.typeLabel + 1
                        font.weight: Font.Medium
                        selectByMouse: true
                        clip: true
                        inputMethodHints: Qt.ImhNoPredictiveText
                        Accessible.role: Accessible.EditableText
                        Accessible.name: root.local("ابحث في التطبيقات والإعدادات والملفات",
                                                    "Search apps, settings and files")

                        onTextEdited: {
                            root.query = text;
                            resultList.currentIndex = -1;
                        }
                        onAccepted: {
                            if (surface.hasQuery) {
                                root.runCurrent(Math.max(0, resultList.currentIndex));
                            }
                        }

                        Keys.onDownPressed: event => { surface.move(1); event.accepted = true; }
                        Keys.onUpPressed: event => { surface.move(-1); event.accepted = true; }
                        Keys.onTabPressed: event => {
                            if (resultList.visible && resultList.count > 0) {
                                resultList.forceActiveFocus();
                                if (resultList.currentIndex < 0) resultList.currentIndex = 0;
                            } else {
                                askRow.forceActiveFocus();
                            }
                            event.accepted = true;
                        }
                        Keys.onPressed: event => {
                            // Ctrl+Enter asks Mo AI instead of running the highlighted result.
                            if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                    && (event.modifiers & Qt.ControlModifier)) {
                                root.askMoAI();
                                event.accepted = true;
                            }
                        }
                        Keys.onEscapePressed: event => {
                            if (text.length > 0) {
                                root.query = "";
                            } else {
                                root.expanded = false;
                            }
                            event.accepted = true;
                        }

                        Text {
                            anchors.fill: parent
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignLeft
                            visible: field.text.length === 0
                            text: root.local("اكتب اسم تطبيق أو إعداد أو ملف…",
                                             "Type an app, a setting or a file…")
                            color: Kirigami.Theme.disabledTextColor
                            font: field.font
                            elide: Text.ElideRight
                        }
                    }

                    PC3.BusyIndicator {
                        Layout.preferredWidth: root.design.iconLarge
                        Layout.preferredHeight: root.design.iconLarge
                        running: surface.hasQuery && results.querying
                        visible: running
                    }

                    PC3.ToolButton {
                        visible: field.text.length > 0
                        icon.name: "moos-close-symbolic"
                        text: root.local("مسح", "Clear")
                        display: PC3.AbstractButton.IconOnly
                        Layout.preferredWidth: root.design.targetCompact
                        Layout.preferredHeight: root.design.targetCompact
                        onClicked: {
                            root.query = "";
                            surface.focusField();
                        }
                    }
                }
            }

            // Results ────────────────────────────────────────────────────────────────────────
            ListView {
                id: resultList
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: surface.hasQuery && count > 0
                clip: true
                model: results
                currentIndex: -1
                spacing: 2
                boundsBehavior: Flickable.StopAtBounds
                activeFocusOnTab: true
                highlightMoveDuration: root.fast()
                Accessible.role: Accessible.List
                Accessible.name: root.local("نتائج البحث", "Search results")
                section.property: "category"
                section.criteria: ViewSection.FullString
                KeyNavigation.backtab: field

                onCountChanged: {
                    if (count < 1) {
                        currentIndex = -1;
                    } else if (currentIndex < 0 || currentIndex >= count) {
                        currentIndex = 0;
                    }
                    root.runQueued();
                }
                Keys.onReturnPressed: event => { root.run(currentIndex); event.accepted = true; }
                Keys.onEnterPressed: event => { root.run(currentIndex); event.accepted = true; }
                Keys.onEscapePressed: event => { surface.focusField(); event.accepted = true; }
                Keys.onUpPressed: event => {
                    if (currentIndex <= 0) surface.focusField(); else decrementCurrentIndex();
                    event.accepted = true;
                }

                section.delegate: Text {
                    required property string section
                    width: ListView.view.width
                    height: Kirigami.Units.gridUnit * 1.6
                    verticalAlignment: Text.AlignBottom
                    leftPadding: root.design.space3
                    rightPadding: root.design.space3
                    bottomPadding: 2
                    text: section
                    textFormat: Text.PlainText
                    horizontalAlignment: Text.AlignLeft
                    color: Kirigami.Theme.highlightColor
                    font.family: root.uiFontFamily
                    font.pixelSize: root.design.typeCaption
                    font.weight: Font.DemiBold
                }

                delegate: PC3.ItemDelegate {
                    id: resultRow
                    required property int index
                    required property var model
                    width: ListView.view.width
                    height: 54
                    hoverEnabled: true
                    enabled: resultRow.model.enabled !== false
                    Accessible.role: Accessible.ListItem
                    Accessible.name: String(resultRow.model.display || "")
                    Accessible.description: String(resultRow.model.subtext || "")
                    readonly property bool current: ListView.isCurrentItem

                    onHoveredChanged: if (hovered) ListView.view.currentIndex = index
                    onClicked: root.run(index)

                    background: Rectangle {
                        radius: root.design.radiusControl
                        color: resultRow.current
                            ? Qt.alpha(Kirigami.Theme.highlightColor, resultRow.down ? 0.22 : 0.13)
                            : "transparent"
                        border.width: resultRow.current && resultList.activeFocus ? root.design.focusWidth : 0
                        border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.8)
                        Behavior on color { ColorAnimation { duration: root.fast() } }
                    }

                    contentItem: RowLayout {
                        spacing: root.design.space3
                        scale: rowFeedback.value
                        MoUI.SpringFeedback {
                            id: rowFeedback
                            active: resultRow.visible
                            targetScale: resultRow.down ? 0.985 : 1
                        }

                        Rectangle {
                            Layout.preferredWidth: 38
                            Layout.preferredHeight: 38
                            radius: root.design.radiusSmall + 2
                            color: Qt.alpha(Kirigami.Theme.textColor, resultRow.current ? 0.10 : 0.06)
                            Kirigami.Icon {
                                anchors.centerIn: parent
                                width: root.design.iconLarge + 4
                                height: width
                                source: resultRow.model.decoration || "moos-search-symbolic"
                                animated: false
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Text {
                                Layout.fillWidth: true
                                text: String(resultRow.model.display || "")
                                textFormat: Text.PlainText
                                color: Kirigami.Theme.textColor
                                font.family: root.uiFontFamily
                                font.pixelSize: root.design.typeBody
                                font.weight: Font.Medium
                                horizontalAlignment: Text.AlignLeft
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: text.length > 0
                                text: String(resultRow.model.subtext || "")
                                textFormat: Text.PlainText
                                color: Kirigami.Theme.disabledTextColor
                                font.family: root.uiFontFamily
                                font.pixelSize: root.design.typeCaption
                                horizontalAlignment: Text.AlignLeft
                                elide: Text.ElideMiddle
                            }
                        }
                        // The action a row will take is visible before it is taken.
                        Rectangle {
                            visible: resultRow.current
                            Layout.preferredHeight: 24
                            Layout.preferredWidth: actionLabel.implicitWidth + root.design.space4
                            radius: 12
                            color: Qt.alpha(Kirigami.Theme.highlightColor, 0.16)
                            Text {
                                id: actionLabel
                                anchors.centerIn: parent
                                text: root.local("فتح  ↵", "Open  ↵")
                                color: Kirigami.Theme.highlightColor
                                font.family: root.uiFontFamily
                                font.pixelSize: root.design.typeCaption
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                }
            }

            // Nothing matched ────────────────────────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: surface.hasQuery && resultList.count === 0 && !results.querying
                spacing: root.design.space2
                Item { Layout.fillHeight: true }
                Kirigami.Icon {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: root.design.iconHero + 8
                    Layout.preferredHeight: root.design.iconHero + 8
                    source: "moos-search-symbolic"
                    opacity: 0.5
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: root.local("لا توجد نتيجة مطابقة", "Nothing matched")
                    color: Kirigami.Theme.textColor
                    font.family: root.uiFontFamily
                    font.pixelSize: root.design.typeLabel
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.local("جرّب كلمة أخرى، أو اسأل Mo AI بالأسفل.",
                                     "Try another word, or ask Mo AI below.")
                    color: Kirigami.Theme.disabledTextColor
                    font.family: root.uiFontFamily
                    font.pixelSize: root.design.typeSecondary
                }
                Item { Layout.fillHeight: true }
            }

            // Before typing: real destinations, not decoration ────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: !surface.hasQuery
                spacing: root.design.space3

                Text {
                    Layout.fillWidth: true
                    visible: recentApps.count > 0
                    leftPadding: root.design.space1
                    text: root.local("استخدمتها مؤخراً", "Recently used")
                    color: Kirigami.Theme.highlightColor
                    font.family: root.uiFontFamily
                    font.pixelSize: root.design.typeCaption
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignLeft
                }

                // The applications this account actually opened, from Plasma's own activity data —
                // the same source the MoOS launcher uses. Nothing is shown when there is no history.
                ListView {
                    id: recentStrip
                    Layout.fillWidth: true
                    Layout.preferredHeight: 86
                    visible: recentApps.count > 0
                    orientation: ListView.Horizontal
                    spacing: root.design.space2
                    clip: true
                    interactive: false
                    model: recentApps
                    activeFocusOnTab: true
                    currentIndex: -1
                    Accessible.role: Accessible.List
                    Accessible.name: root.local("التطبيقات المستخدمة مؤخراً", "Recently used apps")
                    Keys.onReturnPressed: event => {
                        root.openRecent(currentIndex);
                        event.accepted = true;
                    }

                    delegate: PC3.ItemDelegate {
                        id: recentTile
                        required property int index
                        required property var model
                        width: Math.floor((recentStrip.width - root.design.space2 * 5) / 6)
                        height: recentStrip.height
                        hoverEnabled: true
                        Accessible.role: Accessible.Button
                        Accessible.name: String(recentTile.model.display || "")
                        onClicked: root.openRecent(index)

                        background: Rectangle {
                            radius: root.design.radiusControl
                            color: Qt.alpha(Kirigami.Theme.textColor,
                                            recentTile.down ? 0.14
                                            : (recentTile.hovered || recentTile.ListView.isCurrentItem ? 0.09 : 0))
                            border.width: recentTile.ListView.isCurrentItem && recentStrip.activeFocus
                                ? root.design.focusWidth : 0
                            border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.8)
                            Behavior on color { ColorAnimation { duration: root.fast() } }
                        }
                        contentItem: ColumnLayout {
                            spacing: root.design.space1
                            scale: recentFeedback.value
                            MoUI.SpringFeedback {
                                id: recentFeedback
                                active: recentTile.visible
                                targetScale: recentTile.down ? root.design.pressScale
                                    : (recentTile.hovered ? 1.04 : 1)
                            }
                            Kirigami.Icon {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredWidth: 40
                                Layout.preferredHeight: 40
                                source: recentTile.model.decoration || "application-x-executable"
                                animated: false
                            }
                            Text {
                                Layout.fillWidth: true
                                text: String(recentTile.model.display || "")
                                textFormat: Text.PlainText
                                color: Kirigami.Theme.textColor
                                font.family: root.uiFontFamily
                                font.pixelSize: root.design.typeCaption
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    leftPadding: root.design.space1
                    text: root.local("انتقال سريع", "Go to")
                    color: Kirigami.Theme.highlightColor
                    font.family: root.uiFontFamily
                    font.pixelSize: root.design.typeCaption
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignLeft
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: root.design.space2
                    columnSpacing: root.design.space2

                    Repeater {
                        model: [
                            { icon: "moos-settings-symbolic", ar: "الإعدادات", en: "Settings", target: "moos://app/settings" },
                            { icon: "moos-install-symbolic", ar: "المتجر", en: "Store", target: "moos://app/store" },
                            { icon: "moos-folder-symbolic", ar: "الملفات", en: "Files",
                              target: StandardPaths.writableLocation(StandardPaths.HomeLocation).toString() },
                            { icon: "moos-safe-update-symbolic", ar: "التحديثات", en: "Updates", target: "moos://app/updater" }
                        ]
                        delegate: PC3.ItemDelegate {
                            id: destination
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 52
                            hoverEnabled: true
                            Accessible.role: Accessible.Button
                            Accessible.name: root.local(destination.modelData.ar, destination.modelData.en)
                            onClicked: root.openDestination(destination.modelData.target)
                            Keys.onReturnPressed: event => {
                                root.openDestination(destination.modelData.target);
                                event.accepted = true;
                            }
                            background: Rectangle {
                                radius: root.design.radiusControl
                                color: Qt.alpha(Kirigami.Theme.textColor,
                                                destination.down ? 0.14 : (destination.hovered ? 0.10 : 0.055))
                                border.width: destination.activeFocus ? root.design.focusWidth : 0
                                border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.8)
                                scale: destinationFeedback.value
                                MoUI.SpringFeedback {
                                    id: destinationFeedback
                                    active: destination.visible
                                    targetScale: destination.down ? root.design.pressScale : 1
                                }
                            }
                            contentItem: RowLayout {
                                spacing: root.design.space3
                                Kirigami.Icon {
                                    Layout.preferredWidth: root.design.iconControl + 2
                                    Layout.preferredHeight: root.design.iconControl + 2
                                    source: destination.modelData.icon
                                    color: Kirigami.Theme.highlightColor
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: root.local(destination.modelData.ar, destination.modelData.en)
                                    color: Kirigami.Theme.textColor
                                    font.family: root.uiFontFamily
                                    font.pixelSize: root.design.typeBody
                                    font.weight: Font.Medium
                                    horizontalAlignment: Text.AlignLeft
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                // Keyboard help as keycaps. One mixed Arabic/Latin sentence was reordered by the
                // bidi algorithm into nonsense on the live Arabic session ("Esc للإغلاق" landed in
                // the middle of the Mo AI hint); each hint is now its own isolated row.
                Flow {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    spacing: root.design.space3
                    Repeater {
                        model: [
                            { keys: "↑ ↓", ar: "تنقّل", en: "Move" },
                            { keys: "Enter", ar: "فتح", en: "Open" },
                            { keys: "Ctrl Enter", ar: "اسأل Mo AI", en: "Ask Mo AI" },
                            { keys: "Esc", ar: "إغلاق", en: "Close" }
                        ]
                        delegate: RowLayout {
                            id: hint
                            required property var modelData
                            spacing: root.design.space1
                            Rectangle {
                                Layout.preferredHeight: 20
                                Layout.preferredWidth: keyText.implicitWidth + root.design.space3
                                radius: 6
                                color: Qt.alpha(Kirigami.Theme.textColor, 0.08)
                                border.width: root.design.borderHairline
                                border.color: Qt.alpha(Kirigami.Theme.textColor, 0.16)
                                Text {
                                    id: keyText
                                    anchors.centerIn: parent
                                    text: hint.modelData.keys
                                    color: Kirigami.Theme.textColor
                                    font.family: root.uiFontFamily
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                }
                            }
                            Text {
                                text: root.local(hint.modelData.ar, hint.modelData.en)
                                color: Kirigami.Theme.disabledTextColor
                                font.family: root.uiFontFamily
                                font.pixelSize: root.design.typeCaption
                            }
                        }
                    }
                }
            }

            // Mo AI hand-off ─────────────────────────────────────────────────────────────────
            PC3.ItemDelegate {
                id: askRow
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                hoverEnabled: true
                Accessible.role: Accessible.Button
                Accessible.name: askLabel.text
                KeyNavigation.backtab: field
                onClicked: root.askMoAI()
                Keys.onReturnPressed: event => { root.askMoAI(); event.accepted = true; }

                background: Rectangle {
                    radius: root.design.radiusControl
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: Qt.alpha(Kirigami.Theme.highlightColor, askRow.hovered ? 0.22 : 0.14) }
                        GradientStop { position: 1; color: Qt.alpha(Kirigami.Theme.highlightColor, askRow.hovered ? 0.10 : 0.04) }
                    }
                    border.width: askRow.activeFocus ? root.design.focusWidth : root.design.borderHairline
                    border.color: Qt.alpha(Kirigami.Theme.highlightColor, askRow.activeFocus ? 0.85 : 0.28)
                    scale: askFeedback.value
                    MoUI.SpringFeedback {
                        id: askFeedback
                        active: askRow.visible
                        targetScale: askRow.down ? root.design.pressScale : 1
                    }
                }
                contentItem: RowLayout {
                    spacing: root.design.space3
                    Kirigami.Icon {
                        Layout.preferredWidth: root.design.iconLarge + 2
                        Layout.preferredHeight: root.design.iconLarge + 2
                        source: "moos-ai-symbolic"
                        color: Kirigami.Theme.highlightColor
                    }
                    Text {
                        id: askLabel
                        Layout.fillWidth: true
                        text: surface.hasQuery
                            ? root.local("اسأل Mo AI: «" + root.query.trim() + "»",
                                         "Ask Mo AI: “" + root.query.trim() + "”")
                            : root.local("افتح Mo AI", "Open Mo AI")
                        textFormat: Text.PlainText
                        color: Kirigami.Theme.textColor
                        font.family: root.uiFontFamily
                        font.pixelSize: root.design.typeBody
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignLeft
                        elide: Text.ElideRight
                    }
                    Text {
                        visible: surface.hasQuery
                        text: "Ctrl ↵"
                        color: Kirigami.Theme.highlightColor
                        font.family: root.uiFontFamily
                        font.pixelSize: root.design.typeCaption
                        font.weight: Font.DemiBold
                    }
                }
            }
        }
    }
}

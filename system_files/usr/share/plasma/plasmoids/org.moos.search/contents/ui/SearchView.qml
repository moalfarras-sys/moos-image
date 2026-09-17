pragma ComponentBehavior: Bound
import QtCore
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI
import "SearchAnswers.js" as Answers


// Source-reviewable Search surface; Plasma owns its models and activation.
FocusScope {
    id: surface
    required property var controller
    required property var resultModel
    required property var recentModel
    readonly property var results: resultModel
    readonly property var recentApps: recentModel
    readonly property var root: controller
    Layout.minimumWidth: Math.min(400, Screen.width - 24)
    Layout.preferredWidth: Kirigami.Units.gridUnit * 30
    Layout.maximumWidth: Kirigami.Units.gridUnit * 34
    Layout.minimumHeight: Kirigami.Units.gridUnit * 16
    Layout.preferredHeight: Math.min(Kirigami.Units.gridUnit * 28, Screen.height - 110)
    Layout.maximumHeight: Kirigami.Units.gridUnit * 32
    focus: true

    LayoutMirroring.enabled: root.rtl
    LayoutMirroring.childrenInherit: true

    readonly property bool hasQuery: root.query.trim().length > 0
    readonly property bool compact: width < 480

    readonly property var inlineAnswer: Answers.evaluate(root.query)
    readonly property bool hasInlineAnswer: inlineAnswer !== null && inlineAnswer.valid === true
    property bool answerCopied: false

    function copyAnswer() {
        if (!hasInlineAnswer) return;
        copyText(inlineAnswer.result);
        answerCopied = true;
        answerCopiedTimer.restart();
    }

    function copyText(val) {
        clipHelper.copyText(val);
    }

    TextInput {
        id: clipHelper
        width: 1
        height: 1
        opacity: 0
        visible: true
        function copyText(val) {
            text = String(val);
            selectAll();
            copy();
        }
    }

    Timer {
        id: answerCopiedTimer
        interval: 2500
        repeat: false
        onTriggered: surface.answerCopied = false
    }

    function bidi(value) { return "\u2068" + value + "\u2069"; }

    function focusContent() {
        if (hasQuery) {
            if (resultList.visible && resultList.count > 0) {
                if (resultList.currentIndex < 0) resultList.currentIndex = 0;
                resultList.forceActiveFocus();
            } else askRow.forceActiveFocus();
        } else if (recentStrip.visible && recentStrip.count > 0) {
            if (recentStrip.currentIndex < 0) recentStrip.currentIndex = 0;
            recentStrip.forceActiveFocus();
        } else destinations.itemAt(0).forceActiveFocus();
    }

    function dismiss() {
        if (root.query.length > 0) {
            root.query = "";
            surface.focusField();
        } else root.expanded = false;
    }

    // These handlers also cover recent apps, destination buttons and the AI row.
    Keys.onEscapePressed: event => { surface.dismiss(); event.accepted = true; }
    Keys.onPressed: event => {
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                && (event.modifiers & Qt.ControlModifier)) {
            root.askMoAI();
            event.accepted = true;
        }
    }

    function focusField() {
        field.forceActiveFocus();
        field.cursorPosition = field.text.length;
    }
    function move(step) {
        if (!hasQuery) { surface.focusContent(); return; }
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
                    objectName: "searchField"
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
                        if (surface.hasInlineAnswer && resultList.currentIndex < 0) {
                            surface.copyAnswer();
                        } else if (surface.hasQuery) {
                            root.runCurrent(Math.max(0, resultList.currentIndex));
                        }
                    }

                    Keys.onDownPressed: event => { surface.move(1); event.accepted = true; }
                    Keys.onUpPressed: event => { surface.move(-1); event.accepted = true; }
                    Keys.onTabPressed: event => {
                        surface.focusContent();
                        event.accepted = true;
                    }
                    KeyNavigation.backtab: askRow
                    Keys.onPressed: event => {
                        // Ctrl+Enter asks Mo AI instead of running the highlighted result.
                        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                && (event.modifiers & Qt.ControlModifier)) {
                            root.askMoAI();
                            event.accepted = true;
                        }
                    }
                    Keys.onEscapePressed: event => {
                        surface.dismiss();
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

        // Inline Answer (Math / Unit conversion / Currency) ─────────────────────────
        Rectangle {
            id: heroAnswerCard
            Layout.fillWidth: true
            visible: surface.hasInlineAnswer
            implicitHeight: answerContent.implicitHeight + root.design.space3 * 2
            radius: root.design.radiusCard
            color: Qt.alpha(Kirigami.Theme.highlightColor, 0.12)
            border.width: 1
            border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.35)

            RowLayout {
                id: answerContent
                anchors.fill: parent
                anchors.margins: root.design.space3
                spacing: root.design.space3

                Rectangle {
                    Layout.preferredWidth: 38
                    Layout.preferredHeight: 38
                    radius: root.design.radiusSmall + 2
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.22)

                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: root.design.iconLarge
                        height: width
                        source: "moos-spark-symbolic"
                        animated: false
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Text {
                        Layout.fillWidth: true
                        text: surface.inlineAnswer ? surface.inlineAnswer.expression : ""
                        color: Kirigami.Theme.disabledTextColor
                        font.family: root.uiFontFamily
                        font.pixelSize: root.design.typeCaption
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        text: surface.inlineAnswer ? surface.inlineAnswer.value : ""
                        color: Kirigami.Theme.textColor
                        font.family: root.uiFontFamily
                        font.pixelSize: root.design.typeTitle
                        font.weight: Font.Bold
                        elide: Text.ElideRight
                    }
                }

                PC3.Button {
                    text: surface.answerCopied ? root.local("تم النسخ ✓", "Copied ✓") : root.local("نسخ ↵", "Copy ↵")
                    display: PC3.AbstractButton.TextBesideIcon
                    icon.name: surface.answerCopied ? "moos-check-symbolic" : "moos-copy-symbolic"
                    Layout.preferredHeight: 30
                    onClicked: surface.copyAnswer()
                }
            }
        }

        // Results ────────────────────────────────────────────────────────────────────────
        ListView {
            id: resultList
            objectName: "searchResults"
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
            KeyNavigation.tab: askRow

            onCountChanged: {
                if (count < 1) {
                    currentIndex = -1;
                } else if (currentIndex < 0 || currentIndex >= count) {
                    currentIndex = 0;
                }
                root.runQueued();
            }
            Keys.onReturnPressed: event => {
                if (event.modifiers & Qt.ControlModifier) root.askMoAI();
                else root.runCurrent(currentIndex);
                event.accepted = true;
            }
            Keys.onEnterPressed: event => {
                if (event.modifiers & Qt.ControlModifier) root.askMoAI();
                else root.runCurrent(currentIndex);
                event.accepted = true;
            }
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
                readonly property string filePath: {
                    if (resultRow.model.urls && resultRow.model.urls.length > 0) {
                        let u = String(resultRow.model.urls[0]);
                        return u.startsWith("file://") ? u.slice(7) : u;
                    }
                    let st = String(resultRow.model.subtext || "");
                    if (st.startsWith("/") || st.startsWith("file://")) {
                        return st.startsWith("file://") ? st.slice(7) : st;
                    }
                    return "";
                }
                readonly property bool isFile: filePath.length > 0

                onHoveredChanged: if (hovered) ListView.view.currentIndex = index
                onClicked: root.runCurrent(index)

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
                    // Quick Actions for file results (Open containing folder, Copy path)
                    RowLayout {
                        visible: resultRow.current && resultRow.isFile
                        spacing: 4

                        PC3.Button {
                            display: PC3.AbstractButton.IconOnly
                            icon.name: "moos-folder-symbolic"
                            Layout.preferredWidth: 26
                            Layout.preferredHeight: 24
                            PC3.ToolTip.visible: hovered
                            PC3.ToolTip.text: root.local("فتح المجلد الحاوي", "Open containing folder")
                            onClicked: {
                                let p = resultRow.filePath;
                                let lastSlash = p.lastIndexOf("/");
                                let dir = lastSlash > 0 ? p.substring(0, lastSlash) : "/";
                                Qt.openUrlExternally("file://" + dir);
                            }
                        }

                        PC3.Button {
                            display: PC3.AbstractButton.IconOnly
                            icon.name: "moos-copy-symbolic"
                            Layout.preferredWidth: 26
                            Layout.preferredHeight: 24
                            PC3.ToolTip.visible: hovered
                            PC3.ToolTip.text: root.local("نسخ المسار الكامل", "Copy full path")
                            onClicked: {
                                surface.copyText(resultRow.filePath);
                            }
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
            visible: surface.hasQuery && !surface.hasInlineAnswer && resultList.count === 0 && !results.querying
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
                objectName: "searchRecentApps"
                Layout.fillWidth: true
                Layout.preferredHeight: 86
                visible: recentApps.count > 0
                orientation: ListView.Horizontal
                spacing: root.design.space2
                clip: true
                interactive: contentWidth > width
                model: recentApps
                activeFocusOnTab: true
                currentIndex: -1
                readonly property int columns: surface.compact ? 4 : 6
                KeyNavigation.backtab: field
                KeyNavigation.tab: destinations.itemAt(0)
                Keys.onDownPressed: event => {
                    destinations.itemAt(0).forceActiveFocus();
                    event.accepted = true;
                }
                Keys.onUpPressed: event => { surface.focusField(); event.accepted = true; }
                Accessible.role: Accessible.List
                Accessible.name: root.local("التطبيقات المستخدمة مؤخراً", "Recently used apps")
                Keys.onReturnPressed: event => {
                    if (event.modifiers & Qt.ControlModifier) root.askMoAI();
                    else root.openRecent(currentIndex);
                    event.accepted = true;
                }
                Keys.onEnterPressed: event => {
                    if (event.modifiers & Qt.ControlModifier) root.askMoAI();
                    else root.openRecent(currentIndex);
                    event.accepted = true;
                }

                delegate: PC3.ItemDelegate {
                    id: recentTile
                    required property int index
                    required property var model
                    width: Math.floor((recentStrip.width
                                       - root.design.space2 * (recentStrip.columns - 1))
                                      / recentStrip.columns)
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
                    id: destinations
                    model: [
                        { icon: "moos-settings-symbolic", ar: "الإعدادات", en: "Settings", target: "moos://app/settings" },
                        { icon: "moos-install-symbolic", ar: "المتجر", en: "Store", target: "moos://app/store" },
                        { icon: "moos-folder-symbolic", ar: "الملفات", en: "Files",
                          target: StandardPaths.writableLocation(StandardPaths.HomeLocation).toString() },
                        { icon: "moos-safe-update-symbolic", ar: "التحديثات", en: "Updates", target: "moos://app/updater" }
                    ]
                    delegate: PC3.ItemDelegate {
                        id: destination
                        required property int index
                        required property var modelData
                        objectName: "searchDestination" + index
                        Layout.fillWidth: true
                        Layout.preferredHeight: 52
                        hoverEnabled: true
                        Accessible.role: Accessible.Button
                        Accessible.name: root.local(destination.modelData.ar, destination.modelData.en)
                        onClicked: root.openDestination(destination.modelData.target)
                        KeyNavigation.backtab: index > 0 ? destinations.itemAt(index - 1)
                            : (recentStrip.visible ? recentStrip : field)
                        KeyNavigation.tab: index < destinations.count - 1 ? destinations.itemAt(index + 1) : askRow
                        Keys.onReturnPressed: event => {
                            if (event.modifiers & Qt.ControlModifier) root.askMoAI();
                            else root.openDestination(destination.modelData.target);
                            event.accepted = true;
                        }
                        Keys.onEnterPressed: event => {
                            if (event.modifiers & Qt.ControlModifier) root.askMoAI();
                            else root.openDestination(destination.modelData.target);
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
            objectName: "searchAskMoAI"
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            hoverEnabled: true
            Accessible.role: Accessible.Button
            Accessible.name: askLabel.text
            KeyNavigation.backtab: surface.hasQuery
                ? (resultList.visible ? resultList : field) : destinations.itemAt(destinations.count - 1)
            KeyNavigation.tab: field
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
                        ? root.local("اسأل " + surface.bidi("Mo AI: «"
                                                           + root.query.trim() + "»"),
                                     "Ask Mo AI: “" + surface.bidi(root.query.trim()) + "”")
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

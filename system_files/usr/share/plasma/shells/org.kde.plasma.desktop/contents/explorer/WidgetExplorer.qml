// SPDX-License-Identifier: GPL-2.0-or-later
// Shell overlay: the catalog, applets, actions and persistence belong to Plasma.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.shell as Shell
import org.kde.kwindowsystem
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

QQC2.Page {
    id: main
    objectName: "moosDesktopCustomizer"
    width: Math.min(540, Screen.width * 0.46)
    height: 800
    padding: MoUI.Tokens.space4
    property QtObject containment
    readonly property var desktopItem: typeof root !== "undefined" ? root.containment : null
    property PlasmaCore.Dialog sidePanel
    property bool draggingWidget: false
    property bool preventWindowHide: draggingWidget || confirmation.visible
    property bool outputOnly: draggingWidget
    property int page: 0
    property var selected: null
    property string message: ""
    property var pendingRemoval: []
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property bool desktopTarget: containment && containment.containmentType === 0
    readonly property bool editable: containment && !containment.immutable
    readonly property var applets: containment ? Array.from(containment.applets) : []
    signal closed()
    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true
    opacity: draggingWidget ? 0.4 : 1
    font.family: MoUI.Tokens.interfaceFamily
    function local(ar, en) { return MoUI.Locale.local(ar, en) }
    function retired(plugin) {
        return ["org.moos.ui2.dashboard", "org.moos.nova.deskclock", "org.moos.heroclock"].indexOf(plugin) >= 0
    }
    function selectWidget(data) {
        selected = {plugin: data.pluginName, name: data.name, description: data.description,
                    screenshot: data.screenshot, icon: data.decoration,
                    supported: data.isSupported && !retired(data.pluginName),
                    reason: retired(data.pluginName) ? local("أداة متقاعدة؛ لا يحتفظ بها نظام المظهر.", "Retired widget; the theme system does not retain it.") : data.unsupportedMessage}
    }
    function actionFor(applet, name) { return applet ? applet.internalAction(name) : null }
    function removeWidgets(items) {
        // Snapshot only this containment, never global removeAllInstances().
        pendingRemoval = items.filter(a => applets.indexOf(a) >= 0 && actionFor(a, "remove")?.enabled)
        if (pendingRemoval.length) confirmation.open()
    }
    function confirmRemoval() {
        const items = pendingRemoval.slice()
        pendingRemoval = []
        for (const applet of items) {
            if (applets.indexOf(applet) >= 0 && actionFor(applet, "remove")?.enabled)
                actionFor(applet, "remove").trigger()
        }
        message = local("استخدم «تراجع» في إشعار سطح المكتب لاستعادة الأداة.", "Use Undo in the desktop notification to restore a removed widget.")
    }
    function arrange() {
        if (!editable || !desktopTarget) return
        containment.corona.editMode = true
        KWindowSystem.showingDesktop = true
        main.closed()
    }
    function openAppearance() {
        if (!Qt.openUrlExternally("moos://settings/themes"))
            message = local("تعذّر فتح إعدادات المظهر.", "Could not open Appearance.")
    }
    onPreventWindowHideChanged: {
        if (!preventWindowHide && sidePanel && !sidePanel.active) sidePanel.requestActivate()
    }
    Component.onCompleted: {
        // DBus has no containment sender; the owning Desktop view is authoritative.
        if (!containment && typeof root !== "undefined") containment = root.containment.plasmoid
        search.forceActiveFocus()
    }
    Shell.WidgetExplorer {
        id: catalog
        containment: main.containment
        onShouldClose: main.closed()
    }
    background: MoUI.GlassSurface { }
    QQC2.Action {
        shortcut: "Escape"
        onTriggered: {
            if (confirmation.visible) confirmation.close()
            else if (main.selected) main.selected = null
            else if (search.text) search.clear()
            else main.closed()
        }
    }
    header: ColumnLayout {
        spacing: MoUI.Tokens.space3
        RowLayout {
            Layout.margins: MoUI.Tokens.space4
            Layout.bottomMargin: 0
            ColumnLayout {
                Layout.fillWidth: true
                QQC2.Label { text: main.local("مساحتك، بطريقتك", "YOUR SPACE, YOUR WAY"); color: Kirigami.Theme.highlightColor; font.pixelSize: MoUI.Tokens.typeCaption }
                QQC2.Label { text: main.local("تخصيص سطح المكتب", "Customize Desktop"); font.pixelSize: MoUI.Tokens.typeHeadline; font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
            MoUI.Button { label: main.local("تم", "Done"); onClicked: { if (main.containment) main.containment.corona.editMode = false; main.closed() } }
        }
        QQC2.Label {
            Layout.fillWidth: true; Layout.leftMargin: 16; Layout.rightMargin: 16
            text: main.desktopTarget ? main.local("أدوات حقيقية. أضف ما تحتاجه، حيث تريده.", "Real widgets. Add what you need, where you want it.") : main.local("إضافة أدوات إلى اللوحة المحددة", "Add widgets to the selected panel")
            color: Kirigami.Theme.disabledTextColor; wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.margins: 16; Layout.topMargin: 0
            MoUI.Button { Layout.fillWidth: true; label: main.local("تصفح الأدوات", "Browse"); primary: main.page === 0; onClicked: { main.page = 0; main.selected = null } }
            MoUI.Button { Layout.fillWidth: true; label: main.local("على سطح المكتب", "On desktop") + " · " + main.applets.length; visible: main.desktopTarget; primary: main.page === 1; onClicked: { main.page = 1; main.selected = null } }
        }
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: MoUI.Tokens.space3
        QQC2.Label {
            visible: !main.editable || !!main.message
            Layout.fillWidth: true; wrapMode: Text.Wrap
            text: !main.editable ? main.local("الأدوات مقفلة في هذه الجلسة.", "Widgets are locked in this session.") : main.message
            textFormat: Text.PlainText
            color: Kirigami.Theme.neutralTextColor
        }
        QQC2.TextField {
            id: search; objectName: "widgetSearch"
            visible: main.page === 0 && !main.selected
            Layout.fillWidth: true
            placeholderText: main.local("ابحث عن ساعة، طقس، ملاحظات…", "Search clocks, weather, notes…")
            Accessible.name: placeholderText
            onTextChanged: catalog.widgetsModel.searchTerm = text
        }
        QQC2.ScrollView {
            visible: main.page === 0 && !main.selected
            Layout.fillWidth: true; Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            GridView {
                id: grid; objectName: "widgetCatalog"
                model: catalog.widgetsModel
                cellWidth: width / 2; cellHeight: 184
                activeFocusOnTab: true
                delegate: QQC2.AbstractButton {
                    id: tile
                    required property var model
                    required property int index
                    width: grid.cellWidth - 8; height: grid.cellHeight - 8
                    text: model.name; Accessible.name: text
                    activeFocusOnTab: true
                    onClicked: main.selectWidget(model)
                    background: MoUI.Card { hovered: tile.hovered; pressed: tile.down; selected: tile.activeFocus }
                    contentItem: ColumnLayout {
                        spacing: 8
                        Kirigami.Icon { source: tile.model.decoration; Layout.alignment: Qt.AlignHCenter; implicitWidth: 48; implicitHeight: 48 }
                        QQC2.Label { Layout.fillWidth: true; text: tile.model.name; textFormat: Text.PlainText; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; font.bold: true }
                        QQC2.Label { Layout.fillWidth: true; text: !tile.model.isSupported || main.retired(tile.model.pluginName) ? main.local("غير مدعومة", "Unavailable") : main.local("عرض التفاصيل", "View preview"); horizontalAlignment: Text.AlignHCenter; color: Kirigami.Theme.disabledTextColor }
                    }
                    padding: 16
                }
                QQC2.Label { anchors.centerIn: parent; width: parent.width - 32; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; visible: grid.count === 0; text: main.local("لا توجد أدوات تطابق بحثك.", "No widgets match your search.") }
            }
        }
        QQC2.ScrollView {
            visible: main.page === 0 && !!main.selected
            Layout.fillWidth: true; Layout.fillHeight: true
            contentWidth: availableWidth
            ColumnLayout {
                width: parent.width
                spacing: 16
                MoUI.Button { label: main.local("العودة إلى الأدوات", "Back to widgets"); onClicked: main.selected = null }
                MoUI.Surface {
                    Layout.fillWidth: true; implicitHeight: 200; interactive: true
                    Image {
                        id: preview; anchors.fill: parent; anchors.margins: 16
                        source: main.selected?.screenshot || ""
                        fillMode: Image.PreserveAspectFit
                    }
                    Kirigami.Icon { anchors.centerIn: parent; width: 72; height: 72; source: main.selected?.icon || ""; visible: preview.status !== Image.Ready }
                }
                QQC2.Label { Layout.fillWidth: true; text: main.selected?.name || ""; textFormat: Text.PlainText; font.pixelSize: MoUI.Tokens.typeTitle; font.bold: true; wrapMode: Text.Wrap }
                QQC2.Label { Layout.fillWidth: true; text: main.selected?.description || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap }
                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: Kirigami.Theme.disabledTextColor; text: preview.status === Image.Ready ? main.local("معاينة يوفرها مطوّر الأداة.", "Preview supplied by the widget author.") : main.local("لا تتوفر صورة معاينة لهذه الأداة. هذه أيقونتها فقط.", "This widget has no preview image. Its icon is shown above.") }
                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText; color: Kirigami.Theme.neutralTextColor; visible: !!main.selected && !main.selected.supported; text: main.selected?.reason || main.local("هذه الأداة غير متوافقة مع الجلسة الحالية.", "This widget is not compatible with the current session.") }
                MoUI.Button {
                    objectName: "previewSelectedWidget"
                    Layout.fillWidth: true
                    label: main.local("معاينة حية في نافذة ↗", "Live preview in a window ↗")
                    enabled: !!main.selected?.supported
                    onClicked: {
                        if (!Qt.openUrlExternally("moos://desktop/preview/" + main.selected.plugin))
                            main.message = main.local("تعذّر فتح المعاينة.", "Could not open the preview.")
                    }
                }
                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: Kirigami.Theme.disabledTextColor; text: main.local("المعاينة تشغّل الأداة الحقيقية دون إضافتها إلى سطح المكتب. أغلق النافذة لإنهائها.", "Preview runs the real widget without adding it to your desktop. Close its window to end it.") }
                MoUI.Button {
                    objectName: "addSelectedWidget"
                    Layout.fillWidth: true; primary: true
                    enabled: main.editable && !!main.selected?.supported
                    label: main.local("أضف الأداة", "Add widget")
                    onClicked: {
                        const before = main.applets.length
                        catalog.addApplet(main.selected.plugin)
                        main.message = main.applets.length > before
                            ? main.local("أضيفت الأداة. اختر «ترتيب» لتحريكها وتغيير حجمها.", "Widget added. Choose Arrange to move and resize it.")
                            : main.local("لم تتم إضافة الأداة. تحقق من رسالة سطح المكتب.", "The widget was not added. Check the desktop error message.")
                    }
                }
                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: Kirigami.Theme.disabledTextColor; text: main.local("أو اسحب الأداة التالية إلى المكان الذي تختاره:", "Or drag the widget below to choose its position:") }
                MoUI.Surface {
                    id: dragSource
                    Layout.fillWidth: true; implicitHeight: 64; interactive: true
                    enabled: main.editable && !!main.selected?.supported
                    QQC2.Label { anchors.centerIn: parent; text: main.local("اسحب إلى سطح المكتب", "Drag to desktop") }
                    Drag.dragType: Drag.Automatic
                    Drag.supportedActions: Qt.MoveAction | Qt.LinkAction
                    Drag.mimeData: ({"text/x-plasmoidservicename": main.selected?.plugin || ""})
                    Drag.onDragStarted: { main.draggingWidget = true; KWindowSystem.showingDesktop = true }
                    Drag.onDragFinished: main.draggingWidget = false
                    DragHandler { target: null; onActiveChanged: dragSource.Drag.active = active }
                }
            }
        }
        QQC2.ScrollView {
            visible: main.page === 1
            Layout.fillWidth: true; Layout.fillHeight: true; contentWidth: availableWidth
            ColumnLayout {
                width: parent.width; spacing: 12
                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; visible: main.applets.length === 0; text: main.local("سطح مكتب هادئ. تصفح الأدوات لإضافة أول أداة.", "A clear desktop. Browse widgets to add your first one.") }
                Repeater {
                    model: main.applets
                    delegate: MoUI.Surface {
                        id: instance
                        required property var modelData
                        readonly property var visual: main.desktopItem?.itemFor(modelData)
                        readonly property var failure: visual?.errorInformation || visual?.fullRepresentationItem?.errorInformation || null
                        readonly property var configureAction: main.actionFor(modelData, "configure")
                        readonly property var removeAction: main.actionFor(modelData, "remove")
                        Layout.fillWidth: true; implicitHeight: instanceContent.implicitHeight + 32; interactive: true
                        ColumnLayout {
                            id: instanceContent; anchors.fill: parent; anchors.margins: 16
                            QQC2.Label { Layout.fillWidth: true; text: instance.modelData.title; textFormat: Text.PlainText; font.bold: true; wrapMode: Text.Wrap }
                            QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: Kirigami.Theme.disabledTextColor; text: instance.failure ? main.local("تعذّر تحميل الأداة: ", "Widget failed to load: ") + (instance.failure.compactError || "") : instance.modelData.configurationRequired ? main.local("تحتاج إلى إعداد", "Setup required") : main.local("على سطح المكتب · " + instance.modelData.id, "On this desktop · " + instance.modelData.id) }
                            RowLayout {
                                MoUI.Button { label: main.local("إعداد", "Configure"); visible: instance.modelData.hasConfigurationInterface; enabled: instance.configureAction?.enabled ?? false; onClicked: instance.configureAction.trigger() }
                                Item { Layout.fillWidth: true }
                                MoUI.Button { objectName: "removeWidget"; label: main.local("إزالة", "Remove"); destructive: true; enabled: main.editable && (instance.removeAction?.enabled ?? false); onClicked: main.removeWidgets([instance.modelData]) }
                            }
                        }
                    }
                }
            }
        }
        MoUI.Separator { Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            MoUI.Button { Layout.fillWidth: true; label: main.local("ترتيب", "Arrange"); enabled: main.editable; visible: main.desktopTarget; onClicked: main.arrange() }
            MoUI.Button { Layout.fillWidth: true; label: main.local("المظهر والخلفية", "Wallpaper & theme"); onClicked: main.openAppearance() }
        }
        MoUI.Button { Layout.fillWidth: true; visible: main.page === 1 && main.desktopTarget; enabled: main.editable && main.applets.length > 0; label: main.local("إعادة ضبط أدوات سطح المكتب…", "Reset desktop widgets…"); destructive: true; onClicked: main.removeWidgets(main.applets) }
    }
    QQC2.Popup {
        id: confirmation
        parent: main
        anchors.centerIn: parent
        width: main.width - 32
        modal: true; focus: true; padding: 24
        closePolicy: QQC2.Popup.CloseOnEscape
        background: MoUI.Surface { }
        onClosed: main.pendingRemoval = []
        contentItem: ColumnLayout {
            spacing: 16
            QQC2.Label { Layout.fillWidth: true; font.bold: true; font.pixelSize: MoUI.Tokens.typeTitle; wrapMode: Text.Wrap; text: main.local("إزالة الأدوات المحددة؟", "Remove selected widgets?") }
            QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: main.local("سيُزال عدد الأدوات التالي من سطح المكتب الحالي: ", "Widgets to remove from this desktop: ") + main.pendingRemoval.length + main.local(". تبقى الملفات والخلفية واللوحة كما هي. تتوفر استعادة مؤقتة عبر إشعار «تراجع» من سطح المكتب.", ". Files, wallpaper and panels are preserved. Desktop notifications offer a brief Undo period.") }
            MoUI.Button { Layout.fillWidth: true; label: main.local("إلغاء", "Cancel"); onClicked: confirmation.close(); Component.onCompleted: forceActiveFocus() }
            MoUI.Button { objectName: "confirmWidgetRemoval"; Layout.fillWidth: true; destructive: true; label: main.local("إزالة الأدوات", "Remove widgets"); onClicked: { main.confirmRemoval(); confirmation.close() } }
        }
    }
}

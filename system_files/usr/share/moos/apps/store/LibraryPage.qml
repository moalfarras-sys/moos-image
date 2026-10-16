pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — My apps: every app installed on this computer, of every kind (including the ones
// added from a file), with the four kinds as chips. Each row opens its page, and offers Open,
// Update when one is waiting, Permissions… where the Store can change them, and Remove….
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: library
    required property var win
    readonly property var design: win.design
    readonly property real padding: library.width > win.fs(1000) ? design.space6 : design.space5

    anchors.fill: parent
    visible: win.page === "library"
    transform: pageEnter.shift
    PageEnter { id: pageEnter; win: library.win; target: library }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: library.padding
        anchors.rightMargin: library.padding
        anchors.topMargin: library.design.space2
        spacing: library.design.space4

        RowLayout {
            Layout.fillWidth: true
            spacing: library.design.space3
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: {
                    var parts = [library.win.rtl ? library.win.appsCountText(library.win.installedApps.length) + " على هذا الجهاز"
                                                 : library.win.appsCountText(library.win.installedApps.length) + " on this computer"]
                    var pending = library.win.updatesState === "known" ? library.win.updateItems().length : 0
                    if (pending > 0) parts.push(library.win.rtl ? library.win.updatesCountText(pending) + " بالانتظار"
                                                                : library.win.updatesCountText(pending) + " waiting")
                    return parts.join("  ·  ")
                }
                color: library.win.txt2
                font.family: library.win.uiFont
                font.pixelSize: library.win.typePx(14)
                elide: Text.ElideRight
            }
            ActionButton {
                win: library.win
                visible: library.win.updatesState === "known" && library.win.updateItems().length > 0
                pill: true
                primary: true
                label: library.win.local("حدّث الكل", "Update all")
                glyphName: "download"
                enabled: !library.win.jobIsActive()
                triggered: function() { library.win.updateAll() }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: library.design.space2
            Repeater {
                model: [{ id: "all", ar: "الكل", en: "All", glyph: "" }].concat(library.win.kindDefs)
                delegate: KindChip {
                    id: libraryChip
                    required property var modelData
                    win: library.win
                    label: libraryChip.modelData.id === "all" ? library.win.local("الكل", "All")
                                                              : library.win.localName(libraryChip.modelData)
                    glyph: libraryChip.modelData.glyph
                    count: library.win.libraryCount(libraryChip.modelData.id)
                    checked: library.win.libraryKind === libraryChip.modelData.id
                    visible: libraryChip.modelData.id === "all" || library.win.libraryCount(libraryChip.modelData.id) > 0
                    onActivated: library.win.libraryKind = libraryChip.modelData.id
                }
            }
            Item { Layout.fillWidth: true }
        }

        ListView {
            id: libraryList
            objectName: "libraryList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: library.design.space2
            model: library.visible ? library.win.libraryApps : []
            bottomMargin: library.win.footClearance
            boundsBehavior: Flickable.StopAtBounds
            keyNavigationEnabled: true
            reuseItems: true
            activeFocusOnTab: count > 0
            Accessible.role: Accessible.List
            Accessible.name: library.win.local("تطبيقاتي", "My apps")
            Keys.onReturnPressed: if (currentIndex >= 0) library.win.openDetails(library.win.libraryApps[currentIndex])
            Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(libraryList, event)
            onActiveFocusChanged: if (activeFocus && count > 0 && currentIndex < 0) currentIndex = 0
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Rectangle {
                id: entry
                required property var modelData
                required property int index
                readonly property var app: entry.modelData
                readonly property bool runnable: library.win.hasRunnableLifecycle(entry.app)
                readonly property var pending: library.win.updateFor(entry.app)
                // The version an update brings: a catalogue pin names it; a Linux app's newest is
                // the catalogue's own version of it.
                readonly property string updateTarget: !entry.pending ? ""
                    : entry.pending.kind === "pin" ? "" + (entry.pending.version || "")
                    : entry.app.version && entry.app.version !== entry.pending.version ? "" + entry.app.version : ""
                width: libraryList.width
                height: Math.max(library.win.fs(76), entryWords.implicitHeight + library.design.space3 * 2)
                radius: library.design.radiusCard
                color: library.win.cardColor
                border.width: 1
                border.color: libraryList.activeFocus && libraryList.currentIndex === entry.index ? library.win.accent
                             : entryHover.hovered ? library.win.tint(library.win.accent, 0.45) : library.win.cardBorder
                HoverHandler { id: entryHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: library.win.openDetails(entry.app) }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: library.design.space4
                    anchors.rightMargin: library.design.space4
                    spacing: library.design.space4
                    AppIcon { win: library.win; app: entry.app; size: library.win.fs(48); showKind: true }
                    ColumnLayout {
                        id: entryWords
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: library.win.localName(entry.app)
                            color: library.win.txt
                            font.family: library.win.uiFont
                            font.pixelSize: library.win.typePx(15)
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: {
                                var parts = [entry.app.kind === "native"
                                    ? entry.app.management === "os"
                                      ? library.win.local("جزء من MoOS · يتحدّث مع النظام", "Part of MoOS · updated with the system")
                                      : library.win.local("مثبّت خارج المتجر · تُدار ملفاته من مصدره", "Installed outside the Store · managed at its source")
                                    : library.win.kindLabel(library.win.appKind(entry.app))]
                                var version = entry.app.installed_version || entry.app.version || ""
                                if (version !== "" && entry.updateTarget !== "" && entry.updateTarget !== version)
                                    parts.push(library.win.ltr(version + "  →  " + entry.updateTarget))
                                else if (version !== "")
                                    parts.push(library.win.ltr(version))
                                else if (entry.pending !== null)
                                    parts.push(library.win.local("تحديث متاح", "Update available"))
                                var fact = library.win.factOf(entry.app)
                                if (fact && fact.installed > 0) parts.push(library.win.sizeText(fact.installed))
                                if (library.win.systemManagedOnly(entry.app)) parts.push(library.win.local("لكل المستخدمين", "For everyone"))
                                return parts.join("  ·  ")
                            }
                            color: library.win.txt2
                            font.family: library.win.uiFont
                            font.pixelSize: library.win.typePx(12)
                            elide: Text.ElideRight
                        }
                        // An installed app its developer has stopped updating: said where the owner
                        // looks after what they have.
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            visible: !!entry.app.eol
                            text: library.win.compatReasonText("eol")
                            color: library.win.warningInk
                            font.family: library.win.uiFont
                            font.pixelSize: library.win.typePx(12)
                            elide: Text.ElideRight
                        }
                    }
                    ProgressButton {
                        win: library.win
                        app: entry.app
                        tabStop: false
                    }
                    CircleButton {
                        win: library.win
                        visible: library.win.canChangePermissions(entry.app)
                        glyph: "lock"
                        accessibleName: library.win.local("أذونات ", "Permissions of ") + library.win.localName(entry.app)
                        onActivated: library.win.openPermissions(entry.app)
                    }
                    CircleButton {
                        win: library.win
                        visible: library.win.canRemove(entry.app)
                        enabled: !library.win.jobIsActive()
                        glyph: "trash"
                        accessibleName: library.win.local("إزالة ", "Remove ") + library.win.localName(entry.app)
                        onActivated: library.win.openRemove(entry.app)
                    }
                }
            }
        }
    }

    // Nothing installed yet: said, with the way to Discover.
    ColumnLayout {
        anchors.centerIn: parent
        visible: library.win.libraryApps.length === 0
        spacing: library.design.space2
        Glyph {
            win: library.win
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: library.win.fs(44)
            Layout.preferredHeight: library.win.fs(44)
            name: "boxes"
            tint: library.win.txt2
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: library.win.installedApps.length === 0
                ? library.win.local("لا تطبيقات مثبّتة بعد", "No apps installed yet")
                : library.win.local("لا تطبيقات من هذا النوع", "No apps of this kind")
            color: library.win.txt
            font.family: library.win.uiFont
            font.pixelSize: library.win.typePx(20)
            font.weight: Font.Bold
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: library.win.local("ما تثبّته من المتجر أو تضيفه من ملف يظهر هنا.",
                                    "What you install from the Store, or add from a file, appears here.")
            color: library.win.txt2
            font.family: library.win.uiFont
            font.pixelSize: library.win.typePx(13)
        }
        ActionButton {
            win: library.win
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: library.design.space2
            pill: true
            primary: true
            label: library.win.local("اكتشف التطبيقات", "Discover apps")
            glyphName: "compass"
            triggered: function() { library.win.navigate("discover") }
        }
    }
}

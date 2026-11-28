pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// The header owns the query. The window ranks matching editions, and the platform
// controls narrow them before the Store chooses one row per product.
Item {
    id: searchPage
    required property var win
    readonly property var design: win.design
    readonly property real padding: searchPage.width > win.fs(1000) ? design.space6 : design.space5
    readonly property bool typed: win.query.trim() !== ""
    readonly property var suggestions: win.rtl
        ? ["متصفح", "واتساب", "تعديل الصور", "مكتب", "ألعاب", "القرآن", "برمجة", "ذكاء اصطناعي"]
        : ["browser", "WhatsApp", "photo editor", "office", "games", "music", "code", "AI"]

    readonly property var matchedFamilies: {
        var families = {}
        for (var app of win.searchMatches) families[app.family] = true
        return families
    }
    readonly property bool otherPlatforms: win.searchKind !== "all" && win.searchMatches.length > 0 && win.searchResults.length === 0

    anchors.fill: parent
    visible: win.page === "search"
    transform: pageEnter.shift
    PageEnter { id: pageEnter; win: searchPage.win; target: searchPage }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: searchPage.padding
        anchors.rightMargin: searchPage.padding
        anchors.topMargin: searchPage.design.space2
        spacing: searchPage.design.space4

        Flow {
            id: platformFilters
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            visible: searchPage.typed && (searchPage.win.searchMatches.length > 0 || searchPage.win.searchKind !== "all")
            spacing: searchPage.design.space2
            Repeater {
                model: [{id: "all", ar: "الكل", en: "All", glyph: ""}].concat(searchPage.win.kindDefs)
                delegate: KindChip {
                    id: platform
                    required property var modelData
                    objectName: "searchKind-" + modelData.id
                    win: searchPage.win
                    visible: modelData.id === "all" || searchPage.matchedFamilies[modelData.id] === true
                             || win.searchKind === modelData.id
                    height: win.fs(44)
                    label: win.localName(modelData)
                    glyph: modelData.glyph
                    checked: win.searchKind === modelData.id
                    onActivated: win.searchKind = modelData.id
                }
            }
        }

        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            visible: searchPage.typed && searchPage.win.searchResults.length > 0
            text: searchPage.win.rtl
                ? searchPage.win.appsCountText(searchPage.win.searchResults.length) + " لـ «" + searchPage.win.query.trim() + "»"
                : searchPage.win.appsCountText(searchPage.win.searchResults.length) + " for “" + searchPage.win.query.trim() + "”"
            color: searchPage.win.txt2
            font.family: searchPage.win.uiFont
            font.pixelSize: searchPage.win.typePx(14)
            elide: Text.ElideRight
        }

        ListView {
            id: searchList
            objectName: "searchList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: searchPage.typed && count > 0
            clip: true
            spacing: searchPage.design.space2
            model: searchPage.visible ? searchPage.win.searchResults : []
            bottomMargin: searchPage.win.footClearance
            boundsBehavior: Flickable.StopAtBounds
            keyNavigationEnabled: true
            reuseItems: true
            cacheBuffer: searchPage.win.fs(84) * 6
            activeFocusOnTab: count > 0
            Accessible.role: Accessible.List
            Accessible.name: searchPage.win.local("نتائج البحث", "Search results")
            Keys.onReturnPressed: if (currentIndex >= 0) searchPage.win.openDetails(searchPage.win.searchResults[currentIndex])
            Keys.onEnterPressed: if (currentIndex >= 0) searchPage.win.openDetails(searchPage.win.searchResults[currentIndex])
            Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(searchList, event)
            onActiveFocusChanged: if (activeFocus && count > 0 && currentIndex < 0) currentIndex = 0
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Item {
                id: result
                required property var modelData
                required property int index
                width: searchList.width
                height: searchPage.win.fs(84)
                AppCard {
                    win: searchPage.win
                    anchors.fill: parent
                    app: result.modelData
                    variant: "row"
                    compositeFocus: true
                    compositeCurrent: searchList.activeFocus && result.index === searchList.currentIndex
                }
            }
        }

        // Nothing typed yet, or nothing found: words that find something. Its rows cap their own
        // width, which caps the column's, so the column is centred rather than left at the start.
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.alignment: Qt.AlignHCenter
            visible: !searchPage.typed || searchPage.win.searchResults.length === 0
            spacing: searchPage.design.space3
            Item { Layout.preferredHeight: searchPage.design.space6 }
            Glyph {
                win: searchPage.win
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: searchPage.win.fs(48)
                Layout.preferredHeight: searchPage.win.fs(48)
                name: "search"
                tint: searchPage.win.txt2
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: searchPage.width - searchPage.padding * 2
                text: searchPage.otherPlatforms
                    ? searchPage.win.local("لا نتائج على المنصة المختارة", "No results on this platform")
                    : searchPage.typed
                    ? (searchPage.win.rtl ? "لا شيء باسم «" + searchPage.win.query.trim() + "» هنا"
                                          : "Nothing called “" + searchPage.win.query.trim() + "” here")
                    : searchPage.win.local("ابحث في كل تطبيقات المتجر", "Search every app in the Store")
                color: searchPage.win.txt
                font.family: searchPage.win.uiFont
                font.pixelSize: searchPage.win.typePx(24)
                font.weight: Font.Bold
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
            ActionButton {
                win: searchPage.win
                objectName: "searchAllPlatforms"
                Layout.alignment: Qt.AlignHCenter
                visible: searchPage.otherPlatforms
                label: win.local("اعرض النتائج من كل المنصات", "Show results from all platforms")
                glyphName: "search"
                triggered: function() { win.searchKind = "all" }
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                visible: !searchPage.otherPlatforms
                Layout.maximumWidth: Math.min(searchPage.width - searchPage.padding * 2, searchPage.win.fs(560))
                text: searchPage.typed
                    ? searchPage.win.local("جرّب كلمة أعمّ، أو اسم التطبيق بالإنجليزية، أو واحدة من هذه:",
                                           "Try a broader word, the app's name in another language, or one of these:")
                    : searchPage.win.local("بالعربية أو بالإنجليزية: اسم تطبيق، أو ما تريد أن تفعله.",
                                           "In English or Arabic: an app's name, or what you want to do.")
                color: searchPage.win.txt2
                font.family: searchPage.win.uiFont
                font.pixelSize: searchPage.win.typePx(14)
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
            Flow {
                Layout.alignment: Qt.AlignHCenter
                visible: !searchPage.otherPlatforms
                Layout.maximumWidth: searchPage.win.fs(640)
                Layout.preferredWidth: Math.min(searchPage.width - searchPage.padding * 2, searchPage.win.fs(640))
                spacing: searchPage.design.space2
                Repeater {
                    model: searchPage.suggestions
                    delegate: KindChip {
                        id: suggestion
                        required property var modelData
                        win: searchPage.win
                        label: suggestion.modelData
                        glyph: "search"
                        onActivated: searchPage.win.searchFor(suggestion.modelData)
                    }
                }
            }
            Item { Layout.fillHeight: true }
        }
    }
}

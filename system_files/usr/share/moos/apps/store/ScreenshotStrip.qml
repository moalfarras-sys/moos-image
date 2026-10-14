pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — an app's screenshots in a row. Each frame is sized from the picture's own width and
// height BEFORE it loads, so nothing jumps; the picture is shown whole (never cropped) and decoded
// at the size it is shown times the screen's scale; its caption sits under it. ←/→ move between
// them, Enter or a click opens one full-screen. Pictures from the internet load only while the
// person allows them, and the row says so when they do not.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
ColumnLayout {
    id: strip
    required property var win
    readonly property var design: win.design
    property var shots: []
    property bool loading: false
    readonly property real frameHeight: Math.min(win.fs(320), Math.max(win.fs(200), strip.width * 0.3))
    readonly property bool needsInternet: {
        for (var i = 0; i < strip.shots.length; ++i)
            if (("" + (strip.shots[i].thumb || strip.shots[i].full || "")).indexOf("https://") === 0) return true
        return false
    }
    readonly property bool blocked: strip.needsInternet && !win.remotePictures

    spacing: design.space3

    SectionHeader {
        win: strip.win
        Layout.fillWidth: true
        title: strip.win.local("لقطات الشاشة", "Screenshots")
        subtitle: strip.shots.length > 0 ? strip.win.local("تُعرض كاملة كما نشرها المطوّر", "Shown whole, as the developer published them") : ""
        glyph: "image"
        showArrows: !strip.blocked && shotList.contentWidth > shotList.width + 1
        canPrevious: strip.win.rtl ? !shotList.atXEnd : !shotList.atXBeginning
        canNext: strip.win.rtl ? !shotList.atXBeginning : !shotList.atXEnd
        onPrevious: shotList.currentIndex = Math.max(0, shotList.currentIndex - 1)
        onNext: shotList.currentIndex = Math.min(shotList.count - 1, shotList.currentIndex + 1)
    }

    // Pictures are off: said, with the switch at hand.
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: strip.win.fs(96)
        visible: strip.blocked
        radius: strip.design.radiusCard + 2
        color: strip.win.cardColor
        border.width: 1
        border.color: strip.win.cardBorder
        RowLayout {
            anchors.fill: parent
            anchors.margins: strip.design.space5
            spacing: strip.design.space4
            Glyph {
                win: strip.win
                name: "image"
                tint: strip.win.txt2
                Layout.preferredWidth: strip.win.fs(28)
                Layout.preferredHeight: strip.win.fs(28)
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    text: strip.win.local("صور التطبيقات من الإنترنت متوقفة", "App pictures from the internet are off")
                    color: strip.win.txt
                    font.family: strip.win.uiFont
                    font.pixelSize: strip.win.typePx(15)
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    text: strip.win.local("لقطات هذا التطبيق على موقع ناشره. لن يحمّلها المتجر حتى تسمح بذلك.",
                                          "This app's screenshots are on its publisher's site. The Store does not fetch them until you allow it.")
                    color: strip.win.txt2
                    font.family: strip.win.uiFont
                    font.pixelSize: strip.win.typePx(13)
                    wrapMode: Text.WordWrap
                }
            }
            ActionButton {
                win: strip.win
                pill: true
                label: strip.win.local("أظهر الصور", "Show pictures")
                glyphName: "image"
                triggered: function() { strip.win.setRemotePictures(true) }
            }
        }
    }

    ListView {
        id: shotList
        Layout.fillWidth: true
        Layout.preferredHeight: strip.frameHeight + strip.win.fs(44)
        visible: !strip.blocked
        orientation: ListView.Horizontal
        spacing: strip.design.space4
        clip: true
        model: strip.loading && strip.shots.length === 0 ? 3 : strip.shots
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        highlightFollowsCurrentItem: false
        activeFocusOnTab: strip.shots.length > 0
        Accessible.role: Accessible.List
        Accessible.name: strip.win.local("لقطات الشاشة", "Screenshots")
        Keys.onReturnPressed: strip.win.openScreenshots(strip.shots, shotList.currentIndex)
        Keys.onEnterPressed: strip.win.openScreenshots(strip.shots, shotList.currentIndex)
        onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
        delegate: Item {
            id: shot
            required property int index
            readonly property var entry: strip.shots.length > shot.index ? strip.shots[shot.index] : null
            readonly property real aspect: shot.entry && shot.entry.width > 0 && shot.entry.height > 0
                                           ? shot.entry.width / shot.entry.height : 16 / 9
            readonly property bool sharp: strip.frameHeight * Math.max(1, Screen.devicePixelRatio) > 440
            readonly property string address: shot.entry
                ? strip.win.pictureSource(shot.sharp ? (shot.entry.full || shot.entry.thumb) : (shot.entry.thumb || shot.entry.full)) : ""
            width: Math.min(strip.frameHeight * shot.aspect, shotList.width * 0.9)
            height: shotList.height

            Rectangle {
                id: frame
                width: parent.width
                height: strip.frameHeight
                radius: strip.design.radiusCard
                color: strip.win.tint(strip.win.txt, strip.win.lightScheme ? 0.06 : 0.07)
                border.width: 1
                border.color: shotList.activeFocus && shotList.currentIndex === shot.index
                              ? strip.win.accent : strip.win.cardBorder
                clip: true
                Glyph {
                    win: strip.win
                    anchors.centerIn: parent
                    width: strip.win.fs(28)
                    height: width
                    name: "image"
                    tint: strip.win.txt2
                    visible: picture.status !== Image.Ready
                    opacity: 0.6
                }
                Image {
                    id: picture
                    anchors.fill: parent
                    anchors.margins: 1
                    source: shot.address
                    asynchronous: true
                    cache: true
                    smooth: true
                    mipmap: true
                    fillMode: Image.PreserveAspectFit
                    sourceSize.height: Math.ceil(strip.frameHeight * Math.max(1, Screen.devicePixelRatio))
                    opacity: status === Image.Ready ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: strip.win.motionEnabled ? strip.design.motionGeometry : 0 } }
                }
                HoverHandler { cursorShape: shot.entry ? Qt.PointingHandCursor : Qt.ArrowCursor }
                TapHandler {
                    enabled: shot.entry !== null
                    onTapped: { shotList.currentIndex = shot.index; strip.win.openScreenshots(strip.shots, shot.index) }
                }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                anchors.top: frame.bottom
                anchors.topMargin: strip.design.space2
                width: parent.width
                text: shot.entry && shot.entry.caption ? shot.entry.caption : ""
                color: strip.win.txt2
                font.family: strip.win.uiFont
                font.pixelSize: strip.win.typePx(12)
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }
    }
}

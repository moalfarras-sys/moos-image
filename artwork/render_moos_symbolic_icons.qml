// Visual-review harness for the MoOS symbolic action-icon family.
//
// Run on a real Wayland session against an icon theme containing the overlay
// built by build_files/build.sh. Qt's offscreen software path loads the QML but
// does not paint KIconLoader results, so it is a syntax smoke, not visual proof:
//   QT_QPA_PLATFORM=wayland qml-qt6 artwork/render_moos_symbolic_icons.qml
//
// The capture is written to /var/tmp/moos-symbolic-kiconloader.png. This uses
// Kirigami.Icon — the same KIconLoader path as the shipped apps.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import org.kde.kirigami as Kirigami
import "moos_symbolic_manifest.js" as IconManifest

ApplicationWindow {
    id: window
    width: 1120
    height: 410
    visible: true
    color: Kirigami.Theme.backgroundColor
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.View

    // Generated from the same geometry inventory as the SVGs. The visual
    // harness therefore cannot silently omit a newly added semantic symbol.
    readonly property var symbols: IconManifest.iconNames

    Item {
        id: preview
        anchors.fill: parent

        Rectangle {
            id: paletteRow
            anchors.fill: parent
            color: Kirigami.Theme.backgroundColor

            Text {
                x: 24
                y: 8
                text: "Active desktop palette · Tidal Cut · KIconLoader"
                color: Kirigami.Theme.textColor
                font.family: window.font.family
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }

            Grid {
                x: 24
                y: 36
                columns: 13
                columnSpacing: 12
                rowSpacing: 5

                Repeater {
                    model: window.symbols

                    delegate: Rectangle {
                        id: iconTile
                        required property string modelData
                        width: 72
                        height: 53
                        radius: 12
                        color: Kirigami.Theme.alternateBackgroundColor
                        border.width: 1
                        border.color: Qt.rgba(
                            Kirigami.Theme.textColor.r,
                            Kirigami.Theme.textColor.g,
                            Kirigami.Theme.textColor.b,
                            0.22)

                        Kirigami.Icon {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: 4
                            width: 26
                            height: 26
                            source: iconTile.modelData
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 4
                            width: parent.width - 8
                            horizontalAlignment: Text.AlignHCenter
                            text: iconTile.modelData
                                .replace("moos-", "")
                                .replace("-symbolic", "")
                            color: Kirigami.Theme.disabledTextColor
                            font.family: window.font.family
                            font.pixelSize: 6
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }

    Timer {
        interval: 1200
        running: true
        repeat: false
        onTriggered: preview.grabToImage(function(result) {
            if (!result.saveToFile("/var/tmp/moos-symbolic-kiconloader.png"))
                console.error("could not save symbolic-icon preview")
            Qt.quit()
        })
    }
}

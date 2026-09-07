import QtQuick
import QtQuick.Controls
ApplicationWindow {
    visible: true; width: 540; height: 960
    Loader { anchors.fill: parent; source: "../../system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents/explorer/WidgetExplorer.qml" }
}

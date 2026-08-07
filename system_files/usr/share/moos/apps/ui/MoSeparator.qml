import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    property bool vertical: false
    property color separatorColor: Qt.alpha(Kirigami.Theme.textColor, 0.16)

    color: separatorColor
    width: vertical ? tokens.borderHairline : parent ? parent.width : 0
    height: vertical ? parent ? parent.height : 0 : tokens.borderHairline

    Tokens { id: tokens }
}

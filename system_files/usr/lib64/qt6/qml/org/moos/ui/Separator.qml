import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    property bool vertical: false
    property color separatorColor: Qt.alpha(Kirigami.Theme.textColor,
                                             Tokens.surfaceRestingOpacity)

    color: separatorColor
    width: vertical ? Tokens.borderHairline : parent ? parent.width : 0
    height: vertical ? parent ? parent.height : 0 : Tokens.borderHairline
    Accessible.ignored: true
}

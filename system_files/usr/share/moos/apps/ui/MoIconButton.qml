import QtQuick

Button {
    property string symbol: ""
    property string accessibleLabel: ""

    iconName: symbol
    compact: true
    Accessible.name: accessibleLabel.length > 0 ? accessibleLabel : symbol
    implicitWidth: tokens.targetControl
    implicitHeight: tokens.targetControl

    Tokens { id: tokens }
}

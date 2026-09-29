import QtQuick

// Text with Mira's type defaults.
Text {
    color: Theme.ink
    font.family: Theme.font
    font.pixelSize: Theme.body
    wrapMode: Text.Wrap
    textFormat: Text.PlainText
    elide: Text.ElideNone
    linkColor: Theme.cyan
}

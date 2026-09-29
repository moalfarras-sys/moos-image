import QtQuick
import QtQuick.Shapes
import "icons.js" as Icons

// A crisp, recolourable line icon from Mira's own 24×24 set, or a `path` of its own on that grid.
Item {
    id: root
    property string name: "sparkle"
    property string path: ""                 // a drawing of its own (wins over `name`)
    property color color: Theme.ink
    property real size: 20
    property real weight: 1.8
    property bool filled: false
    readonly property string drawing: path || Icons.paths[name] || Icons.paths["sparkle"]
    // Qt Quick's software scene graph (ARM, machines without a GPU) draws a Shape even outside a
    // clipping ancestor: an icon scrolled out of a page or a card list showed over the dock. There
    // the same drawing is an SVG image, which that renderer clips like any other image.
    readonly property bool softwareScene: GraphicsInfo.api === GraphicsInfo.Software
    implicitWidth: size
    implicitHeight: size

    Shape {
        visible: !root.softwareScene
        width: 24; height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.color
            strokeWidth: root.weight
            fillColor: root.filled ? root.color : "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.softwareScene ? "" : root.drawing }
        }
    }
    Image {
        visible: root.softwareScene
        width: root.size; height: root.size
        source: root.softwareScene ? Icons.svgUrl(root.drawing, root.color, root.weight, root.filled) : ""
        sourceSize: Qt.size(Math.max(1, Math.ceil(root.size)), Math.max(1, Math.ceil(root.size)))
        smooth: true
    }
}

import QtQuick
import QtQuick.Shapes
import "icons.js" as Icons

// A crisp, recolourable line icon from Mira's own 24×24 set.
Item {
    id: root
    property string name: "sparkle"
    property color color: Theme.ink
    property real size: 20
    property real weight: 1.8
    property bool filled: false
    implicitWidth: size
    implicitHeight: size

    Shape {
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
            PathSvg { path: Icons.paths[root.name] || Icons.paths["sparkle"] }
        }
    }
}

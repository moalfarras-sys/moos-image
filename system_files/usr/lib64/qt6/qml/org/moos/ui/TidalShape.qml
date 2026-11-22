/*
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity
    SPDX-License-Identifier: GPL-2.0-or-later
*/
import QtQuick
import QtQuick.Shapes

// The Tidal Cut at surface size: one silhouette, geometric and curved at once.
//
// MoOS's window actions already wear it (artwork/generate_moos_aurorae.py):
// three corners rounded, ONE corner cut at 45°, with the light running along
// the top edge and down the cut. Meyar's letters move the same way — straight
// strokes that end in a curve — so the session cards and docks and the
// keyboard take this shape too, at their own size. The cut sits on the
// TOP-TRAILING corner: top right when reading left to right, top left in
// Arabic, mirroring with the layout like the session glyphs do.
//
// Pure geometry, no state: it never animates and never owns input. One fill
// (a colour, or a colour lit from above when `sheen` > 0), one hairline rim
// inset by half its width so it stays inside the item, and one specular line
// along the straight top edge and the cut. Works on the software renderer.
Shape {
    id: tidal

    property real radius: 24
    // The cut's leg on both edges it meets; the window tiles use their radius.
    property real cut: radius
    property bool mirrored: tidal.LayoutMirroring.enabled
    property color fillColor: "transparent"
    // How much lighter the top edge of the fill is (0 = flat).
    property real sheen: 0
    property color sheenColor: "white"
    property color strokeColor: "transparent"
    property real strokeWidth: 0
    property color specularColor: "transparent"
    property real specularWidth: 1

    readonly property real r: Math.max(0, Math.min(radius, width / 2, height / 2))
    readonly property real c: Math.max(0, Math.min(cut, width / 2, height / 2))

    preferredRendererType: Shape.CurveRenderer

    // The closed outline, inset by `i` on every side.
    function outline(i) {
        const x = i, y = i, w = tidal.width - i, h = tidal.height - i;
        const r = Math.max(0, tidal.r - i), c = Math.max(0, tidal.c - i);
        const arc = (ex, ey) => ` A ${r} ${r} 0 0 1 ${ex} ${ey}`;
        if (!tidal.mirrored) {
            return `M ${x + r} ${y} H ${w - c} L ${w} ${y + c} V ${h - r}` + arc(w - r, h)
                + ` H ${x + r}` + arc(x, h - r) + ` V ${y + r}` + arc(x + r, y) + " Z";
        }
        return `M ${x + c} ${y} H ${w - r}` + arc(w, y + r) + ` V ${h - r}` + arc(w - r, h)
            + ` H ${x + r}` + arc(x, h - r) + ` V ${y + c} L ${x + c} ${y} Z`;
    }
    // The lit edge: the straight top, then down the cut.
    function lightEdge(i) {
        const x = i, y = i, w = tidal.width - i;
        const r = Math.max(0, tidal.r - i), c = Math.max(0, tidal.c - i);
        return tidal.mirrored ? `M ${w - r} ${y} H ${x + c} L ${x} ${y + c}`
                              : `M ${x + r} ${y} H ${w - c} L ${w} ${y + c}`;
    }

    ShapePath {
        strokeColor: "transparent"
        strokeWidth: -1
        fillColor: tidal.sheen > 0 ? "transparent" : tidal.fillColor
        fillGradient: tidal.sheen > 0 ? lit : null
        PathSvg { path: tidal.width > 0 && tidal.height > 0 ? tidal.outline(0) : "" }
    }
    LinearGradient {
        id: lit
        x1: 0; y1: 0
        x2: 0; y2: tidal.height
        GradientStop { position: 0.0; color: Qt.tint(tidal.fillColor, Qt.alpha(tidal.sheenColor, tidal.sheen)) }
        GradientStop { position: 0.5; color: tidal.fillColor }
        GradientStop { position: 1.0; color: tidal.fillColor }
    }
    ShapePath {
        strokeColor: tidal.strokeWidth > 0 ? tidal.strokeColor : "transparent"
        strokeWidth: tidal.strokeWidth > 0 ? tidal.strokeWidth : -1
        fillColor: "transparent"
        joinStyle: ShapePath.RoundJoin
        PathSvg { path: tidal.strokeWidth > 0 && tidal.width > 0 ? tidal.outline(tidal.strokeWidth / 2) : "" }
    }
    ShapePath {
        strokeColor: tidal.specularColor
        strokeWidth: tidal.specularColor.a > 0 ? tidal.specularWidth : -1
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        PathSvg { path: tidal.specularColor.a > 0 && tidal.width > 0
                        ? tidal.lightEdge(tidal.strokeWidth + tidal.specularWidth / 2) : "" }
    }
}

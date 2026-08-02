.pragma library

// Shared keyboard/viewport contract for first-party MoOS QML applications.
// A focused control must never remain clipped outside one of its Flickable ancestors, and
// Page Up/Down must move by a predictable viewport-sized step without overshooting its bounds.

function revealFocus(item) {
    if (!item) return
    var pad = 12
    for (var flick = item.parent; flick; flick = flick.parent) {
        // Flickable and its subclasses expose this exact seam. Checking properties keeps the
        // helper usable with GridView/ListView without importing or guessing a concrete type.
        if (flick.contentItem === undefined || flick.contentY === undefined
                || flick.flicking === undefined) continue
        var pos = item.mapToItem(flick.contentItem, 0, 0)
        if (flick.contentHeight > flick.height) {
            var yMin = flick.originY || 0
            var yMax = yMin + flick.contentHeight - flick.height
            if (pos.y < flick.contentY + pad)
                flick.contentY = Math.max(yMin, pos.y - pad)
            else if (pos.y + item.height > flick.contentY + flick.height - pad)
                flick.contentY = Math.min(yMax, pos.y + item.height + pad - flick.height)
        }
        if (flick.contentWidth > flick.width) {
            var xMin = flick.originX || 0
            var xMax = xMin + flick.contentWidth - flick.width
            if (pos.x < flick.contentX + pad)
                flick.contentX = Math.max(xMin, pos.x - pad)
            else if (pos.x + item.width > flick.contentX + flick.width - pad)
                flick.contentX = Math.min(xMax, pos.x + item.width + pad - flick.width)
        }
    }
}

function pageScrollKeys(flick, event) {
    if (event.key !== Qt.Key_PageDown && event.key !== Qt.Key_PageUp) {
        // Keys.onPressed sits before an item's own key handler. Explicitly pass arrows and
        // activation onward so GridView/ListView navigation is never swallowed by this helper.
        event.accepted = false
        return
    }
    var yMin = flick.originY || 0
    var yMax = Math.max(yMin, yMin + flick.contentHeight - flick.height)
    var step = flick.height * 0.9 * (event.key === Qt.Key_PageDown ? 1 : -1)
    flick.contentY = Math.max(yMin, Math.min(yMax, flick.contentY + step))
    event.accepted = true
}

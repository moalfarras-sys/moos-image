.pragma library

// Shared keyboard/viewport contract for first-party MoOS QML applications.
function revealFocus(item, requestedPadding) {
    if (!item) return
    var pad = requestedPadding === undefined ? 12 : requestedPadding
    for (var flick = item.parent; flick; flick = flick.parent) {
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
        event.accepted = false
        return
    }
    var yMin = flick.originY || 0
    var yMax = Math.max(yMin, yMin + flick.contentHeight - flick.height)
    var step = flick.height * 0.9 * (event.key === Qt.Key_PageDown ? 1 : -1)
    flick.contentY = Math.max(yMin, Math.min(yMax, flick.contentY + step))
    event.accepted = true
}

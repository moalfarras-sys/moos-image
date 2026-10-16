#!/usr/bin/env python3
"""Native Qt input probe; invoked only with the page walker's private environment.

No Store bridge is registered. Touchscreen, wheel, mouse and keyboard events go
only to this offscreen QQuickWindow, never to the desktop or Remote input socket.
"""
import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QInputDevice, QPointingDevice, QWheelEvent
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest


def argument(name, default=""):
    prefix = "--" + name + "="
    return next((arg[len(prefix):] for arg in sys.argv if arg.startswith(prefix)), default)


input_clock_start = time.monotonic()
app = QGuiApplication(sys.argv)
font = app.font()
font.setPointSize(int(argument("font", "10")))
app.setFont(font)
engine = QQmlApplicationEngine()
# Match the real C++ host's independent KDE platform selection. Its native
# executable is exercised separately: this probe supplies Qt's input APIs only.
engine.setProperty("_kirigamiTheme", "org.kde.desktop")
engine.load(QUrl(argument("src")))
assert engine.rootObjects(), "Store window did not load"
win = engine.rootObjects()[0]
win.setWidth(int(argument("w", "1280")))
win.setHeight(int(argument("h", "800")))
win.requestActivate()
# The offscreen backend may defer its first polish until the first grab. Start
# that frame before waiting for layout/arrival motion, otherwise large-font
# probes inject a wheel into the rail's still-moving initial geometry.
assert QTest.qWaitForWindowExposed(win, 5000), "Store window was not exposed"
win.grabWindow()
QTest.qWait(800)
checks = []
output = Path(argument("fixtures")).parent
assert win.grabWindow().save(str(output / "touch-discover.png")), "Discover render failed"


def evaluate(source, item=win):
    expression = QQmlExpression(qmlContext(item), item, source)
    value = expression.evaluate()[0]
    assert not expression.hasError(), expression.error().toString()
    return value


def descendants(item):
    result = []
    for child in item.childItems():
        result.append(child)
        result.extend(descendants(child))
    return result


def named(name):
    item = win.findChild(QQuickItem, name)
    if item is None:
        item = next((child for child in descendants(win.contentItem()) if child.objectName() == name), None)
    assert item is not None, "missing " + name
    return item


def check(label, condition, **measurements):
    checks.append(dict(label=label, passed=bool(condition), **measurements))
    print("STORE INPUT " + json.dumps(checks[-1], ensure_ascii=False), flush=True)
    assert condition, label + ": " + repr(measurements)


def cancel(flick):
    evaluate("cancelFlick()", flick)
    QTest.qWait(30)


def bring(flick, target):
    cancel(flick)
    relative = target.mapToItem(flick, QPointF(target.width()/2, target.height()/2))
    value = flick.property("contentY") + relative.y() - flick.height()*0.60
    maximum = max(0, flick.property("contentHeight")-flick.height())
    flick.setProperty("contentY", max(0, min(maximum, value)))
    QTest.qWait(80)
    point = target.mapToScene(QPointF(target.width()/2, target.height()/2))
    clipped = target
    within_clips = True
    while clipped is not None:
        if clipped.clip() and not clipped.contains(clipped.mapFromScene(point)):
            within_clips = False
        clipped = clipped.parentItem()
    check("gesture begins inside the visible pane", 0 < point.x() < win.width()
          and 0 < point.y() < win.height() and within_clips, x=point.x(), y=point.y())
    return point


touch = QTest.createTouchDevice()
touchpad = QTest.createTouchDevice(QInputDevice.DeviceType.TouchPad,
                                  QInputDevice.Capability.Position | QInputDevice.Capability.PixelScroll)


def swipe(point, dx=0, dy=-140):
    sequence = QTest.touchEvent(win, touch)
    sequence.press(0, point.toPoint(), win).commit()
    for step in range(1, 11):
        QTest.qWait(20)
        sequence.move(0, QPoint(round(point.x()+dx*step/10),
                               round(point.y()+dy*step/10)), win).commit()
    sequence.release(0, QPoint(round(point.x()+dx), round(point.y()+dy)), win).commit()
    QTest.qWait(250)


def wheel(point, angle=QPoint(0, -120), pixel=QPoint(), modifiers=Qt.NoModifier):
    if not pixel.isNull():
        # QTest.wheelEvent uses a Mouse device; real pixel scrolling identifies
        # itself as a TouchPad and carries begin/update/end phases.
        updates = []
        previous = QPoint()
        for step in range(1, 6):
            cumulative = QPoint(round(pixel.x()*step/5), round(pixel.y()*step/5))
            updates.append((Qt.ScrollUpdate, cumulative-previous))
            previous = cumulative
        for phase, delta in [(Qt.ScrollBegin, QPoint()), *updates, (Qt.ScrollEnd, QPoint())]:
            # Native pixel updates also carry the wheel-axis indication. Qt
            # classifies a following zero-angle ScrollUpdate as a compatibility
            # duplicate and skips it before delivering it to any QML item.
            axes = angle
            if phase == Qt.ScrollUpdate and angle.isNull():
                axes = QPoint(0 if delta.x() == 0 else (1 if delta.x() > 0 else -1),
                              0 if delta.y() == 0 else (1 if delta.y() > 0 else -1))
            event = QWheelEvent(point, win.mapToGlobal(point.toPoint()), delta, axes,
                                Qt.NoButton, modifiers, phase, False,
                                Qt.MouseEventSynthesizedBySystem, touchpad)
            event.setTimestamp(int((time.monotonic()-input_clock_start)*1000))
            QCoreApplication.sendEvent(win, event)
            QTest.qWait(25)
    else:
        # QTest.wheelEvent forwards native pixels without converting on the
        # offscreen platform (observed 400,540 -> 160,216 at 2.5x). Deliver a
        # real mouse QWheelEvent in window coordinates, as Qt receives it.
        event = QWheelEvent(point, win.mapToGlobal(point.toPoint()), pixel, angle,
                            Qt.NoButton, modifiers, Qt.NoScrollPhase, False,
                            Qt.MouseEventNotSynthesized, QPointingDevice.primaryPointingDevice())
        event.setTimestamp(int((time.monotonic()-input_clock_start)*1000))
        QCoreApplication.sendEvent(win, event)
    QTest.qWait(180)


if argument("reduced-motion") == "1":
    check("input remains available with Reduced Motion", not win.property("motionEnabled"),
          duration=evaluate("Kirigami.Units.longDuration"), app_name=app.applicationName())

# A long real-fixture shelf exercises both axes even on a wide window. Its
# members remain existing catalogue rows, not invented apps or transactions.
evaluate("var c=collections.slice(); c[0]=Object.assign({},c[0],"
         "{apps:browseOrder.slice(0,12)}); collections=c")
QTest.qWait(150)
flick = named("discoverFlick")
shelves = [item for item in descendants(flick)
           if "QQuickListView" in item.metaObject().className()
           and evaluate("Number(orientation)", item) == 1 and item.isVisible()]
assert shelves, "no nested shelf"
shelf = shelves[0]
point = bring(flick, shelf)
before_y, before_x = flick.property("contentY"), shelf.property("contentX")
wheel(point)
check("vertical angle wheel crosses the horizontal shelf",
      flick.property("contentY") > before_y+20 and abs(shelf.property("contentX")-before_x) < 1,
      parent_delta=flick.property("contentY")-before_y,
      shelf_delta=shelf.property("contentX")-before_x)

point = bring(flick, shelf)
before_y, before_x = flick.property("contentY"), shelf.property("contentX")
wheel(point, QPoint(), QPoint(0, -55))
check("vertical pixel wheel crosses the horizontal shelf",
      flick.property("contentY") > before_y+20 and abs(shelf.property("contentX")-before_x) < 1,
      parent_delta=flick.property("contentY")-before_y,
      shelf_delta=shelf.property("contentX")-before_x)

point = bring(flick, shelf)
before_y = flick.property("contentY")
swipe(point)
check("touchscreen vertical drag crosses the horizontal shelf",
      flick.property("contentY") > before_y+25 and win.property("page") == "discover",
      parent_delta=flick.property("contentY")-before_y)

point = bring(flick, shelf)
before_y, before_x = flick.property("contentY"), shelf.property("contentX")
direction = 140 if evaluate("rtl") else -140
swipe(point, dx=direction, dy=0)
check("touchscreen horizontal drag stays on the shelf",
      abs(shelf.property("contentX")-before_x) > 25 and abs(flick.property("contentY")-before_y) < 1,
      parent_delta=flick.property("contentY")-before_y,
      shelf_delta=shelf.property("contentX")-before_x, start_x=before_x, origin=shelf.property("originX"),
      content_width=shelf.property("contentWidth"), viewport_width=shelf.width(), moving=shelf.property("moving"))

cancel(shelf)
point = bring(flick, shelf)
before_y, before_x = flick.property("contentY"), shelf.property("contentX")
wheel(point, QPoint(-120 if not evaluate("rtl") else 120, -40))
check("diagonal angle wheel uses the horizontal axis once",
      20 < abs(shelf.property("contentX")-before_x) < 180 and abs(flick.property("contentY")-before_y) < 1,
      parent_delta=flick.property("contentY")-before_y,
      shelf_delta=shelf.property("contentX")-before_x, start_x=before_x, origin=shelf.property("originX"),
      content_width=shelf.property("contentWidth"), viewport_width=shelf.width(), moving=shelf.property("moving"))

cancel(shelf)
point = bring(flick, shelf)
before_y, before_x = flick.property("contentY"), shelf.property("contentX")
wheel(point, QPoint(), QPoint(55 if evaluate("rtl") else -55, -12))
check("diagonal pixel wheel keeps its native horizontal axis",
      20 < abs(shelf.property("contentX")-before_x) < 100 and abs(flick.property("contentY")-before_y) < 1,
      parent_delta=flick.property("contentY")-before_y,
      shelf_delta=shelf.property("contentX")-before_x)
cancel(shelf)
point = bring(flick, shelf)
before_y, before_x = flick.property("contentY"), shelf.property("contentX")
wheel(point, QPoint(0, 120 if evaluate("rtl") else -120), modifiers=Qt.ShiftModifier)
check("Shift wheel scrolls the shelf once without moving the page",
      119 < abs(shelf.property("contentX")-before_x) < 121 and abs(flick.property("contentY")-before_y) < 1,
      parent_delta=flick.property("contentY")-before_y,
      shelf_delta=shelf.property("contentX")-before_x)
cancel(shelf)
# Finger drags starting on the actual action pill must scroll, not open its
# review or the card's detail page. A real tap and click must still act.
action_index = evaluate("browseOrder.slice(0,12).findIndex(a=>primaryAction(a)==='get')")
assert action_index >= 0, "no actionable real fixture app"
evaluate("positionViewAtIndex("+str(action_index)+", ListView.Center)", shelf)
QTest.qWait(100)
action_id = evaluate("browseOrder["+str(action_index)+"].id")
buttons = [item for item in descendants(shelf)
           if item.objectName() == "app-action-"+action_id and item.isVisible()]
assert len(buttons) == 1, "one visible action pill is required"
button = buttons[0]
point = bring(flick, button)
before_y = flick.property("contentY")
wheel(point, QPoint(0, 120))
check("wheel starting on an action pill scrolls back up without activating",
      flick.property("contentY") < before_y-20 and win.property("page") == "discover"
      and not win.property("reviewOpened"), parent_delta=flick.property("contentY")-before_y,
      parent_before=before_y, content_height=flick.property("contentHeight"), viewport=flick.height())
point = bring(flick, button)
before_y = flick.property("contentY")
wheel(point, QPoint(), QPoint(0, -55))
check("pixel wheel starting on an action pill scrolls down without activating",
      flick.property("contentY") > before_y+20 and win.property("page") == "discover"
      and not win.property("reviewOpened"), parent_delta=flick.property("contentY")-before_y)
cancel(shelf)
point = bring(flick, button)
before_y = flick.property("contentY")
swipe(point)
check("drag starting on an action pill scrolls without activating",
      flick.property("contentY") > before_y+25 and win.property("page") == "discover"
      and not win.property("reviewOpened"), parent_delta=flick.property("contentY")-before_y)
point = bring(flick, button)
sequence = QTest.touchEvent(win, touch)
sequence.press(0, point.toPoint(), win).commit()
QTest.qWait(30)
sequence.release(0, point.toPoint(), win).commit()
QTest.qWait(160)
check("action pill touch tap opens only the review",
      win.property("reviewOpened") and win.property("page") == "discover",
      page=win.property("page"), review=win.property("reviewOpened"))
evaluate("escapeAction(); clearPicks()")
QTest.qWait(200)
point = bring(flick, button)
QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, point.toPoint())
QTest.qWait(150)
check("action pill mouse click opens only the review",
      win.property("reviewOpened") and win.property("page") == "discover",
      page=win.property("page"), review=win.property("reviewOpened"))
evaluate("escapeAction(); clearPicks()")
QTest.qWait(200)

card = button.parentItem()
while card is not None and "AppCard" not in card.metaObject().className():
    card = card.parentItem()
assert card is not None, "action has no real app card"
bring(flick, card)
point = card.mapToScene(QPointF(card.width()/2, card.height()*0.35))
before_y = flick.property("contentY")
swipe(point)
check("vertical touchscreen drag starting on card content scrolls the page",
      flick.property("contentY") > before_y+25 and win.property("page") == "discover"
      and not win.property("reviewOpened"), parent_delta=flick.property("contentY")-before_y)
cancel(shelf)
bring(flick, card)
point = card.mapToScene(QPointF(card.width()/2, card.height()*0.35))
sequence = QTest.touchEvent(win, touch)
sequence.press(0, point.toPoint(), win).commit()
QTest.qWait(30)
sequence.release(0, point.toPoint(), win).commit()
QTest.qWait(150)
check("card content touch tap still opens actual app details",
      evaluate("page==='app' && selectedApp.id==="+json.dumps(action_id)))
evaluate("navigate('discover')")
QTest.qWait(150)

# Platform entries stay before the editorial hero; these controls use the same
# real openKind/filter contracts as Apps and My apps.
flick.setProperty("contentY", 0)
QTest.qWait(150)
for family in ("linux", "windows", "android", "web"):
    platform = named("platform-"+family)
    point = bring(flick, platform)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, point.toPoint())
    QTest.qWait(150)
    check("platform control selects actual "+family+" rows",
          evaluate("page==='apps' && activeKind==='"+family+"' && visibleApps.length>0"
                   " && visibleApps.every(a=>a.family==='"+family+"')"))
    evaluate("navigate('discover')")
    QTest.qWait(100)

evaluate("activeKind='all'; recompute(); navigate('apps')")
QTest.qWait(150)
assert win.grabWindow().save(str(output / "touch-apps.png")), "Apps render failed"
grid = named("appGrid")
point = grid.mapToScene(QPointF(grid.width()/2, grid.height()/2))
before_y = grid.property("contentY")
swipe(point)
check("app grid touchscreen drag remains available", grid.property("contentY") > before_y+25)
grid.forceActiveFocus()
before_y = grid.property("contentY")
QTest.keyClick(win, Qt.Key_PageDown)
QTest.qWait(150)
check("app grid keyboard paging remains available", grid.property("contentY") > before_y)

evaluate("navigate('library')")
win.setWidth(1000)
QTest.qWait(250)
library_list = named("libraryList")
open_buttons = [item for item in descendants(library_list)
                if "ProgressButton" in item.metaObject().className()
                and item.isVisible() and item.property("action") == "open"]
assert open_buttons, "no installed app Open button"
point = bring(library_list, open_buttons[0])
named("storeToast").setProperty("text", "")
sequence = QTest.touchEvent(win, touch)
sequence.press(0, point.toPoint(), win).commit()
QTest.qWait(30)
sequence.release(0, point.toPoint(), win).commit()
QTest.qWait(160)
check("installed app Open tap invokes only its lifecycle action",
      win.property("page") == "library"
      and named("storeToast").property("text") == evaluate("local('تعذّر فتح التطبيق', 'Could not open the app')"),
      page=win.property("page"), toast=named("storeToast").property("text"))
for glyph, sheet_name in (("trash", "removeSheet"), ("lock", "permissionsSheet")):
    choices = [item for item in descendants(library_list)
               if "CircleButton" in item.metaObject().className() and item.isVisible()
               and item.property("glyph") == glyph and item.isEnabled()]
    assert choices, "no real installed app "+glyph+" control"
    point = bring(library_list, choices[0])
    sequence = QTest.touchEvent(win, touch)
    sequence.press(0, point.toPoint(), win).commit()
    QTest.qWait(30)
    sequence.release(0, point.toPoint(), win).commit()
    QTest.qWait(150)
    check("installed app "+glyph+" tap opens only its management sheet",
          win.property("page") == "library" and named(sheet_name).isVisible(),
          page=win.property("page"))
    evaluate("escapeAction()")
    QTest.qWait(200)
kind_flick = named("libraryKindFlick")
last = named("libraryKind-web")
last.forceActiveFocus(Qt.TabFocusReason)
QTest.qWait(200)
mapped = last.mapToItem(kind_flick, QPointF())
check("all installed-platform filters remain reachable",
      mapped.x() >= -1 and mapped.x()+last.width() <= kind_flick.width()+1,
      x=mapped.x(), width=last.width(), viewport=kind_flick.width())
QTest.keyClick(win, Qt.Key_Return)
QTest.qWait(150)
check("installed platform keyboard selection uses real rows",
      evaluate("libraryKind==='web' && libraryApps.every(a=>a.family==='web')"))

(output / "touch-receipt.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2))
win.grabWindow().save(str(output / "touch-library.png"))
print("STORE INPUT DONE", len(checks), flush=True)
win.close()

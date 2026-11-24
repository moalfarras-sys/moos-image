"""Exercise the shipped Plasma connection on the test's isolated bus, without audio."""
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import ClassInfo, QObject, QPointF, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtDBus import QDBusConnection
from PySide6.QtGui import QAccessible, QGuiApplication, QIcon, QInputDevice
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

SERVICE = "org.moos.Mira"


@ClassInfo({"D-Bus Interface": SERVICE})
class Voice(QObject):
    IslandVoiceChanged = Signal(str)

    def __init__(self, phase, activated=False):
        super().__init__()
        self.phase = phase
        self.shows = []
        self.starts = 0
        self.stops = 0
        self.activated = activated

    @Slot(str, result=str)
    def Show(self, page):
        self.shows.append(page)
        return "ok"

    @Slot(result=str)
    def IslandVoiceState(self):
        return self.phase

    @Slot(result=str)
    def IslandTalk(self):
        self.starts += 1
        self.phase = "listening"
        self.IslandVoiceChanged.emit(self.phase)
        return "ok"

    @Slot(result=str)
    def IslandStop(self):
        self.stops += 1
        if self.stops > 1 or self.activated:
            self.phase = "idle"
            self.IslandVoiceChanged.emit(self.phase)
            if self.activated:
                QTimer.singleShot(250, QGuiApplication.quit)
        return "ok"


def wait(check, description, timeout=3):
    until = time.monotonic() + timeout
    while not check() and time.monotonic() < until:
        QTest.qWait(15)
    assert check(), description


def check_device_tools(engine, ui, voice):
    component = QQmlComponent(engine)
    component.setData(b"""import QtQuick
import org.kde.kirigami as Kirigami
Window {
    id: win
    color: Kirigami.Theme.backgroundColor
    width: 408; height: 145; visible: true
    property int returns: 0
    IslandDeviceTools {
        id: tools; objectName: "tools"; rtl: false; anchors.fill: parent
        onBack: win.returns++
    }
}""", QUrl.fromLocalFile(str(ui / "PrivateDeviceFixture.qml")))
    window = component.create()
    assert window is not None, component.errorString()
    window.requestActivate()
    assert QTest.qWaitForWindowExposed(window)
    tools = window.findChild(QQuickItem, "tools")
    # Repeater delegates belong to the visual row, not the QObject tree.
    def visual(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            match = visual(child, name)
            if match is not None:
                return match
        return None
    buttons = [visual(tools, "moosStrip_" + key) for key in ("overview", "audio", "display", "mira")]
    back = visual(tools, "islandDeviceToolsBack")
    for rtl in (False, True):
        tools.setProperty("rtl", rtl)
        for width in (248, 408):
            window.setWidth(width)
            QTest.qWait(350)  # Allow the native symbolic icon fade to finish.
            positions = []
            painted = window.grabWindow()
            assert not painted.isNull(), "no native frame for the device controls"
            scale = painted.devicePixelRatio()
            for button in buttons:
                box = button.mapRectToItem(tools, button.boundingRect())
                assert box.left() >= 0 and box.right() <= tools.width() + 1, box
                assert box.top() >= 0 and box.bottom() <= tools.height() + 1, box
                assert box.width() >= 44 and box.height() >= 48 and button.isVisible(), box
                # Bounds and accessible names can both pass for a blank native ToolButton.
                # Ignore borders and require contrasting glyph pixels in each actual interior.
                box_on_screen = button.mapRectToScene(button.boundingRect()).adjusted(8, 8, -8, -8)
                samples = [painted.pixelColor(x, y).lightness()
                           for x in range(round(box_on_screen.left() * scale), round(box_on_screen.right() * scale))
                           for y in range(round(box_on_screen.top() * scale), round(box_on_screen.bottom() * scale))]
                samples.sort()
                assert samples[-8] - samples[7] >= 55, (button.objectName(), width, rtl, samples[7], samples[-8], "missing ink")
                positions.append(box.left())
            assert positions == sorted(positions, reverse=rtl), positions
    tools.focusBack()
    assert back.hasActiveFocus()
    QTest.keyClick(window, Qt.Key_Tab)
    assert buttons[0].hasActiveFocus(), "Tab did not enter the native system strip"
    mira = buttons[-1]
    center = mira.mapToScene(QPointF(mira.width() / 2, mira.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, center)
    wait(lambda: voice.shows == [""], "Mira button did not open the window")
    assert voice.starts == 0
    QTest.keyClick(window, Qt.Key_Escape)
    assert window.property("returns") == 1, "Escape did not return to the Island"
    tools.setEnabled(False)
    mira.clicked.emit()
    QTest.qWait(50)
    assert voice.shows == [""], "disabled device tools dispatched"
    window.close()


def run():
    app = QGuiApplication([])
    overlay = Path(__file__).resolve().parents[1] / "system_files/usr/share/icons"
    QIcon.setThemeSearchPaths([str(overlay)] + QIcon.themeSearchPaths())
    QIcon.setThemeName("MoOSUI2Bloom")
    QAccessible.setActive(True)
    cold = sys.argv[1] == "--activated"
    server = QDBusConnection.connectToBus(os.environ["DBUS_SESSION_BUS_ADDRESS"], "voice-fixture")
    voice = Voice("idle" if cold else "listening", activated=cold)
    assert server.registerObject("/Mira", voice, QDBusConnection.ExportAllSlots | QDBusConnection.ExportAllSignals)
    assert server.registerService(SERVICE)
    marker = Path(os.environ["HOME"]) / "cold-start"
    if cold:
        marker.touch()
        QTimer.singleShot(12000, app.quit)
        return app.exec()

    ui = Path(sys.argv[1]).parent
    engine = QQmlEngine()
    engine.setProperty("_kirigamiTheme", "KirigamiPlasmaStyle")
    engine.addImportPath(str(Path(__file__).resolve().parents[1] / "system_files/usr/lib64/qt6/qml"))
    component = QQmlComponent(engine)
    component.setData(b"""import QtQuick
Window {
    width: 368; height: 248; visible: true
    MiraVoiceConnection { id: voice; objectName: "privateLink" }
    MiraVoicePanel {
        anchors.fill: parent; connection: voice; rtl: true
        phaseLabel: voice.phase; motionDuration: 0
    }
}""", QUrl.fromLocalFile(str(ui / "PrivateVoiceFixture.qml")))
    window = component.create()
    assert window is not None, component.errorString()
    window.requestActivate()
    assert QTest.qWaitForWindowExposed(window)
    link = window.findChild(QQuickItem, "privateLink")
    action = window.findChild(QQuickItem, "miraIslandTalk")
    assert link is not None and action is not None
    center = action.mapToScene(QPointF(action.width() / 2, action.height() / 2)).toPoint()
    wait(lambda: link.property("phase") == "listening", "missed a conversation active before the panel loaded")
    assert link.property("owner") == server.baseService() and voice.starts == 0
    status = window.findChild(QQuickItem, "miraIslandVoiceStatus")
    action_access = QAccessible.queryAccessibleInterface(action)
    assert action_access.text(QAccessible.Text.Description) == status.property("text") == "listening"
    check_device_tools(engine, ui, voice)
    window.requestActivate()
    voice.IslandVoiceChanged.emit("invalid")
    QTest.qWait(40)
    assert link.property("active")
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, center)
    wait(lambda: link.property("stopping"), "stop was not sent to the existing owner")
    wait(lambda: link.property("result") == "stopUnconfirmed", "unacknowledged stop left the control disabled", 7)
    assert link.property("active") and not link.property("stopping")
    assert action.isEnabled()
    action.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Return)
    wait(lambda: link.property("phase") == "idle" and not link.property("pending"), "retry never completed")
    assert voice.stops == 2 and voice.starts == 0

    voice.IslandVoiceChanged.emit("speaking")
    wait(lambda: link.property("phase") == "speaking", "missing phase signal")
    assert server.unregisterService(SERVICE)
    wait(lambda: link.property("result") == "unavailable" and not link.property("active"), "service loss kept a stale state")
    link.refresh()
    QTest.qWait(100)
    assert not marker.exists(), "a passive observer launched Mira"
    touch = QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)
    QTest.touchEvent(window, touch).press(0, center, window).commit()
    QTest.touchEvent(window, touch).release(0, center, window).commit()
    wait(lambda: link.property("phase") == "listening" and not link.property("pending"), "explicit cold start failed")
    assert marker.exists()
    link.request()
    wait(lambda: link.property("phase") == "idle" and not link.property("pending"), "cold-started owner did not stop")
    print("MIRA_ISLAND_PRIVATE_BUS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(run())

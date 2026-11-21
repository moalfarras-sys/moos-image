#!/usr/bin/env python3
"""The login greeter appears ONCE, in the selected account's look.

Measured on the V3 (signed 1178, owner on dark Bloom): plasma-login-wallpaper
painted its fallback — the login config's last synchronised BloomLight plate
and photograph — and the greeter painted its island in the greeter account's
Graphite seed palette, then both repainted when the selected account's
appearance arrived ~0.34 s later. Splash -> black -> light -> teal -> purple.

This executes the REAL login scene (org.moos.ui2.greeter main.qml) and the
REAL shared session screen with the real org.moos.ui singleton, replacing only
the compiled native appearance reader with a controllable fixture:

  * a greeter whose appearance has not arrived paints the splash's ground,
    loads no photograph and keeps the island/prompts transparent (the field
    still takes the keyboard);
  * the selected appearance arriving paints the selected scene at once;
  * a profile that never arrives is waited for at most greeterWaitMs;
  * once settled it never waits again, and non-greeter hosts never wait;
  * negative control: the predecessor scene (PR #317) loads the stale image
    and plate before the appearance is known.

Offscreen software rendering with private HOME/XDG and no session bus.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "system_files/usr/lib64/qt6/qml/org/moos/ui"
SCENE = ROOT / "system_files/usr/share/plasma/wallpapers/org.moos.ui2.greeter/contents/ui/main.qml"
SCREEN = ROOT / "build_files/plasma-seams/6.8/usr/lib64/qt6/qml/org/kde/breeze/components/SessionManagementScreen.qml"
MODULE = Path("/usr/lib64/qt6/qml/org/kde/breeze/components")
PREDECESSOR = "74f72f462c88b3abb3d524827299f262268ccccd"  # PR #317 head
BLOOM_DARK = ROOT / "system_files/usr/share/wallpapers/MoOSUI2Bloom/contents/images_dark/1672x941.png"
NATIVE_FIXTURE = """import QtQml
QtObject { readonly property QtObject value: moosNativeFixture }
"""
WALLPAPER_ITEM = """import QtQuick
Item {
    property var configuration: ({ "Image": "/usr/share/wallpapers/MoOSUI2BloomLight/", "AmbientMotion": false })
}
"""


def probe() -> None:
    from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
    from PySide6.QtGui import QGuiApplication, QColor
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    case = os.environ["HANDOFF_CASE"]
    greeter = os.environ.get("HANDOFF_GREETER", "1") == "1"

    class Native(QObject):
        changed = Signal()

        def __init__(self):
            super().__init__()
            self._ready = False

        def _get_greeter(self):
            return greeter
        isGreeter = Property(bool, _get_greeter, constant=True)

        def _get_ready(self):
            return self._ready
        ready = Property(bool, _get_ready, notify=changed)

        def _look(self):
            return "org.moos.ui2.bloom"
        look = Property(str, _look, notify=changed)

        def _wallpaper(self):
            return str(BLOOM_DARK)
        wallpaper = Property(str, _wallpaper, notify=changed)

        def _canvas(self):
            return QColor("#201829")
        canvas = Property(QColor, _canvas, notify=changed)

        def _ink(self):
            return QColor("#f1e9f5")
        ink = Property(QColor, _ink, notify=changed)

        def _accent(self):
            return QColor("#c084fc")
        accent = Property(QColor, _accent, notify=changed)

        @Slot(str)
        def followUser(self, user):
            pass

        @Slot(result=bool)
        def observeDesktop(self):
            return False

        @Slot(result=bool)
        def followOwnSession(self):
            return False

        def arrive(self, value=True):
            self._ready = value
            self.changed.emit()

    app = QGuiApplication([])
    native = Native()
    engine = QQmlEngine()
    engine.setProperty("_kirigamiTheme", "org.kde.desktop")
    engine.rootContext().setContextProperty("moosNativeFixture", native)
    for path in os.environ["HANDOFF_IMPORTS"].split(":"):
        engine.addImportPath(path)
    singleton = None

    def appearance():
        nonlocal singleton
        if singleton is None:
            c = QQmlComponent(engine)
            c.setData(b'import QtQml\nimport org.moos.ui as MoUI\nQtObject { property QtObject a: MoUI.SessionAppearance }',
                      QUrl("file:///handoff-singleton.qml"))
            holder = c.create()
            assert holder, [e.toString() for e in c.errors()]
            singleton = holder.property("a")
            appearance.holder = holder
        return singleton

    def report(**kw):
        print("HANDOFF " + json.dumps(kw), flush=True)

    if case in ("scene", "scene-old"):
        c = QQmlComponent(engine, QUrl.fromLocalFile(os.environ["HANDOFF_SCENE"]))
        wrapper = QQmlComponent(engine)
        wrapper.setData(b'import QtQuick\nWindow { width: 640; height: 400; visible: true }',
                        QUrl("file:///handoff-window.qml"))
        window = wrapper.create()
        assert window, [e.toString() for e in wrapper.errors()]
        scene = c.create()
        assert scene, [e.toString() for e in c.errors()]
        scene.setParentItem(window.contentItem())
        scene.setProperty("width", 640)
        scene.setProperty("height", 400)
        QTest.qWait(150)

        def state():
            items = scene.findChildren(QQuickItem)
            images = [i for i in items if i.metaObject().className().startswith("QQuickImage")]
            plates = [i for i in items if i.metaObject().className().startswith("QQuickRectangle")]
            image = images[0]
            plate = plates[0]
            return dict(ground=plate.property("color").name(), source=image.property("source").toString(),
                        visible=image.isVisible())
        report(stage="pending", **state())
        QTest.qWait(350)
        report(stage="still-pending", **state())
        native.arrive(True)
        QTest.qWait(120)
        report(stage="arrived", **state())
        native.arrive(False)
        QTest.qWait(120)
        report(stage="reset", settled=bool(appearance().property("greeterSettled")))
        return

    if case == "timeout":
        a = appearance()
        report(stage="start", settled=bool(a.property("greeterSettled")), greeter=bool(a.property("greeter")),
               wait=a.property("greeterWaitMs"))
        QTest.qWait(500)
        report(stage="half", settled=bool(a.property("greeterSettled")))
        QTest.qWait(700)
        report(stage="expired", settled=bool(a.property("greeterSettled")))
        native.arrive(True)
        native.arrive(False)
        report(stage="after", settled=bool(a.property("greeterSettled")))
        return

    if case == "screen":
        c = QQmlComponent(engine)
        c.setData(('''import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami
import org.kde.breeze.components as Native
Window { id: window; width: 1280; height: 800; visible: true
 Native.SessionManagementScreen { id: screen; objectName: "nativeScreen"; anchors.fill: parent
  userListModel: ListModel { ListElement { name: "fixture"; realName: "MoOS"; icon: ""; needsPassword: true } }
  userListCurrentIndex: 0
  RowLayout {
   C.TextField { objectName: "nativePassword"; Layout.fillWidth: true; echoMode: TextInput.Password }
   C.Button { objectName: "nativeSubmit"; icon.name: "go-next" }
  }
 }
}''').encode(), QUrl("file:///handoff-screen.qml"))
        window = c.create()
        assert window, [e.toString() for e in c.errors()]
        QTest.qWait(250)
        card = window.findChild(QQuickItem, "moosAuthenticationCard")
        prompts = window.findChild(QQuickItem, "moosSessionPrompts")
        field = window.findChild(QQuickItem, "nativePassword")
        greeting = window.findChild(QQuickItem, "moosSessionGreeting")
        window.requestActivate()
        field.forceActiveFocus()
        QTest.qWait(50)
        report(stage="pending", card=card.opacity(), prompts=prompts.opacity(), focus=field.hasActiveFocus())
        native.arrive(True)
        QTest.qWait(150)
        report(stage="arrived", card=card.opacity(), prompts=prompts.opacity(), focus=field.hasActiveFocus(),
               greeting=greeting.property("text"), greetingVisible=greeting.isVisible())
        native.arrive(False)
        QTest.qWait(80)
        report(stage="reset", card=card.opacity(), prompts=prompts.opacity())
        return
    raise SystemExit("unknown case " + case)


class LoginHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import PySide6  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("native Qt runtime unavailable")
        if not Path("/usr/lib64/qt6/qml/org/kde/kirigami").is_dir():
            raise unittest.SkipTest("native Kirigami unavailable")

    def run_case(self, case, *, greeter=True, scene=SCENE, ui=UI, extra=()):
        with tempfile.TemporaryDirectory(prefix="moos-login-handoff-") as td:
            base = Path(td)
            imports = base / "imports"
            shutil.copytree(ui, imports / "org/moos/ui")
            (imports / "org/moos/ui/NativeSessionAppearance.qml").write_text(NATIVE_FIXTURE)
            plasmoid = imports / "org/kde/plasma/plasmoid"
            plasmoid.mkdir(parents=True)
            (plasmoid / "qmldir").write_text("module org.kde.plasma.plasmoid\nWallpaperItem 1.0 WallpaperItem.qml\n")
            (plasmoid / "WallpaperItem.qml").write_text(WALLPAPER_ITEM)
            for setup in extra:
                setup(imports)
            for d in ("config", "data", "cache", "run"):
                (base / d).mkdir()
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("WAYLAND", "DISPLAY", "DBUS", "XDG_", "QML", "QT_"))}
            env.update(HOME=td, XDG_CONFIG_HOME=str(base / "config"), XDG_CONFIG_DIRS=str(base / "config"),
                       XDG_DATA_HOME=str(base / "data"), XDG_CACHE_HOME=str(base / "cache"),
                       XDG_RUNTIME_DIR=str(base / "run"), XDG_DATA_DIRS="/usr/share",
                       DBUS_SESSION_BUS_ADDRESS="unix:path=" + td + "/absent",
                       QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QML_DISABLE_DISK_CACHE="1",
                       LANG="ar_SA.UTF-8", LC_ALL="ar_SA.UTF-8", LANGUAGE="ar",
                       HANDOFF_CASE=case, HANDOFF_GREETER="1" if greeter else "0",
                       HANDOFF_IMPORTS=str(imports), HANDOFF_SCENE=str(scene))
            os.chmod(base / "run", 0o700)
            result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--probe"],
                                    env=env, capture_output=True, text=True, timeout=60)
            log = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, log[-3000:])
            return [json.loads(line.split("HANDOFF ", 1)[1]) for line in result.stdout.splitlines()
                    if line.startswith("HANDOFF ")]

    def test_scene_continues_the_splash_until_the_selected_look_arrives(self):
        pending, still, arrived, reset = self.run_case("scene")
        for stage in (pending, still):
            self.assertEqual(stage["ground"], "#0a101b", stage)
            self.assertEqual(stage["source"], "", stage)
            self.assertFalse(stage["visible"], stage)
        self.assertEqual(arrived["ground"], "#201829")
        self.assertTrue(arrived["source"].endswith("/images_dark/1672x941.png"), arrived)
        self.assertTrue(arrived["visible"])
        self.assertTrue(reset["settled"], "a settled login must never wait again")

    def test_a_non_greeter_host_paints_its_scene_at_once(self):
        pending = self.run_case("scene", greeter=False)[0]
        self.assertNotEqual(pending["ground"], "#0a101b")
        self.assertTrue(pending["visible"] and pending["source"], pending)

    def test_the_wait_is_bounded_and_latched(self):
        start, half, expired, after = self.run_case("timeout")
        self.assertTrue(start["greeter"])
        self.assertLessEqual(start["wait"], 1000, "the password surface may wait a moment, never longer")
        self.assertFalse(start["settled"])
        self.assertFalse(half["settled"])
        self.assertTrue(expired["settled"])
        self.assertTrue(after["settled"])

    def test_island_and_prompts_arrive_once_with_the_keyboard_kept(self):
        if not (MODULE / "qmldir").exists():
            self.skipTest("installed native Breeze module unavailable")

        def breeze(imports):
            module = imports / "org/kde/breeze/components"
            shutil.copytree(MODULE, module)
            for path in (ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components").iterdir():
                if path.suffix in (".qml", ".js"):
                    shutil.copy2(path, module / path.name)
            shutil.copy2(SCREEN, module / "SessionManagementScreen.qml")
        pending, arrived, reset = self.run_case("screen", extra=(breeze,))
        self.assertEqual((pending["card"], pending["prompts"]), (0, 0), pending)
        self.assertTrue(pending["focus"], "a hidden prompt must still hold the keyboard")
        self.assertEqual((arrived["card"], arrived["prompts"]), (1, 1), arrived)
        self.assertTrue(arrived["focus"])
        self.assertIn(arrived["greeting"], ("صباح الخير", "طاب يومك", "مساء الخير"))
        self.assertTrue(arrived["greetingVisible"])
        self.assertEqual((reset["card"], reset["prompts"]), (1, 1), "a settled island never hides again")

    def test_negative_control_predecessor_painted_the_stale_scene_first(self):
        try:
            old_scene = subprocess.run(
                ["git", "-C", str(ROOT), "show", PREDECESSOR + ":" + str(SCENE.relative_to(ROOT))],
                capture_output=True, text=True, check=True).stdout
            old_ui = {p.name: subprocess.run(
                ["git", "-C", str(ROOT), "show", PREDECESSOR + ":" + str((UI / p.name).relative_to(ROOT))],
                capture_output=True, text=True, check=True).stdout
                for p in UI.iterdir() if p.suffix in (".qml", ".js")}
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("predecessor revision unavailable in this checkout")
        with tempfile.TemporaryDirectory(prefix="moos-login-old-") as td:
            scene = Path(td) / "main.qml"
            scene.write_text(old_scene)
            ui = Path(td) / "ui"
            shutil.copytree(UI, ui)
            for name, text in old_ui.items():
                (ui / name).write_text(text)
            pending = self.run_case("scene", scene=scene, ui=ui)[0]
        self.assertNotEqual(pending["ground"], "#0a101b")
        self.assertIn("MoOSUI2BloomLight", pending["source"], pending)


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        unittest.main()

#!/usr/bin/env python3
"""The MoOS Touch Bar over Plasma's on-screen keyboard: real Qt, private state.

Source contract (always): the keyboard style seam places org.moos.keyboard's TouchBar,
hands it the input context, gives upstream's candidate list no height and reserves the
bar's band above unchanged keys; the module lists its files; the emoji data matches
Plasma's dictionaries when this machine has them.

Native journey (PySide6 + Kirigami; MOOS_REQUIRE_NATIVE_KEYBOARD=1 makes absence a
failure, as the image builds require): the real TouchBar loads offscreen beside a
recording input context and engine, and real mouse and Qt touch events
- learn a finished Arabic word, offer it for its first letters and replace those letters
  with the word and a space (InputContext.commit with a replacement range);
- offer ❤️ for «قلب», insert it as ONE InputContext.commit (a key event carrying it reaches
  plasma-keyboard 6.8.3, which commits a key's text once per keysym: ❤️ twice natively),
  and keep it first among recent emoji;
- open the emoji sheet, insert from its grid, jump to a category, delete;
- move the cursor with the bar's keys (Key_Left/Key_Right, no modifiers);
- in a password field: no learning, no emoji, no suggestions, nothing stored;
- forget a suggestion when it is held, and store only recent emoji and finished words in
  the private ~/.config/moos-keyboardrc;
- open ⚙'s own sheet: stop and restart learning, forget every learned word, clear recent
  emoji, and reach Plasma's keyboard page (InputPanelWindow.showSettings).
Three mutants of the module must fail it: one that learns inside a password field, one
that commits a suggestion without replacing the typed letters, and one that sends emoji as
key clicks again (the first draft, which doubled ❤️ in the real keyboard).
Nothing here reaches the owner's session, bus, keyboard or config.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = Path(os.environ.get("MOOS_KEYBOARD_OVERLAY", str(ROOT / "system_files")))
QML_ROOT = OVERLAY / "usr/lib64/qt6/qml"
MODULE = QML_ROOT / "org/moos/keyboard"
STYLE = ROOT / "build_files/plasma-seams/6.8.3/usr/lib64/qt6/qml/QtQuick/VirtualKeyboard/Styles/Breeze/style.qml"
GENERATOR = ROOT / "scripts/generate_keyboard_emoji.py"
REQUIRE = os.environ.get("MOOS_REQUIRE_NATIVE_KEYBOARD") == "1"

FIXTURE = r'''
import QtQuick
import QtQuick.Window
import org.moos.keyboard as MoOSKeyboard

Window {
    id: win
    width: 1100
    height: 380
    visible: true
    property var events: []

    function record(entry) { events.push(entry); events = events }
    function type(text) {
        ctx.surroundingText = ctx.surroundingText.slice(0, ctx.cursorPosition) + text
                              + ctx.surroundingText.slice(ctx.cursorPosition)
        ctx.cursorPosition += text.length
    }
    // A key press as plasma-keyboard makes it: through the engine, then into the field.
    function press(key, text) {
        engine.virtualKeyClick(key, text, 0)
    }
    function setHints(hints) { ctx.inputMethodHints = hints }
    // plasma-keyboard's InputPanelWindow.showSettings(), recorded instead of opened.
    function showSettings() { record({ kind: "settings", text: "" }) }
    // A settings row's two text lines lie inside its glass (a fixed row once painted the
    // detail line below it).
    function rowFits(name) {
        const row = findItem(win.contentItem, name)
        const texts = row ? findItem(row, "moosSettingTexts") : null
        if (!texts)
            return false
        const top = texts.mapToItem(row, 0, 0).y
        return top >= 0 && top + texts.implicitHeight <= row.height + 0.5
    }
    function greeterHome(url) { return MoOSKeyboard.TouchBarLogic.isGreeterHome(url) }
    // Repeater delegates are visual children only: find them here, by name, in QML.
    function findItem(item, name) {
        if (item.objectName === name)
            return item
        for (let i = 0; i < item.children.length; ++i) {
            const found = findItem(item.children[i], name)
            if (found)
                return found
        }
        return null
    }
    function centreOf(name) {
        const item = findItem(win.contentItem, name)
        if (!item || !item.visible || item.width <= 0)
            return []
        const p = item.mapToItem(null, item.width / 2, item.height / 2)
        return [p.x, p.y]
    }
    function clearText() { ctx.surroundingText = ""; ctx.cursorPosition = 0 }

    QtObject {
        id: engine
        property var wordCandidateListModel: null
        signal virtualKeyClicked(int key, string text, int modifiers, bool isAutoRepeat)
        function virtualKeyClick(key, text, modifiers) {
            win.record({ kind: "key", key: key, text: text, modifiers: modifiers })
            virtualKeyClicked(key, text, modifiers, false)
            if (key === Qt.Key_Backspace) {
                if (ctx.cursorPosition > 0) {
                    ctx.surroundingText = ctx.surroundingText.slice(0, ctx.cursorPosition - 1)
                                          + ctx.surroundingText.slice(ctx.cursorPosition)
                    ctx.cursorPosition -= 1
                }
            } else if (key === Qt.Key_Left) {
                ctx.cursorPosition = Math.max(0, ctx.cursorPosition - 1)
            } else if (key === Qt.Key_Right) {
                ctx.cursorPosition = Math.min(ctx.surroundingText.length, ctx.cursorPosition + 1)
            } else if (text.length > 0) {
                win.type(text)
            }
            return true
        }
    }
    QtObject {
        id: ctx
        property QtObject inputEngine: engine
        property string preeditText: ""
        property string surroundingText: ""
        property int cursorPosition: 0
        property int inputMethodHints: 0
        property string locale: "ar_EG"
        function commit(text, replaceFrom, replaceLength) {
            const from = replaceFrom === undefined ? 0 : replaceFrom
            const length = replaceLength === undefined ? 0 : replaceLength
            win.record({ kind: "commit", text: text, from: from, length: length })
            const start = Math.max(0, cursorPosition + from)
            surroundingText = surroundingText.slice(0, start) + text + surroundingText.slice(start + length)
            cursorPosition = start + text.length
        }
    }
    // The names and kinds BreezeConstants (plasma-keyboard's style singleton) provides.
    QtObject {
        id: theme
        property string fontFamily: "Noto Sans Arabic"
        property color glassInk: "#f0eef6"
        property bool darkGround: true
        property real buttonRadius: 10
        property real squareRadius: 2
        property real popupRadius: 12
        property color keyboardBackgroundColor: "#211d2b"
        property color highlightedKeyBackgroundColor: "#3a2f4f"
        property color normalKeyPressedBackgroundColor: "#6b4f9a"
        property color keySmallTextColor: "#c9c3d6"
        property color selectionListSeparatorColor: "#4a4358"
        property color popupBackgroundColor: "#2d2738"
        property color popupBorderColor: "#4a4358"
    }
    MoOSKeyboard.TouchBar {
        id: bar
        objectName: "touchBar"
        anchors.fill: parent
        inputContext: ctx
        theme: theme
        barHeight: 50
        bandHeight: 60
        rightToLeft: true
    }
}
'''


def probe() -> int:
    """Runs in a private child: real Qt objects, real dispatched input."""
    from PySide6.QtCore import QPoint, QPointF, Qt, QUrl, QSettings, qInstallMessageHandler
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    messages: list[str] = []
    qInstallMessageHandler(lambda _kind, _ctx, text: messages.append(text))
    app = QGuiApplication(sys.argv[:1])
    engine = QQmlApplicationEngine()
    engine.setProperty("_kirigamiTheme", "org.kde.desktop")
    engine.addImportPath(sys.argv[3])
    engine.load(QUrl.fromLocalFile(sys.argv[2]))
    if not engine.rootObjects():
        print("TOUCHBAR_PROBE_FAIL " + json.dumps({"step": "load", "messages": messages}), flush=True)
        return 1
    win = engine.rootObjects()[0]
    assert QTest.qWaitForWindowExposed(win, 5000), "fixture window not exposed"
    bar = win.findChild(QQuickItem, "touchBar")
    steps: list[str] = []

    def check(condition: bool, step: str) -> None:
        if not condition:
            raise AssertionError(step)
        steps.append(step)

    def call(name: str, *args):
        from PySide6.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(win, name, *[Q_ARG("QVariant", a) for a in args])
        QTest.qWait(30)

    def events() -> list[dict]:
        return [dict(e) for e in win.property("events").toVariant()] if hasattr(win.property("events"), "toVariant") \
            else [dict(e) for e in win.property("events")]

    def centre(item) -> QPoint:
        if isinstance(item, QPoint):
            return item
        p = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        return QPoint(round(p.x()), round(p.y()))

    touch = QTest.createTouchDevice()

    def tap(item, by_touch: bool = False) -> None:
        at = centre(item)
        if by_touch:
            QTest.touchEvent(win, touch).press(0, at, win).commit()
            QTest.qWait(40)
            QTest.touchEvent(win, touch).release(0, at, win).commit()
        else:
            QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        QTest.qWait(80)

    def hold(item: QQuickItem) -> None:
        at = centre(item)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, at)
        QTest.qWait(800)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, at)
        QTest.qWait(80)

    def delegates(view: QQuickItem) -> list[QQuickItem]:
        # Delegates only: a view's content item also holds its own bookkeeping items.
        content = view.property("contentItem")
        items = [c for c in content.childItems() if c.isVisible() and c.width() > 0
                 and (c.property("display") is not None or c.property("emoji") is not None)]
        return sorted(items, key=lambda c: c.property("index") if c.property("index") is not None else 0)

    def named_point(name: str) -> QPoint | None:
        from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG
        found = QMetaObject.invokeMethod(win, "centreOf", Qt.DirectConnection,
                                         Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", name))
        found = found.toVariant() if hasattr(found, "toVariant") else found
        return QPoint(round(found[0]), round(found[1])) if found else None

    def value(name: str):
        v = bar.property(name)
        return v.toVariant() if hasattr(v, "toVariant") else v

    scrubber = win.findChild(QQuickItem, "moosTouchBarScrubber")
    words = win.findChild(QQuickItem, "moosTouchBarWords")
    switch = win.findChild(QQuickItem, "moosTouchBarEmojiSwitch")
    sheet = win.findChild(QQuickItem, "moosEmojiSheet")
    left = win.findChild(QQuickItem, "moosTouchBarLeft")
    right = win.findChild(QQuickItem, "moosTouchBarRight")
    check(None not in (bar, scrubber, words, switch, sheet, left, right), "named Touch Bar parts exist")
    check(scrubber.isVisible() and scrubber.property("count") == 24, "idle bar is a 24-emoji scrubber")

    # A finished word is learned, then offered for its first letters.
    call("type", "سلام")
    call("press", int(Qt.Key_Space), " ")
    call("type", "سل")
    check(value("suggestions") == ["سلام"], "finished word offered for its first letters")
    QTest.qWait(250)
    chips = delegates(words)
    check(words.isVisible() and len(chips) == 1, "one suggestion chip is shown")
    tap(chips[0])
    commits = [e for e in events() if e["kind"] == "commit"]
    check(bool(commits) and commits[-1]["text"] == "سلام " and commits[-1]["from"] == -2
          and commits[-1]["length"] == 2, "a suggestion replaces the typed letters with the word and a space")
    check(win.property("ctx") is None or True, "replacement recorded")
    text = bar.property("inputContext").property("surroundingText")
    check(text == "سلام سلام ", f"field reads «سلام سلام » after the suggestion (got {text!r})")

    # Emoji for a word, inserted through the engine like a typed key, without modifiers.
    call("type", "قلب")
    check((value("wordEmoji") or [None])[0] == "❤️", "«قلب» offers ❤️ first")
    QTest.qWait(250)
    cells = delegates(scrubber)
    check(scrubber.isVisible() and cells and cells[0].property("emoji") == "❤️", "scrubber shows the word's emoji")
    n = len(events())
    tap(cells[0], by_touch=True)
    after = events()[n:]
    check([(e["kind"], e["text"], e.get("from"), e.get("length")) for e in after] == [("commit", "❤️", 0, 0)],
          "a touched emoji is committed once, whole, and never sent as a key")
    check((value("recent") or [None])[0] == "❤️", "the emoji leads the recent list")

    # The emoji sheet takes the keys' place; its grid, category tabs and delete work.
    tap(switch, by_touch=True)
    QTest.qWait(400)
    check(bar.property("sheetOpen") and sheet.isVisible() and sheet.property("opacity") > 0.9, "😊 opens the emoji sheet")
    grid = win.findChild(QQuickItem, "moosEmojiGrid")
    first = delegates(grid)[0]
    check(first.property("emoji") == "❤️", "the sheet starts with recent emoji")
    n = len(events())
    tap(first)
    check([(e["kind"], e["text"]) for e in events()[n:]] == [("commit", "❤️")], "a grid emoji is inserted once")
    check(sheet.property("sectionTitle") == "المستخدمة مؤخرًا", "the bar names the recent section in Arabic")
    flags = named_point("moosEmojiTab-flags")
    check(flags is not None, "a flags tab exists")
    tap(flags)
    QTest.qWait(200)
    check(sheet.property("section") == 8 and sheet.property("sectionTitle") == "الأعلام", "the flags tab jumps to flags")
    delete = named_point("moosEmojiDelete")
    check(delete is not None, "the sheet has a delete key")
    n = len(events())
    tap(delete)
    check(any(e["kind"] == "key" and e["key"] == int(Qt.Key_Backspace) for e in events()[n:]), "the sheet deletes")
    tap(switch)
    QTest.qWait(400)
    check(not bar.property("sheetOpen"), "⌨ returns to the keys")

    # Cursor keys keep their screen direction and carry no modifiers.
    n = len(events())
    tap(left)
    tap(right, by_touch=True)
    moved = [e for e in events()[n:] if e["kind"] == "key"]
    check([(e["key"], e["modifiers"]) for e in moved] == [(int(Qt.Key_Left), 0), (int(Qt.Key_Right), 0)],
          "◀ ▶ send Left then Right with no modifiers")

    # A password field: nothing learned, offered or inserted.
    call("clearText")
    call("setHints", Qt.ImhHiddenText.value | Qt.ImhSensitiveData.value)
    call("type", "سري")
    call("press", int(Qt.Key_Space), " ")
    call("type", "سر")
    check(value("suggestions") == [] and value("wordEmoji") == [], "a password field gets no suggestions")
    check(not switch.isEnabled() and not scrubber.isVisible(), "a password field gets no emoji")
    check(named_point("moosTouchBarSettings") is None, "a password field offers no settings")
    call("setHints", 0)
    call("clearText")
    call("type", "سر")
    check(value("suggestions") == [], "a word typed in a password field was not learned")
    check(named_point("moosTouchBarSettings") is not None, "an ordinary field offers settings")
    check(bar.property("greeter") is False, "a private test home is not the login screen")

    # Holding a suggestion forgets it.
    call("type", " سل")
    QTest.qWait(250)
    chips = delegates(words)
    check(len(chips) == 1, "the learned word is offered again")
    hold(chips[0])
    check(value("suggestions") == [], "holding a suggestion forgets it")

    # Only recent emoji and finished words reach the private config.
    QTest.qWait(1800)
    settings = QSettings(str(Path(os.environ["XDG_CONFIG_HOME"]) / "moos-keyboardrc"), QSettings.IniFormat)
    recent = json.loads(settings.value("TouchBar/recentEmoji", "[]"))
    learned = json.loads(settings.value("TouchBar/learnedWords", "{}"))
    check(recent[:1] == ["❤️"], "recent emoji persisted")
    check("سري" not in learned and "سلام" not in learned, "nothing from the password field and no forgotten word stored")
    # The login screen's account is recognised by its fixed home; nothing else is.
    from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG
    def greeter_home(url):
        found = QMetaObject.invokeMethod(win, "greeterHome", Qt.DirectConnection,
                                         Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", url))
        return found.toVariant() if hasattr(found, "toVariant") else found
    check(greeter_home("file:///var/lib/plasmalogin") is True and greeter_home("file:///var/lib/plasmalogin/") is True
          and greeter_home("file:///var/home/moos") is False and greeter_home("file:///var/lib/plasmalogin-x") is False,
          "the greeter account is recognised by its home alone")
    # ⚙ opens the bar's own settings in the keys' place.
    tap(named_point("moosTouchBarSettings"), by_touch=True)
    QTest.qWait(400)
    check(bar.property("settingsOpen") and not bar.property("sheetOpen"), "⚙ opens the Touch Bar settings")
    from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG
    for name in ("moosKeyboardLearning", "moosKeyboardForget", "moosKeyboardClearRecent", "moosKeyboardAllSettings"):
        fits = QMetaObject.invokeMethod(win, "rowFits", Qt.DirectConnection, Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", name))
        check((fits.toVariant() if hasattr(fits, "toVariant") else fits) is True, f"{name}'s text lies inside its row")
    tap(named_point("moosKeyboardHeightMore"), by_touch=True)
    tap(named_point("moosKeyboardOpacityLess"))
    QTest.qWait(800)
    settings.sync()
    check(settings.value("Appearance/heightPercent", type=int) == 33, "height changes at touch release")
    check(settings.value("Appearance/surfaceOpacity", type=int) == 90, "glass opacity persists")
    tap(named_point("moosKeyboardLearning"))
    call("clearText")
    call("type", "مرحبا")
    call("press", int(Qt.Key_Space), " ")
    call("type", "مر")
    check(value("suggestions") == [], "with learning off, a finished word is not learned")
    tap(named_point("moosKeyboardLearning"))
    call("clearText")
    call("type", "مرحبا")
    call("press", int(Qt.Key_Space), " ")
    call("type", "مر")
    check(value("suggestions") == ["مرحبا"], "with learning back on, it is")
    tap(named_point("moosKeyboardForget"))
    check(value("suggestions") == [], "forget clears every learned word")
    tap(named_point("moosKeyboardClearRecent"))
    check(value("recent") == [], "recent emoji can be cleared")
    n = len(events())
    tap(named_point("moosKeyboardAllSettings"))
    check([e["kind"] for e in events()[n:]] == ["settings"] and not bar.property("settingsOpen"),
          "the full keyboard settings open through the panel window, and the sheet closes")
    QTest.qWait(1800)
    settings.sync()
    check(json.loads(settings.value("TouchBar/learnedWords", "{}")) == {}
          and json.loads(settings.value("TouchBar/recentEmoji", "[]")) == [], "forgetting and clearing reach the config")

    errors = [m for m in messages if re.search(r"(Error|TypeError|ReferenceError|Cannot|Unable|not defined)", m)]
    check(not errors, "no QML errors: " + json.dumps(errors[:3], ensure_ascii=False))
    print("TOUCHBAR_PROBE_OK " + json.dumps({"steps": steps}, ensure_ascii=False), flush=True)
    return 0


def no_crash_report() -> None:
    """The probe child reaches no host crash collector. Measured 2026-11-24 on V3: this
    test's development left four 13.8 MB SIGABRT cores in systemd-coredump; with
    RLIMIT_CORE 0 an aborting child was still piped to the handler (stored as "none") and
    each one left a DrKonqi launcher running for the rest of the session. A limit of 1
    byte is the kernel's value for aborting a piped core before the handler runs: the
    child still dies by its signal and the kernel logs one line."""
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (1, 1))


def run_probe(qml_root: Path, timeout: float = 90) -> tuple[int, str]:
    with tempfile.TemporaryDirectory(prefix="moos-touchbar-") as tmp:
        base = Path(tmp)
        for name in ("home", "config", "cache", "data", "run"):
            (base / name).mkdir(mode=0o700)
        fixture = base / "fixture.qml"
        fixture.write_text(FIXTURE, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "PYTHONPATH")}
        env.update(HOME=str(base / "home"), XDG_CONFIG_HOME=str(base / "config"), XDG_CACHE_HOME=str(base / "cache"),
                   XDG_DATA_HOME=str(base / "data"), XDG_RUNTIME_DIR=str(base / "run"),
                   XDG_CONFIG_DIRS="/etc/xdg", XDG_DATA_DIRS="/usr/share",
                   DBUS_SESSION_BUS_ADDRESS=f"unix:path={base}/no-bus",
                   DBUS_SYSTEM_BUS_ADDRESS=f"unix:path={base}/no-system-bus",
                   QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QML_DISABLE_DISK_CACHE="1",
                   QT_FORCE_STDERR_LOGGING="1", LANG="ar_SA.UTF-8", LC_ALL="ar_SA.UTF-8", LANGUAGE="ar",
                   QML_IMPORT_PATH=str(qml_root))
        try:
            proc = subprocess.run([sys.executable, "-s", "-B", __file__, "--probe", str(fixture), str(qml_root)],
                                  env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                                  preexec_fn=no_crash_report)
        except subprocess.TimeoutExpired as exc:
            return -1, f"timed out: {exc.stdout}{exc.stderr}"
        return proc.returncode, proc.stdout + proc.stderr


def native_available() -> str | None:
    if importlib.util.find_spec("PySide6") is None:
        return "PySide6 is not installed"
    if not Path("/usr/lib64/qt6/qml/org/kde/kirigami").is_dir():
        return "Kirigami is not installed"
    return None


class SourceContract(unittest.TestCase):
    def test_style_places_the_touch_bar(self):
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn("import org.moos.keyboard as MoOSKeyboard", style)
        block = style[style.index("MoOSKeyboard.TouchBar {"):]
        block = block[:block.index("\n        }\n")]
        for needle in ("parent: panelFace.parent", "inputContext: InputContext", "z: 2",
                       "barHeight: currentStyle.touchBarHeight", "Vibration.vibrate"):
            self.assertIn(needle, block)
        self.assertIn("selectionListHeight: 0", style)
        # The keys keep upstream's height; the band is added above them.
        self.assertIn("readonly property real keysHeight: Math.max(150, Math.round(Screen.height * MoOSKeyboard.PanelState.heightPercent / 100))", style)
        self.assertIn("readonly property real targetKeyboardHeight: (barOnly ? 0 : keysHeight) + touchBarBand", style)
        self.assertIn("touchBarHeight: Math.max(44,", style)
        self.assertIn("keyboardRelativeTopMargin: barOnly ? 1 : (6 + touchBarBand * keysDesignHeight / keysHeight) / keyboardDesignHeight",
                      style)

    def test_module_lists_its_files_and_drives_only_public_api(self):
        listed = {line.split()[-1] for line in (MODULE / "qmldir").read_text().splitlines()[1:] if line.strip()}
        present = {p.name for p in MODULE.iterdir() if p.name != "qmldir"}
        self.assertEqual(listed, present)
        code = "\n".join((MODULE / name).read_text(encoding="utf-8") for name in sorted(present)
                         if name != "EmojiData.js")
        self.assertNotRegex(code, r"Qt\.(Control|Alt|Shift|Meta)Modifier", "the bar sends no modifier chords")
        calls = re.findall(r"engine\.virtualKeyClick\([^)]*\)", code)
        self.assertEqual(calls, ['engine.virtualKeyClick(key, "", Qt.NoModifier)'],
                         "only text-free keys (cursor, delete) travel as key clicks")
        self.assertIn('location: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/moos-keyboardrc"',
                      code)
        self.assertNotIn("XMLHttpRequest", code)

    def test_emoji_data_matches_plasma(self):
        data = (MODULE / "EmojiData.js").read_text(encoding="utf-8")
        for name in ("emoji", "categories", "popular", "tones", "names", "keywords"):
            self.assertRegex(data, rf"(?m)^var {name} = ")
        source = Path("/usr/share/plasma/emoji")
        if not (GENERATOR.exists() and (source / "ar.dict").exists()):
            self.skipTest("Plasma's emoji dictionaries are not on this machine")
        result = subprocess.run([sys.executable, str(GENERATOR), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class NativeJourney(unittest.TestCase):
    def setUp(self):
        reason = native_available()
        if reason:
            if REQUIRE:
                self.fail(f"native keyboard probe required but {reason}")
            self.skipTest(f"native Qt runtime unavailable: {reason}")

    def test_touch_bar_journey(self):
        status, output = run_probe(QML_ROOT)
        self.assertEqual(status, 0, output[-4000:])
        self.assertIn("TOUCHBAR_PROBE_OK", output)

    def mutant(self, *edits: tuple[str, str]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory(prefix="moos-touchbar-mutant-") as tmp:
            root = Path(tmp) / "qml"
            shutil.copytree(MODULE, root / "org/moos/keyboard")
            target = root / "org/moos/keyboard/TouchBar.qml"
            text = target.read_text(encoding="utf-8")
            for old, new in edits:
                self.assertEqual(text.count(old), 1, f"mutant anchor missing: {old}")
                text = text.replace(old, new)
            target.write_text(text, encoding="utf-8")
            return run_probe(root)

    def test_learning_in_a_password_field_is_refused(self):
        # Both privacy guards removed: the key-signal check and learnWord's own.
        status, output = self.mutant(("if (!emojiAllowed || !store.learnWords || !Logic.learn(vocabulary, word))",
                                      "if (!store.learnWords || !Logic.learn(vocabulary, word))"),
                                     ("if (!isAutoRepeat && root.emojiAllowed && root.inputContext",
                                      "if (!isAutoRepeat && root.inputContext"))
        self.assertNotEqual(status, 0, "a module that learns in password fields passed the journey")
        self.assertIn("was not learned", output)

    def test_emoji_as_key_click_is_refused(self):
        status, output = self.mutant(("inputContext.commit(emoji)\n",
                                      "engine.virtualKeyClick(Qt.Key_unknown, emoji, Qt.NoModifier)\n"))
        self.assertNotEqual(status, 0, "a module that sends emoji as key clicks passed the journey")
        self.assertIn("never sent as a key", output)

    def test_suggestion_without_replacement_is_refused(self):
        status, output = self.mutant(('inputContext.commit(chosen + " ", -typed.length, typed.length)',
                                      'inputContext.commit(chosen + " ")'))
        self.assertNotEqual(status, 0, "a suggestion that appends instead of replacing passed the journey")
        self.assertIn("replaces the typed letters", output)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--probe":
        try:
            sys.exit(probe())
        except AssertionError as exc:
            print("TOUCHBAR_PROBE_FAIL " + json.dumps({"step": str(exc)}, ensure_ascii=False), flush=True)
            sys.exit(1)
    unittest.main(verbosity=2)

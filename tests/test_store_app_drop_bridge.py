#!/usr/bin/env python3
"""Exercise the production App Drop bridge with Qt Core and intercepted spawning.

No installer is executed. Only QProcess is replaced; QUrl/QFileInfo and the
complete production method remain real. Executable cases explicitly skip when
Qt development headers/compiler are unavailable, never count a mock URL parser
as production evidence.
"""
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "build_files/moos-qml-shell.cpp"


def method(signature: str = "    Q_INVOKABLE bool installFile("):
    source = SOURCE.read_text()
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


# The Store's newer verbs. Each is one fixed moos-storectl argv; ids pass validId, and a
# permission's key and value pass fixed lists in C++ before moos-storectl checks them again.
NEW_VERBS = {
    "removeAppData": "    Q_INVOKABLE bool removeAppData(",
    "updateApp": "    Q_INVOKABLE bool updateApp(",
    "appPermissions": "    Q_INVOKABLE bool appPermissions(",
    "setPermission": "    Q_INVOKABLE bool setPermission(",
    "setAutoUpdates": "    Q_INVOKABLE bool setAutoUpdates(",
}
PERMISSION_KEYS = ("network", "files-home", "files-all", "downloads", "devices", "sound",
                   "bluetooth", "background", "notifications", "microphone", "camera",
                   "location", "clipboard", "screen")


class SourceBoundary(unittest.TestCase):
    def test_the_newer_verbs_are_fixed_argv_behind_the_same_gates(self):
        for name, signature in NEW_VERBS.items():
            with self.subTest(verb=name):
                body = method(signature)
                self.assertIn("m_enabled", body)
                self.assertIn("start({", body, "a verb must start the one fixed backend")
                self.assertNotIn("startDetached", body, "a verb started its own process")
                self.assertNotIn("/bin/sh", body)
                if name != "setAutoUpdates":
                    self.assertIn("validId(id)", body)
        permission = method(NEW_VERBS["setPermission"])
        for key in PERMISSION_KEYS:
            self.assertIn(f'QStringLiteral("{key}")', permission)
        self.assertIn("keys.contains(key)", permission)
        self.assertIn("values.contains(value)", permission)
        storectl = (ROOT / "system_files/usr/bin/moos-storectl").read_text(encoding="utf-8")
        for key in PERMISSION_KEYS:
            self.assertIn(f'"{key}"', storectl, f"the backend does not know the bridge's key {key}")

    def test_fixed_helper_without_shell_or_success_claim(self):
        body = method()
        self.assertIn('QStringLiteral("/usr/bin/moos-app-drop")', body)
        self.assertIn("QStringList{path}", body)
        self.assertNotIn("/bin/sh", body)
        self.assertNotIn("system(", body)
        for guard in ("!m_enabled", "!url.isLocalFile()", "!url.host().isEmpty()",
                      "url.hasQuery()", "url.hasFragment()", "file.isSymLink()",
                      "!file.isFile()", "!file.isAbsolute()", "!file.isReadable()"):
            self.assertIn(guard, body)


class ForeignConsent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import runpy
        import sys
        with mock.patch.object(sys, "path", sys.path[:]):
            cls.helper = runpy.run_path(str(ROOT / "system_files/usr/bin/moos-app-drop"))

    def test_foreign_handoff_declined_never_starts_process(self):
        from types import SimpleNamespace
        namespace = self.helper["handle"].__globals__
        plan = SimpleNamespace(handoff="foreign", path=pathlib.Path("/tmp/untrusted.exe"))
        with mock.patch.object(namespace["appdrop"], "inspect", return_value=plan), \
                mock.patch.dict(namespace, {"ask": mock.Mock(return_value=False)}), \
                mock.patch.object(namespace["subprocess"], "Popen") as launch, \
                mock.patch.object(namespace["subprocess"], "run") as run:
            self.assertEqual(namespace["handle"](str(plan.path)), 0)
            namespace["ask"].assert_called_once()
            launch.assert_not_called()
            run.assert_not_called()

    def test_foreign_handoff_confirmed_uses_fixed_helper_and_literal_path(self):
        from types import SimpleNamespace
        namespace = self.helper["handle"].__globals__
        plan = SimpleNamespace(handoff="foreign", path=pathlib.Path("/tmp/a ; $(no).exe"))
        with mock.patch.object(namespace["appdrop"], "inspect", return_value=plan), \
                mock.patch.dict(namespace, {"ask": mock.Mock(return_value=True)}), \
                mock.patch.object(namespace["subprocess"], "Popen") as launch:
            self.assertEqual(namespace["handle"](str(plan.path)), 0)
            launch.assert_called_once_with(["/usr/bin/moos-run-foreign", str(plan.path)],
                                          stdin=subprocess.DEVNULL, start_new_session=True)


class ExecutableBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("g++") or shutil.which("clang++")
        pkg = shutil.which("pkg-config")
        if not compiler or not pkg:
            raise unittest.SkipTest("C++ compiler/pkg-config unavailable; executable bridge unproven")
        flags = subprocess.run([pkg, "--cflags", "--libs", "Qt6Core"],
                               capture_output=True, text=True)
        if flags.returncode:
            raise unittest.SkipTest("Qt6Core development headers unavailable; executable bridge unproven")
        cls.temp = tempfile.TemporaryDirectory(prefix="moos-store-bridge-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = pathlib.Path(cls.temp.name)
        cpp = cls.directory / "bridge.cpp"
        cpp.write_text('''#include <QCoreApplication>
#include <QUrl>
#include <QFileInfo>
#include <QStringList>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <iostream>
struct ProcessProbe {
    static inline int calls = 0;
    static inline QString program;
    static inline QStringList arguments;
    static bool startDetached(const QString &p, const QStringList &a) {
        ++calls; program = p; arguments = a; return true;
    }
};
#define QProcess ProcessProbe
class Bridge {
public:
    bool m_enabled;
''' + method() + '''
};
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    Bridge bridge{QString::fromUtf8(argv[1]) == "enabled"};
    bool accepted = bridge.installFile(QUrl::fromEncoded(argv[2], QUrl::StrictMode));
    QJsonObject out{{"accepted", accepted}, {"calls", ProcessProbe::calls},
        {"program", ProcessProbe::program},
        {"arguments", QJsonArray::fromStringList(ProcessProbe::arguments)}};
    std::cout << QJsonDocument(out).toJson(QJsonDocument::Compact).constData();
}
''')
        cls.binary = cls.directory / "bridge"
        import shlex
        subprocess.run([compiler, "-std=c++17", "-fPIC", str(cpp), "-o", str(cls.binary),
                        *shlex.split(flags.stdout)], check=True, capture_output=True, text=True)

    def invoke(self, url, enabled=True):
        import json
        return json.loads(subprocess.check_output(
            [str(self.binary), "enabled" if enabled else "disabled", url], text=True))

    def test_regular_file_and_metacharacters_are_one_literal_argument(self):
        for name in ("application.AppImage", "spaces ; $(touch NEVER) ' quote.AppImage"):
            path = self.directory / name
            path.write_bytes(b"test fixture, never installed")
            self.assertEqual(self.invoke(path.as_uri()), {
                "accepted": True, "calls": 1, "program": "/usr/bin/moos-app-drop",
                "arguments": [str(path)]})

    def test_disabled_and_invalid_urls_never_spawn(self):
        path = self.directory / "valid.AppImage"
        path.write_bytes(b"fixture")
        link = self.directory / "symlink.AppImage"
        link.symlink_to(path)
        for url in ("https://example.com/application.AppImage", "file://host" + str(path),
                    "file://localhost" + str(path), path.as_uri() + "?download=1",
                    path.as_uri() + "#fragment", "file:relative.AppImage",
                    (self.directory / "missing").as_uri(), self.directory.as_uri(), link.as_uri()):
            with self.subTest(url=url):
                result = self.invoke(url)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["calls"], 0)
        self.assertEqual(self.invoke(path.as_uri(), enabled=False)["calls"], 0)

    def test_existing_control_character_files_never_spawn(self):
        for control in ("\n", "\r", "\t", "\x7f"):
            path = self.directory / ("control" + control + ".AppImage")
            path.write_bytes(b"fixture")
            result = self.invoke(path.as_uri())
            self.assertFalse(result["accepted"])
            self.assertEqual(result["calls"], 0)


class ExecutableVerbs(unittest.TestCase):
    """The newer verbs compiled from the production source, QProcess intercepted."""

    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("g++") or shutil.which("clang++")
        pkg = shutil.which("pkg-config")
        if not compiler or not pkg:
            raise unittest.SkipTest("C++ compiler/pkg-config unavailable; executable verbs unproven")
        flags = subprocess.run([pkg, "--cflags", "--libs", "Qt6Core"], capture_output=True, text=True)
        if flags.returncode:
            raise unittest.SkipTest("Qt6Core development headers unavailable; executable verbs unproven")
        cls.temp = tempfile.TemporaryDirectory(prefix="moos-store-verbs-")
        cls.addClassCleanup(cls.temp.cleanup)
        directory = pathlib.Path(cls.temp.name)
        bodies = "\n".join(method(signature) for signature in NEW_VERBS.values())
        helpers = method("    static bool validId(") + "\n" + method("    static bool start(")
        cpp = directory / "verbs.cpp"
        cpp.write_text('''#include <QCoreApplication>
#include <QRegularExpression>
#include <QStringList>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <iostream>
struct ProcessProbe {
    static inline int calls = 0;
    static inline QString program;
    static inline QStringList arguments;
    static bool startDetached(const QString &p, const QStringList &a) {
        ++calls; program = p; arguments = a; return true;
    }
};
#define QProcess ProcessProbe
class Bridge {
public:
    bool m_enabled;
''' + bodies + '''
private:
''' + helpers + '''
};
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    Bridge bridge{QString::fromUtf8(argv[1]) == "enabled"};
    const QString verb = QString::fromUtf8(argv[2]);
    auto arg = [&](int i) { return i < argc ? QString::fromUtf8(argv[i]) : QString(); };
    bool accepted = false;
    if (verb == "removeAppData") accepted = bridge.removeAppData(arg(3));
    else if (verb == "updateApp") accepted = bridge.updateApp(arg(3));
    else if (verb == "appPermissions") accepted = bridge.appPermissions(arg(3));
    else if (verb == "setPermission") accepted = bridge.setPermission(arg(3), arg(4), arg(5));
    else if (verb == "setAutoUpdates") accepted = bridge.setAutoUpdates(arg(3) == "true");
    QJsonObject out{{"accepted", accepted}, {"calls", ProcessProbe::calls},
        {"program", ProcessProbe::program},
        {"arguments", QJsonArray::fromStringList(ProcessProbe::arguments)}};
    std::cout << QJsonDocument(out).toJson(QJsonDocument::Compact).constData();
}
''')
        cls.binary = directory / "verbs"
        import shlex
        subprocess.run([compiler, "-std=c++17", "-fPIC", str(cpp), "-o", str(cls.binary),
                        *shlex.split(flags.stdout)], check=True, capture_output=True, text=True)

    def call(self, *argv, enabled=True):
        import json
        return json.loads(subprocess.check_output(
            [str(self.binary), "enabled" if enabled else "disabled", *argv], text=True))

    def test_each_verb_is_one_fixed_backend_argv(self):
        for argv, expected in (
                (("removeAppData", "org.example.App"), ["remove", "--delete-data", "org.example.App"]),
                (("updateApp", "photocraft"), ["update", "photocraft"]),
                (("appPermissions", "chatgpt"), ["permissions", "chatgpt"]),
                (("setPermission", "org.example.App", "network", "deny"),
                 ["set-permission", "org.example.App", "network", "deny"]),
                (("setPermission", "chatgpt", "microphone", "reset"),
                 ["set-permission", "chatgpt", "microphone", "reset"]),
                (("setAutoUpdates", "true"), ["auto-updates", "on"]),
                (("setAutoUpdates", "false"), ["auto-updates", "off"])):
            with self.subTest(argv=argv):
                self.assertEqual(self.call(*argv), {"accepted": True, "calls": 1,
                                                    "program": "/usr/bin/moos-storectl",
                                                    "arguments": expected})

    def test_ids_keys_and_values_outside_the_lists_never_spawn(self):
        for argv in (("removeAppData", "-x"), ("removeAppData", "a/b"), ("updateApp", "a..b"),
                     ("appPermissions", "x\n"), ("updateApp", ""),
                     ("setPermission", "org.example.App", "filesystem=/", "allow"),
                     ("setPermission", "org.example.App", "--reset", "allow"),
                     ("setPermission", "org.example.App", "Network", "allow"),
                     ("setPermission", "org.example.App", "network", "ALLOW"),
                     ("setPermission", "org.example.App", "network", "maybe"),
                     ("setPermission", "../x", "network", "deny")):
            with self.subTest(argv=argv):
                self.assertEqual(self.call(*argv)["calls"], 0)
        for argv in (("removeAppData", "org.example.App"), ("setAutoUpdates", "true")):
            with self.subTest(disabled=argv):
                self.assertEqual(self.call(*argv, enabled=False)["calls"], 0)


if __name__ == "__main__":
    unittest.main()

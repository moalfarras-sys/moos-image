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


def method():
    source = SOURCE.read_text()
    start = source.index("    Q_INVOKABLE bool installFile(")
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class SourceBoundary(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

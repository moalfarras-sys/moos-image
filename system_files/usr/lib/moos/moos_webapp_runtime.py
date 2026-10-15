"""The window of a MoOS web app (see moos_webapp_policy for every rule it follows).

One process per web app, one window, its own profile: cookies and storage survive a restart and
never mix with another app or with the person's browser. The policy module decides; this module
only draws and asks.

Kept small on purpose. What a web app can do here:
  * stay on its own hosts — sign-in pages of the providers its entry names included — while every
    other link opens in the person's browser;
  * ask for a permission its catalogue entry offers; the person answers once and Mo Store can
    change the answer later (both read the same permissions.json);
  * notify through the desktop's notification server, filed under the app's own launcher;
  * download into the person's Downloads folder;
  * go full screen, zoom (remembered), and remember where its window was.
What it cannot do: open file:, data: or moos: addresses, read the clipboard without a granted
permission, reach a developer console, or run a plugin.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import sys

from PySide6.QtCore import (QBuffer, QByteArray, QIODevice, QLocale, QProcess, QStandardPaths,
                            Qt, QTimer, QUrl)
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEnginePermission,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

import moos_webapp_policy as policy

ARABIC = QLocale.system().language() == QLocale.Language.Arabic or \
    os.environ.get("LANG", "").startswith("ar")

# The person-facing words, both languages, in one place.
WORDS = {
    "allow": ("السماح", "Allow"),
    "deny": ("عدم السماح", "Don't allow"),
    "open_browser": ("افتح في المتصفّح", "Open in browser"),
    "reload": ("إعادة التحميل", "Reload"),
    "ask_title": ("طلب إذن", "Permission request"),
    "ask_body": ("يطلب «{app}» {what}.\nيمكنك تغيير هذا لاحقاً من Mo Store.",
                 "{app} wants {what}.\nYou can change this later in Mo Store."),
    "notifications": ("إظهار الإشعارات", "to show notifications"),
    "microphone": ("استخدام الميكروفون", "to use your microphone"),
    "camera": ("استخدام الكاميرا", "to use your camera"),
    "location": ("معرفة موقعك", "to know your location"),
    "clipboard": ("قراءة الحافظة", "to read your clipboard"),
    "screen": ("مشاركة شاشتك", "to share your screen"),
    "downloaded": ("اكتمل التنزيل: {name}", "Downloaded: {name}"),
    "download_failed": ("تعذّر التنزيل: {name}", "Download failed: {name}"),
    "open": ("فتح", "Open"),
}


def words(key: str, **values: str) -> str:
    arabic, english = WORDS[key]
    return (arabic if ARABIC else english).format(**values)


def app_name(app: policy.WebApp) -> str:
    return app.name_ar if ARABIC else app.name_en


# Qt permission types -> the catalogue's permission names. Capture of both microphone and camera
# needs both answers.
PERMISSION_NAMES = {
    QWebEnginePermission.PermissionType.Notifications: ("notifications",),
    QWebEnginePermission.PermissionType.MediaAudioCapture: ("microphone",),
    QWebEnginePermission.PermissionType.MediaVideoCapture: ("camera",),
    QWebEnginePermission.PermissionType.MediaAudioVideoCapture: ("microphone", "camera"),
    QWebEnginePermission.PermissionType.Geolocation: ("location",),
    QWebEnginePermission.PermissionType.ClipboardReadWrite: ("clipboard",),
    QWebEnginePermission.PermissionType.DesktopVideoCapture: ("screen",),
    QWebEnginePermission.PermissionType.DesktopAudioVideoCapture: ("screen", "microphone"),
}


_LIVE: set = set()   # notification processes still waiting for an answer


def notify(app: policy.WebApp, icon: Path, summary: str, body: str,
           on_click=None) -> None:
    """A desktop notification filed under THIS web app's launcher (its own entry in Settings)."""
    argv = ["notify-send", "--app-name", app_name(app), "--icon", str(icon),
            f"--hint=string:desktop-entry:{app.desktop_id}"]
    if on_click is not None:
        argv += ["--action", f"default={words('open')}", "--wait"]
    process = QProcess()
    process.setProgram(argv[0])
    process.setArguments(argv[1:] + ["--", summary[:200], body[:500]])

    def finished(*_):
        _LIVE.discard(process)
        if on_click is not None and bytes(process.readAllStandardOutput()).strip() == b"default":
            on_click()
        process.deleteLater()

    _LIVE.add(process)
    process.finished.connect(finished)
    process.start()


class Page(QWebEnginePage):
    """One page of the app. Navigation and new windows obey policy.navigation()."""

    def __init__(self, shell: "Shell", popup: bool = False) -> None:
        super().__init__(shell.profile, shell.window)
        self.shell = shell
        self.popup = popup
        self.permissionRequested.connect(shell.on_permission)
        self.fullScreenRequested.connect(shell.on_fullscreen)
        self.windowCloseRequested.connect(self.on_close_requested)

    def acceptNavigationRequest(self, url: QUrl, kind, main_frame: bool) -> bool:  # noqa: N802
        if not main_frame:
            return True
        address = url.toString()
        verdict = policy.navigation(address, self.shell.app)
        if verdict == "inside":
            # A popup is shown once it reaches a real page of its own (sign-in, share sheet);
            # the about:blank it starts on decides nothing.
            if self.popup and address != "about:blank" and not self.shell.popup_window_for(self):
                self.shell.show_popup(self)
            return True
        if verdict == "external":
            QDesktopServices.openUrl(url)
        if self.popup:
            current = self.url().toString()
            if not self.shell.popup_window_for(self) or current in ("", "about:blank"):
                self.shell.close_popup(self)
        return False

    def createWindow(self, kind):  # noqa: N802
        # The new page decides where it belongs on its first navigation (see above).
        return Page(self.shell, popup=True)

    def on_close_requested(self) -> None:
        if self.popup:
            self.shell.close_popup(self)

    def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
        pass  # the site's console is not the person's business, nor the journal's


class Window(QMainWindow):
    def __init__(self, shell: "Shell") -> None:
        super().__init__()
        self.shell = shell

    def closeEvent(self, event) -> None:  # noqa: N802
        self.shell.on_window_close(event)


class Shell:
    """The app: profile, main window, popups, permissions, downloads, single instance."""

    def __init__(self, app: policy.WebApp, qt_app: QApplication) -> None:
        self.app = app
        self.qt_app = qt_app
        self.paths = policy.paths(app.id)
        self.paths.data.mkdir(parents=True, exist_ok=True)
        os.chmod(self.paths.data, 0o700)
        self.permissions = policy.PermissionStore(app, self.paths.permissions)
        self.popups: dict[int, QWebEngineView] = {}
        self.pending: list = []
        self.state = self.read_state()
        self.profile = self.make_profile()
        self.window = Window(self)
        self.window.setWindowTitle(app_name(app))
        self.window.setWindowIcon(QIcon(str(policy.icon_for(app))))
        self.view = QWebEngineView(self.window)
        self.page = Page(self)
        self.view.setPage(self.page)
        self.window.setCentralWidget(self.view)
        self.view.titleChanged.connect(self.on_title)
        self.view.iconChanged.connect(self.on_icon)
        self.view.setZoomFactor(float(self.state.get("zoom", 1.0)))
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.on_context_menu)
        self.page.renderProcessTerminated.connect(self.on_renderer_gone)
        self.install_shortcuts()
        self.restore_geometry()

    # ── profile ────────────────────────────────────────────────────────────────
    def make_profile(self) -> QWebEngineProfile:
        profile = QWebEngineProfile(self.app.id, self.qt_app)
        profile.setPersistentStoragePath(str(self.paths.profile))
        profile.setCachePath(str(self.paths.cache))
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        # Our own answers decide; the engine must ask every time and remember nothing itself.
        profile.setPersistentPermissionsPolicy(
            QWebEngineProfile.PersistentPermissionsPolicy.AskEveryTime)
        # The engine's own token makes some sign-in pages refuse an otherwise ordinary browser.
        profile.setHttpUserAgent(re.sub(r" QtWebEngine/[0-9.]+", "", profile.httpUserAgent()))
        profile.setHttpAcceptLanguage("ar,en-US;q=0.9,en;q=0.8" if ARABIC
                                      else "en-US,en;q=0.9,ar;q=0.8")
        languages = spellcheck_languages()
        if languages:
            profile.setSpellCheckEnabled(True)
            profile.setSpellCheckLanguages(languages)
        profile.setNotificationPresenter(self.present_notification)
        profile.downloadRequested.connect(self.on_download)
        settings = profile.settings()
        attribute = QWebEngineSettings.WebAttribute
        for name, value in (
            ("LocalContentCanAccessRemoteUrls", False),
            ("LocalContentCanAccessFileUrls", False),
            ("PluginsEnabled", False),
            ("JavascriptCanOpenWindows", True),
            ("JavascriptCanAccessClipboard", True),   # writing; reading needs "clipboard"
            ("JavascriptCanPaste", False),
            ("FullScreenSupportEnabled", True),
            ("ScreenCaptureEnabled", "screen" in self.app.permissions),
            ("WebRTCPublicInterfacesOnly", True),
            ("DnsPrefetchEnabled", False),
            ("PdfViewerEnabled", True),
            ("ScrollAnimatorEnabled", True),
            ("PlaybackRequiresUserGesture", True),
            ("NavigateOnDropEnabled", False),
            ("ErrorPageEnabled", True),
        ):
            member = getattr(attribute, name, None)
            if member is not None:
                settings.setAttribute(member, value)
        return profile

    # ── window state ───────────────────────────────────────────────────────────
    def read_state(self) -> dict:
        try:
            data = json.loads(self.paths.window.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def write_state(self) -> None:
        state = {
            "geometry": base64.b64encode(bytes(self.window.saveGeometry())).decode("ascii"),
            "zoom": round(self.view.zoomFactor(), 2),
            "icon_size": int(self.state.get("icon_size", 0)),
        }
        try:
            policy._atomic_write(self.paths.window, json.dumps(state) + "\n", 0o600)
        except OSError:
            pass

    def restore_geometry(self) -> None:
        encoded = self.state.get("geometry")
        if isinstance(encoded, str):
            try:
                if self.window.restoreGeometry(QByteArray(base64.b64decode(encoded))):
                    return
            except (ValueError, TypeError):
                pass
        screen = self.qt_app.primaryScreen()
        area = screen.availableGeometry() if screen else None
        if area is not None:
            width = min(1280, int(area.width() * 0.82))
            height = min(860, int(area.height() * 0.86))
            self.window.resize(width, height)
            self.window.move(area.x() + (area.width() - width) // 2,
                             area.y() + (area.height() - height) // 2)
        else:
            self.window.resize(1200, 800)

    def on_window_close(self, event) -> None:
        self.write_state()
        for view in list(self.popups.values()):
            view.close()
        event.accept()
        QTimer.singleShot(0, self.qt_app.quit)

    # ── page events ────────────────────────────────────────────────────────────
    def on_title(self, title: str) -> None:
        title = (title or "").strip()
        self.window.setWindowTitle(title if title else app_name(self.app))

    def on_icon(self, icon: QIcon) -> None:
        if icon.isNull():
            return
        sizes = sorted(icon.availableSizes(), key=lambda size: size.width() * size.height())
        best = sizes[-1] if sizes else None
        if best is None or best.width() < 32:
            return
        pixmap = icon.pixmap(best)
        if best.width() < 128:
            pixmap = pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        buffer.close()
        # Keep the larger of what we had and what the site offers now.
        stored = int(self.state.get("icon_size", 0) or 0)
        if best.width() < stored and self.paths.icon_png.is_file():
            return
        try:
            path = policy.set_icon(self.app, bytes(data))
        except (OSError, policy.WebAppError):
            return
        self.state["icon_size"] = best.width()
        self.window.setWindowIcon(QIcon(str(path)))

    def on_renderer_gone(self, status, code) -> None:
        if status != QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus:
            QTimer.singleShot(600, self.view.reload)

    def on_fullscreen(self, request) -> None:
        request.accept()
        if request.toggleOn():
            self.window.showFullScreen()
        else:
            self.window.showNormal()

    def on_context_menu(self, position) -> None:
        menu = self.view.createStandardContextMenu()
        menu.addSeparator()
        reload_action = menu.addAction(words("reload"))
        reload_action.triggered.connect(self.view.reload)
        browser = menu.addAction(words("open_browser"))
        browser.triggered.connect(lambda: QDesktopServices.openUrl(self.view.url()))
        if ARABIC:
            menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        menu.popup(self.view.mapToGlobal(position))

    def install_shortcuts(self) -> None:
        def zoom(delta: float | None) -> None:
            value = 1.0 if delta is None else min(3.0, max(0.5, self.view.zoomFactor() + delta))
            self.view.setZoomFactor(value)

        for keys, action in (
            (QKeySequence.StandardKey.Refresh, self.view.reload),
            ("Ctrl+R", self.view.reload),
            (QKeySequence.StandardKey.Back, self.view.back),
            (QKeySequence.StandardKey.Forward, self.view.forward),
            (QKeySequence.StandardKey.ZoomIn, lambda: zoom(0.1)),
            ("Ctrl+=", lambda: zoom(0.1)),
            (QKeySequence.StandardKey.ZoomOut, lambda: zoom(-0.1)),
            ("Ctrl+0", lambda: zoom(None)),
            ("F11", self.toggle_fullscreen),
        ):
            shortcut = QShortcut(QKeySequence(keys), self.window)
            shortcut.activated.connect(action)

    def toggle_fullscreen(self) -> None:
        if self.window.isFullScreen():
            self.window.showNormal()
        else:
            self.window.showFullScreen()

    # ── popups (sign-in windows) ───────────────────────────────────────────────
    def popup_window_for(self, page: Page) -> QWebEngineView | None:
        return self.popups.get(id(page))

    def show_popup(self, page: Page) -> None:
        view = QWebEngineView()
        view.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        view.setPage(page)
        view.setWindowTitle(app_name(self.app))
        view.setWindowIcon(self.window.windowIcon())
        view.resize(560, 720)
        view.titleChanged.connect(view.setWindowTitle)
        view.destroyed.connect(lambda *_: self.popups.pop(id(page), None))
        self.popups[id(page)] = view
        view.show()

    def close_popup(self, page: Page) -> None:
        view = self.popups.pop(id(page), None)
        if view is not None:
            view.close()
        page.deleteLater()

    # ── permissions ────────────────────────────────────────────────────────────
    def on_permission(self, permission: QWebEnginePermission) -> None:
        names = PERMISSION_NAMES.get(permission.permissionType())
        origin = permission.origin().toString()
        if not names or not policy.origin_allowed(origin, self.app):
            permission.deny()
            return
        decisions = [self.permissions.decision(name) for name in names]
        if "refused" in decisions or "deny" in decisions:
            permission.deny()
            return
        if all(decision == "allow" for decision in decisions):
            permission.grant()
            return
        # Ask once per name that has no answer yet; remember the answer.
        self.pending.append(permission)
        for name, decision in zip(names, decisions):
            if decision != "ask":
                continue
            box = QMessageBox(self.window)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(words("ask_title"))
            box.setText(words("ask_body", app=app_name(self.app), what=words(name)))
            allow = box.addButton(words("allow"), QMessageBox.ButtonRole.AcceptRole)
            deny = box.addButton(words("deny"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(deny)
            box.setEscapeButton(deny)
            if ARABIC:
                box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            box.exec()
            answer = "allow" if box.clickedButton() is allow else "deny"
            try:
                self.permissions.set(name, answer)
            except (OSError, policy.WebAppError):
                pass
            if answer == "deny":
                break
        self.pending.remove(permission)
        if all(self.permissions.decision(name) == "allow" for name in names):
            permission.grant()
        else:
            permission.deny()

    # ── notifications and downloads ────────────────────────────────────────────
    def present_notification(self, notification) -> None:
        if self.permissions.decision("notifications") != "allow":
            return
        if not policy.origin_allowed(notification.origin().toString(), self.app):
            return
        keep = notification
        self.pending.append(keep)

        def clicked():
            self.raise_window()
            try:
                keep.click()
            except RuntimeError:
                pass

        notify(self.app, policy.icon_for(self.app), notification.title() or app_name(self.app),
               notification.message(), on_click=clicked)
        QTimer.singleShot(120_000, lambda: keep in self.pending and self.pending.remove(keep))

    def on_download(self, download: QWebEngineDownloadRequest) -> None:
        folder = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation) or str(Path.home() / "Downloads")
        Path(folder).mkdir(parents=True, exist_ok=True)
        download.setDownloadDirectory(folder)
        name = Path(download.downloadFileName() or "download").name
        candidate, number = name, 1
        while (Path(folder) / candidate).exists():
            stem, dot, suffix = name.partition(".")
            candidate = f"{stem} ({number}){dot}{suffix}"
            number += 1
        download.setDownloadFileName(candidate)

        def finished():
            if not download.isFinished():
                return
            state = download.state()
            key = "downloaded" if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted \
                else "download_failed"
            target = Path(download.downloadDirectory()) / download.downloadFileName()
            notify(self.app, policy.icon_for(self.app), app_name(self.app),
                   words(key, name=target.name),
                   on_click=lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent))))

        download.isFinishedChanged.connect(finished)
        download.accept()

    # ── single instance ────────────────────────────────────────────────────────
    def raise_window(self) -> None:
        if self.window.isMinimized():
            self.window.showNormal()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def listen(self, server: QLocalServer) -> None:
        def connection():
            socket = server.nextPendingConnection()
            if socket is None:
                return

            def ready():
                line = bytes(socket.readLine()).strip()
                if line == b"activate":
                    socket.write(b"ok\n")
                    socket.flush()
                    self.raise_window()
                elif line == b"quit":
                    socket.write(b"ok\n")
                    socket.flush()
                    self.window.close()
                else:
                    socket.write(b"no\n")
                socket.disconnectFromServer()

            socket.readyRead.connect(ready)

        server.newConnection.connect(connection)

    def start(self) -> None:
        self.window.show()
        self.view.load(QUrl(self.app.url))


def spellcheck_languages() -> list[str]:
    folder = Path(os.environ.get("QTWEBENGINE_DICTIONARIES_PATH",
                                 "/usr/lib64/qt6/qtwebengine_dictionaries"))
    try:
        names = {path.stem for path in folder.glob("*.bdic")}
    except OSError:
        return []
    chosen = []
    for preferred in (("ar_SA", "ar"), ("en_US", "en-US")):
        for name in preferred:
            if name in names:
                chosen.append(name)
                break
    return chosen


def hand_over(app_id: str) -> bool:
    """When this app already runs, raise it and return True."""
    socket = QLocalSocket()
    socket.connectToServer(str(policy.socket_path(app_id)))
    if not socket.waitForConnected(800):
        return False
    socket.write(b"activate\n")
    socket.flush()
    socket.waitForReadyRead(800)
    socket.disconnectFromServer()
    return True


def run(app: policy.WebApp, argv: list[str]) -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    QApplication.setDesktopFileName(app.desktop_id)
    QApplication.setApplicationName(app.desktop_id)
    qt_app = QApplication(argv[:1])
    if ARABIC:
        qt_app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    if hand_over(app.id):
        return 0
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    path = str(policy.socket_path(app.id))
    if not server.listen(path):
        QLocalServer.removeServer(path)
        if not server.listen(path):
            print(f"moos-webapp: cannot listen on {path}", file=sys.stderr)
    shell = Shell(app, qt_app)
    shell.listen(server)
    shell.start()
    code = qt_app.exec()
    server.close()
    QLocalServer.removeServer(path)
    return code

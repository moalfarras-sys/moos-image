"""MoOS web apps — a website that behaves like an installed application.

ChatGPT, Claude, Gemini, WhatsApp or Word on the web have no Linux program of their own, yet a
person expects each of them to be an app: its own icon in the menu and the dock, its own window,
its own sign-in that survives a restart, its own notifications. A browser tab is none of that.
Mo Store installs such a site as a MoOS web app; `moos-webapp <id>` draws it.

This module is the half without Qt, so every rule here is testable anywhere:

  * which web apps exist — ONLY the signed catalogue (/usr/share/moos/store/catalog.json)
    defines one. `moos-webapp` takes a catalogue id and nothing else: no address ever comes from
    argv, from a launcher, from a moos: link or from a web page;
  * where an app may go — its own HTTPS hosts and the sign-in pages of the identity providers its
    entry names stay inside the window; every other address opens in the person's browser. A
    frame inside a page may load any web page, never another program's address (moos:, file:);
  * what it may ask for — only the permissions its entry lists, each answered once by the person
    and changeable from Mo Store, which reads and writes the same small file;
  * the launcher Mo Store writes — `org.moos.webapp.<id>.desktop`, whose name IS the window's
    app id, so the dock shows the app's own icon.

The Qt half is moos_webapp_runtime.py. tests/test_moos_webapp.py holds both.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable
from urllib.parse import urlsplit

CATALOG = Path(os.environ.get("MOOS_STORE_CATALOG", "/usr/share/moos/store/catalog.json"))
RUNTIME = "/usr/bin/moos-webapp"
DESKTOP_PREFIX = "org.moos.webapp."
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
HOST_PATTERN = re.compile(r"^(\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
ACCENT_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")

# What a web app may be allowed to use, in the words Mo Store shows. A permission that is not in
# an app's catalogue entry is refused without asking.
PERMISSIONS = ("notifications", "microphone", "camera", "location", "clipboard", "screen")
DECISIONS = ("allow", "deny")

# Sign-in pages that must stay inside the app window: a sign-in that hops to the browser leaves
# its cookie there, and the app never learns that the person signed in. Main-frame only.
IDENTITY_PROVIDERS = {
    "google": ("accounts.google.com", "accounts.youtube.com"),
    "microsoft": ("login.microsoftonline.com", "login.live.com", "login.microsoft.com",
                  "account.live.com", "account.microsoft.com"),
    "apple": ("appleid.apple.com", "idmsa.apple.com"),
    "github": ("github.com",),
}

# Store categories -> freedesktop menu categories, so an installed web app lands in the same
# menu folder as a native app of its kind.
MENU_CATEGORIES = {
    "ai": "Office;Utility;",
    "work": "Office;",
    "office": "Office;",
    "comm": "Network;InstantMessaging;",
    "internet": "Network;WebBrowser;",
    "graphics": "Graphics;",
    "art": "Graphics;",
    "media": "AudioVideo;",
    "dev": "Development;",
    "edu": "Education;",
    "fun": "Game;",
    "games": "Game;",
    "util": "Utility;",
    "ess": "Utility;",
}


class WebAppError(Exception):
    """A refusal with a stable code; the caller owns the words."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class WebApp:
    id: str
    name_en: str
    name_ar: str
    summary_en: str
    summary_ar: str
    url: str
    hosts: tuple[str, ...]
    identity: tuple[str, ...]
    permissions: tuple[str, ...]
    accent: str
    category: str
    developer: str

    @property
    def desktop_id(self) -> str:
        return DESKTOP_PREFIX + self.id

    @property
    def start_host(self) -> str:
        return urlsplit(self.url).hostname or ""


# ── The catalogue ────────────────────────────────────────────────────────────────────────────

def load_catalog(path: Path | None = None) -> dict:
    source = Path(path) if path is not None else CATALOG
    try:
        with source.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        raise WebAppError("catalog_unreadable", str(error)) from error
    if not isinstance(data, dict) or not isinstance(data.get("apps"), list):
        raise WebAppError("catalog_unreadable", "no apps list")
    return data


def _text(value: object, limit: int = 300) -> str:
    """One display line: no control characters, bounded length."""
    if not isinstance(value, str):
        return ""
    cleaned = "".join(ch for ch in value if ch >= " " and ch != "\x7f")
    return cleaned.strip()[:limit]


def _host_ok(pattern: str) -> bool:
    return bool(HOST_PATTERN.fullmatch(pattern))


def parse_entry(entry: dict) -> WebApp:
    """Validate one catalogue entry as a web app; raise WebAppError with the first defect."""
    if not isinstance(entry, dict):
        raise WebAppError("not_webapp")
    app_id = entry.get("id")
    install = entry.get("install")
    if not isinstance(app_id, str) or not ID_PATTERN.fullmatch(app_id):
        raise WebAppError("bad_id", repr(app_id))
    if entry.get("source") != "moos" or not isinstance(install, dict) or install.get("kind") != "webapp":
        raise WebAppError("not_webapp", app_id)
    url = install.get("url")
    if not isinstance(url, str):
        raise WebAppError("bad_url", app_id)
    parts = urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.port not in (None, 443) or "\\" in url or any(ch <= " " for ch in url)):
        raise WebAppError("bad_url", url)
    hosts = install.get("hosts")
    if not isinstance(hosts, list) or not hosts or len(hosts) > 24:
        raise WebAppError("bad_hosts", app_id)
    clean_hosts: list[str] = []
    for host in hosts:
        if not isinstance(host, str) or not _host_ok(host.lower()):
            raise WebAppError("bad_hosts", repr(host))
        clean_hosts.append(host.lower())
    if not host_matches(parts.hostname.lower(), clean_hosts):
        raise WebAppError("start_outside_hosts", url)
    identity = install.get("identity", [])
    if not isinstance(identity, list) or any(item not in IDENTITY_PROVIDERS for item in identity):
        raise WebAppError("bad_identity", app_id)
    permissions = install.get("permissions", [])
    if (not isinstance(permissions, list) or any(item not in PERMISSIONS for item in permissions)
            or len(set(permissions)) != len(permissions)):
        raise WebAppError("bad_permissions", app_id)
    accent = install.get("accent", "#6d5dfc")
    if not isinstance(accent, str) or not ACCENT_PATTERN.fullmatch(accent):
        raise WebAppError("bad_accent", app_id)
    name_en = _text(entry.get("en"), 80)
    if not name_en:
        raise WebAppError("bad_name", app_id)
    return WebApp(
        id=app_id,
        name_en=name_en,
        name_ar=_text(entry.get("ar"), 80) or name_en,
        summary_en=_text(entry.get("desc_en")),
        summary_ar=_text(entry.get("desc_ar")),
        url=url,
        hosts=tuple(clean_hosts),
        identity=tuple(identity),
        permissions=tuple(permissions),
        accent=accent.lower(),
        category=_text(entry.get("cat"), 24),
        developer=_text(entry.get("developer"), 80),
    )


def webapps(catalog: dict) -> dict[str, WebApp]:
    """Every valid web app in the catalogue, by id. Invalid entries are skipped, not trusted."""
    found: dict[str, WebApp] = {}
    for entry in catalog.get("apps", []):
        install = entry.get("install") if isinstance(entry, dict) else None
        if not isinstance(install, dict) or install.get("kind") != "webapp":
            continue
        try:
            app = parse_entry(entry)
        except WebAppError:
            continue
        found.setdefault(app.id, app)
    return found


def lookup(app_id: str, catalog_path: Path | None = None) -> WebApp:
    if not isinstance(app_id, str) or not ID_PATTERN.fullmatch(app_id):
        raise WebAppError("bad_id", repr(app_id))
    catalog = load_catalog(catalog_path)
    for entry in catalog.get("apps", []):
        if isinstance(entry, dict) and entry.get("id") == app_id:
            return parse_entry(entry)
    raise WebAppError("unknown_app", app_id)


# ── Where an address belongs ─────────────────────────────────────────────────────────────────

def host_matches(host: str, patterns: Iterable[str]) -> bool:
    """`*.example.com` matches every subdomain of example.com (not example.com itself)."""
    host = (host or "").lower().rstrip(".")
    if not host:
        return False
    for pattern in patterns:
        pattern = pattern.lower()
        if pattern.startswith("*."):
            suffix = pattern[1:]
            if host.endswith(suffix) and len(host) > len(suffix):
                return True
        elif host == pattern:
            return True
    return False


def identity_hosts(app: WebApp) -> tuple[str, ...]:
    hosts: list[str] = []
    for provider in app.identity:
        hosts.extend(IDENTITY_PROVIDERS.get(provider, ()))
    return tuple(hosts)


def navigation(url: str, app: WebApp) -> str:
    """'inside' (stay in the app window), 'external' (hand to the browser) or 'block'."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "block"
    scheme = (parts.scheme or "").lower()
    if scheme == "about" and url in ("about:blank", "about:srcdoc"):
        return "inside"
    if scheme == "https":
        host = (parts.hostname or "").lower()
        if host_matches(host, app.hosts) or host in identity_hosts(app):
            return "inside"
        return "external" if host else "block"
    if scheme in ("http", "mailto", "tel"):
        return "external"
    # file:, data:, javascript:, blob: at the top level, moos:, and anything unknown.
    return "block"


# The browser's own documents that real apps build frames from: WhatsApp, Gmail, Teams and Office
# all draw parts of themselves in blob: and data: frames (and in about:blank and about:srcdoc,
# matched by name below).
FRAME_DOCUMENT_SCHEMES = ("blob", "data")


def frame_navigation(url: str, app: WebApp) -> str:
    """Where an address opened inside one of the page's frames (an iframe) goes: 'inside',
    'external' or 'block', as navigation() answers for the window.

    A frame belongs to the page around it (an advert, a map, an embedded video, a sign-in
    button), so it may load any web page, another host's included, and the browser's own frame
    documents. Any other address is not a page but a door out of it — moos:, file:, appstream:,
    ssh:, a protocol the desktop would hand to another program — and a frame gets exactly the
    window's answer for it: mail and phone links open in their apps, everything else nowhere.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "block"
    scheme = (parts.scheme or "").lower()
    if scheme in ("http", "https"):
        return "inside" if parts.hostname else "block"
    if scheme in FRAME_DOCUMENT_SCHEMES:
        return "inside"
    if scheme == "about" and parts.path in ("blank", "srcdoc"):
        return "inside"
    return navigation(url, app)


def origin_allowed(origin: str, app: WebApp) -> bool:
    """A permission prompt is only ever answered for the app's own HTTPS hosts."""
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    return parts.scheme == "https" and host_matches(parts.hostname or "", app.hosts)


# ── Where an app keeps things ────────────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class Paths:
    data: Path
    profile: Path
    cache: Path
    launcher: Path
    icon_png: Path
    icon_svg: Path
    permissions: Path
    window: Path


def paths(app_id: str, home: Path | None = None) -> Paths:
    """Where one app lives. With no `home`, the person's XDG folders; with one, under it only."""
    if not ID_PATTERN.fullmatch(app_id or ""):
        raise WebAppError("bad_id", repr(app_id))
    if home is None:
        base = Path.home()
        data_home = Path(os.environ.get("XDG_DATA_HOME") or base / ".local/share")
        cache_home = Path(os.environ.get("XDG_CACHE_HOME") or base / ".cache")
    else:
        data_home = Path(home) / ".local/share"
        cache_home = Path(home) / ".cache"
    data = data_home / "moos/webapps" / app_id
    return Paths(
        data=data,
        profile=data / "profile",
        cache=cache_home / "moos/webapps" / app_id,
        launcher=data_home / "applications" / f"{DESKTOP_PREFIX}{app_id}.desktop",
        icon_png=data / "icon.png",
        icon_svg=data / "icon.svg",
        permissions=data / "permissions.json",
        window=data / "window.json",
    )


def _atomic_write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


# ── Permissions, shared with Mo Store ────────────────────────────────────────────────────────

class PermissionStore:
    """The person's answers for one web app: {"version": 1, "decisions": {name: allow|deny}}.

    A name that the app's catalogue entry does not list is always refused and is never stored.
    """

    def __init__(self, app: WebApp, path: Path) -> None:
        self.app = app
        self.path = Path(path)

    def _read(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        decisions = data.get("decisions") if isinstance(data, dict) else None
        if not isinstance(decisions, dict):
            return {}
        return {name: value for name, value in decisions.items()
                if name in self.app.permissions and value in DECISIONS}

    def decision(self, name: str) -> str:
        """'allow', 'deny', 'ask' (allowed by the catalogue, not yet answered) or 'refused'."""
        if name not in self.app.permissions:
            return "refused"
        return self._read().get(name, "ask")

    def snapshot(self) -> dict[str, str]:
        return {name: self.decision(name) for name in self.app.permissions}

    def set(self, name: str, value: str | None) -> None:
        if name not in self.app.permissions:
            raise WebAppError("permission_not_offered", name)
        if value is not None and value not in DECISIONS:
            raise WebAppError("bad_decision", repr(value))
        decisions = self._read()
        if value is None:
            decisions.pop(name, None)
        else:
            decisions[name] = value
        _atomic_write(self.path, json.dumps({"version": 1, "decisions": decisions},
                                            indent=1, sort_keys=True) + "\n", 0o600)


# ── The launcher and its icon ────────────────────────────────────────────────────────────────

def _desktop_value(value: str) -> str:
    """Desktop Entry string escaping for one line; the catalogue text is trusted but bounded."""
    value = _text(value)
    return value.replace("\\", "\\\\").replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _initials(name: str) -> str:
    words = [word for word in re.split(r"[\s._-]+", name) if word]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].capitalize() if len(words[0]) > 1 else words[0].upper()
    return (words[0][0] + words[1][0]).upper()


def fallback_icon_svg(app: WebApp) -> str:
    """A MoOS-styled tile with the app's initials, shown until the site's own icon arrives."""
    initials = "".join(ch for ch in _initials(app.name_en) if ch.isalnum())[:2] or "W"
    accent = app.accent
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{accent}"/>'
        f'<stop offset="1" stop-color="{accent}" stop-opacity="0.72"/>'
        '</linearGradient></defs>'
        '<rect x="12" y="12" width="232" height="232" rx="56" fill="url(#g)"/>'
        '<rect x="12.5" y="12.5" width="231" height="231" rx="55.5" fill="none" '
        'stroke="#ffffff" stroke-opacity="0.28"/>'
        '<text x="128" y="128" dy="0.35em" text-anchor="middle" '
        'font-family="Inter, Noto Sans, sans-serif" font-size="104" font-weight="700" '
        f'fill="#ffffff">{initials}</text></svg>\n'
    )


def icon_for(app: WebApp, home: Path | None = None) -> Path:
    found = paths(app.id, home)
    return found.icon_png if found.icon_png.is_file() else found.icon_svg


def launcher_text(app: WebApp, icon: Path) -> str:
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.5",
        f"Name={_desktop_value(app.name_en)}",
        f"Name[ar]={_desktop_value(app.name_ar)}",
    ]
    if app.summary_en:
        lines.append(f"Comment={_desktop_value(app.summary_en)}")
    if app.summary_ar:
        lines.append(f"Comment[ar]={_desktop_value(app.summary_ar)}")
    lines += [
        f"Exec={RUNTIME} {app.id}",
        f"TryExec={RUNTIME}",
        f"Icon={icon}",
        "Terminal=false",
        f"Categories={MENU_CATEGORIES.get(app.category, 'Network;')}",
        f"StartupWMClass={app.desktop_id}",
        "StartupNotify=true",
        f"X-MoOS-WebApp={app.id}",
        "",
    ]
    return "\n".join(lines)


def install(app: WebApp, home: Path | None = None) -> Paths:
    """Write the launcher (and a fallback icon). Idempotent; keeps the person's data."""
    found = paths(app.id, home)
    found.data.mkdir(parents=True, exist_ok=True)
    os.chmod(found.data, 0o700)
    if not found.icon_png.is_file():
        _atomic_write(found.icon_svg, fallback_icon_svg(app))
    _atomic_write(found.launcher, launcher_text(app, icon_for(app, home)))
    return found


def set_icon(app: WebApp, png: bytes, home: Path | None = None) -> Path:
    """Keep the site's own icon (PNG bytes) and point the launcher at it."""
    if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > 4 * 1024 * 1024:
        raise WebAppError("bad_icon")
    found = paths(app.id, home)
    found.data.mkdir(parents=True, exist_ok=True)
    temporary = found.icon_png.with_suffix(".png.new")
    temporary.write_bytes(png)
    os.replace(temporary, found.icon_png)
    if found.launcher.is_file():
        _atomic_write(found.launcher, launcher_text(app, found.icon_png))
    return found.icon_png


def is_installed(app_id: str, home: Path | None = None) -> bool:
    launcher = paths(app_id, home).launcher
    try:
        text = launcher.read_text(encoding="utf-8")
    except OSError:
        return False
    return f"\nX-MoOS-WebApp={app_id}\n" in text


def socket_path(app_id: str) -> Path:
    """The running window listens here; a second launch raises it, Mo Store can ask it to close."""
    if not ID_PATTERN.fullmatch(app_id or ""):
        raise WebAppError("bad_id", repr(app_id))
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime) / f"moos-webapp-{app_id}.socket"


def ask_running(app_id: str, message: str, timeout: float = 2.0) -> bool:
    """Send 'activate' or 'quit' to a running window. False when none answers."""
    import socket

    if message not in ("activate", "quit"):
        raise WebAppError("bad_message", message)
    path = socket_path(app_id)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(path))
            client.sendall(message.encode() + b"\n")
            return client.recv(16).startswith(b"ok")
    except OSError:
        return False


def installed_ids(home: Path | None = None) -> list[str]:
    folder = paths("probe", home).launcher.parent
    found = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    for name in names:
        if not (name.startswith(DESKTOP_PREFIX) and name.endswith(".desktop")):
            continue
        app_id = name[len(DESKTOP_PREFIX):-len(".desktop")]
        if ID_PATTERN.fullmatch(app_id) and is_installed(app_id, home):
            found.append(app_id)
    return found


def remove(app_id: str, home: Path | None = None, *, delete_data: bool = False) -> bool:
    """Remove the launcher; with delete_data also the sign-in, storage, cache and answers."""
    found = paths(app_id, home)
    removed = False
    if found.launcher.is_file() and is_installed(app_id, home):
        found.launcher.unlink()
        removed = True
    if delete_data:
        import shutil
        import time

        # A window that is still open holds its storage; close it before deleting under it.
        if home is None and ask_running(app_id, "quit"):
            deadline = time.monotonic() + 5.0
            while socket_path(app_id).exists() and time.monotonic() < deadline:
                time.sleep(0.1)
        for folder in (found.data, found.cache):
            if folder.is_dir() and not folder.is_symlink():
                shutil.rmtree(folder)
                removed = True
    return removed

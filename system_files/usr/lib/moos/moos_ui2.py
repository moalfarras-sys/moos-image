"""MoOS UI2 — the one place the look of a first-party GTK app is defined.

This lived inside mo-pc-remote, and then MoOS grew two more GTK apps (the updater and the
recovery front-end). Three copies of a palette is three chances for MoOS to be three slightly
different shades of itself, and the first person to notice is always the user.

So: one module, imported by every first-party GTK app. The Plasma side of the desktop reads the
same rails from the UI2 look-and-feel; this is that palette expressed for GTK.

Usage:

    from moos_ui2 import MoOSApp

    class Updater(MoOSApp):
        APP_ID = "org.moos.updater"     # MUST equal the .desktop basename, or the dock draws
        TITLE  = "MoOS Updater"          # the app twice with two different icons
        def build(self, page):
            page.append(self.card(...))

    Updater().run()
"""
import configparser
import os
from pathlib import Path
import re

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib  # noqa: E402

# MoOS UI2 semantic colours — the Graphite (dark) and Tidal (light) rails.
UI2_DARK = {
    "canvas": "#14191C", "surface": "#1D2529", "card": "#232D32",
    "raised": "#2C383E", "primary": "#4ED7C8", "secondary": "#78AFFF", "luminous": "#A8F1E8",
    "positive": "#69D9A5", "warning": "#F4C56A", "negative": "#FF7D88",
    "text": "#E8F1EF", "muted": "#9CAFAC", "outline": "#415158",
    "on_accent": "#102522", "on_negative": "#14191C",
    "shadow": "rgba(4, 10, 12, 0.42)",
}
UI2_LIGHT = {
    "canvas": "#D8EBE7", "surface": "#C9E2DD", "card": "#E1F0EC",
    "raised": "#B8D8D2", "primary": "#006D67", "secondary": "#1D6278", "luminous": "#0B6965",
    "positive": "#086B4B", "warning": "#7B520F", "negative": "#A52F3F",
    "text": "#17302E", "muted": "#3D5854", "outline": "#527F79",
    "on_accent": "#E8F1EF", "on_negative": "#D8EBE7",
    "shadow": "rgba(23, 48, 46, 0.16)",
}

PALETTE_ROLES = frozenset({
    "canvas", "surface", "card", "raised", "primary", "secondary",
    "luminous", "positive", "warning", "negative", "text", "muted",
    "outline", "on_accent", "on_negative", "shadow",
})
_SAFE_SCHEME_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_RTL_LANGUAGES = frozenset({"ar", "fa", "he", "ur"})


def session_language(environment=None):
    """Return the active POSIX session language without depending on gettext.

    These small recovery/control applications ship their Arabic and English
    strings in-tree and must still choose correctly when no translation catalog
    is installed. LC_ALL and LC_MESSAGES outrank LANG exactly as the locale
    contract specifies.
    """
    env = os.environ if environment is None else environment
    raw = (
        env.get("LC_ALL")
        or env.get("LC_MESSAGES")
        or env.get("LANG")
        or "en"
    )
    return raw.split(".", 1)[0].split("@", 1)[0].replace("-", "_").split("_", 1)[0].lower()


def ui_is_rtl(environment=None):
    return session_language(environment) in _RTL_LANGUAGES


def local_text(arabic, english, environment=None):
    """Choose one visible locale; never concatenate two UI translations."""
    return arabic if ui_is_rtl(environment) else english


def logical_start(environment=None):
    """Gtk.Label.xalign for logical start rather than physical left."""
    return 1.0 if ui_is_rtl(environment) else 0.0


def _rgb(value):
    parts = tuple(int(part.strip()) for part in value.split(","))
    if len(parts) != 3 or any(channel < 0 or channel > 255 for channel in parts):
        raise ValueError(f"invalid KDE RGB value: {value!r}")
    return parts


def _hex(colour):
    return "#{:02X}{:02X}{:02X}".format(*colour)


def _luminance(colour):
    channels = []
    for channel in colour:
        value = channel / 255
        channels.append(
            value / 12.92
            if value <= 0.04045
            else ((value + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(first, second):
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _mix(first, second, amount):
    return tuple(
        round(first[index] + (second[index] - first[index]) * amount)
        for index in range(3)
    )


def _accessible_outline(canvas, surface, card, raised, muted):
    """Return the quietest muted-derived edge visible on every UI2 surface."""
    backgrounds = (canvas, surface, card, raised)
    for step in range(1, 101):
        candidate = _mix(card, muted, step / 100)
        if all(_contrast(candidate, background) >= 3.0
               for background in backgrounds):
            return candidate
    return muted


def _kconfig(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    with Path(path).open(encoding="utf-8") as source:
        parser.read_file(source)
    return parser


def palette_from_color_scheme(path):
    """Map one KDE ``.colors`` file to MoOS GTK semantic roles.

    No family names or colours are hardcoded here.  All sixteen MoOS palettes
    expose the same KColorScheme roles, and user-installed schemes can use the
    same path when they provide a complete, accessible relationship.
    """
    scheme = _kconfig(path)

    def colour(section, key):
        try:
            return _rgb(scheme[section][key])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"{path}: missing/invalid {section}/{key}") from exc

    view = "Colors:View"
    window = "Colors:Window"
    button = "Colors:Button"
    selection = "Colors:Selection"
    complementary = "Colors:Complementary"

    canvas = colour(view, "BackgroundNormal")
    surface = colour(window, "BackgroundNormal")
    card = colour(view, "BackgroundAlternate")
    raised = colour(button, "BackgroundNormal")
    primary = colour(selection, "BackgroundNormal")
    secondary = colour(selection, "BackgroundAlternate")
    luminous = colour(selection, "DecorationHover")
    positive = colour(window, "ForegroundPositive")
    warning = colour(window, "ForegroundNeutral")
    negative = colour(window, "ForegroundNegative")
    text = colour(window, "ForegroundNormal")
    muted = colour(window, "ForegroundInactive")
    on_accent = colour(selection, "ForegroundNormal")
    # on_negative is the ink drawn ON a negative fill inside NORMAL windows, so
    # it pairs with this scheme's own light/dark side — the View canvas.  It
    # used to read Complementary's background, which only worked while light
    # schemes (wrongly) declared a light Complementary; since 2026-08-02 the
    # Complementary set is the family's DARK session surface on every palette
    # (KDE's actual semantic), and reading it here paired a dark ink with the
    # light scheme's dark negative at 2.69:1.  The session surfaces get their
    # own internally-consistent pairing from the Complementary set directly.
    on_negative = canvas
    outline = _accessible_outline(canvas, surface, card, raised, muted)
    is_dark = _luminance(canvas) < 0.45
    shadow_alpha = 0.42 if is_dark else 0.16

    palette = {
        "canvas": _hex(canvas),
        "surface": _hex(surface),
        "card": _hex(card),
        "raised": _hex(raised),
        "primary": _hex(primary),
        "secondary": _hex(secondary),
        "luminous": _hex(luminous),
        "positive": _hex(positive),
        "warning": _hex(warning),
        "negative": _hex(negative),
        "text": _hex(text),
        "muted": _hex(muted),
        "outline": _hex(outline),
        "on_accent": _hex(on_accent),
        "on_negative": _hex(on_negative),
        "shadow": (
            f"rgba({canvas[0]}, {canvas[1]}, {canvas[2]}, {shadow_alpha:.2f})"
        ),
    }

    # A malformed/custom scheme must not make a first-party control unreadable.
    # Fall back at the caller rather than silently accepting a broken pairing.
    critical_pairs = (
        (text, canvas, "text/canvas"),
        (text, card, "text/card"),
        (text, raised, "text/raised"),
        (text, surface, "text/surface"),
        (muted, canvas, "muted/canvas"),
        (muted, card, "muted/card"),
        (muted, surface, "muted/surface"),
        (positive, canvas, "positive/canvas"),
        (positive, card, "positive/card"),
        (warning, canvas, "warning/canvas"),
        (warning, card, "warning/card"),
        (negative, canvas, "negative/canvas"),
        (negative, card, "negative/card"),
        (on_accent, primary, "on_accent/primary"),
        (on_negative, negative, "on_negative/negative"),
    )
    for foreground, background, label in critical_pairs:
        ratio = _contrast(foreground, background)
        if ratio < 4.5:
            raise ValueError(f"{path}: {label} contrast is only {ratio:.2f}:1")
    for background, label in (
        (canvas, "canvas"),
        (surface, "surface"),
        (card, "card"),
        (raised, "raised"),
    ):
        if _contrast(outline, background) < 3.0:
            raise ValueError(f"{path}: outline/{label} contrast is below 3:1")
    return palette


def kdeglobals_path(config_home=None):
    base = Path(
        config_home
        if config_home is not None
        else os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    )
    return base / "kdeglobals"


def active_color_scheme(config_path=None):
    path = Path(config_path) if config_path is not None else kdeglobals_path()
    try:
        name = _kconfig(path)["General"]["ColorScheme"].strip()
    except (OSError, KeyError, configparser.Error):
        return None
    return name if _SAFE_SCHEME_NAME.fullmatch(name) else None


def _data_roots(data_dirs=None):
    if data_dirs is not None:
        return tuple(Path(path) for path in data_dirs)
    home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    system = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    return (home, *(Path(path) for path in system.split(":") if path))


def find_color_scheme(name, data_dirs=None):
    if not name or not _SAFE_SCHEME_NAME.fullmatch(name):
        return None
    for root in _data_roots(data_dirs):
        candidate = root / "color-schemes" / f"{name}.colors"
        if candidate.is_file():
            return candidate
    return None


def active_ui2_palette(config_path=None, data_dirs=None, prefers_dark=None):
    """Resolve the live KDE ColorScheme, failing safely to Graphite/Tidal."""
    dark = gtk_prefers_dark() if prefers_dark is None else bool(prefers_dark)
    fallback = UI2_DARK if dark else UI2_LIGHT
    try:
        name = active_color_scheme(config_path)
        path = find_color_scheme(name, data_dirs)
        if path is None:
            return dict(fallback)
        return palette_from_color_scheme(path)
    except (OSError, ValueError, configparser.Error):
        return dict(fallback)


def watch_kdeglobals(callback, config_path=None):
    """Watch the config directory so atomic KDE rewrites are observed too."""
    target = Path(config_path) if config_path is not None else kdeglobals_path()
    if not target.parent.is_dir():
        return None
    try:
        monitor = Gio.File.new_for_path(str(target.parent)).monitor_directory(
            Gio.FileMonitorFlags.NONE, None
        )
    except GLib.Error:
        return None

    def changed(_monitor, changed_file, other_file, _event):
        paths = {
            file.get_path()
            for file in (changed_file, other_file)
            if file is not None and file.get_path()
        }
        if str(target) in paths:
            callback()

    monitor.connect("changed", changed)
    return monitor


def ui2_css(p):
    return f"""
@define-color ui2_canvas {p['canvas']};
@define-color ui2_surface {p['surface']};
@define-color ui2_card {p['card']};
@define-color ui2_raised {p['raised']};
@define-color ui2_primary {p['primary']};
@define-color ui2_secondary {p['secondary']};
@define-color ui2_luminous {p['luminous']};
@define-color ui2_positive {p['positive']};
@define-color ui2_warning {p['warning']};
@define-color ui2_negative {p['negative']};
@define-color ui2_text {p['text']};
@define-color ui2_muted {p['muted']};
@define-color ui2_outline {p['outline']};
@define-color ui2_on_accent {p['on_accent']};
@define-color ui2_on_negative {p['on_negative']};

window.moos-ui2 {{
  background-color: @ui2_canvas;
  color: @ui2_text;
}}
window.moos-ui2 .remote-shell,
window.moos-ui2 .moos-shell {{
  background-color: transparent;
  color: @ui2_text;
}}
window.moos-ui2 .title-1,
window.moos-ui2 .heading {{ color: @ui2_text; }}
window.moos-ui2 .dim-label {{ color: @ui2_muted; }}
window.moos-ui2 .ui2-card {{
  background-color: @ui2_card;
  color: @ui2_text;
  border: 1px solid @ui2_outline;
  border-radius: 18px;
  padding: 14px;
  box-shadow: 0 10px 28px {p['shadow']};
}}
window.moos-ui2 .ui2-icon-plate {{
  background-color: @ui2_primary;
  color: @ui2_on_accent;
  border: 1px solid @ui2_outline;
  border-radius: 16px;
  padding: 12px;
}}
window.moos-ui2 .ui2-icon-plate image {{ color: @ui2_on_accent; }}
window.moos-ui2 .ui2-kicker {{
  color: @ui2_muted;
  font-size: 0.86em;
}}
window.moos-ui2 .ui2-value {{
  color: @ui2_text;
  font-size: 1.28em;
  font-weight: 700;
}}
window.moos-ui2 .ui2-badge {{
  background-color: @ui2_surface;
  color: @ui2_positive;
  border: 1px solid @ui2_outline;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 0.84em;
}}
window.moos-ui2 .ui2-status {{
  color: @ui2_text;
  font-weight: 600;
}}
window.moos-ui2 .ui2-details {{ color: @ui2_muted; }}
window.moos-ui2 .ui2-log-frame {{
  background-color: @ui2_surface;
  border: 1px solid @ui2_outline;
  border-radius: 12px;
}}
window.moos-ui2 button {{
  background-color: @ui2_raised;
  color: @ui2_text;
  border: 1px solid @ui2_outline;
  border-radius: 12px;
  padding: 10px 16px;
}}
window.moos-ui2 button:hover {{
  border-color: @ui2_outline;
  box-shadow: 0 0 0 2px @ui2_primary;
}}
window.moos-ui2 button:focus-visible {{
  border-color: @ui2_outline;
  outline: 2px solid @ui2_outline;
  outline-offset: 2px;
}}
window.moos-ui2 button:active {{ background-color: @ui2_surface; }}
window.moos-ui2 button.suggested-action {{
  background-image: none;
  background-color: @ui2_primary;
  color: @ui2_on_accent;
  border-color: @ui2_outline;
}}
window.moos-ui2 button.destructive-action {{
  background-color: @ui2_negative;
  color: @ui2_on_negative;
  border-color: transparent;
}}
window.moos-ui2 button:disabled {{
  background-color: @ui2_surface;
  color: @ui2_muted;
  border-color: @ui2_outline;
}}
window.moos-ui2 .success {{ color: @ui2_positive; }}
window.moos-ui2 .warn    {{ color: @ui2_warning; }}
window.moos-ui2 .error   {{ color: @ui2_negative; }}
window.moos-ui2 .ui2-log,
window.moos-ui2 .ui2-log text {{
  background-color: @ui2_surface;
  color: @ui2_text;
}}
window.moos-ui2 progressbar progress {{
  background-image: linear-gradient(to right, @ui2_primary, @ui2_secondary);
  border: 1px solid @ui2_outline;
  border-radius: 999px;
}}
window.moos-ui2 progressbar trough {{
  background-color: @ui2_surface;
  border-radius: 999px;
}}
window.moos-ui2 selection {{
  background-color: @ui2_primary;
  color: @ui2_on_accent;
}}
window.moos-ui2 scrollbar trough {{
  background-color: @ui2_surface;
}}
window.moos-ui2 scrollbar slider {{
  background-color: @ui2_outline;
  border-radius: 999px;
}}
"""


def gtk_prefers_dark():
    settings = Gtk.Settings.get_default()
    if settings is None:
        return True
    try:
        if settings.get_property("gtk-application-prefer-dark-theme"):
            return True
        return "dark" in (settings.get_property("gtk-theme-name") or "").lower()
    except (TypeError, AttributeError):
        return True


class UI2StyleController:
    """Bind one CSS provider to the active KDE scheme and restyle it live."""

    DEBOUNCE_MS = 75

    def __init__(
        self,
        provider,
        *,
        config_path=None,
        data_dirs=None,
        settings=None,
        prefers_dark=None,
    ):
        self.provider = provider
        self.config_path = (
            Path(config_path) if config_path is not None else kdeglobals_path()
        )
        self.data_dirs = data_dirs
        self.prefers_dark = prefers_dark
        self._pending_source = 0
        self._monitor = watch_kdeglobals(self.schedule_restyle, self.config_path)
        self._settings = Gtk.Settings.get_default() if settings is None else settings
        if self._settings:
            self._settings.connect(
                "notify::gtk-application-prefer-dark-theme", self.schedule_restyle
            )
            self._settings.connect("notify::gtk-theme-name", self.schedule_restyle)
        self.restyle()

    def _fallback_prefers_dark(self):
        return (
            self.prefers_dark()
            if callable(self.prefers_dark)
            else self.prefers_dark
        )

    def restyle(self, *_):
        self._pending_source = 0
        palette = active_ui2_palette(
            config_path=self.config_path,
            data_dirs=self.data_dirs,
            prefers_dark=self._fallback_prefers_dark(),
        )
        css = ui2_css(palette)
        if hasattr(self.provider, "load_from_string"):
            self.provider.load_from_string(css)
        else:  # GTK < 4.12 compatibility
            self.provider.load_from_data(css)
        return False

    def schedule_restyle(self, *_):
        if not self._pending_source:
            self._pending_source = GLib.timeout_add(
                self.DEBOUNCE_MS, self.restyle
            )
        return False

    def close(self):
        if self._pending_source:
            GLib.source_remove(self._pending_source)
            self._pending_source = 0
        if self._monitor:
            self._monitor.cancel()
            self._monitor = None


class MoOSApp(Gtk.Application):
    """A first-party MoOS window: one instance, the right icon, the MoOS palette.

    Subclasses set APP_ID/TITLE and implement build(page).

    APP_ID is load-bearing twice over. It is the GApplication id, so it is the Wayland app_id
    KWin sees — and Plasma matches a window to its launcher BY that id. Set it to anything other
    than the .desktop file's basename and the dock shows the app twice, with two different icons:
    the pinned launcher, and an unrecognised window beside it. It is also what makes the app
    unique, so a second click reaches the window you already have instead of opening another one.
    """

    APP_ID = "org.moos.app"
    TITLE = "MoOS"
    SIZE = (760, 640)

    def __init__(self):
        super().__init__(application_id=self.APP_ID)

    def do_activate(self):
        # Second launch: show the window that exists. GApplication is unique by default, so the
        # second process correctly hands off to this one — and what it hands off TO is this
        # method. Build a new window here and the user gets two, inside one process.
        existing = self.get_active_window()
        if existing is not None:
            existing.present()
            return

        self.win = Gtk.ApplicationWindow(application=self, title=self.TITLE)
        self.win.set_direction(
            Gtk.TextDirection.RTL if ui_is_rtl() else Gtk.TextDirection.LTR
        )
        self.win.add_css_class("moos-ui2")
        self.win.set_default_size(*self.SIZE)

        self._css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._style_controller = UI2StyleController(self._css)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                       margin_top=22, margin_bottom=22, margin_start=24, margin_end=24)
        page.add_css_class("moos-shell")
        self.build(page)

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_child(page)
        self.win.set_child(scroller)
        self.win.present()

    # -- building blocks -------------------------------------------------------

    def build(self, page):
        raise NotImplementedError

    @staticmethod
    def card(*children, spacing=10):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        box.add_css_class("ui2-card")
        for c in children:
            box.append(c)
        return box

    @staticmethod
    def title(text):
        lbl = Gtk.Label(label=text, xalign=logical_start())
        lbl.add_css_class("title-1")
        return lbl

    @staticmethod
    def subtitle(text):
        lbl = Gtk.Label(label=text, xalign=logical_start(), wrap=True)
        lbl.add_css_class("dim-label")
        return lbl

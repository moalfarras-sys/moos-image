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
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib  # noqa: E402

# MoOS UI2 semantic colours — the Graphite (dark) and Tidal (light) rails.
UI2_DARK = {
    "canvas": "#14191C", "surface": "#1D2529", "card": "#232D32",
    "raised": "#2C383E", "primary": "#4ED7C8", "secondary": "#78AFFF", "luminous": "#A8F1E8",
    "positive": "#69D9A5", "warning": "#F4C56A", "negative": "#FF7D88",
    "text": "#E8F1EF", "muted": "#9CAFAC", "outline": "#415158",
    "on_accent": "#102522", "shadow": "rgba(4, 10, 12, 0.42)",
}
UI2_LIGHT = {
    "canvas": "#D8EBE7", "surface": "#C9E2DD", "card": "#E1F0EC",
    "raised": "#B8D8D2", "primary": "#006D67", "secondary": "#1D6278", "luminous": "#0B6965",
    "positive": "#086B4B", "warning": "#7B520F", "negative": "#A52F3F",
    "text": "#17302E", "muted": "#466360", "outline": "#527F79",
    "on_accent": "#E8F1EF", "shadow": "rgba(23, 48, 46, 0.16)",
}


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
window.moos-ui2 button {{
  background-color: @ui2_raised;
  color: @ui2_text;
  border: 1px solid @ui2_outline;
  border-radius: 12px;
  padding: 10px 16px;
}}
window.moos-ui2 button:hover,
window.moos-ui2 button:focus-visible {{
  border-color: @ui2_primary;
  outline-color: @ui2_luminous;
}}
window.moos-ui2 button:active {{ background-color: @ui2_surface; }}
window.moos-ui2 button.suggested-action {{
  background-image: linear-gradient(to bottom right, @ui2_primary, @ui2_secondary);
  color: @ui2_on_accent;
  border-color: transparent;
}}
window.moos-ui2 button.destructive-action {{
  background-color: @ui2_negative;
  color: @ui2_on_accent;
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
        self.win.add_css_class("moos-ui2")
        self.win.set_default_size(*self.SIZE)

        self._css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._restyle()
        settings = Gtk.Settings.get_default()
        if settings:
            settings.connect("notify::gtk-application-prefer-dark-theme", self._restyle)
            settings.connect("notify::gtk-theme-name", self._restyle)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                       margin_top=22, margin_bottom=22, margin_start=24, margin_end=24)
        page.add_css_class("moos-shell")
        self.build(page)

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_child(page)
        self.win.set_child(scroller)
        self.win.present()

    def _restyle(self, *_):
        self._css.load_from_data(ui2_css(UI2_DARK if gtk_prefers_dark() else UI2_LIGHT))

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
        lbl = Gtk.Label(label=text, xalign=0)
        lbl.add_css_class("title-1")
        return lbl

    @staticmethod
    def subtitle(text):
        lbl = Gtk.Label(label=text, xalign=0, wrap=True)
        lbl.add_css_class("dim-label")
        return lbl

#!/usr/bin/python3
"""
Combined KDE/Wayland portal helper: one RemoteDesktop+ScreenCast session gives us both
input injection and a live PipeWire video stream.

  stdin   JSON lines  -> input events + video settings
  stdout  JSON lines  -> ready / video geometry / errors
  argv[1] unix socket -> length-prefixed JPEG frames (4-byte LE length, then payload)

The screen is encoded by GStreamer straight off the PipeWire node, so a frame costs a few
milliseconds instead of the ~700ms a spectacle+PNG round trip used to.
"""
import json, os, socket, struct, subprocess, sys, threading, time, uuid

import gi
gi.require_version("Gio", "2.0")
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")   # force-key-unit events, for a phone that joins mid-stream
from gi.repository import Gio, GLib, Gst, GstVideo

BUS = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
REMOTE = "org.freedesktop.portal.RemoteDesktop"
CAST = "org.freedesktop.portal.ScreenCast"

TOKEN_FILE = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "MoRemote", "portal-restore-token",
)

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
out_lock = threading.Lock()


def emit(**msg):
    with out_lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


def request(method, signature, values, iface=REMOTE):
    """Call a portal method and block until its Request.Response signal arrives."""
    handle = values[-1].get("handle_token") if isinstance(values[-1], dict) else None
    handle = handle.unpack() if handle else ("req_" + uuid.uuid4().hex)
    sender = bus.get_unique_name().lstrip(":").replace(".", "_")
    expected = f"/org/freedesktop/portal/desktop/request/{sender}/{handle}"
    loop = GLib.MainLoop()
    answer = {}

    def response(_c, _s, _p, _i, _sig, params):
        code, data = params.unpack()
        answer.update(code=code, data=data)
        loop.quit()

    sid = bus.signal_subscribe(BUS, "org.freedesktop.portal.Request", "Response",
                               expected, None, Gio.DBusSignalFlags.NONE, response)
    bus.call_sync(BUS, PATH, iface, method, GLib.Variant(signature, values),
                  GLib.VariantType.new("(o)"), Gio.DBusCallFlags.NONE, 10000, None)
    # The user may take a while in the picker dialog; don't hang forever if they walk away.
    GLib.timeout_add_seconds(120, lambda: (loop.quit(), False)[1])
    loop.run()
    bus.signal_unsubscribe(sid)
    if answer.get("code") != 0:
        # 1 = the user cancelled the dialog. Tell the agent apart from a transient failure so it
        # backs off instead of re-popping the permission dialog once a second, forever.
        raise PortalDenied(f"portal {method} denied/cancelled ({answer.get('code', 'timeout')})",
                           answer.get("code") == 1)
    return answer["data"]


class PortalDenied(RuntimeError):
    def __init__(self, message, by_user):
        super().__init__(message)
        self.by_user = by_user


EXIT_DENIED = 3   # user said no — the agent should not retry in a tight loop
EXIT_LOST = 4     # session/pipeline died under us — retrying makes sense


def die(code, why):
    emit(type="error", error=why, fatal=True)
    os._exit(code)


def load_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip() or None
    except OSError:
        return None


def save_token(token):
    if not token:
        return
    try:
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        os.chmod(TOKEN_FILE, 0o600)
    except OSError as e:
        emit(type="warn", warn=f"could not persist restore token: {e}")


# ---------------------------------------------------------------- portal session
try:
    tok = "moremote_" + uuid.uuid4().hex
    created = request("CreateSession", "(a{sv})", ({
        "handle_token": GLib.Variant("s", tok),
        "session_handle_token": GLib.Variant("s", tok + "s"),
    },))
    session = created["session_handle"]
except PortalDenied as e:
    die(EXIT_DENIED if e.by_user else EXIT_LOST, str(e))

# Pointer (1) | keyboard (2). persist_mode 2 = keep the grant across restarts.
select_devices = {
    "handle_token": GLib.Variant("s", tok + "d"),
    "types": GLib.Variant("u", 3),
    "persist_mode": GLib.Variant("u", 2),
}
restore = load_token()
if restore:
    select_devices["restore_token"] = GLib.Variant("s", restore)
try:
    request("SelectDevices", "(oa{sv})", (session, select_devices))
except PortalDenied as e:
    die(EXIT_DENIED if e.by_user else EXIT_LOST, str(e))

# Same session also carries the video stream: MONITOR source.
#
# cursor_mode matters enormously for cost. EMBEDDED (2) paints the cursor into the frames,
# so every pointer move damages the screen and forces a full JPEG re-encode (~285KB) — at
# 30fps that is ~64 Mbit/s just to move the mouse. HIDDEN (1) means pointer motion produces
# no frames at all; the phone draws its own cursor at the position it commanded, which is
# both free and instant. EMBEDDED stays available for anyone who wants the true cursor.
#
# No persist_mode here — on a combined session the portal refuses it and the RemoteDesktop
# restore token above already covers the sources too.
CURSOR_EMBEDDED, CURSOR_HIDDEN = 2, 1
cursor_mode = CURSOR_EMBEDDED if os.environ.get("MOREMOTE_EMBED_CURSOR") == "1" else CURSOR_HIDDEN
select_sources = {
    "handle_token": GLib.Variant("s", tok + "v"),
    "types": GLib.Variant("u", 1),          # MONITOR
    "multiple": GLib.Variant("b", False),
    "cursor_mode": GLib.Variant("u", cursor_mode),
}
try:
    request("SelectSources", "(oa{sv})", (session, select_sources), iface=CAST)
    started = request("Start", "(osa{sv})", (session, "", {"handle_token": GLib.Variant("s", tok + "x")}))
except PortalDenied as e:
    die(EXIT_DENIED if e.by_user else EXIT_LOST, str(e))

save_token(started.get("restore_token"))

streams = started.get("streams", [])
if not streams:
    die(EXIT_LOST, "portal returned no video stream")
node_id, node_props = streams[0]
node_id = int(node_id)

# ScreenCast v6 gives us a stable PipeWire object serial in addition to the
# transient node id. A node id may be reused after suspend/resume, a monitor
# hot-plug or a mode switch; reconnecting pipewiresrc to that stale number can
# therefore produce a healthy-looking pipeline whose frames belong to nothing
# (the controller sees a black/frozen desktop). `pipewiresrc path=` maps to
# PW_KEY_TARGET_OBJECT, which the portal specification says must use the serial
# when it is available. Old portal backends do not publish the property, so the
# node id remains the compatibility fallback.
pipewire_target = int(node_props.get("pipewire-serial", node_id))

# The portal validates absolute pointer coordinates against the *logical* desktop size it
# advertises here (e.g. 1396x785 on a 3840x2160 screen at 2.75x scale) — NOT against the
# pixel size of the video stream. Anything else comes back as "Invalid position".
logical_w, logical_h = (int(v) for v in node_props["size"])

def open_pipewire_fd():
    """A fresh PipeWire remote fd. Each pipeline gets its own; pipewiresrc closes it on NULL."""
    reply, fds = bus.call_with_unix_fd_list_sync(
        BUS, PATH, CAST, "OpenPipeWireRemote",
        GLib.Variant("(oa{sv})", (session, {})),
        GLib.VariantType.new("(h)"), Gio.DBusCallFlags.NONE, 5000, None, None)
    return fds.get(reply.unpack()[0])


empty = {}


# If the user revokes the grant (the "Stop sharing" applet) or xdg-desktop-portal restarts, the
# session is closed under us. Without this the helper would happily keep running with a dead
# session: every click would be silently swallowed and the video would freeze on its last frame,
# while the agent still believed everything was fine. Exiting lets the agent respawn us (which
# restores from the token, no dialog) and, failing that, fall back to ydotool/spectacle.
bus.signal_subscribe(BUS, "org.freedesktop.portal.Session", "Closed", session, None,
                     Gio.DBusSignalFlags.NONE,
                     lambda *_: die(EXIT_LOST, "portal session closed"))

_notify_failures = 0


def _notify_done(_bus, res):
    """Failure accounting for fire-and-forget injection. A transient compositor
    hiccup must not kill the helper (that used to force a full pipeline rebuild
    back onto JPEG); only a sustained failure streak means the session is dead."""
    global _notify_failures
    try:
        bus.call_finish(res)
        _notify_failures = 0
    except GLib.GError as e:
        _notify_failures += 1
        if _notify_failures >= 20:
            die(EXIT_LOST, f"input injection failing: {e.message}")


def notify(method, sig, args):
    """Input injection, asynchronous on purpose. call_sync made every keystroke
    wait a full compositor round-trip on the input thread, so a burst (an
    autocorrect rewrite, fast Arabic typing) serialized at compositor pace while
    KWin was also being hammered — which is exactly when the picture froze.
    Ordering is safe: async calls on one GDBus connection are sent in call
    order, so down always precedes up."""
    bus.call(BUS, PATH, REMOTE, method, GLib.Variant(sig, args), None,
             Gio.DBusCallFlags.NO_AUTO_START, 1000, None, _notify_done)


def notify_sync(method, sig, args):
    """The same injection, AWAITED. Used only inside a batch that also changes the
    keymap group, where the whole point is that nothing may overtake anything."""
    bus.call_sync(BUS, PATH, REMOTE, method, GLib.Variant(sig, args), None,
                  Gio.DBusCallFlags.NO_AUTO_START, 2000, None)


# ---------------------------------------------------------------- keymap group
#
# Arabic is typed by selecting the Arabic group and pressing the keys that carry it, because
# KWin resolves an injected keysym against the ACTIVE group only, at shift level one. The
# clipboard borrow this replaces was the source of every scrambling report in the agent's
# history: one shared slot, an asynchronous fetch, and a copy that returns before the
# selection is servable.
#
# THE ORDERING HAZARD, AND WHY THE SWITCH LIVES INSIDE THE BATCH
#
# A group switch and a keystroke are two independent messages to KWin, and the switch can
# overtake keys already queued. Measured on the live session with a sub-millisecond gap:
# 0 of 25 runs correct — "مرحبا" arrived as "lvpfhab", the GERMAN reading of the same
# positions. Neither available signal helps: setLayout's own reply and the layoutChanged
# signal (0.15 ms median) both mean ACCEPTED, not APPLIED, and typing straight after either
# is still wrong.
#
# So there is only ever one channel. A batch carrying a layout element is executed strictly
# sequentially with every call awaited, so the switch cannot overtake a key and a key cannot
# overtake the switch. That is a happens-before, not a delay somebody guessed.
KEYBOARD_BUS = "org.kde.keyboard"
KEYBOARD_PATH = "/Layouts"
KEYBOARD_IFACE = "org.kde.KeyboardLayouts"

# `warned` is a SET of group names, not a bool: one missing layout used to mute the warning for
# every other one, so a machine lacking both `ara` and `us` reported only whichever failed first.
layout_state = {"codes": [], "ara": None, "us": None, "home": None, "current": None,
                "warned": set(), "typed": False, "toggle": False}


def _group_toggle_available():
    """Does this keymap carry the Alt+Shift group switch we ride on?

    Read from the kxkbrc cascade, user file first — the same file System Settings > Keyboard
    writes and the same key moos-selfcheck already gates (`Options` must contain
    `alt_shift_toggle`). A machine that has removed it still types Arabic, just through the
    slower out-of-band path in select_group().
    """
    home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    for path in (os.path.join(home, "kxkbrc"), "/etc/xdg/kxkbrc"):
        try:
            with open(path) as f:
                for line in f:
                    if line.startswith("Options="):
                        return "grp:alt_shift_toggle" in line
        except OSError:
            continue
    return False


def _layout_call(method, sig=None, args=None, reply=None):
    return bus.call_sync(KEYBOARD_BUS, KEYBOARD_PATH, KEYBOARD_IFACE, method,
                         GLib.Variant(sig, args) if sig else None,
                         GLib.VariantType.new(reply) if reply else None,
                         Gio.DBusCallFlags.NONE, 2000, None)


def load_layouts():
    """Read the groups KWin ACTUALLY loaded — never the config, which can disagree with the
    running session for the whole life of a login."""
    try:
        codes = [row[0] for row in _layout_call("getLayoutsList", reply="(a(sss))").unpack()[0]]
        current = _layout_call("getLayout", reply="(u)").unpack()[0]
    except GLib.GError as e:
        emit(type="warn", warn=f"keyboard layouts unavailable: {e.message}")
        return
    layout_state["codes"] = codes
    layout_state["current"] = current
    # `home` is the group the user was on before we ever touched it, so restoring is restoring
    # THEIR choice and not a hard-coded country.
    if layout_state["home"] is None:
        layout_state["home"] = current
    layout_state["ara"] = next((i for i, c in enumerate(codes) if c.startswith("ara")), None)
    layout_state["us"] = next((i for i, c in enumerate(codes) if c == "us" or c.startswith("us(")), None)
    layout_state["toggle"] = _group_toggle_available() and len(codes) > 1
    emit(type="layouts", codes=codes, current=current, arabic=layout_state["ara"],
         us=layout_state["us"], toggle=layout_state["toggle"])


# THE GROUP CHANGE TRAVELS AS KEYSTROKES, AND THAT IS THE WHOLE FIX.
#
# The obvious implementation — call setLayout, then inject — is broken, and measurably so. A
# switch and a keystroke reach KWin as two INDEPENDENT messages, so the switch can overtake keys
# already in flight. Measured end to end against the real helper: 4 of 12 Arabic words lost their
# tail to the German layout ("مكتوب" -> "مكتوf", "عليكم" -> "عليكl") — those positions read on
# the wrong group.
#
# Nothing in the interface offers a barrier. setLayout's own reply and the layoutChanged signal
# both fire in ~0.15 ms and both mean ACCEPTED, not APPLIED: typing straight after either is
# still wrong (0/25 and 1/30 correct). getLayout reports the requested value before injected keys
# ever see it. And awaiting the PORTAL call is not a barrier either — it proves
# xdg-desktop-portal handled the call, not KWin, which the portal reaches over a second
# connection asynchronously. A sleep long enough to paper over all that is a guess, and this
# file has already thrown one mechanism away ("paste anyway") for being exactly that.
#
# So the switch stops being a second channel. xkb's own `grp:alt_shift_toggle` — which MoOS ships
# in /etc/xdg/kxkbrc and moos-selfcheck already gates — cycles the group in response to ORDINARY
# KEY EVENTS. Injecting Alt+Shift through the portal puts the group change in the SAME ordered
# stream as the letters, down the same connection, so neither can overtake the other. Measured on
# the live session: injected Alt+Shift cycles 0 -> 1 -> 2 -> 0 reliably, wrapping.
#
# The cost is that it is relative — reaching a group takes (target - current) mod N toggles — so
# the current index is read once at startup and updated on every toggle we make.
ALT_CODE, SHIFT_CODE = 56, 42
# Pacing between our own consecutive group-switch chords, and after the last one.
#
# Sent back to back with no pacing at all, the second Alt+Shift was swallowed and the group
# landed one short: "بالعالم" arrived as "fhguhgl" and "عليكم" as "ugd;l" — those positions read
# on a Latin group. 10 ms measured clean 38/38 across two end-to-end runs against the real
# helper, with a group change on EVERY line, which is far harsher than real typing (a sentence
# is one change, because the agent gathers a word before it types).
# Enough attempts to cross a three-group ring twice and still absorb a swallowed chord.
MAX_TOGGLE_ATTEMPTS = 8
TOGGLE_CONFIRM_TRIES = 12
TOGGLE_CONFIRM_POLL_MS = 5


def _read_layout():
    """The group KWin ACTUALLY has. Unlike setLayout, this is only ever used to observe a change
    our own keystrokes caused, never to assert one."""
    try:
        return _layout_call("getLayout", reply="(u)").unpack()[0]
    except GLib.GError:
        return None


def _toggle_events(times):
    """The keystrokes that advance the xkb group `times` steps."""
    out = []
    for _ in range(times):
        out += [(ALT_CODE, True), (SHIFT_CODE, True), (SHIFT_CODE, False), (ALT_CODE, False)]
    return out


def _group_index(name):
    """Which xkb group `name` means, or None if this machine has no such layout.

    THIS USED TO BE `layout_state["ara"] if name == "ara" else layout_state["home"]`, WHICH
    ALIASED EVERY OTHER NAME TO THE USER'S OWN LAYOUT.

    Harmless while `ara` and `home` were the only names anyone asked for. It stopped being harmless
    the moment UsKeymap started asking for `us` to type symbols: the request resolved to `home`,
    the batch typed US POSITIONS on the GERMAN group, and the user got German faces. Measured live
    on this machine with the exact positions UsKeymap emits for `@ / - ;`, group 0 (de) active:

        expected  @ / - ;
        got       " - ss oe        (quotedbl, minus, ssharp, odiaeresis)

    and on the real `us` group the same positions produced `@/-;` correctly. Nothing failed: no
    warning, no dropped run, no log line. The text simply arrived wrong, which is the worst shape
    a bug can have.

    A position is only deterministic once the group is known — that is the premise of BOTH keymap
    tables — so a name that silently resolves to a different group defeats the mechanism it serves.

    `home` and `ara` keep their cached answers (resolved once at startup); anything else is looked
    up by prefix in the live ring, exactly the way `ara` itself is found.
    """
    if name == "home":
        return layout_state["home"]
    if name == "ara":
        return layout_state["ara"]
    codes = layout_state["codes"]
    return next((i for i, c in enumerate(codes) if c.startswith(name)), None)


def select_group(name, send):
    """Put `name` on the active group by injecting toggles through `send` — the SAME sender the
    batch's letters use. Returns False when the group does not exist or cannot be reached."""
    idx = _group_index(name)
    if idx is None:
        # Name the group that is actually missing. This hard-coded the Arabic message for EVERY
        # failure, so a machine without a `us` group told its owner to install an Arabic keyboard.
        if name not in layout_state["warned"]:
            layout_state["warned"].add(name)
            emit(type="warn", warn=f"no '{name}' keyboard layout is configured; text needing it "
                                   f"cannot be typed until one is added in "
                                   f"System Settings > Keyboard")
        return False
    cur = layout_state["current"]
    if cur is None or not layout_state["codes"]:
        return False
    if cur == idx:
        return True

    if layout_state["toggle"]:
        # ONE CHORD AT A TIME, EACH CONFIRMED — because a swallowed toggle desyncs everything.
        #
        # Pacing alone is not enough. Sent back to back the second Alt+Shift is sometimes
        # swallowed and the group lands one short: measured, "بالعالم" arrived "fhguhgl" and
        # "كيف الحال" arrived ";dt hgphg" — those positions read on a Latin group. Worse, a lost
        # toggle desyncs the tracked index, so every later switch is wrong too.
        #
        # So each chord is followed by a bounded read of the group KWin actually has, and the
        # loop simply keeps going until the target is reached. That makes a swallowed chord
        # self-correcting instead of permanent, and it re-syncs the tracked index from the
        # compositor rather than trusting our own count. It is the same "confirm before use"
        # discipline this project already applied to the clipboard — reading back is the only
        # honest confirmation, and a fixed sleep is a guess.
        #
        # The read is safe where a setLayout is not: we are confirming state BEFORE any letter is
        # sent, not racing a switch against letters already in flight.
        for _ in range(MAX_TOGGLE_ATTEMPTS):
            now = _read_layout()
            if now is None:
                break
            layout_state["current"] = now
            if now == idx:
                return True
            for code, down in _toggle_events(1):
                send("NotifyKeyboardKeycode", "(oa{sv}iu)",
                     (session, empty, code, 1 if down else 0))
            # Give the chord time to reach KWin before asking what it did.
            for _ in range(TOGGLE_CONFIRM_TRIES):
                time.sleep(TOGGLE_CONFIRM_POLL_MS / 1000.0)
                seen = _read_layout()
                if seen is not None and seen != now:
                    layout_state["current"] = seen
                    break
        final = _read_layout()
        if final == idx:
            layout_state["current"] = final
            return True
        emit(type="warn", warn=f"could not reach keyboard group {idx} (now {final}); "
                               "dropping the run rather than typing it on the wrong layout")
        if final is not None:
            layout_state["current"] = final
        return False

    # This keymap has no group-switch shortcut, so the only route left is the out-of-band call
    # that CAN overtake keys. Drain first, and keep the failure honest: a machine without
    # grp:alt_shift_toggle gets the measured second-best rather than silent corruption.
    if layout_state["typed"]:
        time.sleep(0.045)
        layout_state["typed"] = False
    try:
        _layout_call("setLayout", "(u)", (idx,), reply="(b)")
    except GLib.GError as e:
        emit(type="warn", warn=f"could not select keyboard group {idx}: {e.message}")
        return False
    layout_state["current"] = idx
    return True


def restore_layout():
    """Hand the user's own group back, so a borrow is not a theft — the same contract the
    clipboard borrow had, applied to the thing we now borrow instead."""
    if layout_state["home"] is not None and layout_state["current"] != layout_state["home"]:
        try:
            _layout_call("setLayout", "(u)", (layout_state["home"],), reply="(b)")
            layout_state["current"] = layout_state["home"]
        except GLib.GError:
            pass


# ---------------------------------------------------------------- frame transport
frames = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
frames.connect(sys.argv[1])
frames_lock = threading.Lock()
frames_alive = True


def send_frame(data):
    global frames_alive
    if not frames_alive:
        return False
    with frames_lock:
        try:
            frames.sendall(struct.pack("<I", len(data)) + data)
            return True
        except OSError:
            frames_alive = False  # agent went away; the pipeline is torn down with us
            return False


# ---------------------------------------------------------------- gstreamer
Gst.init(None)

# The hard ceiling on encode width, and why it is no longer 1920.
#
# 1920 was not a hardware limit, it was a guess, and on a 4K desktop it is a 2x downscale of
# everything the user is looking at. A 3840-wide screen at 2.25x scaling carries text drawn for
# 1707 logical pixels; halving it to 1920 physical is roughly one device pixel per logical pixel,
# which is exactly where thin strokes start to blur. "The picture is not sharp" was that, and no
# bitrate could fix it — the detail was thrown away before the encoder ever saw it.
#
# Measured on this machine (RTX 2080 SUPER, nvh264enc, pattern=snow which is the worst case
# content there is — real desktops compress far better):
#
#     1920x1080@30   30.3 fps
#     1920x1080@60   60.3 fps
#     2560x1440@30   30.3 fps
#     2560x1440@60   60.3 fps      <- comfortable
#     3840x2160@30   30.3 fps
#     3840x2160@60   31.9 fps      <- the encoder runs out here
#
# So 2560 is where the hardware stops being the limit at a frame rate worth having. It is a
# CEILING and not a target: target_size() still takes the smaller of this, the source, and what
# the client asked for, so a 1080p desktop is untouched and a phone on cellular still gets the
# small picture its quality preset asks for.
MAX_WIDTH = 2560

# What a client that only speaks `scale` gets. See the note in target_size(): raising the ceiling
# would otherwise change the meaning of every fraction an already-cached PWA sends.
LEGACY_MAX_WIDTH = 1920
# `streaming` gates the encode pipeline on somebody actually watching. It starts False and the
# agent flips it on the first viewer, because a PLAYING pipeline is not free while nobody looks:
# pipewiresrc keeps the ScreenCast stream active, so the COMPOSITOR copies every damaged frame out
# for us, forever. Measured on this machine with zero clients connected: kwin_wayland 55% of a core
# and this helper 32%, permanently — the desktop felt broken and the GPU was one Konsole away from
# the VRAM ceiling that SIGSEGVs kwin. Idle must cost nothing.
state = {"sw": 0, "sh": 0, "scale": 1.0, "width": 0, "quality": 70, "fps": 30, "out": (0, 0),
         "codec": "jpeg", "want": "jpeg", "streaming": False}
pipeline = None
enc = rate = None

# pipewiresrc repeats its last buffer at this interval even when the desktop has no damage. That
# changes what "no frames" means: a static desktop is healthy and still advances this clock, while
# five missed keepalives means the source/encoder/appsink chain has stopped making progress.
FRAME_KEEPALIVE_MS = 1000
FRAME_STARVATION_MS = 5000
FRAME_HEALTH_CHECK_MS = 1000


class PipelineHealth:
    """Small, dependency-free progress clock so starvation policy is behaviour-tested in isolation."""

    def __init__(self, timeout_ms):
        self.timeout_ms = int(timeout_ms)
        self.last_progress_ms = None
        self.seen_frame = False

    def start(self, now_ms):
        # A newly PLAYING pipeline also owes us its first frame. Starting from now gives it the same
        # five-keepalive budget as a pipeline which had already produced frames and then stopped.
        self.last_progress_ms = int(now_ms)
        self.seen_frame = False

    def stop(self):
        self.last_progress_ms = None
        self.seen_frame = False

    def note_frame(self, now_ms):
        if self.last_progress_ms is not None:
            self.last_progress_ms = int(now_ms)
            self.seen_frame = True

    def stalled(self, now_ms):
        return (self.last_progress_ms is not None
                and int(now_ms) - self.last_progress_ms >= self.timeout_ms)

    def age_ms(self, now_ms):
        return 0 if self.last_progress_ms is None else max(0, int(now_ms) - self.last_progress_ms)


video_health = PipelineHealth(FRAME_STARVATION_MS)


def monotonic_ms():
    return GLib.get_monotonic_time() // 1000


# ---------------------------------------------------------------- codec selection
#
# JPEG has no temporal compression at all: every frame is a whole picture, so a desktop that is
# merely *being looked at* costs the same as one being scrubbed through. Measured on this machine,
# 1080p: JPEG 79 Mbit/s against H.264's 4.3. On a home LAN that is merely wasteful. On mobile
# data — which is the entire point of reaching the machine from outside the house — 79 Mbit/s is
# not a stream, it is a stall.
#
# Best encoder first. nvh264enc is NVENC and costs the CPU nothing; vah264enc is the same deal on
# Intel/AMD; openh264enc is software and costs perhaps a fifth of a core at 1080p30 — still a
# trade worth making, because the bandwidth saved is 18x and the JPEG path already burns ~9% of a
# core doing worse.
#
# Every one of these can be present and still refuse to start. NVENC in particular needs free VRAM
# to open a session, and on a machine that also runs a local LLM there may be none: measured here,
# nvh264enc failed with "Failed to open encoder" at 7748/8192 MiB used and worked again at 7625.
# So the encoder is not chosen by what is *installed* — it is chosen by what actually reaches
# PLAYING, and anything that does not falls through to the next one. JPEG is the floor, and the
# floor never fails.
H264_ENCODERS = [
    ("nvh264enc",   "bitrate={kbps} gop-size={gop} bframes=0 zerolatency=true rc-mode=cbr"),
    ("vah264enc",   "bitrate={kbps} key-int-max={gop} rate-control=cbr"),
    ("vah264lpenc", "bitrate={kbps} key-int-max={gop} rate-control=cbr"),
    # ONE SLICE PER FRAME, and it is both the compatible choice and the fast one.
    #
    # `tune=zerolatency` turns on x264's SLICED THREADS, which splits every frame into one slice per
    # thread so a slice can leave the encoder before the frame is finished. On this 8-core box that
    # is 8 slices in every access unit — measured by parsing the shipping encoder's own output:
    #
    #     sliced-threads=true   AUs=200  P-slices=1568  IDR-slices=32  -> 8.0 slices/frame
    #     sliced-threads=false  AUs=200  P-slices=196   IDR-slices=4   -> 1.0 slices/frame
    #
    # Multi-slice H.264 is legal and Chrome eats it. It is the single most common thing an iOS
    # WebCodecs VideoDecoder refuses, and iOS is not a hypothetical client here: the only online
    # peer on this tailnet is an iPhone. The symptom matched exactly — the room held H.264 for
    # 14-15 seconds and then fell to JPEG, every time, which is the periodic IDR interval at this
    # desktop's real damage-driven frame rate, and the IDR is the access unit carrying 8 IDR slices.
    # The stream was otherwise healthy (all SPS byte-identical, IDR only 2.0x a P-frame) and the
    # agent logged zero backlog drops, so the failure was inside the decoder and nowhere else.
    #
    # `threads=2` is what makes this free. Without sliced threads x264 falls back to FRAME threading,
    # which delays output by (threads - 1) frames — the very latency zerolatency exists to avoid — so
    # the thread count is now a latency budget rather than left at "as many as you have". Measured on
    # this machine at the live 1836x1032, 300 frames of desktop-like content:
    #
    #     sliced-threads=true             8.15s  ->  36.8 fps   8 slices, 0 frames of delay
    #     sliced-threads=false threads=1 13.87s  ->  21.6 fps   1 slice,  0 frames  (too slow)
    #     sliced-threads=false threads=2  7.40s  ->  40.5 fps   1 slice,  1 frame   <- this
    #
    # So one slice per frame is 10% FASTER than what shipped, and costs a single frame (~33ms at
    # 30fps) of pipeline delay — against the ~200ms teardown-and-rebuild that a codec fallback costs
    # every fifteen seconds. Do not raise `threads` without re-reading that middle column: every
    # extra thread is another frame of latency the person feels on every mouse move.
    ("x264enc",     "bitrate={kbps} key-int-max={gop} tune=zerolatency speed-preset=veryfast "
                    "sliced-threads=false threads=2"),
    # usage-type=screen tells openh264 the content is a desktop, not camera footage. It changes how the
    # rate controller spends its budget: a desktop is large flat areas and thin high-contrast text, and
    # the screen profile stops it smoothing that text away to hold a frame rate nothing is asking for.
    # max-bitrate is the ceiling the rate controller is otherwise free to ignore — openh264 overshoots
    # hard on a scene change (a window opening, a page scrolling), and an overshoot on a link with a
    # 12-frame queue is a stall. Ceiling at 1.5x the target so bursts have room without becoming spikes.
    ("openh264enc", "bitrate={bps} max-bitrate={maxbps} gop-size={gop} complexity=low "
                    "rate-control=bitrate usage-type=screen"),
]
H264_ENCODER_FACTORIES = frozenset(name for name, _props in H264_ENCODERS)


def is_h264_encoder_factory(factory):
    """Only a failure raised by an encoder we selected is eligible for codec fallback."""
    return factory in H264_ENCODER_FACTORIES


def element_factory_name(element):
    """Factory name from a Gst message source, or empty when the source is a bin/pipeline."""
    try:
        feature = element.get_factory() if element is not None else None
        return feature.get_name() if feature is not None else ""
    except Exception:
        return ""

# Elements that were present and then failed to start -> when they failed.
#
# A SET WAS THE WRONG SHAPE, AND MO AI IS THE REASON.
#
# This was a plain set: an encoder that refused to open once was condemned for the life of the
# helper. That is right for a broken element and wrong for the failure that actually happens on this
# machine, which is not permanent and is not even about the encoder.
#
# MoOS ships a local LLM. `moai.service` loads ~6 GB onto the card and holds it, and NVENC needs free
# VRAM to open a session — measured here on an RTX 2080 SUPER: nvh264enc fails with "Failed to open
# encoder" at 7748/8192 MiB used and works again at 7625. So the sequence "chat with Mo AI, then open
# the remote on your phone" audition-fails NVENC, blacklists it for ever, and drops the session to
# software or to JPEG — 79 Mbit/s against H.264's 4.3 at 1080p. The user experiences that as "the
# picture on my phone is bad", and nothing anywhere says the assistant took the encoder.
#
# MoOS already has the tool for this: `moos-gpu-headroom` unloads the idle brain so a GPU app can
# start, and moai-gateway reloads it on the next message. MoPlayer, moos-open, moai-do and moos-storectl
# all call it. The remote never did — it is the one first-party GPU consumer that was left to lose.
#
# So: remember WHEN an element failed rather than merely THAT it did, expire the entry, and on the way
# out ask for the memory back. A condition that lasts a minute must not cost the session an hour.
_h264_blacklist = {}
# Long enough that a genuinely broken element is not re-auditioned every rebuild (each failed
# audition costs a pipeline build), short enough that the session recovers within one reconnect.
BLACKLIST_TTL_MS = 90_000


def _blacklisted(name):
    at = _h264_blacklist.get(name)
    return at is not None and (GLib.get_monotonic_time() // 1000) - at < BLACKLIST_TTL_MS


def pick_h264():
    """The best H.264 encoder that is installed and is not currently in the sin bin."""
    reg = Gst.Registry.get()
    for name, props in H264_ENCODERS:
        if _blacklisted(name):
            continue
        if reg.lookup_feature(name) is not None:
            return name, props
    return None, None


_headroom_running = False


def free_gpu_and_retry():
    """Ask MoOS to give the encoder its VRAM back, then try the pipeline again.

    Runs on a worker thread because moos-gpu-headroom shells out to nvidia-smi and systemctl, and
    this must never block the GLib loop that is also carrying input injection. Best-effort in every
    direction: no NVIDIA, no such tool, or a refusal all end the same way — the pipeline we already
    built keeps running, on whatever encoder it managed to get.
    """
    global _headroom_running
    if _headroom_running:
        return
    _headroom_running = True

    def work():
        global _headroom_running
        try:
            subprocess.run(["moos-gpu-headroom"], timeout=25,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            _headroom_running = False
        # Forget the failure explicitly rather than waiting out the TTL: we have just changed the
        # condition that caused it, so the next build should get the real answer, not the old one.
        _h264_blacklist.clear()
        state["out"] = (0, 0)          # force a real rebuild rather than a no-op
        GLib.idle_add(rebuild)

    threading.Thread(target=work, daemon=True).start()


def tune_for_latency(el, bps, fps):
    """Ask an H.264 encoder for the interactive trade, not the broadcast one.

    WHY THESE ARE SET HERE AND NOT IN THE LAUNCH STRING

    Everything below is optional and encoder-specific, and a property that does not exist is not a
    warning in Gst.parse_launch — it is a PARSE FAILURE. The pipeline would fail to build, build()
    would read that as "this encoder will not start", blacklist it, and fall down the list to JPEG.
    On an NVIDIA machine that means the one property name that GStreamer renamed between releases
    silently costs the user hardware encoding and eighteen times the bandwidth, for ever, with a
    log line that says only "nvh264enc would not start". That failure has already happened twice in
    this file's history for exactly this reason (see the `and w` note in build()).

    So every one of these goes through set_prop, which asks the element whether it HAS the property
    before setting it. An encoder that has never heard of `tune` simply keeps its defaults and still
    runs. Nothing here can cost us an encoder.

    WHAT EACH ONE BUYS

      preset / tune   NVENC's modern knobs. `tune=ultra-low-latency` is documented as taking effect
                      with the p1..p7 presets, so the two are set together; p4 ("medium") is the
                      balance point NVIDIA recommends for live encode — p1 is faster than a 1080p30
                      desktop needs and spends quality to get there. Without these NVENC runs its
                      default tuning, which is built for quality-per-bit on recorded video and
                      happily reorders and looks ahead.

      vbv-buffer-size THE ONE THAT MATTERS MOST, and it is about stalls rather than about bitrate.
                      A rate controller with a large VBV is allowed to spend far more than the
                      average on one frame and pay it back later. That is correct for a file and
                      wrong for a wire: a single frame five times the budget is a burst that has to
                      cross a link sized for the average, and on the 12-frame queue in
                      StreamSession that burst is a visible stall. Sized at ONE FRAME of bits
                      (kbit/s ÷ fps) the encoder is forced to keep every frame inside its budget, so
                      the stream becomes flat instead of spiky. This is the same choice every
                      low-latency game-streaming encoder makes.

      rc-lookahead=0  Lookahead is frames of delay by definition — it decides the current frame's
                      type by reading ones that have not been sent yet.

      bframes=0       A B-frame is coded from a FUTURE frame, so it cannot be sent until that
                      future frame exists. Already set in the launch string for NVENC; repeated
                      here for the encoders whose string does not carry it.

      qos=false       Downstream QoS events would make the encoder start dropping on its own
                      schedule. Dropping is already decided in exactly two deliberate places (the
                      leaky queue upstream, videorate) and a third opinion is how frames go missing
                      for reasons nobody can trace.
    """
    kbps = max(1, int(bps) // 1000)
    fps = max(1, int(fps))
    # Enum properties take their nickname as a string in PyGObject. Guarded anyway: an element that
    # has the property but not the value would raise, and losing the encoder over a tuning hint is
    # precisely the trade this whole function exists to refuse.
    for name, value in (("preset", "p4"), ("tune", "ultra-low-latency"),
                        ("vbv-buffer-size", max(1, kbps // fps)),
                        ("rc-lookahead", 0), ("bframes", 0), ("qos", False)):
        try:
            set_prop(el, name, value)
        except Exception:
            pass
    # x264enc measures its VBV in MILLISECONDS rather than in kbits (default 600, i.e. six tenths of
    # a second of slack), so it needs its own line: one frame at 30fps is 33ms.
    try:
        set_prop(el, "vbv-buf-capacity", max(1, 1000 // fps))
    except Exception:
        pass


def h264_bitrate_bps(w=0, h=0):
    """Bits per second for a picture of this size, from the 10..95 quality slider.

    WHY THIS IS NOT `quality * 100` ANY MORE, AND WHY THAT MAPPING MADE THE STUTTER SELF-SUSTAINING
    -----------------------------------------------------------------------------------------------
    The old mapping read the slider and nothing else — not width, not height, not framerate. But the
    slider moves the RESOLUTION too (types.ts couples quality and scale in one preset), and it moves it
    in the same direction, so the bitrate request ended up INVERTED against the picture it was paying
    for:

        preset      request        picture      bits/pixel/frame
        Low         4.5 Mbit/s     960x540      0.289
        Balanced    6.2 Mbit/s     1344x756     0.203
        High        8.0 Mbit/s     1920x1080    0.129

    Low asks for 2.25x the bits per pixel that High does, and only 44% fewer bits in total for a
    quarter of the pixels. So when RTT crosses the ladder's threshold and the client steps DOWN to
    relieve a struggling link, the encoder is told to spend almost as much on a much smaller image —
    the one mechanism that exists to reduce load makes the load worse, which sustains the very
    congestion that triggered it. That is a continuous stutter with no event behind it, which is what
    "تقطيع" describes far better than any freeze.

    Bits per pixel per frame is the quantity that actually determines whether text looks crisp, so make
    that the thing the slider controls and let the bitrate fall out of it. 0.03..0.10 bpp is the useful
    range for desktop content: at 1080p30 that is 1.9..6.2 Mbit/s, so the default 62 still lands on
    today's known-good figure, while Low at 960x540 now asks under 1 Mbit/s instead of 4.5.

    Returns BITS per second. openh264enc wants bits; the kilobit encoders get it divided at the call
    site. w/h are passed in explicitly because target_size() returns (0,0) until the stream geometry
    arrives and state["out"] is transiently (0,0) as a rebuild sentinel — reading either from in here
    would silently produce the floor.
    """
    if not w or not h:
        w, h = state.get("out") or (0, 0)
    if not w or not h:
        w, h = 1920, 1080          # a sane assumption beats a zero-sized budget
    fps = state.get("fps") or 30
    q = max(10, min(95, int(state["quality"])))
    bpp = 0.03 + (q - 10) / 85.0 * 0.07     # 10 -> 0.03, 95 -> 0.10
    return int(max(800_000, min(12_000_000, bpp * w * h * fps)))


def target_size():
    """Encode resolution.

    A CLIENT MAY NOW ASK IN PIXELS, AND THAT IS THE POINT.

    `scale` is a fraction of the target width, and a fraction is not a resolution: the same 0.7
    preset is 1344 pixels on a 1920 desktop and 1792 on a 4K one, so "Balanced" meant something
    different on every machine and nothing the user could reason about. Worse, the client has no
    way to find out which it got — `hello` carries the LOGICAL desktop size (1707x960 here), not
    the source pixels the encoder actually sees (3840x2160).

    So a client can now say what it wants in pixels (`width`), and the answer is the smallest of
    what it asked for, what the source has, and what the hardware ceiling allows. That makes a
    preset mean the same thing everywhere, which is what lets the UI honestly offer "1440p".

    `scale` stays for older clients and for nothing else — it is exactly the previous behaviour.
    """
    sw, sh = state["sw"], state["sh"]
    if not sw or not sh:
        return (0, 0)
    want = state.get("width") or 0
    if want:
        w = max(480, min(int(want), min(sw, MAX_WIDTH)))
    else:
        # NO PIXEL REQUEST MEANS AN OLD CLIENT, AND AN OLD CLIENT KEEPS THE OLD CEILING.
        #
        # `scale` is a fraction of the target, so raising the target silently changes what every
        # existing fraction means: a cached PWA asking for its "High" (scale 1.0) would jump from
        # 1920 to 2560 — 1.8x the pixels and the bandwidth — without anyone choosing it, on a phone
        # that may well be on cellular. Service workers make that a real client and not a
        # hypothetical one; this agent already has a "legacy cached controller" path for exactly
        # that population.
        #
        # So the higher ceiling is something a client OPTS INTO by naming pixels. A client that
        # only knows fractions gets byte-for-byte what it got before.
        w = max(480, min(int(min(sw, LEGACY_MAX_WIDTH) * state["scale"]), min(sw, LEGACY_MAX_WIDTH)))
    w = w // 2 * 2
    h = max(2, round(sh * w / sw)) // 2 * 2
    return (w, h)


def on_sample(sink):
    sample = sink.emit("pull-sample")
    if sample is None:
        return Gst.FlowReturn.OK
    if not state["sw"]:
        # Source geometry is only known once buffers flow; learn it, then rebuild at the right size.
        caps = sample.get_caps()
        if caps:
            s = caps.get_structure(0)
            state["sw"], state["sh"] = s.get_value("width"), s.get_value("height")
            GLib.idle_add(rebuild)
    buf = sample.get_buffer()
    ok, info = buf.map(Gst.MapFlags.READ)
    if ok:
        try:
            # Health means a frame made it through the ENTIRE pipeline and into the agent socket,
            # not merely that pipewiresrc produced a buffer upstream of a wedged encoder/appsink.
            if send_frame(info.data):
                video_health.note_frame(monotonic_ms())
        finally:
            buf.unmap(info)
    return Gst.FlowReturn.OK


def on_bus(_b, msg):
    # A pipeline error or EOS means frames have stopped for good (monitor unplugged, compositor
    # restart, stream torn down). Die so the agent respawns us instead of serving a frozen frame.
    if msg.type == Gst.MessageType.ERROR:
        err, dbg = msg.parse_error()
        # …unless it is the H.264 encoder giving up mid-stream, which is a thing NVENC really does:
        # the LLM on this machine can grow into the VRAM the encode session was holding. Losing the
        # hardware encoder should cost the user some bandwidth, not their remote desktop. Blacklist
        # it, rebuild on the next one down, and keep the session alive.
        factory = element_factory_name(msg.src)
        if state["codec"] == "h264" and is_h264_encoder_factory(factory):
            # msg.src.get_name() is the element INSTANCE name — every H.264 pipeline builds the
            # encoder as `name=enc`, so it is always "enc". The blacklist is keyed by FACTORY name
            # (nvh264enc/vah264enc/x264enc/openh264enc), so read the factory; otherwise the failing
            # encoder is never sin-binned and the next rebuild re-selects the same one.
            emit(type="warn", warn=f"h264 encoder {factory} failed mid-stream "
                                   f"({err.message}); falling back")
            # _h264_blacklist is a dict {factory: monotonic_ms}; the old `.add()` was a leftover
            # from when it was a set and would have raised AttributeError had the match fired.
            _h264_blacklist[factory] = monotonic_ms()
            # pick_h264() returns (name, props) on success and (None, None) when nothing is left —
            # BOTH are non-empty tuples, so `not pick_h264()` is ALWAYS False and this latch never
            # fired. Test the element, so once no encoder remains we settle on JPEG instead of
            # re-auditioning (and eating a 4s PREROLL freeze) on every rebuild.
            if pick_h264()[0] is None:
                state["want"] = "jpeg"
            state["out"] = (0, 0)          # force a real rebuild rather than a no-op
            GLib.idle_add(rebuild)
            return True
        # An error from pipewiresrc, videoscale, videoconvert, appsink, the pipeline itself, or an
        # unknown element is NOT evidence that another encoder can help. Rebuilding the same broken
        # source around another encoder loops forever with a black frame. Exit instead: PortalBridge
        # respawns us, which recreates the RemoteDesktop/ScreenCast session and obtains a fresh node.
        die(EXIT_LOST, f"gstreamer {factory or 'pipeline'}: {err.message} ({dbg or ''})")
    elif msg.type == Gst.MessageType.EOS:
        die(EXIT_LOST, "gstreamer: stream ended")
    return True


def teardown():
    """Drop the pipeline. NULL makes pipewiresrc close its fd, which deactivates the ScreenCast
    stream — that is what actually stops the compositor copying frames and takes idle back to 0%.
    The portal SESSION stays open, so resuming costs a pipeline build (~200ms) and never re-prompts
    the user for permission."""
    global pipeline, enc, rate
    video_health.stop()
    if pipeline is None:
        return False
    pipeline.set_state(Gst.State.NULL)
    pipeline = None
    enc = rate = None
    state["out"] = (0, 0)
    return False


_rebuild_timer = 0
# How long to let a burst of settings settle before standing a pipeline up. Long enough to cover
# the round trips a connecting client needs, short enough that nobody waits for a picture.
REBUILD_DEBOUNCE_MS = 220


def rebuild():
    """Ask for a (re)build, coalescing a burst of changes into ONE.

    WHY THIS IS DEBOUNCED, AND WHAT IT LOOKED LIKE WHEN IT WAS NOT

    Every setting that changes the pipeline used to rebuild it immediately, and a client that has
    just connected changes three of them in quick succession — because it cannot say them all at
    once. Measured on the maintainer's machine, one phone opening the remote:

        11:19:16  Video stream: 1920x1080     <- built as JPEG, before the phone had said anything
        11:19:16  Video codec: h264           <- rebuild: the phone declared WebCodecs H.264
        11:19:16  Video stream: 1920x1080
        11:19:18  Video stream: 960x540       <- rebuild: its quality preset finally arrived

    Four builds in two seconds for one viewer. Each is ~200ms with no picture and a fresh IDR after
    it, so opening the remote meant watching the screen appear, blank, appear, blank and appear
    again. That is the flash at connect time, and it is not a network problem — the machine did it
    to itself.

    The order is not fixable by reordering the client, either: the codec declaration goes out with
    the auth message, but the quality preset can only be sent after `hello` comes back, which is a
    round trip later. On a LAN that is 2ms and on a relayed cellular link it is closer to 400ms. So
    there is no fixed point at which "the client has finished talking" — which is exactly the shape
    debouncing solves. Every change restarts a short timer; the build happens when the changes stop.

    The idle case deliberately does NOT wait: `streaming` going false tears the pipeline down at
    once, because the whole point of that path is to stop the compositor copying frames the instant
    the last viewer leaves, and a quarter second of extra load is a quarter second nobody asked for.
    """
    global _rebuild_timer

    if not state["streaming"]:
        if _rebuild_timer:
            GLib.source_remove(_rebuild_timer)
            _rebuild_timer = 0
        return teardown()

    if _rebuild_timer:
        GLib.source_remove(_rebuild_timer)
    _rebuild_timer = GLib.timeout_add(REBUILD_DEBOUNCE_MS, _rebuild_now)
    return False


def _rebuild_now():
    """The actual (re)build, once the settings have stopped moving.

    The scale is baked into the pipeline instead of being swapped on a live capsfilter: changing
    caps mid-stream makes pipewiresrc renegotiate and the stream collapses to <1 fps. Tearing the
    pipeline down and standing a new one up costs ~200ms and is rock solid, and only happens when
    the resolution actually changes (startup, or the user moving the quality slider).

    No viewer, no pipeline: every caller funnels through here, so this one guard is what keeps a
    quality tweak or a stray settings push from resurrecting the encoder on an idle machine.
    """
    global pipeline, enc, rate, _rebuild_timer

    _rebuild_timer = 0

    if not state["streaming"]:
        return teardown()

    w, h = target_size()
    if pipeline is not None and (w, h) == state["out"]:
        return False
    if pipeline is not None:
        pipeline.set_state(Gst.State.NULL)
        pipeline = None
        video_health.stop()
    try:
        return build(w, h)
    except Exception as e:
        # GLib swallows exceptions raised inside idle callbacks, which would leave us alive with
        # no pipeline and no video, forever. Make it loud and let the agent restart us.
        die(EXIT_LOST, f"could not build pipeline: {e}")


def build(w, h):
    global pipeline, enc, rate

    # Scale BEFORE the colour convert: on a 4K source, converting every pixel to I420 and only
    # then shrinking costs more than the encode itself.
    caps = f"! video/x-raw,width={w},height={h} " if w else ""
    head = (
        f"pipewiresrc fd={open_pipewire_fd()} path={pipewire_target} do-timestamp=true "
        f"keepalive-time={FRAME_KEEPALIVE_MS} "
        # THE QUEUE IS NOT DECORATION — IT IS WHAT KEEPS A SLOW ENCODER OFF THE COMPOSITOR'S THREAD.
        #
        # Without it this whole chain — scale, colour convert, encode, and the socket write in
        # on_sample — runs on pipewiresrc's own streaming thread. That thread is the one draining the
        # ScreenCast stream, so anything that makes the encode slow (a 4K source, NVENC busy, a
        # momentarily blocked socket) applies BACKPRESSURE to the compositor: kwin cannot hand off the
        # next damaged frame until we have finished with the last one. The desktop itself stutters,
        # in front of the person sitting at it, because somebody far away has a bad link.
        #
        # One queue moves everything downstream onto its own thread, so the compositor hands a frame
        # over and is immediately free. leaky=downstream drops the OLDEST buffer when we cannot keep
        # up, which is exactly the right thing to throw away and exactly the right PLACE to throw it:
        # upstream of the encoder, where a dropped frame costs one frame. (Downstream of the encoder a
        # dropped P-frame corrupts every frame after it until the next IDR — which is why the appsink
        # below still has drop=false on the H.264 path.)
        #
        # max-size-buffers=2, and time/bytes disabled so they cannot impose a longer bound: two frames
        # is enough to absorb one slow encode without ever becoming a place where latency hides.
        f"! queue name=capq leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 "
        f"! videorate drop-only=true max-rate={state['fps']} name=rate "
        f"! videoscale method=bilinear {caps}"
        f"! videoconvert "
    )

    codec, elem = "jpeg", None
    # `and w` is load-bearing, and its absence cost every session H.264 about half the time.
    #
    # build() is called once when the stream is created, BEFORE the source has told us its size —
    # every such build logged "Video stream: 0x0 (source 0x0)". With w == 0 the caps filter above is
    # omitted entirely, so the encoder is asked to reach PLAYING on a source that has not negotiated
    # a format yet, and openh264enc cannot: it needs a width and a height to create an encoder at all.
    #
    # It therefore failed, was BLACKLISTED as a broken element, and since it is the only H.264 encoder
    # present on a GPU-less server, pick_h264() then returned nothing and the whole session latched to
    # JPEG for the lifetime of the helper. Nine occurrences in this log, every one of them preceded by
    # a 0x0 build, and every one of them a session that spent its life at ~79 Mbit/s of JPEG for want
    # of a number that arrived a millisecond later.
    #
    # So do not audition an encoder before there is anything to encode. JPEG covers the gap — it has
    # no such requirement — and the size change that follows rebuilds with real caps and gets H.264.
    if state["want"] == "h264" and w:
        elem, props = pick_h264()
        if elem:
            codec = "h264"

    if codec == "h264":
        # An IDR is many times the size of a P-frame, so a periodic one is a periodic bandwidth spike —
        # and on a 12-frame queue a spike is a stall. It was every 2 seconds, which is 30 spikes a
        # minute paid to solve a problem that is already solved explicitly: RequestKeyframe() is
        # called when a viewer joins and after a backlog drop, which are the only two moments a
        # client actually needs one. Keep a periodic IDR as insurance against undetected corruption,
        # but at 10 seconds rather than 2 — a fifth of the spikes for the same recovery guarantee.
        gop = max(15, state["fps"] * 10)
        _bps = h264_bitrate_bps(w, h)
        tail = (
            # PIN THE CHROMA TO 4:2:0, AND THE REASON IS THE ONLY REASON H.264 EVER WORKED HERE.
            #
            # `videoconvert` upstream has no format caps, so the format was decided by negotiation
            # with whatever encoder got picked. pipewiresrc hands KDE's screencast over as BGRx —
            # 4:4:4 — and x264enc happily accepts Y444 rather than convert, so the stream that left
            # this machine was High 4:4:4 Predictive. Read off the live encoder and off the client's
            # own VideoDecoder.configure():
            #
            #     no format caps      profile_idc=244  High 4:4:4 Predictive  avc1.f4001f
            #     format={I420,NV12}  profile_idc=100  High                   avc1.64001f
            #
            # profile_idc 244 is not a profile any HARDWARE H.264 decoder implements. iOS
            # VideoToolbox, Android MediaCodec and essentially every phone and TV do Baseline/Main/
            # High (66/77/100) and nothing above it. Desktop Chrome hid this completely, because it
            # falls back to a software decoder and decodes 4:4:4 without complaint — measured here,
            # 1761 frames, zero errors — which is why every previous session that tested on a
            # desktop browser concluded the stream was fine. On the phone the picture held only
            # until the decoder actually had to run, then failed, and the client did exactly what
            # it was designed to do: three strikes at 15/30/60s and settle on JPEG. JPEG at 1080p
            # then saturates the link, which is the slowness, and the teardown/rebuild churn around
            # it is the screen cutting out.
            #
            # A LIST, not `format=I420`: NV12 is what the hardware encoders (nvh264enc, vah264enc)
            # want, and both members are 4:2:0, so negotiation still picks the cheapest conversion
            # for whichever encoder pick_h264() landed on — it just can no longer pick 4:4:4.
            # Nothing here is a quality loss worth having: at these bitrates 4:2:0 is what every
            # video call on earth uses, and 4:4:4 was costing chroma bandwidth on a desktop stream
            # that no decoder on the far end could use.
            "! video/x-raw,format=(string){ I420, NV12 } "
            # ONE value, computed for the size this pipeline is actually building, then expressed in
            # whichever unit the chosen encoder wants. Calling the budget three times invited the three
            # to disagree; and it must be told w/h explicitly, since state["out"] is not set yet here.
            f"! {elem} " + props.format(kbps=max(1, _bps // 1000), bps=_bps,
                                        maxbps=int(_bps * 1.5), gop=gop)
            + " name=enc "
            # config-interval=-1 repeats SPS/PPS before every keyframe: a decoder that joins late
            # needs them, and on a live stream "late" is the only way anyone ever joins.
            # byte-stream (Annex-B) is what WebCodecs takes with no `description` — the alternative,
            # AVCC, would mean shipping an avcC box out of band for no gain.
            "! h264parse config-interval=-1 "
            "! video/x-h264,stream-format=byte-stream,alignment=au "
            # drop=false, unlike JPEG. Every JPEG is a whole picture, so dropping one costs one
            # frame; an H.264 P-frame is a diff against its predecessor, so dropping one corrupts
            # everything after it until the next IDR. Raw frames are already dropped upstream by
            # videorate — once a frame is ENCODED it is delivered, or the stream is a mess.
            "! appsink name=sink emit-signals=true max-buffers=8 drop=false sync=false"
        )
    else:
        tail = (
            f"! jpegenc quality={state['quality']} idct-method=ifast name=enc "
            "! appsink name=sink emit-signals=true max-buffers=1 drop=true sync=false"
        )

    pipeline = Gst.parse_launch(head + tail)
    enc = pipeline.get_by_name("enc")
    rate = pipeline.get_by_name("rate")
    if codec == "h264":
        tune_for_latency(enc, _bps, state["fps"])
    pipeline.get_by_name("sink").connect("new-sample", on_sample)
    bus_ = pipeline.get_bus()
    bus_.add_signal_watch()
    bus_.connect("message", on_bus)

    # An encoder that exists is not an encoder that runs. NVENC opens a session against the GPU and
    # can simply refuse — out of VRAM, out of sessions — and it refuses at PREROLL, not at
    # parse time, so the only honest test is to wait for PLAYING and see. If it will not start we
    # blacklist that element and come back through here with the next one; JPEG is the floor.
    pipeline.set_state(Gst.State.PLAYING)
    ok, _st, _pending = pipeline.get_state(4 * Gst.SECOND)
    if ok not in (Gst.StateChangeReturn.SUCCESS, Gst.StateChangeReturn.NO_PREROLL):
        # get_state() only says the PIPELINE did not become usable. It does not say the encoder was
        # at fault. Pull the ERROR which caused the failed transition while this callback still owns
        # the main context: a pipewiresrc error left in the queue is otherwise dispatched later and,
        # historically, the codec branch below condemned every encoder before that happened.
        startup_msg = bus_.timed_pop_filtered(0, Gst.MessageType.ERROR)
        startup_factory = element_factory_name(startup_msg.src) if startup_msg is not None else ""
        if startup_msg is not None:
            startup_error, startup_debug = startup_msg.parse_error()
            startup_reason = f"{startup_error.message} ({startup_debug or ''})"
        else:
            startup_reason = f"state transition returned {ok}"
        pipeline.set_state(Gst.State.NULL)
        pipeline = None
        if codec == "h264" and is_h264_encoder_factory(startup_factory):
            emit(type="warn", warn=f"{elem} would not start; falling back")
            # Defence in depth for the same mistake: only condemn an element that failed with real
            # dimensions. The selection above should already never hand us an encoder at w == 0, and
            # if that ever regresses, a permanent JPEG latch is far too expensive a way to find out.
            if w:
                _h264_blacklist[elem] = GLib.get_monotonic_time() // 1000
                # The commonest reason a hardware encoder refuses to open on this machine is that
                # the local brain is holding the card. Ask for it back and come round again; see the
                # note on _h264_blacklist. Costs nothing where there is no GPU and no brain.
                free_gpu_and_retry()
                # (name, props) or (None, None) — both truthy as tuples, so test the element.
                if pick_h264()[0] is None:
                    state["want"] = "jpeg"
            return build(w, h)
        # Unknown is deliberately fatal too. Only a positive encoder factory identity licenses a
        # codec fallback; guessing here recreates the same black-but-'healthy' loop this guard fixes.
        die(EXIT_LOST, f"gstreamer {startup_factory or 'pipeline'} would not start: "
                       f"{startup_reason}")

    state["codec"] = codec
    state["out"] = (w, h)
    # Start only after PLAYING was proven. The synchronous get_state above may legitimately spend
    # four seconds auditioning an encoder; counting that setup time as starvation would condemn a
    # pipeline at the instant it became healthy.
    video_health.start(monotonic_ms())
    if w:
        emit(type="video", codec=codec, encoder=(elem or "jpegenc"),
             width=w, height=h, source_width=state["sw"], source_height=state["sh"],
             logical_width=logical_w, logical_height=logical_h, node=node_id,
             pipewire_serial=pipewire_target)
    return False  # one-shot idle


def check_video_health():
    """Retire a PLAYING pipeline which stopped delivering its one-second keepalive frames."""
    if state["streaming"] and pipeline is not None and video_health.stalled(monotonic_ms()):
        age = video_health.age_ms(monotonic_ms())
        phase = "after frames had started" if video_health.seen_frame else "before its first frame"
        die(EXIT_LOST, f"video pipeline starved {phase}: no delivered frame for {age} ms; "
                       "restarting the portal session")
    return True


_last_keyframe = 0


def force_keyframe():
    """A phone that has just connected holds no reference frames, so every P-frame it receives is
    noise until an IDR arrives. Rather than make it wait up to a GOP, ask for one now.

    Rate-limited, because the one moment this gets asked for repeatedly is the one moment it must
    not be granted repeatedly. Every caller — a viewer joining, the agent dropping a backlog, a
    phone whose decoder gave up — is reacting to a link that is already struggling, and an IDR is
    several times the size of a P-frame. Granting them all turns a recoverable stall into a
    self-feeding one: each keyframe deepens the congestion that triggers the next request. 500ms is
    below anything a person perceives as a delay in recovering, and far above the rate at which
    requests can pile up.
    """
    global _last_keyframe
    if pipeline is None or state["codec"] != "h264":
        return
    now_ms = GLib.get_monotonic_time() // 1000
    if now_ms - _last_keyframe < 500:
        return
    _last_keyframe = now_ms
    try:
        pipeline.send_event(
            GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE, True, 0))
    except Exception:
        pass


# Deliberately NOT building a pipeline here. We come up idle and stay idle until the agent tells
# us somebody is watching ({"type":"video","streaming":true}) — see the note on state["streaming"].
# Input still works while idle: pointer and keys go through portal D-Bus calls, not the pipeline.


# ---------------------------------------------------------------- input loop
def set_prop(el, name, value):
    """Set a property only if this encoder actually has it. The two encoders share one slider but
    not one property: jpegenc has `quality`, the H.264 family has `bitrate` — and openh264enc
    counts it in bits while everyone else counts kilobits. Setting a property an element does not
    have raises, and this runs on the pipeline thread."""
    if el is not None and el.find_property(name) is not None:
        el.set_property(name, value)
        return True
    return False


# openh264enc counts `bitrate` in BITS per second. x264enc, nvh264enc, vah264enc and vah264lpenc all
# count it in KILOBITS. There is no property to interrogate for the difference, so it has to be known.
BITS_PER_SECOND_ENCODERS = {"openh264enc"}


def apply_h264_bitrate():
    """Set the live encoder's bitrate in the units THAT encoder uses.

    THE BUG THIS REPLACES, WHICH MADE THE PICTURE UNWATCHABLE
    ---------------------------------------------------------
    This used to be:

        if not set_prop(enc, "bitrate", h264_bitrate()):
            set_prop(enc, "bitrate", h264_bitrate() * 1000)   # openh264enc counts bits

    which reads as "try kilobits, and if this encoder has no such property, try bits". But set_prop
    reports whether the property EXISTS, not whether the value made sense — and openh264enc has a
    `bitrate` property. So the first call always succeeded, writing 6200 into a field measured in
    bits per second: 6.2 kbit/s where 6.2 Mbit/s was meant, a thousandfold under-run. The fallback
    line, and its comment about openh264enc, could never run on openh264enc.
    Worse, it is not the pipeline's initial state that is wrong — the build string interpolates {bps}
    correctly — it is the FIRST settings message from the client that destroys it. Every viewer that
    connected, pushed its quality preset, and got H.264 dropped to a few kilobits within a second of
    joining. On a GPU-less server openh264enc is the only H.264 encoder there is, so this was every
    H.264 session, and 1080p at 6 kbit/s is not a degraded picture, it is a smear that never resolves.
    """
    if enc is None:
        return
    bps = h264_bitrate_bps()
    try:
        name = enc.get_factory().get_name()
    except Exception:
        name = ""
    in_bits = name in BITS_PER_SECOND_ENCODERS
    set_prop(enc, "bitrate", bps if in_bits else max(1, bps // 1000))
    # The ceiling has to move with the target or it stops being a ceiling and becomes a cap that
    # throttles the very preset the user just asked for.
    ceiling = int(bps * 1.5)
    set_prop(enc, "max-bitrate", ceiling if in_bits else max(1, ceiling // 1000))


def apply_h264_gop():
    """Keep the periodic IDR at ten SECONDS after the frame rate moves.

    The GOP is baked into the launch string as `fps * 10`, which is only ten seconds at the frame
    rate the pipeline was built with. Drop from 30fps to 10 and that same number becomes thirty
    seconds between insurance keyframes; climb to 60 and it becomes five, which is 12 extra
    bandwidth spikes a minute paid for nothing. The two encoder families spell the same idea
    differently and set_prop skips whichever name this element does not have.
    """
    gop = max(15, state["fps"] * 10)
    set_prop(enc, "gop-size", gop)
    set_prop(enc, "key-int-max", gop)


def set_video(m):
    # quality and fps are plain element properties — safe to change on a running pipeline.
    # scale and codec change the pipeline itself, which is not, so they go through rebuild().
    if "streaming" in m:
        want = bool(m["streaming"])
        if want != state["streaming"]:
            state["streaming"] = want
            rebuild()                       # builds when a viewer arrives, tears down when the last leaves
            # The last viewer leaving is the honest moment to hand the keyboard group back: the
            # phone that borrowed it is gone, and whoever sits at the desk next should find
            # their own layout. A quieter timer would guess; this is an event.
            if not want:
                restore_layout()
            emit(type="video", streaming=want)
    # FPS FIRST, AND THE ORDER IS THE FIX.
    #
    # The H.264 budget is bits-per-pixel x width x height x FPS (see h264_bitrate_bps), so the frame
    # rate is an INPUT to the bitrate, not an independent knob. This block used to run after the
    # quality block, so a client that sent {quality, fps} together — which is exactly what
    # pushSettings does, in one message — had its bitrate computed against the PREVIOUS frame rate
    # and then never recomputed. Halving the rate left the encoder spending a full-rate budget on
    # half the frames; doubling it left every frame with half the bits it was promised, which looks
    # like the quality slider having no effect and reads as a soft, smeary picture that no setting
    # fixes.
    #
    # Setting it first means the quality block below computes against the rate that is now true, and
    # an fps-only message re-applies the budget itself.
    if "fps" in m:
        state["fps"] = max(1, min(60, int(m["fps"])))
        if rate is not None:
            rate.set_property("max-rate", state["fps"])
        if state["codec"] == "h264" and "quality" not in m:
            apply_h264_bitrate()
            apply_h264_gop()
    if "quality" in m:
        state["quality"] = max(10, min(95, int(m["quality"])))
        if state["codec"] == "h264":
            apply_h264_bitrate()
            apply_h264_gop()
        else:
            set_prop(enc, "quality", state["quality"])
    if "codec" in m:
        want = "h264" if str(m["codec"]).lower() == "h264" else "jpeg"
        if want != state["want"]:
            state["want"] = want
            state["out"] = (0, 0)   # the pipeline is different, not merely differently sized
            rebuild()
    # An explicit pixel width wins over the fraction, and clearing it (0) goes back to the
    # fraction — so a client can move between the two without the helper being restarted.
    if "width" in m:
        want = int(m["width"] or 0)
        state["width"] = max(480, min(want, MAX_WIDTH)) if want else 0
        rebuild()
    if "scale" in m:
        state["scale"] = max(0.2, min(1.0, float(m["scale"])))
        rebuild()
    return False


def handle(m):
    t = m.get("type")
    if t == "absolute":
        # x,y arrive normalized 0..1; the portal wants the logical desktop space.
        notify("NotifyPointerMotionAbsolute", "(oa{sv}udd)",
               (session, empty, node_id,
                min(max(float(m["x"]), 0.0), 1.0) * (logical_w - 1),
                min(max(float(m["y"]), 0.0), 1.0) * (logical_h - 1)))
    elif t == "relative":
        notify("NotifyPointerMotion", "(oa{sv}dd)", (session, empty, float(m["dx"]), float(m["dy"])))
    elif t == "button":
        notify("NotifyPointerButton", "(oa{sv}iu)", (session, empty, int(m["button"]), 1 if m["down"] else 0))
    elif t == "axis":
        notify("NotifyPointerAxis", "(oa{sv}dd)", (session, empty, float(m["dx"]), float(m["dy"])))
    elif t == "axisDiscrete":
        notify("NotifyPointerAxisDiscrete", "(oa{sv}ui)", (session, empty, int(m["axis"]), int(m["steps"])))
    elif t == "key":
        notify("NotifyKeyboardKeycode", "(oa{sv}iu)", (session, empty, int(m["code"]), 1 if m["down"] else 0))
    elif t == "keysym":
        notify("NotifyKeyboardKeysym", "(oa{sv}iu)", (session, empty, int(m["keysym"]), 1 if m["down"] else 0))
    elif t == "keysyms":
        # A committed phone edit arrives as one ordered batch. Entries carry a keysym (the
        # character, resolved against whatever layout is loaded), a raw evdev code (a position, or
        # a modifier, which has no character to resolve), or a keymap GROUP to select first. All
        # three are needed in one ordered stream: a capital letter is Shift-down, keysym, Shift-up,
        # and an Arabic word is group-select then positions — splitting either across messages
        # races, and the group race is the one that produced "lvpfhab" for "مرحبا".
        events = m.get("events", [])
        # A batch that changes the group is executed AWAITED, end to end. A caller may also request
        # that guarantee explicitly with sync:true — the Unicode paste fallback uses it when its
        # synthetic sequence must not be overtaken by a later input batch. Everything else keeps the
        # fire-and-forget path, because serializing ordinary typing at compositor pace freezes the
        # picture for no ordering benefit.
        ordered = bool(m.get("sync")) or any("layout" in e for e in events)
        send = notify_sync if ordered else notify
        for event in events:
            if "layout" in event:
                if not select_group(str(event["layout"]), send):
                    # The group we need does not exist. Typing the rest would deliver the OTHER
                    # layout's reading of those positions — the exact corruption this design
                    # exists to prevent — so the run is dropped and reported.
                    emit(type="warn", warn="dropped a typed run: its keyboard group is unavailable")
                    break
            elif "code" in event:
                send("NotifyKeyboardKeycode", "(oa{sv}iu)",
                     (session, empty, int(event["code"]), 1 if event["down"] else 0))
                layout_state["typed"] = True
            else:
                send("NotifyKeyboardKeysym", "(oa{sv}iu)",
                     (session, empty, int(event["keysym"]), 1 if event["down"] else 0))
                layout_state["typed"] = True
    elif t == "keyframe":
        # A phone that just connected has no reference frame. Asking costs one larger frame;
        # not asking costs it up to a whole GOP of garbage.
        GLib.idle_add(lambda: (force_keyframe(), False)[1])
    elif t == "video":
        GLib.idle_add(set_video, m)
    elif t == "ping":
        emit(type="pong")


def stdin_loop():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except Exception as e:
            emit(type="error", error=str(e))
    loop.quit()


load_layouts()

emit(type="ready", backend="KDE RemoteDesktop + ScreenCast portal", node=node_id,
     logical_width=logical_w, logical_height=logical_h)

loop = GLib.MainLoop()
GLib.timeout_add(FRAME_HEALTH_CHECK_MS, check_video_health)
threading.Thread(target=stdin_loop, daemon=True).start()
try:
    loop.run()
finally:
    # Give the user their own keyboard group back before going away. Leaving a desk keyboard
    # on Arabic because a phone typed a word an hour ago is the same class of theft the
    # clipboard borrow was careful to avoid.
    restore_layout()
    if pipeline is not None:
        pipeline.set_state(Gst.State.NULL)

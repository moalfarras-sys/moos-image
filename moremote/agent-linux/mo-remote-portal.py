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
import json, os, socket, struct, sys, threading, uuid

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


def notify(method, sig, args):
    """Input injection. A dead session raises on every call — bail out rather than swallow it."""
    global _notify_failures
    try:
        bus.call_sync(BUS, PATH, REMOTE, method, GLib.Variant(sig, args), None,
                      Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
        _notify_failures = 0
    except GLib.GError as e:
        _notify_failures += 1
        if _notify_failures >= 5:
            die(EXIT_LOST, f"input injection failing: {e.message}")
        raise


# ---------------------------------------------------------------- frame transport
frames = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
frames.connect(sys.argv[1])
frames_lock = threading.Lock()
frames_alive = True


def send_frame(data):
    global frames_alive
    if not frames_alive:
        return
    with frames_lock:
        try:
            frames.sendall(struct.pack("<I", len(data)) + data)
        except OSError:
            frames_alive = False  # agent went away; the pipeline is torn down with us


# ---------------------------------------------------------------- gstreamer
Gst.init(None)

MAX_WIDTH = 1920
# `streaming` gates the encode pipeline on somebody actually watching. It starts False and the
# agent flips it on the first viewer, because a PLAYING pipeline is not free while nobody looks:
# pipewiresrc keeps the ScreenCast stream active, so the COMPOSITOR copies every damaged frame out
# for us, forever. Measured on this machine with zero clients connected: kwin_wayland 55% of a core
# and this helper 32%, permanently — the desktop felt broken and the GPU was one Konsole away from
# the VRAM ceiling that SIGSEGVs kwin. Idle must cost nothing.
state = {"sw": 0, "sh": 0, "scale": 1.0, "quality": 70, "fps": 30, "out": (0, 0),
         "codec": "jpeg", "want": "jpeg", "streaming": False}
pipeline = None
enc = rate = None


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
    ("x264enc",     "bitrate={kbps} key-int-max={gop} tune=zerolatency speed-preset=veryfast"),
    # usage-type=screen tells openh264 the content is a desktop, not camera footage. It changes how the
    # rate controller spends its budget: a desktop is large flat areas and thin high-contrast text, and
    # the screen profile stops it smoothing that text away to hold a frame rate nothing is asking for.
    # max-bitrate is the ceiling the rate controller is otherwise free to ignore — openh264 overshoots
    # hard on a scene change (a window opening, a page scrolling), and an overshoot on a link with a
    # 12-frame queue is a stall. Ceiling at 1.5x the target so bursts have room without becoming spikes.
    ("openh264enc", "bitrate={bps} max-bitrate={maxbps} gop-size={gop} complexity=low "
                    "rate-control=bitrate usage-type=screen"),
]
_h264_blacklist = set()   # elements that were present and then failed to start


def pick_h264():
    """The best H.264 encoder that is installed and has not already failed on us."""
    reg = Gst.Registry.get()
    for name, props in H264_ENCODERS:
        if name in _h264_blacklist:
            continue
        if reg.lookup_feature(name) is not None:
            return name, props
    return None, None


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
    """Encode resolution. `scale` is a fraction of the *target* width, not of the source: a 4K
    source is already clamped to MAX_WIDTH, so scaling the raw 3840 and then clamping would make
    every scale above ~0.5 collapse onto the same 1920 and the slider would do nothing."""
    sw, sh = state["sw"], state["sh"]
    if not sw or not sh:
        return (0, 0)
    target = min(sw, MAX_WIDTH)
    w = max(480, min(int(target * state["scale"]), target)) // 2 * 2
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
            send_frame(info.data)
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
        if state["codec"] == "h264":
            elem = msg.src.get_name() if msg.src else ""
            emit(type="warn", warn=f"h264 encoder failed mid-stream ({err.message}); falling back")
            for name, _ in H264_ENCODERS:
                if name in elem:
                    _h264_blacklist.add(name)
            if not pick_h264():
                state["want"] = "jpeg"
            state["out"] = (0, 0)          # force a real rebuild rather than a no-op
            GLib.idle_add(rebuild)
            return True
        die(EXIT_LOST, f"gstreamer: {err.message} ({dbg or ''})")
    elif msg.type == Gst.MessageType.EOS:
        die(EXIT_LOST, "gstreamer: stream ended")
    return True


def teardown():
    """Drop the pipeline. NULL makes pipewiresrc close its fd, which deactivates the ScreenCast
    stream — that is what actually stops the compositor copying frames and takes idle back to 0%.
    The portal SESSION stays open, so resuming costs a pipeline build (~200ms) and never re-prompts
    the user for permission."""
    global pipeline, enc, rate
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
        f"pipewiresrc fd={open_pipewire_fd()} path={node_id} do-timestamp=true keepalive-time=1000 "
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
    if ok == Gst.StateChangeReturn.FAILURE:
        pipeline.set_state(Gst.State.NULL)
        pipeline = None
        if codec == "h264":
            emit(type="warn", warn=f"{elem} would not start; falling back")
            # Defence in depth for the same mistake: only condemn an element that failed with real
            # dimensions. The selection above should already never hand us an encoder at w == 0, and
            # if that ever regresses, a permanent JPEG latch is far too expensive a way to find out.
            if w:
                _h264_blacklist.add(elem)
                if not pick_h264():
                    state["want"] = "jpeg"
            return build(w, h)
        die(EXIT_LOST, "the JPEG pipeline would not start")

    state["codec"] = codec
    state["out"] = (w, h)
    if w:
        emit(type="video", codec=codec, encoder=(elem or "jpegenc"),
             width=w, height=h, source_width=state["sw"], source_height=state["sh"],
             logical_width=logical_w, logical_height=logical_h, node=node_id)
    return False  # one-shot idle


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
        # A committed phone edit arrives as one ordered batch. Entries carry EITHER a keysym (the
        # character, resolved against whatever layout is loaded) or a raw evdev code (a modifier,
        # which has no character to resolve). Both are needed in one ordered stream: a capital
        # letter is Shift-down, keysym, Shift-up, and splitting that across messages races.
        for event in m.get("events", []):
            if "code" in event:
                notify("NotifyKeyboardKeycode", "(oa{sv}iu)",
                       (session, empty, int(event["code"]), 1 if event["down"] else 0))
            else:
                notify("NotifyKeyboardKeysym", "(oa{sv}iu)",
                       (session, empty, int(event["keysym"]), 1 if event["down"] else 0))
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


emit(type="ready", backend="KDE RemoteDesktop + ScreenCast portal", node=node_id,
     logical_width=logical_w, logical_height=logical_h)

loop = GLib.MainLoop()
threading.Thread(target=stdin_loop, daemon=True).start()
try:
    loop.run()
finally:
    if pipeline is not None:
        pipeline.set_state(Gst.State.NULL)

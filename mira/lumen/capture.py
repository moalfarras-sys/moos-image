"""The screen as Lumen sees it: a tiny RGB thumbnail of one monitor, delivered a few dozen times a second.

On Wayland no program can read the screen by itself. The compositor hands the picture out through
xdg-desktop-portal's ScreenCast interface as a PipeWire stream, after the owner has approved it in
a system dialog. Everything here follows from that, and from the fact that the analysis needs only
64x36 pixels of a 3840x2160 desktop.

The portal session asks for exactly what Lumen needs and no more. It is a ScreenCast session, not
the RemoteDesktop session Mo PC Remote opens, because following the picture requires no input
control and the grant should not imply any. It asks for one monitor (types=1, multiple=False) with
the cursor HIDDEN (cursor_mode=1). The pointer is not part of the picture a light should follow,
and with the cursor painted in, every mouse movement would damage the screen and produce a frame.
persist_mode=2 keeps the grant until the owner revokes it, so the portal returns a restore token
and the next start passes without a dialog. The token is single-use: a successful Start consumes
the one it was given and returns a replacement. The replacement is written whole or not at all
(staging file, fsync, rename, mode 0600), because losing it means the owner is asked again.
The stream's PipeWire target is the ScreenCast v6 `pipewire-serial` when the portal provides it.
A node id can be reused after a suspend or a monitor hot-plug, and reconnecting to a reused id
yields a healthy-looking pipeline showing nothing. That trap was found in mo-remote-portal.py, whose
patterns this module follows without importing it.

The pipeline is ordered for cost, and the order was chosen by measurement, not by expectation
(3840x2160 BGRx live source at 30 fps, i5-14400F and RTX 2080 SUPER, process CPU from
/proc/self/stat; the source's own cost is excluded by re-pushing one frame with imagefreeze):

    videoscale nearest-neighbour -> 64x36             0.5-0.6 % of one core
    videoscale nearest -> 384x216, bilinear2 -> 64x36  1.4-1.5 %   <- used
    cudaupload ! cudascale ! cudadownload             14.5-15 %
    glupload ! glcolorconvert ! glcolorscale          16.7-24 %

The GPU paths lose because a frame in system memory must first be uploaded whole, 33 MB per
frame, before the GPU can shrink it. Shrinking on the CPU reads only the pixels it samples. The
two-stage scale costs about one percent of a core more than a single nearest-neighbour step and
buys an average of 36 samples per output pixel instead of one. Measured on moving test content,
that reduces frame-to-frame jitter of a region's colour 2.4x (scrolling bars) to 8x (noise). Without
it, fine detail such as text, foliage or film grain becomes flicker on the wall. Colour conversion
happens last, on 64x36 pixels, because converting 4K and then shrinking it is the expensive order.

The frame rate is capped at the SOURCE. The capsfilter after pipewiresrc offers
`max-framerate=<fps>/1`, which pipewiresrc turns into the stream's maxFramerate, so a compositor that
honours it can stop copying frames the consumer would only discard. The KWin throttling has not yet
been measured on a live portal stream. A second caps structure without the field keeps negotiation
working with a compositor that does not offer it. `videorate drop-only` enforces the cap whatever
was negotiated.

The caps never change mid-stream. The output is fixed at width x height RGB for the pipeline's
whole life. A monitor mode switch upstream is absorbed by the scaler and is invisible downstream.
Renegotiating a live pipewiresrc collapses the stream to under one frame a second (Mo PC Remote
measured this).

`appsink max-buffers=1 drop=true sync=false`, pulled from this module's own thread, means the
newest frame always wins. Nothing slow ever runs on GStreamer's streaming thread, so a slow
consumer costs frames, never compositor time.

A still desktop produces no frames, so pipewiresrc repeats its last buffer every second
(keepalive). Silence for five seconds therefore means the stream is dead, not that the screen is
still. Death is reported as state 'error' with a reason. The owner ending the share from the tray
(the portal session closes) is reported the same way. start() opens a new session, which the
restore token makes silent. pipewiresrc duplicates the PipeWire fd it is given, so this module
closes its own copy, and only after the pipeline has reached NULL: the plugin caches connections by
fd NUMBER, and a number reused while an old connection lives would be handed the stale one.
"""
from __future__ import annotations

import collections
import os
import pathlib
import threading
import time
import uuid
from typing import Callable

try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gio, GLib, Gst
except (ImportError, ValueError):           # PyGObject or GStreamer typelibs missing
    Gio = GLib = Gst = None

PORTAL_BUS = 'org.freedesktop.portal.Desktop'
PORTAL_PATH = '/org/freedesktop/portal/desktop'
CAST = 'org.freedesktop.portal.ScreenCast'
REQUEST = 'org.freedesktop.portal.Request'
SESSION = 'org.freedesktop.portal.Session'

SOURCE_MONITOR = 1            # ScreenCast source types: 1 monitor, 2 window, 4 virtual
CURSOR_HIDDEN = 1             # cursor modes: 1 hidden, 2 embedded, 4 metadata
PERSIST_UNTIL_REVOKED = 2     # persist modes: 0 none, 1 while the app runs, 2 until revoked

ANSWER_TIMEOUT_S = 120        # the owner may take a while in the dialog; not forever
CALL_TIMEOUT_MS = 10000
KEEPALIVE_MS = 1000           # pipewiresrc repeats its last frame this often on a still desktop
STALL_S = 5.0                 # five missed keepalives: the stream is dead
PULL_MS = 100                 # how long one pull waits; also how quickly stop() is noticed
SCALE_STEP = 6                # the intermediate picture is 6x the output: 36 samples per pixel
FPS_WINDOW_S = 2.0

STATES = ('idle', 'asking', 'running', 'denied', 'error')


class PortalDenied(Exception):
    """The owner declined (portal response code 1)."""


class CaptureError(Exception):
    def __init__(self, message: str, reason: str = 'error'):
        super().__init__(message)
        self.reason = reason


class _Stopped(Exception):
    """stop() was called while the portal was still talking."""


class _Portal:
    """One ScreenCast session through xdg-desktop-portal, driven on the capture thread's context.

    Every portal call returns a Request object path at once and answers later with that
    Request's Response signal. The subscription is made BEFORE the call, on the path the
    portal will use (derived from our bus name and the handle_token), so an answer cannot
    arrive unheard.
    """

    def __init__(self, bus, ctx, stopping: threading.Event, restore_token: str | None):
        self.bus = bus
        self.ctx = ctx
        self.stopping = stopping
        self.restore_token_in = restore_token
        self.restore_token: str | None = None
        self.session: str | None = None
        self.closed = False
        self._closed_sub = None
        self._sender = bus.get_unique_name().lstrip(':').replace('.', '_')
        self._prefix = 'mira_lumen_' + uuid.uuid4().hex[:12]

    # ── the call sequence ────────────────────────────────────────────
    def open(self, keep_token: Callable[[str | None], None]) -> tuple[int, int]:
        """CreateSession -> SelectSources -> Start -> OpenPipeWireRemote. Returns (fd, target).
        keep_token receives Start's replacement restore token at once: Start has consumed the old
        one, so the new one must be kept even if a later step fails."""
        tok = self._prefix
        created = self._request('CreateSession', '(a{sv})', ({
            'handle_token': GLib.Variant('s', tok + '_c'),
            'session_handle_token': GLib.Variant('s', tok),
        },))
        self.session = str(created['session_handle'])
        self._closed_sub = self.bus.signal_subscribe(
            PORTAL_BUS, SESSION, 'Closed', self.session, None, Gio.DBusSignalFlags.NONE,
            self._on_closed)

        options = {
            'handle_token': GLib.Variant('s', tok + '_s'),
            'types': GLib.Variant('u', SOURCE_MONITOR),
            'multiple': GLib.Variant('b', False),
            'cursor_mode': GLib.Variant('u', CURSOR_HIDDEN),
            'persist_mode': GLib.Variant('u', PERSIST_UNTIL_REVOKED),
        }
        if self.restore_token_in:
            options['restore_token'] = GLib.Variant('s', self.restore_token_in)
        self._request('SelectSources', '(oa{sv})', (self.session, options))

        started = self._request('Start', '(osa{sv})', (
            self.session, '', {'handle_token': GLib.Variant('s', tok + '_x')}))
        token = started.get('restore_token')
        self.restore_token = str(token) if token else None
        keep_token(self.restore_token)
        streams = started.get('streams') or []
        if not streams:
            raise CaptureError('the portal returned no screen stream', 'portal')
        node_id, props = streams[0]
        target = int((props or {}).get('pipewire-serial', node_id))

        reply, fds = self.bus.call_with_unix_fd_list_sync(
            PORTAL_BUS, PORTAL_PATH, CAST, 'OpenPipeWireRemote',
            GLib.Variant('(oa{sv})', (self.session, {})), GLib.VariantType.new('(h)'),
            Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None, None)
        fd = fds.get(reply.unpack()[0])        # a duplicate that this process owns
        return fd, target

    def close(self) -> None:
        if self._closed_sub is not None:
            self.bus.signal_unsubscribe(self._closed_sub)
            self._closed_sub = None
        if self.session and not self.closed:
            try:
                self.bus.call_sync(PORTAL_BUS, self.session, SESSION, 'Close', None, None,
                                   Gio.DBusCallFlags.NONE, 2000, None)
            except GLib.Error:
                pass                            # already gone: nothing left to release
        self.session = None

    # ── plumbing ─────────────────────────────────────────────────────
    def _on_closed(self, *_args) -> None:
        self.closed = True

    def _subscribe(self, path: str, answer: dict) -> int:
        def response(_conn, _sender, _path, _iface, _signal, params):
            if 'code' not in answer:
                answer['code'], answer['results'] = params.unpack()
        return self.bus.signal_subscribe(PORTAL_BUS, REQUEST, 'Response', path, None,
                                         Gio.DBusSignalFlags.NONE, response)

    def _request(self, method: str, signature: str, values: tuple) -> dict:
        handle = values[-1]['handle_token'].unpack()
        path = f'{PORTAL_PATH}/request/{self._sender}/{handle}'
        answer: dict = {}
        subs = [self._subscribe(path, answer)]
        try:
            reply = self.bus.call_sync(PORTAL_BUS, PORTAL_PATH, CAST, method,
                                       GLib.Variant(signature, values), GLib.VariantType.new('(o)'),
                                       Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None)
            returned = reply.unpack()[0]
            if returned != path:                # portals before 0.9 chose their own path
                path = returned
                subs.append(self._subscribe(path, answer))
            self._wait(lambda: 'code' in answer, ANSWER_TIMEOUT_S)
            if 'code' not in answer:
                self._close_request(path)       # take the dialog off the owner's screen
                if self.stopping.is_set():
                    raise _Stopped()
                raise CaptureError('no answer from the screen-sharing dialog', 'timeout')
        finally:
            for sub in subs:
                self.bus.signal_unsubscribe(sub)
        code = answer['code']
        if code == 1:
            raise PortalDenied('the owner declined screen sharing')
        if code != 0:
            raise CaptureError(f'the screen-sharing portal ended {method} (code {code})', 'portal')
        return answer['results'] or {}

    def _close_request(self, path: str) -> None:
        try:
            self.bus.call_sync(PORTAL_BUS, path, REQUEST, 'Close', None, None,
                               Gio.DBusCallFlags.NONE, 2000, None)
        except GLib.Error:
            pass

    def _wait(self, done: Callable[[], bool], timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        tick = GLib.timeout_source_new(PULL_MS)   # wakes the blocking iteration to re-check
        tick.set_callback(lambda *_: True)
        tick.attach(self.ctx)
        try:
            while not done() and not self.stopping.is_set() and time.monotonic() < deadline:
                self.ctx.iteration(True)
        finally:
            tick.destroy()


class ScreenCapture:
    """One monitor, shrunk to width x height RGB24, handed to on_frame on the capture thread."""

    def __init__(self, on_frame: Callable[[bytes, int, int], None], *, fps: int = 30,
                 width: int = 64, height: int = 36, token_path: pathlib.Path | None = None,
                 source: str = 'portal', bus=None):
        """on_frame(rgb: bytes, width: int, height: int) is called on a capture thread for every
        frame (RGB24, row-major, len == width*height*3). source='portal' = the desktop via the
        ScreenCast portal (monitor, cursor hidden); source='test' = videotestsrc (tests, review).
        token_path keeps the portal's restore token across processes (0600); without it the token
        lives only as long as this object. bus replaces the session bus (tests pass a fake)."""
        if not callable(on_frame):
            raise ValueError('on_frame must be callable')
        for name, value, lo, hi in (('fps', fps, 1, 60), ('width', width, 4, 512),
                                    ('height', height, 4, 512)):
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise ValueError(f'{name} must be an integer {lo}..{hi}')
        if source not in ('portal', 'test'):
            raise ValueError("source must be 'portal' or 'test'")
        self._on_frame = on_frame
        self.fps, self.width, self.height = fps, width, height
        self.token_path = pathlib.Path(token_path) if token_path is not None else None
        self.source = source
        self._bus = bus
        self.state = 'idle'
        self.error = ''
        self.reason = ''
        self._token: str | None = None
        self._token_error = ''
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._ctx = None
        self._pipeline = None
        self._frames = 0
        self._times: collections.deque = collections.deque(maxlen=int(FPS_WINDOW_S * 60) + 8)
        self._since = 0.0
        self._callback_errors = 0
        self._callback_error = ''

    # ── public ───────────────────────────────────────────────────────
    def start(self) -> None:
        """Begin capturing. Non-blocking: watch `state` ('asking' while the portal may show its
        dialog, then 'running', or 'denied'/'error' with `error` saying why). Calling it while
        asking or running does nothing; after 'error' or 'denied' it tries again."""
        with self._lock:
            old = self._thread
            if old is not None and old.is_alive() and not self._stopping.is_set():
                return
        if old is not None and old.is_alive():
            old.join(timeout=3.0)                  # a stop() still finishing; it needs the lock
        with self._lock:
            if self._thread is not old:
                return                             # another start() won the race
            if old is not None and old.is_alive():
                self._set('error', 'the previous capture is still shutting down', 'busy')
                return
            if Gst is None:
                self._set('error', 'GStreamer for Python (PyGObject) is not available', 'missing')
                return
            Gst.init(None)
            self._stopping = stopping = threading.Event()
            self._frames = 0
            self._times.clear()
            self._callback_errors = 0
            self._callback_error = ''
            self._set('asking' if self.source == 'portal' else 'idle', '', '')
            self._thread = threading.Thread(target=self._run, args=(stopping,),
                                            name='lumen-capture', daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Idempotent. Takes the pipeline to NULL (releasing PipeWire), closes the portal session,
        and leaves state 'idle'. Safe to call from on_frame itself."""
        with self._lock:
            thread = self._thread
            self._stopping.set()
            ctx = self._ctx
        if ctx is not None:
            ctx.wakeup()
        if thread is None:
            return
        if thread is threading.current_thread():
            return                                 # the thread finishes its own teardown
        thread.join(timeout=5.0)
        if not thread.is_alive():
            self._set('idle', '', '')

    def stats(self) -> dict:
        now = time.monotonic()
        window = min(FPS_WINDOW_S, now - self._since) if self.state == 'running' else 0.0
        try:
            times = tuple(self._times)
        except RuntimeError:                       # appended to while being copied
            times = ()
        recent = sum(1 for t in times if t > now - window) if window > 0 else 0
        out = {
            'fps': round(recent / window, 1) if window > 0.2 else 0.0,
            'frames': self._frames,
            'source': self.source,
            'state': self.state,
            'error': self.error,
            'reason': self.reason,
            'scaler': f'cpu: nearest {self.width * SCALE_STEP}x{self.height * SCALE_STEP}, '
                      f'bilinear2 {self.width}x{self.height}',
            'callback_errors': self._callback_errors,
        }
        if self._callback_error:
            out['callback_error'] = self._callback_error
        if self._token_error:
            out['token_error'] = self._token_error
        return out

    # ── pipeline description (tests and measurements replace the source) ──
    def _source_description(self, fd: int, target: int) -> str:
        return (f'pipewiresrc fd={fd} path={target} do-timestamp=true '
                f'keepalive-time={KEEPALIVE_MS} on-disconnect=error client-name=mira-lumen')

    def _test_description(self) -> str:
        # moving colour bars, at twice the requested rate so the rate cap is exercised
        return ('videotestsrc is-live=true pattern=smpte horizontal-speed=8 '
                f'! video/x-raw,format=BGRx,width=1280,height=720,framerate={min(120, 2 * self.fps)}/1')

    def _scale_description(self) -> str:
        w, h = self.width, self.height
        return (f'videoscale method=nearest-neighbour '
                f'! video/x-raw,width={w * SCALE_STEP},height={h * SCALE_STEP} '
                f'! videoscale method=bilinear2 ! video/x-raw,width={w},height={h} ')

    def _description(self, head: str) -> str:
        w, h = self.width, self.height
        return (f'{head} ! capsfilter name=lumen_srccaps '
                f'! videorate drop-only=true max-rate={self.fps} '
                f'! {self._scale_description()}'
                f'! videoconvert ! video/x-raw,format=RGB,width={w},height={h} '
                '! appsink name=lumen_sink max-buffers=1 drop=true sync=false emit-signals=false '
                'enable-last-sample=false')

    # ── the capture thread ───────────────────────────────────────────
    def _run(self, stopping: threading.Event) -> None:
        ctx = GLib.MainContext.new()
        ctx.push_thread_default()
        with self._lock:
            self._ctx = ctx
        portal = pipeline = None
        fd = -1
        outcome = ('idle', '', '')
        try:
            if self.source == 'portal':
                bus = self._bus if self._bus is not None else Gio.bus_get_sync(Gio.BusType.SESSION, None)
                portal = _Portal(bus, ctx, stopping, self._load_token())
                fd, target = portal.open(self._store_token)
                head = self._source_description(fd, target)
            else:
                head = self._test_description()
            if stopping.is_set():
                raise _Stopped()
            pipeline = Gst.parse_launch(self._description(head))
            pipeline.get_by_name('lumen_srccaps').set_property('caps', Gst.Caps.from_string(
                f'video/x-raw,max-framerate={self.fps}/1; video/x-raw'))
            self._pipeline = pipeline
            self._stream(pipeline, ctx, portal, stopping)
        except _Stopped:
            pass
        except PortalDenied as e:
            outcome = ('denied', str(e), 'denied')
        except CaptureError as e:
            outcome = ('error', str(e), e.reason)
        except Exception as e:                      # GLib.Error from D-Bus, a broken pipeline …
            message = getattr(e, 'message', None) or str(e)
            reason = 'portal' if isinstance(e, GLib.Error) else 'internal'
            outcome = ('error', f'screen capture failed: {message}', reason)
        finally:
            if pipeline is not None:
                pipeline.set_state(Gst.State.NULL)  # pipewiresrc drops its PipeWire connection
                pipeline.get_state(2 * Gst.SECOND)
            self._pipeline = None
            if fd >= 0:
                try:
                    os.close(fd)                    # our copy; only after NULL (see docstring)
                except OSError:
                    pass
            if portal is not None:
                portal.close()
            ctx.pop_thread_default()
            with self._lock:
                if self._ctx is ctx:
                    self._ctx = None
                if stopping is self._stopping:      # a newer start() owns the state otherwise
                    if stopping.is_set():
                        self._set('idle', '', '')
                    else:
                        self._set(*outcome)

    def _stream(self, pipeline, ctx, portal, stopping: threading.Event) -> None:
        bus = pipeline.get_bus()
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            self._check_bus(bus)
            raise CaptureError('the capture pipeline would not start', 'pipeline')
        sink = pipeline.get_by_name('lumen_sink')
        # No blocking wait for PLAYING: a source that never gets there is caught by the same
        # five-second watchdog as one that stops, and stop() stays responsive meanwhile.
        self._since = last = time.monotonic()
        running = False
        while not stopping.is_set():
            sample = sink.emit('try-pull-sample', PULL_MS * Gst.MSECOND)
            while ctx.iteration(False):             # D-Bus signals: the session may have closed
                pass
            if portal is not None and portal.closed:
                raise CaptureError('screen sharing was ended from the system (session closed)',
                                   'closed')
            self._check_bus(bus)
            now = time.monotonic()
            if not running and (sample is not None or pipeline.get_state(0)[1] == Gst.State.PLAYING):
                running = True
                self._since = now
                if stopping is self._stopping and not stopping.is_set():
                    self._set('running', '', '')
            if sample is None:
                if now - last > STALL_S:
                    raise CaptureError(f'no picture from the screen for {STALL_S:.0f} s', 'stalled')
                continue
            last = now
            self._deliver(sample, now)

    @staticmethod
    def _check_bus(bus) -> None:
        msg = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if msg is None:
            return
        if msg.type == Gst.MessageType.EOS:
            raise CaptureError('the screen stream ended', 'ended')
        err, _debug = msg.parse_error()
        where = msg.src.get_name() if msg.src is not None else 'pipeline'
        raise CaptureError(f'capture failed in {where}: {err.message}', 'pipeline')

    def _deliver(self, sample, now: float) -> None:
        buf = sample.get_buffer()
        data = buf.extract_dup(0, buf.get_size())
        w, h = self.width, self.height
        row = w * 3
        if len(data) != row * h:                   # GStreamer pads RGB rows to 4 bytes
            stride = (row + 3) & ~3
            if len(data) < stride * (h - 1) + row:
                return
            data = b''.join(data[y * stride:y * stride + row] for y in range(h))
        self._frames += 1
        self._times.append(now)
        try:
            self._on_frame(data, w, h)
        except Exception as e:                      # the consumer's bug must not end the capture
            self._callback_errors += 1
            self._callback_error = f'{type(e).__name__}: {e}'

    # ── state and the restore token ─────────────────────────────────
    def _set(self, state: str, error: str, reason: str) -> None:
        self.state, self.error, self.reason = state, error, reason

    def _load_token(self) -> str | None:
        if self._token:
            return self._token
        if self.token_path is None:
            return None
        try:
            return self.token_path.read_text(encoding='utf-8').strip() or None
        except OSError:
            return None

    def _store_token(self, token: str | None) -> None:
        """Keep the portal's replacement token. Without one (the owner did not let the grant be
        remembered) the consumed old token is removed rather than offered again."""
        self._token = token or None
        if self.token_path is None:
            return
        path = self.token_path
        try:
            if not token:
                path.unlink(missing_ok=True)
                return
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            staging = path.with_name(path.name + '.new')
            fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                os.fchmod(fh.fileno(), 0o600)       # O_CREAT keeps an existing file's mode
                fh.write(token)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(staging, path)
            self._token_error = ''
        except OSError as e:
            self._token_error = f'could not keep the screen-sharing approval: {e}'

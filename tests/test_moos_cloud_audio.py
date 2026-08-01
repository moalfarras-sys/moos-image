#!/usr/bin/python3
"""moos-cloud-audio — the cloud edition's browser sound, exercised for real.

This file exists because the previous version of this feature was verified in a
shell that had an encoder the image does not contain, shipped broken, and then
took the whole cloud edition offline for four commits. So the gates here are of
two kinds and both matter:

  * STATIC — the pipeline still names the elements build.sh asserts are present,
    still forces stereo, and still writes to a private fd instead of stdout.
  * LIVE   — the server is actually started, with a stand-in `gst-launch-1.0` on
    PATH, and driven over HTTP: a listener gets bytes, the encoder is spawned on
    demand and reaped on disconnect, and the listener cap answers 503 instead of
    piling encoders onto a two-core VPS.

GStreamer itself is not required here on purpose. Whether `opusenc` exists is a
question about the IMAGE, and the image is where it is asked (build.sh). What is
asked here is whether the server around it is correct, which is a question this
repo can answer in a second without a container.
"""
import http.client
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIO = ROOT / "system_files/usr/bin/moos-cloud-audio"
UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-cloud-audio.service"
BUILD = ROOT / "build_files/build.sh"

# A stand-in for gst-launch that honours `fdsink fd=N`, and deliberately prints
# on stdout the way the real one does when it is not quiet. If the server ever
# goes back to reading the encoder's stdout, that noise lands inside the WebM
# header and this stub reproduces the failure exactly.
STUB = textwrap.dedent("""\
    #!/usr/bin/python3
    import os, sys, time
    fd = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("fd=")), None)
    print("Setting pipeline to PAUSED ...", flush=True)
    if fd is None:
        sys.exit("no fdsink fd= in argv")
    open(os.environ["STUB_PIDFILE"], "w").write(str(os.getpid()))
    n = 0
    try:
        while True:
            os.write(fd, b"OPUSWEBM%04d;" % n)
            n += 1
            time.sleep(0.02)
    except (BrokenPipeError, OSError):
        pass
""")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestPipelineShape(unittest.TestCase):
    """The parts of the pipeline that fail silently when they regress."""

    @classmethod
    def setUpClass(cls):
        cls.src = AUDIO.read_text(encoding="utf-8")

    def test_encoder_is_gstreamer_and_not_ffmpeg(self):
        """ffmpeg-free has no libopus. Reaching for ffmpeg here ships silence."""
        self.assertIn("gst-launch-1.0", self.src)
        self.assertNotIn("ffmpeg", self.src.split('"""', 2)[-1],
                         "moos-cloud-audio is back on ffmpeg — the image's ffmpeg-free "
                         "has no libopus, so the stream would never start")

    def test_pipeline_elements_match_the_build_gate(self):
        """build.sh asserts a list of elements against the image. Drift breaks both."""
        gated = re.search(r'need = \(([^)]*)\)', BUILD.read_text(encoding="utf-8"))
        self.assertIsNotNone(gated, "build.sh no longer asserts the audio elements")
        for element in re.findall(r'"([a-z0-9]+)"', gated.group(1)):
            self.assertIn(element, self.src,
                          f"build.sh gates on {element!r} but the pipeline no longer uses it")

    def test_stereo_is_forced_after_conversion(self):
        """A null sink's monitor is MONO. Without this, stereo audio is folded flat."""
        self.assertRegex(self.src, r'audio/x-raw,rate=48000,channels=2')
        # The caps must come after audioconvert, or they constrain the source
        # instead of asking audioconvert to upmix — and pulsesrc simply fails to
        # negotiate rather than converting anything.
        self.assertLess(self.src.index("audioconvert"),
                        self.src.index("audio/x-raw,rate=48000,channels=2"))

    def test_media_never_travels_on_stdout(self):
        """gst-launch prints progress on stdout; those bytes corrupt the WebM header."""
        self.assertRegex(self.src, r'"fdsink", f"fd=\{out_fd\}"')
        self.assertNotIn('fd=1', self.src)
        self.assertIn("stdout=subprocess.DEVNULL", self.src)

    def test_a_dead_peer_is_detected_while_the_stream_is_writing(self):
        """Keepalive alone cannot see this: a writing socket is never idle."""
        self.assertIn("TCP_USER_TIMEOUT", self.src)

    def test_unit_is_a_server_not_a_one_shot(self):
        directives = [ln for ln in UNIT.read_text(encoding="utf-8").splitlines()
                      if ln and not ln.startswith("#")]
        self.assertIn("Restart=always", directives)
        self.assertIn("ExecStart=/usr/bin/moos-cloud-audio", directives)
        self.assertIn("WantedBy=default.target", directives)
        for line in directives:
            self.assertNotIn("ffmpeg", line)

    def test_encoder_reaping_is_bounded_even_after_sigkill(self):
        """A wedged encoder must never pin an HTTP worker indefinitely."""
        reap = re.search(r"def _reap\(.*?(?=\n\nclass Server)", self.src, re.S)
        self.assertIsNotNone(reap, "could not locate the encoder reaper")
        body = reap.group(0)
        waits = re.findall(r"proc\.wait\(([^)]*)\)", body)
        self.assertEqual(
            waits, ["timeout=3", "timeout=3"],
            "both TERM and KILL waits must be bounded",
        )
        self.assertNotIn("except Exception", body)


@unittest.skipIf(shutil.which("python3") is None, "no python3")
class TestServerBehaviour(unittest.TestCase):
    """Start it and talk to it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="moos-audio-")
        binroot = pathlib.Path(cls.tmp, "bin")
        binroot.mkdir()
        stub = binroot / "gst-launch-1.0"
        stub.write_text(STUB, encoding="utf-8")
        stub.chmod(0o755)

        cls.pidfile = str(pathlib.Path(cls.tmp, "stub.pid"))
        cls.port = free_port()
        env = dict(os.environ,
                   PATH=f"{binroot}:{os.environ.get('PATH', '')}",
                   STUB_PIDFILE=cls.pidfile,
                   MOOS_AUDIO_PORT=str(cls.port),
                   MOOS_AUDIO_HOST="127.0.0.1")
        cls.proc = subprocess.Popen([sys.executable, str(AUDIO)], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                socket.create_connection(("127.0.0.1", cls.port), 0.2).close()
                break
            except OSError:
                if cls.proc.poll() is not None:
                    raise AssertionError("moos-cloud-audio exited on startup")
                time.sleep(0.05)
        else:
            raise AssertionError("moos-cloud-audio never opened its port")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def conn(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

    def open_stream(self, wait=6.0):
        """A stream slot, waiting for one if the previous test just gave it back.

        Releasing a slot is not instant: the server thread is blocked in a write
        and only lets go once the closed socket errors, so a test that opens a
        stream immediately after another test closed four of them can legitimately
        meet a 503. Retrying is the honest fix — the cap itself is asserted
        deliberately in its own test, with open_stream_now().
        """
        deadline = time.monotonic() + wait
        while True:
            r = self.open_stream_now()
            if r.status != 503 or time.monotonic() > deadline:
                return r
            r.close()
            time.sleep(0.1)

    def open_stream_now(self):
        """Returns the RESPONSE, and that distinction is the whole point.

        The stream answers `Connection: close`, so http.client hands the socket
        over to the response object and closes the HTTPConnection immediately —
        `conn.close()` afterwards is a no-op on an already-closed handle. Holding
        the connection therefore keeps nothing open, and dropping the response is
        what actually hangs up. Getting this backwards made an earlier version of
        these tests report a listener cap that did not work and an encoder that
        was never reaped, when both were fine.
        """
        c = self.conn()
        c.request("GET", "/stream.webm")
        return c.getresponse()

    def test_landing_page_is_arabic_rtl_and_self_contained(self):
        c = self.conn()
        c.request("GET", "/")
        r = c.getresponse()
        body = r.read().decode("utf-8")
        c.close()
        self.assertEqual(r.status, 200)
        self.assertTrue(r.getheader("Content-Type", "").startswith("text/html"))
        self.assertIn('dir="rtl"', body)
        self.assertIn('lang="ar"', body)
        # A remote desktop is reached over a tailnet with no route to a CDN, and
        # the browser is the only client. Every asset has to be in this response.
        self.assertNotRegex(body, r'src="https?://')
        self.assertNotRegex(body, r'href="https?://')
        # Autoplay with sound is blocked by every browser, so the button is not
        # decoration — without it the page is silent and looks broken.
        self.assertIn("<button", body)
        self.assertIn("/stream.webm", body)

    def test_stream_carries_media_and_no_encoder_chatter(self):
        r = self.open_stream()
        try:
            self.assertEqual(r.status, 200)
            self.assertEqual(r.getheader("Content-Type"), "audio/webm")
            self.assertEqual(r.getheader("Connection"), "close")
            # A live stream has no length and must not be range-probed.
            self.assertIsNone(r.getheader("Content-Length"))
            self.assertEqual(r.getheader("Accept-Ranges"), "none")
            data = r.read(96)
            self.assertTrue(data.startswith(b"OPUSWEBM"), data[:40])
            self.assertNotIn(b"Setting pipeline", data)
        finally:
            r.close()

    def test_encoder_starts_on_demand_and_is_reaped_on_disconnect(self):
        """Idle cost has to be zero, and a listener leaving must not orphan a process."""
        if os.path.exists(self.pidfile):
            os.unlink(self.pidfile)
        r = self.open_stream()
        r.read(32)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not os.path.exists(self.pidfile):
            time.sleep(0.05)
        self.assertTrue(os.path.exists(self.pidfile), "no encoder was spawned for a listener")
        with open(self.pidfile) as fh:
            pid = int(fh.read())
        os.kill(pid, 0)          # raises if it is not running

        r.close()                # the listener leaves
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            self.fail(f"encoder {pid} survived the listener leaving — a VPS would "
                      f"accumulate one per closed tab")

    def test_listener_cap_answers_503_instead_of_piling_up_encoders(self):
        held = []
        try:
            for n in range(4):                 # MAX_LISTENERS
                r = self.open_stream()
                held.append(r)
                self.assertEqual(r.status, 200, f"listener {n + 1} was refused")
                r.read(16)                     # prove the encoder really started
            r = self.open_stream_now()         # no retry: the refusal IS the assertion
            held.append(r)
            self.assertEqual(r.status, 503,
                             "the fifth listener was accepted — four Opus encoders is "
                             "already the budget on a two-core VPS")
        finally:
            for r in held:
                r.close()

    def test_unknown_routes_do_not_start_an_encoder(self):
        c = self.conn()
        c.request("GET", "/../etc/passwd")
        r = c.getresponse()
        r.read()
        c.close()
        self.assertEqual(r.status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)

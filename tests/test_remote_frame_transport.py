#!/usr/bin/env python3
"""Execute the helper's real frame writer on private sockets, never the portal."""
import ast
import os
from pathlib import Path
import socket
import struct
import threading
import types
import unittest

HELPER = Path(__file__).resolve().parents[1] / "moremote/agent-linux/mo-remote-portal.py"


def functions():
    tree = ast.parse(HELPER.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in {"send_frame", "source_size", "on_sample"}]
    ns = {"struct": struct}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(HELPER), "exec"), ns)
    return ns


def receive(sock, count):
    data = bytearray()
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise AssertionError("frame ended before its declared length")
        data.extend(part)
    return bytes(data)


class FrameTransport(unittest.TestCase):
    def setUp(self):
        self.writer, self.reader = socket.socketpair()
        self.reader.settimeout(2)
        self.addCleanup(self.writer.close)
        self.addCleanup(self.reader.close)
        self.ns = functions()
        self.ns.update(frames=self.writer, frames_alive=True, frames_lock=threading.Lock())

    def test_same_payload_is_routed_by_its_pipeline_codec_not_stdout_or_magic(self):
        payload = b"\0\0\0\1\x65\xff\xd8"
        for codec, flag in [("h264", 0x80000000), ("jpeg", 0), ("h264", 0x80000000)]:
            self.assertTrue(self.ns["send_frame"](payload, codec))
            header, = struct.unpack("<I", receive(self.reader, 4))
            self.assertEqual(header, len(payload) | flag)
            self.assertEqual(receive(self.reader, header & 0x7fffffff), payload)

    def test_invalid_codec_empty_and_oversized_frame_never_enter_the_socket(self):
        for payload, codec in [(b"data", "unknown"), (b"", "jpeg"), (bytes(32 * 1024 * 1024 + 1), "h264")]:
            with self.assertRaises(ValueError):
                self.ns["send_frame"](payload, codec)
        self.reader.setblocking(False)
        with self.assertRaises(BlockingIOError):
            self.reader.recv(1)
        self.assertTrue(self.ns["frames_alive"])

    def test_departing_agent_refuses_this_and_later_frames(self):
        self.reader.close()
        self.assertFalse(self.ns["send_frame"](b"data", "h264"))
        self.assertFalse(self.ns["frames_alive"])
        self.assertFalse(self.ns["send_frame"](b"data", "jpeg"))

    @unittest.skipUnless(os.environ.get("MOOS_GST_SOURCE_PROOF") == "1", "Opt-in native GStreamer, no desktop/portal")
    def test_native_jpeg_and_h264_callbacks_keep_their_own_pipeline_codec(self):
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)
        for codec, encoder in [("jpeg", "jpegenc"), ("h264", "video/x-raw,format=I420 ! openh264enc bitrate=256000 gop-size=30 ! h264parse ! video/x-h264,stream-format=byte-stream,alignment=au")]:
            with self.subTest(codec=codec):
                ns = functions()
                packets = []
                # Use the actual socket writer and callback, with deliberately contrary global
                # codec state. Only the immutable argument belonging to this pipeline is valid.
                ns.update({k: self.ns[k] for k in ("frames", "frames_alive", "frames_lock")})
                ns.update(state={"sw": 320, "sh": 180, "codec": "jpeg" if codec == "h264" else "h264"},
                          Gst=Gst, video_health=types.SimpleNamespace(note_frame=lambda _: None), monotonic_ms=lambda: 1)
                pipeline = Gst.parse_launch(f"videotestsrc num-buffers=3 ! video/x-raw,width=320,height=180 ! videoconvert ! {encoder} ! appsink name=sink emit-signals=true sync=false")
                pipeline.get_by_name("sink").connect("new-sample", ns["on_sample"], None, codec)
                try:
                    pipeline.set_state(Gst.State.PLAYING)
                    for _ in range(3):
                        header, = struct.unpack("<I", receive(self.reader, 4))
                        self.assertEqual(bool(header & 0x80000000), codec == "h264")
                        packets.append(receive(self.reader, header & 0x7fffffff))
                    result = pipeline.get_bus().timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
                    self.assertIsNotNone(result)
                    self.assertEqual(result.type, Gst.MessageType.EOS)
                finally:
                    pipeline.set_state(Gst.State.NULL)
                if codec == "jpeg":
                    import io
                    from PIL import Image
                    self.assertTrue(all(Image.open(io.BytesIO(p)).size == (320, 180) for p in packets))
                else:
                    self.assertTrue(all(p.startswith((b"\0\0\0\1", b"\0\0\1")) for p in packets))
                    decoder = Gst.parse_launch("appsrc name=input ! h264parse ! openh264dec ! videoconvert ! appsink name=output sync=false")
                    source = decoder.get_by_name("input")
                    source.set_property("caps", Gst.Caps.from_string("video/x-h264,stream-format=byte-stream,alignment=au"))
                    try:
                        decoder.set_state(Gst.State.PLAYING)
                        for payload in packets:
                            buffer = Gst.Buffer.new_allocate(None, len(payload), None)
                            buffer.fill(0, payload)
                            self.assertEqual(source.emit("push-buffer", buffer), Gst.FlowReturn.OK)
                        source.emit("end-of-stream")
                        for _ in packets:
                            sample = decoder.get_by_name("output").emit("try-pull-sample", 5 * Gst.SECOND)
                            self.assertIsNotNone(sample, "transported H264 did not decode")
                            caps = sample.get_caps().get_structure(0)
                            self.assertEqual((caps.get_value("width"), caps.get_value("height")), (320, 180))
                        result = decoder.get_bus().timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
                        self.assertIsNotNone(result)
                        self.assertEqual(result.type, Gst.MessageType.EOS)
                    finally:
                        decoder.set_state(Gst.State.NULL)


if __name__ == "__main__":
    unittest.main()

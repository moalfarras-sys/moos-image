#!/usr/bin/env python3
"""Gate: Mo PC Remote scales on the GPU only where it is safe, and never loses a session to it.

The capture chain scaled and converted every 4K frame on the CPU before NVENC. Measured on the
daily driver, moving that into CUDA memory cut it from ~6.1 to ~2.9 ms per frame. This gate
keeps the three promises that made the change safe:

* the GPU path is used only with the NVENC encoders and only when both CUDA elements exist;
* a GPU scaler that fails at startup rebuilds the SAME encoder on the CPU path first;
* a GPU scaler that fails mid-stream rebuilds on the CPU path instead of ending the session;

and, where GStreamer and an NVIDIA GPU are present, it runs the exact GPU caps into nvh264enc.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTAL = (ROOT / "moremote/agent-linux/mo-remote-portal.py").read_text(encoding="utf-8")
GPU_CAPS = "video/x-raw(memory:CUDAMemory),format=NV12,width={w},height={h}"


def function(name):
    match = re.search(rf"^def {name}\(.*?(?=^def |\Z)", PORTAL, re.S | re.M)
    assert match, f"{name}() not found"
    return match.group(0)


class CudaScalerSourceTests(unittest.TestCase):
    def test_gpu_path_is_limited_to_nvenc_and_both_elements(self):
        self.assertIn('CUDA_ENCODERS = frozenset({"nvh264enc", "nvautogpuh264enc"})', PORTAL)
        self.assertIn('CUDA_SCALERS = ("cudaupload", "cudaconvertscale")', PORTAL)
        body = function("cuda_path_available")
        self.assertIn("if elem not in CUDA_ENCODERS", body)
        self.assertIn("Gst.ElementFactory.find(name) is not None for name in CUDA_SCALERS", body)

    def test_build_chooses_one_scaler_and_keeps_the_cpu_path(self):
        body = function("build")
        self.assertIn('gpu = codec == "h264" and cuda_path_available(elem)', body)
        self.assertIn("! cudaupload ! cudaconvertscale ", body)
        self.assertIn(GPU_CAPS, body)
        self.assertIn("! videoscale method=bilinear {caps}", body)
        self.assertIn('("" if gpu else "! video/x-raw,format=(string){ I420, NV12 } ")', body)
        # The encoder is chosen before the scaler, so the scaler can depend on it.
        self.assertLess(body.index("elem, props = pick_h264()"), body.index("gpu = codec ==") )

    def test_startup_failure_retries_on_the_cpu_before_blaming_the_encoder(self):
        body = function("build")
        retry = body.index("        if gpu:\n")
        blame = body.index('if codec == "h264" and is_h264_encoder_factory(startup_factory):')
        self.assertLess(retry, blame)
        segment = body[retry:blame]
        self.assertIn('_cuda_failed_at["ms"] = monotonic_ms()', segment)
        self.assertIn("return build(w, h)", segment)

    def test_mid_stream_gpu_failure_rebuilds_instead_of_dying(self):
        body = function("on_bus")
        branch = body.index('if state.get("gpu") and is_cuda_scaler_factory(factory):')
        self.assertLess(branch, body.index('die(EXIT_LOST, f"gstreamer {factory'))
        segment = body[branch:body.index('if state["codec"] == "h264" and is_h264_encoder_factory(factory):')]
        self.assertIn("GLib.idle_add(rebuild)", segment)
        self.assertIn("return True", segment)


@unittest.skipUnless(shutil.which("gst-inspect-1.0") and shutil.which("nvidia-smi"),
                     "needs GStreamer and an NVIDIA GPU")
class CudaScalerRuntimeTests(unittest.TestCase):
    def test_the_gpu_caps_negotiate_into_nvenc(self):
        for element in ("cudaupload", "cudaconvertscale", "nvh264enc"):
            if subprocess.run(["gst-inspect-1.0", element], capture_output=True).returncode != 0:
                self.skipTest(f"{element} is not installed")
        pipeline = [
            "gst-launch-1.0", "-q", "videotestsrc", "num-buffers=30", "!",
            "video/x-raw,format=BGRx,width=1280,height=720,framerate=30/1", "!",
            "queue", "!", "cudaupload", "!", "cudaconvertscale", "!",
            GPU_CAPS.format(w=640, h=360), "!",
            "nvh264enc", "bitrate=2000", "gop-size=30", "bframes=0", "zerolatency=true", "rc-mode=cbr", "!",
            "h264parse", "config-interval=-1", "!", "fakesink", "sync=false",
        ]
        result = subprocess.run(pipeline, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-800:])


if __name__ == "__main__":
    unittest.main(verbosity=2)

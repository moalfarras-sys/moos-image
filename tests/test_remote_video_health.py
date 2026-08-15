#!/usr/bin/env python3
"""Gate the recovery contract for Mo PC Remote's PipeWire/GStreamer video path.

The failure this protects against is worse than a clean disconnect: the helper stays alive and
the agent keeps reporting it as ready, but the last frame is frozen or the client has only black.
There are two independent parts to the contract:

* only an error raised by the selected H.264 encoder may fall through to another encoder/JPEG;
  pipewiresrc, converters, sinks, bins and unknown sources require a new portal session;
* a PLAYING pipeline owes the agent a frame at least once per starvation window, both before its
  first frame and after it has previously worked.  pipewiresrc's one-second keepalive makes that
  safe even for a completely unchanged desktop.

The policy objects are executed below without importing the helper.  Importing it would contact
the desktop portal and require PyGObject, neither of which belongs in a repository gate.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"
BRIDGE = ROOT / "moremote/agent-linux/PortalBridge.cs"


def named_node(tree: ast.Module, kind: type[ast.AST], name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, kind) and getattr(node, "name", None) == name:
            return node
    raise AssertionError(f"could not find {kind.__name__} {name}")


def assigned_literal(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"could not find literal assignment {name}")


def execute_node(node: ast.AST, namespace: dict[str, object]) -> None:
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(HELPER), "exec"), namespace)


def function_code(tree: ast.Module, name: str) -> str:
    return ast.unparse(named_node(tree, (ast.FunctionDef, ast.AsyncFunctionDef), name))


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    if not HELPER.is_file() or not BRIDGE.is_file():
        print("GATE FAIL: remote video implementation files are missing.")
        return 1

    helper = HELPER.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(helper, filename=str(HELPER))

    try:
        keepalive_ms = assigned_literal(tree, "FRAME_KEEPALIVE_MS")
        starvation_ms = assigned_literal(tree, "FRAME_STARVATION_MS")
        check_ms = assigned_literal(tree, "FRAME_HEALTH_CHECK_MS")
        encoders = assigned_literal(tree, "H264_ENCODERS")

        policy_ns: dict[str, object] = {}
        execute_node(named_node(tree, ast.ClassDef, "PipelineHealth"), policy_ns)
        policy_ns["H264_ENCODER_FACTORIES"] = frozenset(name for name, _props in encoders)
        execute_node(named_node(tree, ast.FunctionDef, "is_h264_encoder_factory"), policy_ns)
    except (AssertionError, ValueError, TypeError, SyntaxError) as exc:
        print(f"GATE FAIL: could not load the dependency-free video health policy: {exc}")
        return 1

    PipelineHealth = policy_ns["PipelineHealth"]
    is_encoder = policy_ns["is_h264_encoder_factory"]

    # Behaviour, not spelling: startup and post-first-frame starvation share one moving deadline.
    health = PipelineHealth(starvation_ms)
    require(not health.stalled(100_000),
            "an inactive pipeline must not be declared starved", errors)
    health.start(1_000)
    require(not health.stalled(1_000 + starvation_ms - 1),
            "the pipeline starved before its full first-frame budget elapsed", errors)
    require(health.stalled(1_000 + starvation_ms),
            "a pipeline which never delivered its first frame was not declared starved", errors)
    health.start(1_000)
    health.note_frame(4_000)
    require(health.seen_frame, "note_frame did not record that delivery had started", errors)
    require(not health.stalled(4_000 + starvation_ms - 1),
            "a delivered frame did not reset the starvation deadline", errors)
    require(health.stalled(4_000 + starvation_ms),
            "post-first-frame starvation was not detected", errors)
    health.stop()
    require(not health.stalled(1_000_000),
            "a stopped/idle pipeline must not be declared starved", errors)
    health.start(10_000)
    require(not health.seen_frame,
            "restarting the pipeline retained seen-frame state from the previous generation", errors)

    known_encoders = {name for name, _props in encoders}
    require(known_encoders and all(is_encoder(name) for name in known_encoders),
            "one or more configured H.264 encoder factories are not classified as encoders", errors)
    for non_encoder in ("pipewiresrc", "videoscale", "videoconvert", "videorate",
                        "queue", "h264parse", "appsink", "jpegenc", "pipeline0", ""):
        require(not is_encoder(non_encoder),
                f"non-encoder factory {non_encoder!r} was allowed to trigger codec fallback", errors)

    # Five missed one-second repeats is deliberate: long enough for scheduling jitter, finite enough
    # that neither helper nor agent can advertise a frozen/black pipeline as healthy indefinitely.
    require(isinstance(keepalive_ms, int) and keepalive_ms > 0,
            "pipewiresrc keepalive must be enabled", errors)
    require(starvation_ms >= keepalive_ms * 4 and starvation_ms <= keepalive_ms * 10,
            "starvation window must cover 4-10 keepalives", errors)
    require(0 < check_ms <= keepalive_ms,
            "health polling must run at least once per keepalive interval", errors)

    try:
        on_bus = function_code(tree, "on_bus")
        on_sample = function_code(tree, "on_sample")
        build = function_code(tree, "build")
        teardown = function_code(tree, "teardown")
        rebuild_now = function_code(tree, "_rebuild_now")
        watchdog = function_code(tree, "check_video_health")
    except AssertionError as exc:
        errors.append(str(exc))
    else:
        require("is_h264_encoder_factory(factory)" in on_bus,
                "GStreamer ERROR handling does not gate fallback by encoder factory", errors)
        require("die(EXIT_LOST" in on_bus,
                "non-encoder GStreamer ERRORs do not terminate the helper for portal recovery", errors)
        require("send_frame" in on_sample and "video_health.note_frame" in on_sample,
                "frame health is not advanced at the final helper-to-agent delivery boundary", errors)
        require("video_health.start" in build,
                "a successfully PLAYING pipeline does not start its first-frame deadline", errors)
        require("timed_pop_filtered" in build
                and "is_h264_encoder_factory(startup_factory)" in build,
                "startup failure still falls through by requested codec instead of ERROR factory", errors)
        require("startup_factory or 'pipeline'" in build and "die(EXIT_LOST" in build,
                "a startup error from pipewiresrc/unknown source does not recreate the portal", errors)
        require("video_health.stop" in teardown and "video_health.stop" in rebuild_now,
                "pipeline teardown/rebuild does not retire the old health generation", errors)
        require("video_health.stalled" in watchdog and "die(EXIT_LOST" in watchdog,
                "starvation does not terminate the helper to recreate the portal session", errors)

    require("keepalive-time={FRAME_KEEPALIVE_MS}" in helper,
            "the pipeline does not use the tested keepalive interval", errors)
    require(re.search(r"GLib\.timeout_add\(\s*FRAME_HEALTH_CHECK_MS\s*,\s*check_video_health\s*\)",
                      helper) is not None,
            "the video health watchdog is defined but not registered with the main loop", errors)

    # The C# side independently stops describing a known-frozen helper as usable while the helper's
    # fatal exit and supervisor restart propagate through the process/socket boundary.
    stalled = re.search(r"public bool Stalled\s*=>\s*(.*?);", bridge, re.S)
    read_frames = re.search(r"private void ReadFrames\(.*?\n    }\n\n    private static bool ReadExact", bridge, re.S)
    error_case = re.search(r'case "error":(.*?)break;', bridge, re.S)
    require("_lastFrameTicks" in bridge and "FrameStarvationMs" in bridge,
            "PortalBridge has no moving last-frame starvation clock", errors)
    require(stalled is not None and "_lastFrameTicks" in stalled.group(1)
            and "_framesReceived" not in stalled.group(1),
            "PortalBridge.Stalled still only covers the never-received-a-frame case", errors)
    require(read_frames is not None and "Interlocked.Exchange(ref _lastFrameTicks" in read_frames.group(0),
            "PortalBridge does not advance health after every delivered frame", errors)
    require(error_case is not None and "fatal" in error_case.group(1) and "_ready = false" in error_case.group(1),
            "a fatal helper event can leave PortalBridge reporting IsReady=true", errors)

    if errors:
        print("GATE FAIL: remote video may remain black/frozen while reported healthy.\n")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OK: encoder-only fallback and first/post-frame starvation recovery are behaviour-tested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

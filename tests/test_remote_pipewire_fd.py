#!/usr/bin/env python3
"""Gate: a rebuilt Mo PC Remote pipeline must give its PipeWire remote back.

WHAT THIS PREVENTS, MEASURED ON A REAL MACHINE

The portal hands the helper one PipeWire remote (a socket) per pipeline, and the helper passes
its number to `pipewiresrc fd=`. The helper believed the element then owned it: "pipewiresrc
closes it on NULL". It does not. pipewiresrc connects through a DUPLICATE and closes only that,
so every build left one socket open for the life of the helper — and the helper rebuilds whenever
a viewer joins or the quality changes.

On the Oracle A1 on 2026-10-04, 61 hours after boot: 73 sockets in the helper, 67 orphaned
clients in `pw-dump`, and the session's pipewire at 464 MiB resident with another 104 MiB in
swap, on a machine whose whole desktop fits in a few hundred. A leaked socket is not a leaked
integer: the daemon keeps a client for it and keeps queueing events nobody will read.

No gate could see this. Every existing Remote gate reads the pipeline STRING or a policy object;
none runs a build and a teardown and then asks the kernel what is still open.

WHAT IS EXECUTED

build(), teardown() and close_pipewire_fd() are lifted out of the helper and run unmodified.
Only their surroundings are replaced: the portal call hands out a real socket, and the pipeline
is a stand-in that does the one thing that matters about pipewiresrc — it duplicates the fd on
the way up and closes its duplicate, and nothing else, on NULL. Importing the helper would
contact the desktop portal and need PyGObject; neither belongs in a repository gate.
"""

from __future__ import annotations

import ast
import os
import re
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"


def is_open(fd: int) -> bool:
    try:
        os.fstat(fd)
        return True
    except OSError:
        return False


def hung_up(far_end: socket.socket) -> bool:
    """The daemon's view of a remote: has EVERY descriptor on the helper's side been closed?

    This, not the number, is the question. A closed number is reused by the very next socket, so
    "is fd 14 still open" answers for whichever remote holds 14 now."""
    try:
        return far_end.recv(1, socket.MSG_DONTWAIT | socket.MSG_PEEK) == b""
    except BlockingIOError:
        return False


def open_count() -> int:
    return len(os.listdir("/proc/self/fd"))


class Died(Exception):
    """die() ends the real helper; here it only has to stop the function under test."""


class FakeBus:
    def add_signal_watch(self): pass
    def remove_signal_watch(self): pass
    def connect(self, *_a): return 1
    def disconnect(self, *_a): pass
    def timed_pop_filtered(self, *_a): return None


class FakeElement:
    def connect(self, *_a): return 1


class FakePipeline:
    """pipewiresrc's contract with the fd it is given, and nothing more."""

    def __init__(self, world, launch):
        self.world = world
        self.given = int(re.search(r"pipewiresrc fd=(-?\d+)", launch).group(1))
        self.duplicate = -1

    def get_by_name(self, _name): return FakeElement()
    def get_bus(self): return FakeBus()

    def set_state(self, state):
        if state == "PLAYING":
            self.duplicate = os.dup(self.given)       # raises if it was handed a closed fd
        elif state == "NULL":
            # The element may read through its duplicate until NULL has returned.
            self.world.open_at_null.append(is_open(self.given))
            if self.duplicate >= 0:
                os.close(self.duplicate)
                self.duplicate = -1

    def get_state(self, _timeout):
        return (self.world.start_result, None, None)


class World:
    """Everything build()/teardown() touch that is not theirs."""

    def __init__(self, tree: ast.Module):
        self.handed: list[int] = []
        self.keep: list[socket.socket] = []
        self.pipelines: list[FakePipeline] = []
        self.open_at_null: list[bool] = []
        self.start_result = "SUCCESS"
        self.parse_fails = False
        world = self

        class Gst:
            SECOND = 1
            class State: PLAYING, NULL = "PLAYING", "NULL"
            class StateChangeReturn: SUCCESS, NO_PREROLL, FAILURE = "SUCCESS", "NO_PREROLL", "FAILURE"
            class MessageType: ERROR = "ERROR"

            @staticmethod
            def parse_launch(launch):
                if world.parse_fails:
                    raise RuntimeError("no element \"nosuchenc\"")
                world.pipelines.append(FakePipeline(world, launch))
                return world.pipelines[-1]

        class Health:
            def start(self, _now): pass
            def stop(self): pass

        def open_pipewire_fd():
            ours, theirs = socket.socketpair()
            self.keep.append(theirs)                  # the daemon's end stays up, as it would
            self.handed.append(ours.detach())
            return self.handed[-1]

        def die(_code, why):
            raise Died(why)

        self.ns: dict[str, object] = {
            "os": os, "Gst": Gst, "open_pipewire_fd": open_pipewire_fd, "die": die,
            "video_health": Health(), "emit": lambda **_m: None, "monotonic_ms": lambda: 0,
            "on_sample": lambda *_a: None, "on_bus": lambda *_a: None,
            "element_factory_name": lambda _e: "", "is_h264_encoder_factory": lambda _f: False,
            "state": {"want": "jpeg", "fps": 30, "quality": 70, "sw": 1920, "sh": 1080,
                      "out": (0, 0), "codec": "jpeg"},
            "pipeline": None, "enc": None, "rate": None,
            "pipeline_bus": None, "pipeline_bus_handler": None,
            "pipewire_target": 58, "node_id": 58, "logical_w": 1920, "logical_h": 1080,
            "FRAME_KEEPALIVE_MS": 1000, "EXIT_LOST": 4,
        }
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "pipeline_fd" for t in node.targets):
                self.ns["pipeline_fd"] = ast.literal_eval(node.value)
        # close_pipewire_fd() is the fix, not the contract: a helper without it is still run, so
        # the gate reports the remotes it leaves rather than a missing name.
        for name in ("close_pipewire_fd", "teardown", "build"):
            node = next((n for n in tree.body
                         if isinstance(n, ast.FunctionDef) and n.name == name), None)
            if node is None:
                if name == "close_pipewire_fd":
                    continue
                raise AssertionError(f"the helper has no {name}()")
            module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
            exec(compile(module, str(HELPER), "exec"), self.ns)

    def build(self): return self.ns["build"](1280, 720)
    def teardown(self): return self.ns["teardown"]()

    def orphans(self) -> int:
        """Remotes the daemon would still be keeping a client for."""
        return sum(1 for far_end in self.keep if not hung_up(far_end))

    def close(self):
        """Give back whatever the helper under test did not, so one scenario cannot feed the next."""
        for pipeline in self.pipelines:
            pipeline.set_state("NULL")
        for far_end, fd in zip(self.keep, self.handed):
            if not hung_up(far_end) and is_open(fd):
                os.close(fd)
        for far_end in self.keep:
            far_end.close()


def main() -> int:
    if not HELPER.is_file():
        print(f"GATE FAIL: {HELPER.relative_to(ROOT)} is missing.")
        return 1
    if not os.path.isdir("/proc/self/fd"):
        print("GATE SKIP: no /proc/self/fd to count descriptors with.")
        return 0

    source = HELPER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(HELPER))
    errors: list[str] = []

    # 1. The ordinary life of a helper: a viewer joins, changes quality, leaves — many times.
    world = World(tree)
    try:
        before = open_count()
        for _ in range(40):
            world.build()
            world.teardown()
        # `keep` holds the far ends on purpose; they are the test's, not the helper's.
        grew = open_count() - before - len(world.keep)
        if world.orphans() or grew > 0:
            errors.append(f"40 builds and teardowns left {world.orphans()} PipeWire remote(s) "
                          f"open (descriptor count grew by {grew}): each one is a client the "
                          "daemon keeps, and keeps queueing events for")
        if not world.open_at_null or not all(world.open_at_null):
            errors.append("the remote was closed BEFORE the pipeline reached NULL; pipewiresrc "
                          "may still be reading through its duplicate until then")
        if world.ns.get("pipeline_fd", -1) != -1:
            errors.append("teardown() left pipeline_fd pointing at a closed descriptor")
    except Exception as e:                                    # noqa: BLE001 — report, do not crash
        errors.append(f"build()/teardown() could not run: {type(e).__name__}: {e}")
    finally:
        world.close()

    # 2. A caller that forgets to tear down must not turn back into the leak.
    world = World(tree)
    try:
        world.build()
        world.build()
        world.pipelines[0].set_state("NULL")      # the abandoned pipeline is collected
        if not hung_up(world.keep[0]):
            errors.append("a second build() without a teardown() abandoned the first remote")
        world.teardown()
        if world.orphans():
            errors.append("teardown() did not close the remote of the standing pipeline")
    except Exception as e:                                    # noqa: BLE001
        errors.append(f"back-to-back build() could not run: {type(e).__name__}: {e}")
    finally:
        world.close()

    # 3. A pipeline that will not start is dropped through teardown() before the helper exits or
    #    falls back; its remote goes with it.
    world = World(tree)
    world.start_result = "FAILURE"
    try:
        world.build()
        errors.append("a pipeline that failed to start did not end the build")
    except Died:
        if world.orphans():
            errors.append("a pipeline that failed to start kept its remote")
    except Exception as e:                                    # noqa: BLE001
        errors.append(f"failed-start build() could not run: {type(e).__name__}: {e}")
    finally:
        world.close()

    # 4. A launch line GStreamer cannot parse leaves a remote and no pipeline at all.
    world = World(tree)
    world.parse_fails = True
    try:
        try:
            world.build()
        except RuntimeError:
            pass
        world.teardown()
        if world.orphans():
            errors.append("a build that failed to parse left its remote open: teardown() returns "
                          "early when there is no pipeline and never reached the close")
    except Exception as e:                                    # noqa: BLE001
        errors.append(f"parse-failure build() could not run: {type(e).__name__}: {e}")
    finally:
        world.close()

    # 5. One way in. A second call site is a second remote that nothing tracks.
    code = re.sub(r'"""[\s\S]*?"""', '""', source)
    code = "\n".join(re.sub(r"#.*$", "", line) for line in code.splitlines())
    calls = len(re.findall(r"(?<!def )\bopen_pipewire_fd\(", code))
    if calls != 1:
        errors.append(f"open_pipewire_fd() is called from {calls} places; build() must be the only "
                      "one, and it must keep the result in pipeline_fd")
    if "fd={open_pipewire_fd()}" in code:
        errors.append("the launch line opens a remote inline, so nothing holds the number to close")

    if errors:
        print("GATE FAIL: Mo PC Remote leaks PipeWire remotes.")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("ok: every Mo PC Remote pipeline closes the PipeWire remote it was built on")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Observe the unmodified recovery bundle's menu, input and clean shutdown.

No credentials, guest agent, modified seed, install action or host block device
is introduced. QMP controls only this private QEMU. Guest writes use overlays.
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import socket
import stat
import struct
import subprocess
import tempfile
import time
import zipfile

PREFIX = "MoOS-UTM-Installer.utm/"
MEMBERS = {PREFIX + p for p in (
    "config.plist", "README-FIRST.txt", "Data/installer.qcow2",
    "Data/target.qcow2", "Data/seed.iso", "Data/moos-icon.png")}
FATAL = re.compile(r"Kernel panic|Entering emergency mode|You are in emergency mode|"
                   r"Reached target[^\n]*emergency|Dependency failed for[^\n]*/boot|"
                   r"Failed to start[^\n]*coldplug", re.I)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args):
    return subprocess.run(args, check=True, capture_output=True, timeout=60)


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        require(len(infos) == len(MEMBERS) and {i.filename for i in infos} == MEMBERS,
                "recovery archive has missing, duplicate or unexpected members")
        require(sum(i.file_size for i in infos) <= 16 * 1024**3,
                "recovery archive exceeds bounded extraction size")
        for info in infos:
            mode = info.external_attr >> 16
            require(not info.flag_bits & 1 and not info.is_dir() and
                    (not stat.S_IFMT(mode) or stat.S_ISREG(mode)),
                    "recovery archive contains an encrypted or nonregular member")
        for info in infos:
            target = destination / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(info) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
    bundle = destination / PREFIX.rstrip("/")
    config = plistlib.loads((bundle / "config.plist").read_bytes())
    require(config.get("Backend") == "QEMU" and config.get("ConfigurationVersion") == 4,
            "unsupported recovery bundle configuration")
    require(config.get("System", {}).get("Architecture") == "aarch64" and
            config["System"].get("CPUCount") == 2 and
            config["System"].get("MemorySize") == 3072 and
            config.get("QEMU", {}).get("Hypervisor") is False,
            "recovery bundle is not the declared iPhone TCG profile")
    drives = config.get("Drive", [])
    require([d.get("ImageName") for d in drives] ==
            ["installer.qcow2", "target.qcow2", "seed.iso"] and
            [d.get("ReadOnly") for d in drives] == [False, False, True],
            "recovery bundle drive order or write policy differs")
    data = bundle / "Data"
    readme = (bundle / "README-FIRST.txt").read_text()
    for name, field in (("installer.qcow2", "installer_sha256"),
                        ("target.qcow2", "target_sha256")):
        matches = re.findall(r"(?m)^" + field + r"=([0-9a-f]{64})$", readme)
        require(len(matches) == 1 and sha(data / name) == matches[0],
                "recovery disk does not match packaged digest: " + field)
    require((data / "seed.iso").stat().st_size > 0, "packaged seed is empty")
    return data


def ocr_word(text):
    word = re.sub(r"[^a-z0-9]+", "", text.lower())
    # Native newt's terminal cursor overlaps the final MoOS cell; retain these
    # measured OCR confusions, never fuzzy-match an arbitrary OS/status banner.
    return {"mo0os": "moos", "mooos": "moos", "0k": "ok"}.get(word, word)


def menu_text(text):
    words = " ".join(word for token in text.split() if (word := ocr_word(token)))
    return all(phrase in words for phrase in
               ("moos utm", "install latest signed moos", "shell serial debug", "cancel"))


def qcow_input(path, maximum):
    require(path.is_file() and not path.is_symlink() and stat.S_ISREG(path.stat().st_mode),
            "disk input is not a regular self-contained file")
    # Refuse dependency-bearing headers before qemu-img can open an external
    # backing/data file named by an otherwise regular ZIP member.
    with path.open("rb") as stream:
        header = stream.read(104)
    require(len(header) >= 72 and header[:4] == b"QFI\xfb", "invalid QCOW2 header")
    version, backing_offset, backing_size = struct.unpack_from(">IQI", header, 4)
    require(version in (2, 3) and backing_offset == 0 and backing_size == 0 and
            struct.unpack_from(">I", header, 32)[0] == 0,
            "backing or encrypted QCOW2 header refused")
    require(version == 2 or (len(header) == 104 and struct.unpack_from(">Q", header, 72)[0] == 0),
            "external, dirty or unsupported QCOW2 feature header refused")
    info = json.loads(run(["qemu-img", "info", "--output=json", "-f", "qcow2", str(path)]).stdout)
    require(info.get("format") == "qcow2" and type(info.get("virtual-size")) is int and
            0 < info["virtual-size"] <= maximum, "invalid recovery disk format or size")
    specific = info.get("format-specific", {}).get("data", {})
    require(not any(key in info for key in ("backing-filename", "full-backing-filename")) and
            not specific.get("data-file") and not specific.get("data-file-raw") and
            specific.get("encrypt") is None and not info.get("encrypted", False),
            "external, backing or encrypted QCOW2 inputs are refused")
    require(not info.get("snapshots"), "unexpected internal QCOW2 snapshot")
    return info


def read_ppm(data):
    match = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", data)
    require(match is not None, "unsupported native screen format")
    width, height = map(int, match.groups())
    pixels = data[match.end():]
    require(0 < width <= 4096 and 0 < height <= 4096 and len(pixels) == width * height * 3,
            "invalid native screen size")
    return width, height, pixels


def dominant(frame, box):
    width, height, pixels = frame
    left, top, right, bottom = box
    require(0 <= left < right <= width and 0 <= top < bottom <= height,
            "menu region outside native frame")
    colors = collections.Counter()
    for y in range(top, bottom):
        row = pixels[(y * width + left) * 3:(y * width + right) * 3]
        colors.update(row[x:x+3] for x in range(0, len(row), 3))
    color, count = colors.most_common(1)[0]
    require(count > (right-left)*(bottom-top)*.50, "menu region has no stable background")
    return color


def phrase_box(rows, phrase):
    words = phrase.split()
    lines = collections.defaultdict(list)
    for row in rows:
        text = ocr_word(row["text"])
        if text:
            lines[tuple(row[k] for k in ("block_num", "par_num", "line_num"))].append((text, row))
    found = []
    for line in lines.values():
        for i in range(len(line)-len(words)+1):
            segment = line[i:i+len(words)]
            if [word for word, _ in segment] == words:
                boxes = [(int(r["left"]), int(r["top"]), int(r["width"]), int(r["height"]))
                         for _, r in segment]
                found.append((min(x for x,y,w,h in boxes), min(y for x,y,w,h in boxes),
                              max(x+w for x,y,w,h in boxes), max(y+h for x,y,w,h in boxes)))
    require(len(found) == 1, "native menu label missing or ambiguous: " + phrase)
    return found[0]


def menu_regions(screen):
    rows = screen[2]
    first = phrase_box(rows, "install latest signed moos")
    second = phrase_box(rows, "shell serial debug")
    require(first[3] < second[1], "native menu item order differs")
    left, right = min(first[0], second[0])-4, max(first[2], second[2])+4
    # Row-wide color changes cannot be a blinking terminal cursor. Keep the
    # exact label coordinates and require background swaps at both owners.
    items = [(left, b[1], right, b[3]) for b in (first, second)]
    return {"items": items, "moos utm": phrase_box(rows, "moos utm"),
            "shell serial debug": second, "cancel": phrase_box(rows, "cancel"),
            "ok": phrase_box(rows, "ok")}


def navigation_changed(before, after, regions):
    a = [dominant(before[0], box) for box in regions["items"]]
    b = [dominant(after[0], box) for box in regions["items"]]
    return anchored(after, regions, ("ok", "cancel")) and a[0] != a[1] and b == a[::-1]


def anchored(screen, regions, buttons):
    # Newt changes the focused control's contrast. Verify the stationary title,
    # debug row and each unfocused button at their original text coordinates.
    try:
        for name in ("moos utm", "shell serial debug", *buttons):
            box = phrase_box(screen[2], name)
            if any(abs(a - b) > 2 for a, b in zip(box, regions[name])):
                return False
        return True
    except RuntimeError:
        return False


def ok_focused(before, after, regions):
    cancel, ok = regions["cancel"], regions["ok"]
    return (anchored(after, regions, ("cancel",)) and
            dominant(before[0], ok) != dominant(after[0], ok) and
            dominant(before[0], cancel) == dominant(after[0], cancel) and
            dominant(after[0], ok) != dominant(after[0], cancel))


def cancel_focused(before, after, regions):
    cancel, ok = regions["cancel"], regions["ok"]
    return (anchored(after, regions, ("ok",)) and
            dominant(before[0], cancel) != dominant(before[0], ok) and
            dominant(before[0], cancel) == dominant(after[0], ok) and
            dominant(before[0], ok) == dominant(after[0], cancel) and
            all(dominant(before[0], box) == dominant(after[0], box) for box in regions["items"]))


def cancelled_screen(screen):
    text = re.sub(r"[^a-z]+", " ", screen[1].lower()).strip()
    return not menu_text(text) and "recovery menu closed" in text


def fatal_serial(text):
    return FATAL.search(re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)) is not None


class QMP:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(5)
        self.sock.connect(str(path))
        self.buffer = b""
        self.events = []
        require("QMP" in self.read(), "private QEMU has no QMP greeting")
        self.command("qmp_capabilities")

    def read(self):
        while b"\n" not in self.buffer:
            chunk = self.sock.recv(65536)
            require(chunk, "private QMP closed before proof completed")
            self.buffer += chunk
            require(len(self.buffer) <= 1024 * 1024, "oversized private QMP response")
        line, self.buffer = self.buffer.split(b"\n", 1)
        return json.loads(line)

    def command(self, name, arguments=None):
        request = {"execute": name}
        if arguments is not None:
            request["arguments"] = arguments
        self.sock.sendall(json.dumps(request).encode() + b"\n")
        while True:
            response = self.read()
            if "event" in response:
                self.events.append(response)
                continue
            require("error" not in response and "return" in response,
                    "private QMP refused " + name)
            return response["return"]

    def key(self, key):
        require(key in {"down", "up", "tab"}, "unsafe recovery navigation key")
        self.command("send-key", {"keys": [{"type": "qcode", "data": key}],
                                  "hold-time": 80})

    def cancel(self, before, after, regions):
        # Native newt's lone/double Escape can remain pending indefinitely.
        # Return is allowed only after the actual Cancel button changes its
        # focus background while OK stays unfocused. No unguarded Enter API.
        require(cancel_focused(before, after, regions), "Cancel focus was not proved")
        self.command("send-key", {"keys": [{"type": "qcode", "data": "ret"}],
                                  "hold-time": 80})


def screenshot(qmp, evidence, label):
    path = evidence / (label + ".ppm")
    qmp.command("screendump", {"filename": str(path)})
    require(path.is_file() and path.stat().st_size > 32, "native screen capture missing")
    tsv = run(["tesseract", str(path), "stdout", "--psm", "6", "-l", "eng", "tsv"]).stdout.decode()
    rows = list(csv.DictReader(io.StringIO(tsv), delimiter="\t"))
    text = " ".join(row["text"] for row in rows if row.get("text"))
    (evidence / (label + ".tsv")).write_text(tsv)
    return read_ppm(path.read_bytes()), text, rows


def wait_screen(qmp, process, serial, evidence, label, predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        require(process.poll() is None, "QEMU exited before native menu acceptance")
        require(not fatal_serial(serial.read_text(errors="replace")),
                "native recovery boot entered a failed/emergency state")
        screen = screenshot(qmp, evidence, label)
        if predicate(screen):
            return screen
        time.sleep(2)
    raise RuntimeError("native recovery screen deadline: " + label)


def firmware():
    for code, variables in (
        ("/usr/share/AAVMF/AAVMF_CODE.no-secboot.fd", "/usr/share/AAVMF/AAVMF_VARS.fd"),
        ("/usr/share/AAVMF/AAVMF_CODE.fd", "/usr/share/AAVMF/AAVMF_VARS.fd"),
        ("/usr/share/edk2/aarch64/QEMU_CODE.fd", "/usr/share/edk2/aarch64/QEMU_VARS.fd")):
        if Path(code).is_file() and Path(variables).is_file():
            return code, variables
    raise RuntimeError("matching AArch64 UEFI code and variable template unavailable")


def preserve_error(record, message):
    record["result"] = "failed"
    record.setdefault("failure", message)
    record.setdefault("refusals", []).append(message)


def prove(archive, evidence, revision, run_id):
    record = {"schema": 1, "result": "failed", "revision": revision,
              "workflow_run_id": run_id, "archive_sha256": sha(archive),
              "scope": "packaged recovery menu/input and clean guest shutdown; no installation",
              "guest_service_exit_status": "unavailable: no guest management access introduced"}
    process = None
    qmp = None
    data = None
    # AF_UNIX paths are bounded; a long checkout/evidence path must not prevent
    # the private QMP socket from being created.
    scratch = tempfile.TemporaryDirectory(prefix="moos-recovery-", dir="/var/tmp")
    work = Path(scratch.name)
    try:
        data = unpack(archive, work)
        record["packaged_files"] = {name: sha(data / name) for name in
                                    ("installer.qcow2", "target.qcow2", "seed.iso")}
        code, variables = firmware()
        shutil.copyfile(variables, work / "vars.fd")
        for name in ("installer", "target"):
            info = qcow_input(data / (name + ".qcow2"), 8*1024**3 if name == "installer" else 32*1024**3)
            (evidence / (name + "-info.json")).write_text(json.dumps(info, indent=2) + "\n")
            run(["qemu-img", "check", str(data / (name + ".qcow2"))])
            run(["qemu-img", "create", "-q", "-f", "qcow2", "-F", "qcow2", "-b",
                 str(data / (name + ".qcow2")), str(work / (name + ".qcow2"))])
        serial = evidence / "serial.log"
        serial.touch()
        qmp_path = work / "qmp.sock"
        args = ["qemu-system-aarch64", "-no-user-config", "-nodefaults", "-no-reboot",
                "-machine", "virt,virtualization=on,gic-version=3", "-accel", "tcg,thread=multi",
                "-cpu", "cortex-a72", "-smp", "2", "-m", "3072", "-display", "none",
                "-drive", "if=pflash,format=raw,readonly=on,file=" + code,
                "-drive", "if=pflash,format=raw,file=" + str(work / "vars.fd"),
                "-drive", "if=none,id=installer,format=qcow2,file=" + str(work / "installer.qcow2"),
                "-device", "virtio-blk-pci,drive=installer,bootindex=0",
                "-drive", "if=none,id=target,format=qcow2,file=" + str(work / "target.qcow2"),
                "-device", "virtio-blk-pci,drive=target,bootindex=1",
                "-drive", "if=none,id=seed,format=raw,media=cdrom,readonly=on,file=" + str(data / "seed.iso"),
                "-device", "virtio-blk-pci,drive=seed,bootindex=2",
                "-netdev", "user,id=net0,restrict=on", "-device", "virtio-net-pci,netdev=net0",
                "-device", "virtio-rng-pci", "-device", "virtio-gpu-pci",
                "-device", "qemu-xhci,id=usb", "-device", "usb-kbd,bus=usb.0",
                "-device", "usb-tablet,bus=usb.0",
                "-serial", "file:" + str(serial), "-qmp", "unix:" + str(qmp_path) + ",server=on,wait=off"]
        with (evidence / "qemu.log").open("wb") as output:
            # No host display, bus or user QEMU configuration enters this proof.
            private = {k:v for k,v in os.environ.items() if k not in
                       ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS")}
            for name in ("home", "config", "cache", "runtime"):
                (work / name).mkdir(mode=0o700)
            private.update(HOME=str(work/"home"), XDG_CONFIG_HOME=str(work/"config"),
                           XDG_CACHE_HOME=str(work/"cache"), XDG_RUNTIME_DIR=str(work/"runtime"),
                           DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(work/"no-bus"))
            process = subprocess.Popen(args, stdout=output, stderr=subprocess.STDOUT, env=private)
            deadline = time.monotonic() + 30
            while not qmp_path.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.1)
            qmp = QMP(qmp_path)
            blocks = qmp.command("query-block")
            require({b.get("device") for b in blocks} >= {"installer", "target", "seed"},
                    "private QEMU did not publish all three packaged drives")
            require(next(b for b in blocks if b.get("device") == "seed")
                    .get("inserted", {}).get("ro") is True, "packaged seed is not read-only")
            (evidence / "query-block.json").write_text(json.dumps(blocks, indent=2) + "\n")
            first = wait_screen(qmp, process, serial, evidence, "menu", lambda s: menu_text(s[1]), 900)
            regions = menu_regions(first)
            qmp.key("down")
            second = wait_screen(qmp, process, serial, evidence, "menu-down",
                                 lambda s: navigation_changed(first, s, regions), 15)
            qmp.key("up")
            restored = wait_screen(qmp, process, serial, evidence, "menu-up",
                                  lambda s: navigation_changed(second, s, regions), 15)
            qmp.key("tab")
            ok = wait_screen(qmp, process, serial, evidence, "ok-focus",
                             lambda s: ok_focused(restored, s, regions), 15)
            qmp.key("tab")
            cancel = wait_screen(qmp, process, serial, evidence, "cancel-focus",
                                 lambda s: cancel_focused(ok, s, regions), 15)
            qmp.cancel(ok, cancel, regions)
            wait_screen(qmp, process, serial, evidence, "cancelled",
                        cancelled_screen, 15)
            qmp.command("system_powerdown")
            deadline = time.monotonic() + 120
            # Drain QMP even if the process already exited: SHUTDOWN can still
            # be queued in the socket after poll observes normal termination.
            while time.monotonic() < deadline:
                try:
                    response = qmp.read()
                    if "event" in response:
                        qmp.events.append(response)
                except (TimeoutError, OSError):
                    pass
                except RuntimeError:
                    # A normal guest poweroff closes QMP after SHUTDOWN. Reap
                    # that process, retaining the required native event below.
                    process.wait(timeout=5)
                    break
            require(process.poll() == 0, "recovery guest did not power off normally")
            require(any(e.get("event") == "SHUTDOWN" and
                        e.get("data", {}).get("guest") is True and
                        e.get("data", {}).get("reason") == "guest-shutdown" for e in qmp.events),
                    "QEMU has no guest-initiated clean shutdown receipt")
            require(not fatal_serial(serial.read_text(errors="replace")), "late recovery boot failure")
            record.update(native_menu="passed", native_navigation="down/up/verified-Cancel",
                          poweroff="clean", qemu_exit=process.returncode)
            record["result"] = "passed"
    except Exception as error:
        preserve_error(record, str(error))
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        try:
            if data is not None and (work / "target.qcow2").exists():
                compare = subprocess.run(["qemu-img", "compare", "-f", "qcow2", "-F", "qcow2",
                                          str(data / "target.qcow2"), str(work / "target.qcow2")],
                                         capture_output=True, timeout=60)
                record["target_content_unchanged"] = compare.returncode == 0
                record["packaged_files_unchanged"] = all(sha(data / n) == value for n, value in
                                                           record["packaged_files"].items())
                if not record["target_content_unchanged"] or not record["packaged_files_unchanged"]:
                    preserve_error(record, "packaged or target bytes changed")
            elif record["result"] == "passed":
                preserve_error(record, "target preservation input disappeared")
            record["archive_unchanged"] = sha(archive) == record["archive_sha256"]
            if not record["archive_unchanged"]:
                preserve_error(record, "input archive changed")
        except Exception as error:
            preserve_error(record, "preservation readback failed: " + str(error))
        if qmp is not None:
            (evidence / "qmp-events.json").write_text(json.dumps(qmp.events, indent=2) + "\n")
            qmp.sock.close()
        (evidence / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        scratch.cleanup()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    args = parser.parse_args()
    require(re.fullmatch("[0-9a-f]{64}", args.expected_sha256) and
            re.fullmatch("[0-9a-f]{40}", args.revision) and args.run_id > 0, "invalid proof identity")
    for tool in ("qemu-system-aarch64", "qemu-img", "tesseract"):
        require(shutil.which(tool), "required recovery proof tool absent: " + tool)
    require(args.archive.is_file() and sha(args.archive) == args.expected_sha256,
            "recovery archive identity differs before boot")
    args.evidence.mkdir(mode=0o700)
    result = prove(args.archive.resolve(), args.evidence.resolve(), args.revision, args.run_id)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

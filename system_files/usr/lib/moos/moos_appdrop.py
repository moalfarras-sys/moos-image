"""MoOS App Drop — install an application that arrived as a FILE.

A person who downloads `Obsidian-1.8.AppImage` or `blender-4.3-linux-x64.tar.xz` expects what
every other desktop gives them: put it in Applications and it is an app. On an image-based system
that has to happen entirely inside their home — /usr is read-only and the signed image must keep
following its origin — so App Drop needs no administrator rights at all.

What it does, and what it deliberately does not:

  AppImage            extracted ONCE, inside a bubblewrap sandbox with no network and no home, into
                      ~/Applications/<name>/ and launched from there. Not mounted at each start:
                      that needs FUSE 2 (absent here), or APPIMAGE_EXTRACT_AND_RUN, which runs from
                      /tmp — where moos-health rightly reports "a program is running from a
                      temporary folder".
  portable archive    .tar.gz/.tar.xz/.tar.bz2/.tar.zst/.zip, extracted by this module (never by a
                      shell), refusing absolute paths, `..`, links that leave the tree, devices,
                      and bombs (size, count and ratio ceilings), then searched for what to launch.
  Flathub .flatpakref resolved to its app id and installed by Mo Store's ordinary verified-Flathub
                      path. A ref that names ANOTHER remote is refused: accepting it would trust a
                      new publisher and their signing key on the strength of a downloaded file.
  .rpm                handed to the existing signed-RPM route (owner, digest, signature, polkit).
  .exe/.msi, .apk     handed to the existing runner (`moos-run-foreign`).
  .deb, .flatpak      refused, with the reason and the alternative. Nothing pretends to work.

The launcher entry is WRITTEN by this module, never copied from the package: a package's own
.desktop file is an instruction from its author (`Exec=sh -c …`). Only its display fields are read,
and each is sanitised. Reading the file is `inspect()`: it never executes it.

One implementation, imported by `moos-storectl install-file` (the job system the Island and Mo
Store already watch) and by `moos-app-drop` (the consent dialog). tests/test_app_drop.py.

Mo Store's catalogue installs the same way (`moos-storectl install <id>` for an `appdrop` recipe):
the download is pinned and verified first, then `plan_for()` names it with the catalogue's id and
name instead of guessing them from a file name, and `install(pinned=…)` lets the reviewed recipe
say which program, icon, window class and menu categories the launcher uses. Even then every
pinned path must lie inside the extracted tree, exactly as the guesses must.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import time
from typing import Any, Callable
import zipfile

BWRAP = "/usr/bin/bwrap"
MAX_SOURCE_BYTES = 6 * 1024 ** 3        # a downloaded installer, not a disk image
MAX_TREE_BYTES = 16 * 1024 ** 3
MAX_TREE_FILES = 250_000
MAX_RATIO = 200                          # uncompressed / compressed: a bomb, not an app
EXTRACT_TIMEOUT = 600

SUPPORTED = ("appimage", "archive", "flatpakref")
HANDOFF = {"rpm": "rpm", "windows": "foreign", "android": "foreign"}
ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tar.zst", ".tar", ".zip")
MAIN_CATEGORIES = {"AudioVideo", "Audio", "Video", "Development", "Education", "Game", "Graphics",
                   "Network", "Office", "Science", "Settings", "System", "Utility"}
FLATHUB_URLS = {"https://dl.flathub.org/repo/", "https://flathub.org/repo/"}
FLATPAK_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z_][A-Za-z0-9_-]*){2,}")
# An App Drop id: the folder in ~/Applications, the record's name and the launcher's suffix.
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{1,63}")
# An application's own reverse-DNS id (its Wayland app id). A launcher with this file name is how
# the dock finds the icon of a native window; anything else falls back to appdrop-<slug>.desktop.
DESKTOP_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z_][A-Za-z0-9_-]*){2,}")
MARKER = "X-MoOS-AppDrop"


class DropError(Exception):
    """Refused or failed. `code` is a stable key the UI owns the words for; `detail` is for a log."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


@dataclasses.dataclass
class Plan:
    path: Path
    kind: str                 # appimage | archive | flatpakref | flatpak | rpm | deb | windows | android | unknown
    name: str                 # a person's name for it
    slug: str                 # ascii id: directory, desktop file and manifest name
    size: int
    supported: bool
    handoff: str = ""         # "" | "rpm" | "foreign"
    refusal: str = ""         # a DropError code when neither supported nor handed off
    flatpak_id: str = ""
    target: Path | None = None
    replaces: bool = False    # an App Drop app with this slug is already installed

    def to_json(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["path"] = str(self.path)
        data["target"] = str(self.target) if self.target else ""
        return data


# ── places ───────────────────────────────────────────────────────────────────
def home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def applications_dir() -> Path:
    return home() / "Applications"


def data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    return Path(configured) if configured and Path(configured).is_absolute() else home() / ".local/share"


def manifest_dir() -> Path:
    return data_home() / "moos/appdrop"


def desktop_dir() -> Path:
    return data_home() / "applications"


# ── looking at a file without running it ─────────────────────────────────────
def _head(path: Path, count: int = 600) -> bytes:
    with path.open("rb") as handle:
        return handle.read(count)


def sniff(path: Path) -> str:
    """The kind of thing this file IS (magic bytes), falling back to what it is CALLED."""
    head = _head(path)
    lower = path.name.lower()
    if head[:4] == b"\x7fELF" and head[8:10] == b"AI" and head[10:11] in (b"\x01", b"\x02"):
        return "appimage"
    if head[:4] == b"\xed\xab\xee\xdb":
        return "rpm"
    if head[:8] == b"!<arch>\n" and b"debian-binary" in head[:80]:
        return "deb"
    if head[:2] == b"MZ" or (head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and lower.endswith((".msi", ".msp"))):
        return "windows"
    if head.lstrip()[:13] == b"[Flatpak Ref]":
        return "flatpakref"
    if lower.endswith(".flatpak"):
        return "flatpak"
    if head[:4] == b"PK\x03\x04":
        if lower.endswith((".xapk", ".apks")):
            raise DropError("split_android_unsupported", path.name)
        return "android" if lower.endswith(".apk") else "archive"
    if (head[:2] == b"\x1f\x8b" or head[:6] == b"\xfd7zXZ\x00" or head[:3] == b"BZh"
            or head[:4] == b"\x28\xb5\x2f\xfd" or head[257:262] == b"ustar"):
        return "archive" if lower.endswith(ARCHIVE_SUFFIXES) else "unknown"
    if lower.endswith(".appimage"):
        return "unknown"          # CALLED an AppImage, but it is not one: never trust the name up
    return "unknown"


def display_name(file_name: str) -> str:
    """`Obsidian-1.8.9-x86_64.AppImage` -> `Obsidian`; `blender-4.3.2-linux-x64.tar.xz` -> `Blender`."""
    stem = file_name
    for suffix in (".appimage", ".flatpakref", *ARCHIVE_SUFFIXES):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    parts = re.split(r"[-_ ]+", stem)
    kept: list[str] = []
    noise = re.compile(r"(?i)^(v?\d[\w.]*|x86[_-]?64|amd64|aarch64|arm64|x64|i[3-6]86|linux|gnu|glibc[\d.]*|"
                       r"portable|release|stable|latest|setup|installer|bin|bundle|unix|64bit)$")
    for part in parts:
        if noise.match(part):
            if kept:
                break              # the name ends where version and platform noise begins
            continue
        kept.append(part)
    name = " ".join(kept).strip() or stem.strip() or "App"
    if name == name.lower():
        name = " ".join(word[:1].upper() + word[1:] for word in name.split())
    return name[:80]


def slugify(name: str, fallback_seed: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]
    if len(slug) < 2:              # an Arabic or symbolic name has no ascii form: stay stable instead
        slug = "app-" + hashlib.sha256(fallback_seed.encode("utf-8")).hexdigest()[:10]
    return slug


def check_source(path: Path) -> Path:
    """A regular file the caller owns, inside their home, reached without a symlink."""
    try:
        if path.is_symlink():
            raise DropError("not_a_plain_file", "the path is a symbolic link")
        resolved = path.resolve(strict=True)
        info = resolved.stat()
    except OSError as error:
        raise DropError("file_missing", str(error)) from error
    if not stat.S_ISREG(info.st_mode):
        raise DropError("not_a_plain_file", "not a regular file")
    if info.st_uid != os.getuid():
        raise DropError("not_your_file", "the file belongs to another account")
    try:
        resolved.relative_to(home().resolve())
    except ValueError as error:
        raise DropError("outside_home", "App Drop only installs files from your own folders") from error
    if info.st_size == 0:
        raise DropError("empty_file")
    if info.st_size > MAX_SOURCE_BYTES:
        raise DropError("too_large", f"{info.st_size} bytes")
    return resolved


def read_flatpakref(path: Path) -> str:
    """The app id of a FLATHUB ref. Any other remote is a new publisher to trust: refused."""
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:60]:
        if "=" in line and not line.lstrip().startswith(("#", "[")):
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()
    if fields.get("Url", "") not in FLATHUB_URLS:
        raise DropError("foreign_remote", fields.get("Url", "no Url"))
    app_id = fields.get("Name", "")
    if fields.get("IsRuntime", "false").lower() == "true" or not FLATPAK_ID.fullmatch(app_id):
        raise DropError("bad_flatpakref", app_id)
    return app_id


def inspect(raw_path: str | os.PathLike[str]) -> Plan:
    """Everything a person needs before saying yes. Never executes the file."""
    path = check_source(Path(raw_path))
    kind = sniff(path)
    name = display_name(path.name)
    return _plan(path, kind, name, slugify(name, path.name))


def plan_for(raw_path: str | os.PathLike[str], name: str, slug: str) -> Plan:
    """The plan for a file whose id and name come from Mo Store's signed catalogue.

    `inspect()` guesses both from the file name, which is right for a file a person dropped and
    wrong for a catalogue download: the catalogue id is what the Store, the index and `remove`
    agree on. The same checks apply — what the file IS still decides its kind, and a folder the
    person made in ~/Applications is still never adopted.
    """
    if not SLUG.fullmatch(slug or ""):
        raise DropError("bad_id", repr(slug))
    path = check_source(Path(raw_path))
    return _plan(path, sniff(path), _clean(name or "", 80) or slug, slug)


def _plan(path: Path, kind: str, name: str, slug: str) -> Plan:
    plan = Plan(path=path, kind=kind, name=name, slug=slug, size=path.stat().st_size,
                supported=kind in SUPPORTED, handoff=HANDOFF.get(kind, ""))
    if kind == "flatpakref":
        plan.flatpak_id = read_flatpakref(path)
        plan.name = plan.flatpak_id.rsplit(".", 1)[-1]
    elif kind in ("appimage", "archive"):
        plan.target = applications_dir() / plan.slug
        plan.replaces = (manifest_dir() / f"{plan.slug}.json").is_file()
        if plan.target.exists() and not plan.replaces:
            # A folder the person made themselves is never overwritten or adopted.
            raise DropError("name_taken", str(plan.target))
    elif not plan.handoff:
        plan.refusal = {"deb": "deb_not_native", "flatpak": "bundle_unsupported"}.get(kind, "unknown_kind")
    return plan


# ── extraction ───────────────────────────────────────────────────────────────
def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


# A line break or any other control character in a file name is never a real application's
# name, and it is how a package would write keys of its own into the launcher MoOS writes: the
# launcher names the program's path and its icon's path, one per line. Refused everywhere a path
# enters App Drop — archive members, AppImage trees and the launcher itself.
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029]")


def _refuse_control(name: str) -> None:
    if _CONTROL.search(name):
        raise DropError("unsafe_archive", f"control character in a name: {name!r}")


def _member_rel(name: str) -> PurePosixPath:
    """An archive member's path, relative to the tree root: no control characters, no absolute
    name, no `..`, never empty. The one place a member's name is turned into path components."""
    _refuse_control(name)
    pure = PurePosixPath(name.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise DropError("unsafe_archive", f"path leaves the archive: {name!r}")
    return pure


def _safe_member_path(root: Path, name: str) -> Path:
    return root.joinpath(*_member_rel(name).parts)


def _descend(root: Path, rel: PurePosixPath) -> Path:
    """Create the folders above `rel` one component at a time, refusing any component that already
    exists as a link or a non-directory, and return that parent. The tree is only ever built from
    real directories this function made, so nothing is created or opened THROUGH a symlink a
    member planted — the defence moos_vendor_rpm._Reader makes the same way."""
    current = root
    for part in rel.parts[:-1]:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            os.mkdir(current, 0o755)
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise DropError("unsafe_archive", f"{'/'.join(rel.parts)!r} passes through a link or a file")
    return current


def _make_dir(root: Path, rel: PurePosixPath) -> None:
    path = _descend(root, rel) / rel.parts[-1]
    try:
        os.mkdir(path, 0o755)
    except FileExistsError:
        if not stat.S_ISDIR(os.lstat(path).st_mode):
            raise DropError("unsafe_archive", f"{'/'.join(rel.parts)!r} is both a folder and something else") from None


class _Budget:
    def __init__(self, compressed: int, cancelled: Callable[[], bool], progress: Callable[[int], None]):
        self.compressed = max(compressed, 1)
        self.cancelled = cancelled
        self.progress = progress
        self.bytes = 0
        self.files = 0
        self._last = 0.0

    def add(self, size: int) -> None:
        self.bytes += size
        self.files += 1
        if self.bytes > MAX_TREE_BYTES or self.files > MAX_TREE_FILES:
            raise DropError("archive_bomb", f"{self.bytes} bytes in {self.files} files")
        if self.bytes > 64 * 1024 ** 2 and self.bytes / self.compressed > MAX_RATIO:
            raise DropError("archive_bomb", f"expands {self.bytes // self.compressed}x")
        now = time.monotonic()
        if now - self._last > 0.4:
            self._last = now
            if self.cancelled():
                raise DropError("cancelled")
            self.progress(self.bytes)


def extract_zip(archive: Path, root: Path, budget: _Budget) -> None:
    """Unpack a .zip under `root`, writing only inside it and never through a link.

    Files and folders are written first, each built one component at a time (`_descend`) and
    opened with O_EXCL|O_NOFOLLOW, so a member can never mkdir or open through a symlink another
    member planted — a chain of in-tree links that each resolve inside the tree yet together
    leave it (reproduced 2026-10-15). Symlink members are created last, once every real file and
    folder exists; each is refused unless its fully resolved target still lands inside the tree,
    while a legitimate in-tree link (a library's `libfoo.so -> libfoo.so.1`) keeps working.
    """
    links: list[tuple[PurePosixPath, str]] = []     # created last, when no file can follow them
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            rel = _member_rel(info.filename)
            mode = (info.external_attr >> 16) & 0o177777
            kind = stat.S_IFMT(mode)
            if stat.S_ISLNK(mode):
                links.append((rel, bundle.read(info).decode("utf-8", "replace")))
                continue
            if info.is_dir() or kind == stat.S_IFDIR:
                _make_dir(root, rel)
                continue
            if kind and kind != stat.S_IFREG:
                raise DropError("unsafe_archive", f"device, pipe or socket: {info.filename!r}")
            parent = _descend(root, rel)
            budget.add(info.file_size)
            try:
                descriptor = os.open(parent / rel.parts[-1],
                                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            except FileExistsError:
                raise DropError("unsafe_archive", f"{info.filename!r} appears twice") from None
            with open(descriptor, "wb") as sink, bundle.open(info) as source:
                shutil.copyfileobj(source, sink, 1024 * 1024)
                # Keep the executable bit and nothing else: never setuid, never world-writable.
                os.fchmod(sink.fileno(), 0o755 if mode & 0o111 else 0o644)
        _extract_zip_links(root, links, budget)


def _extract_zip_links(root: Path, links: list[tuple[PurePosixPath, str]], budget: _Budget) -> None:
    """Create the archive's symlink members now that every file and folder is in place, so no
    file was ever written through one. A link is refused if it is absolute or lexically leaves the
    tree; then, with the whole set created, each link's fully resolved target is checked once more
    — a chain of links can only be judged after all of its hops exist."""
    resolved_root = root.resolve()
    for rel, link in links:
        destination = _descend(root, rel) / rel.parts[-1]
        if os.path.lexists(destination):
            raise DropError("unsafe_archive", f"{'/'.join(rel.parts)!r} appears twice")
        target = Path(os.path.normpath(destination.parent / link))
        if os.path.isabs(link) or not _inside(resolved_root, target):
            raise DropError("unsafe_archive", f"link leaves the archive: {'/'.join(rel.parts)!r}")
        destination.symlink_to(link)
        budget.add(0)
    for rel, _link in links:
        final = Path(os.path.realpath(root.joinpath(*rel.parts)))
        if not _inside(resolved_root, final):
            raise DropError("unsafe_archive", f"link leaves the archive: {'/'.join(rel.parts)!r}")


def extract_tar(archive: Path, root: Path, budget: _Budget) -> None:
    with tarfile.open(archive, mode="r:*") as bundle:
        for member in bundle:
            target = _safe_member_path(root, member.name)
            if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                raise DropError("unsafe_archive", f"device node: {member.name!r}")
            if member.issym() or member.islnk():
                link = member.linkname
                base = target.parent if member.issym() else root
                resolved = (base / link).resolve() if not os.path.isabs(link) else Path(link)
                if os.path.isabs(link) or not _inside(root.resolve(), resolved):
                    raise DropError("unsafe_archive", f"link leaves the archive: {member.name!r}")
            budget.add(member.size if member.isreg() else 0)
            # The "data" filter refuses absolute names, `..`, links that leave the tree, devices,
            # setuid and group/world write. The checks above are the same promise, made here so the
            # refusal has a name the UI can explain.
            bundle.extract(member, root, filter="data")


def _sandbox_base() -> list[str]:
    """No network, no home, no session, no capabilities: the image's /usr read-only and nothing else."""
    argv = [BWRAP, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/sbin", "/sbin",
            "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/run"]
    for optional in ("/etc/ld.so.cache", "/etc/ld.so.conf", "/etc/ld.so.conf.d"):
        if Path(optional).exists():
            argv += ["--ro-bind", optional, optional]
    return argv


def _sandbox_tail(out: Path) -> list[str]:
    return ["--bind", str(out), "/out", "--chdir", "/out",
            "--clearenv", "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/out",
            "--setenv", "TMPDIR", "/tmp"]


def sandbox_argv(appimage: Path, out: Path) -> list[str]:
    """Run an AppImage's own extractor with no network, no home and no way to reach the session."""
    return (_sandbox_base() + ["--ro-bind", str(appimage), "/in/app.AppImage"] + _sandbox_tail(out)
            + ["/in/app.AppImage", "--appimage-extract"])


def tool_sandbox_argv(inputs: dict[str, Path], out: Path, command: list[str]) -> list[str]:
    """Run one of the image's own tools over a downloaded file, in the same sandbox as above.

    `inputs` maps a name under /in to a file outside; each is bound read-only. The tool writes only
    into `out`, seen as /out. Used to read a Windows program's icon without trusting the parser
    with the person's home or the network.
    """
    argv = _sandbox_base()
    for name, source in inputs.items():
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", name):
            raise DropError("unsafe_archive", f"sandbox input name {name!r}")
        argv += ["--ro-bind", str(source), f"/in/{name}"]
    return argv + _sandbox_tail(out) + list(command)


def extract_appimage(appimage: Path, root: Path, budget: _Budget,
                     run: Callable[..., Any] = subprocess.run) -> None:
    if not Path(BWRAP).is_file() and run is subprocess.run:
        raise DropError("no_sandbox", "bubblewrap is missing; an AppImage is never extracted unsandboxed")
    stage = root.parent / (root.name + ".image")
    stage.mkdir()
    try:
        staged = stage / "app.AppImage"
        shutil.copyfile(appimage, staged)
        staged.chmod(0o500)
        out = stage / "out"
        out.mkdir()
        try:
            done = run(sandbox_argv(staged, out), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, timeout=EXTRACT_TIMEOUT, check=False)
        except subprocess.TimeoutExpired as error:
            raise DropError("extract_timeout") from error
        tree = out / "squashfs-root"
        if getattr(done, "returncode", 1) != 0 or not tree.is_dir():
            detail = (getattr(done, "stderr", b"") or b"")[-300:].decode("utf-8", "replace")
            raise DropError("appimage_unreadable", detail)
        for path in tree.rglob("*"):
            _refuse_control(path.name)
            if path.is_symlink():
                continue
            if path.is_file():
                budget.add(path.stat().st_size)
                path.chmod(path.stat().st_mode & 0o755)          # drop setuid and group/world write
        tree.rename(root)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# ── what to launch, and how it looks ─────────────────────────────────────────
def _clean(value: str, limit: int) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", " ", value).strip()[:limit]


def _desktop_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    section = ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:400]
    except OSError:
        return fields
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            section = line
        elif section == "[Desktop Entry]" and "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            fields.setdefault(key.strip(), value.strip())
    return fields


def _is_elf_or_script(path: Path) -> bool:
    try:
        head = _head(path, 4)
    except OSError:
        return False
    return head == b"\x7fELF" or head[:2] == b"#!"


_LAUNCHABLE = re.compile(r'<launchable\s+type\s*=\s*"desktop-id"\s*>\s*([^<\s]{1,255})\s*</launchable>')


def _metainfo_desktop_id(root: Path) -> str:
    """The desktop id an AppStream metainfo file declares, read as text and never executed."""
    for folder in ("usr/share/metainfo", "usr/share/appdata", "share/metainfo", "share/appdata"):
        directory = root / folder
        if not directory.is_dir() or directory.is_symlink():
            continue
        for candidate in sorted(directory.glob("*.xml"))[:8]:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            try:
                with candidate.open("rb") as handle:
                    text = handle.read(65536).decode("utf-8", "replace")
            except OSError:
                continue
            match = _LAUNCHABLE.search(text)
            if match and match.group(1).endswith(".desktop"):
                stem = match.group(1)[: -len(".desktop")]
                if DESKTOP_ID.fullmatch(stem):
                    return stem
    return ""


def _pinned_path(root: Path, relative: object) -> Path | None:
    """A catalogue path inside the extracted tree: relative, no `..`, no control characters."""
    if not isinstance(relative, str) or not relative or len(relative) > 255:
        return None
    return _safe_member_path(root, relative)


def find_launcher(root: Path, name: str, slug: str,
                  pinned: dict[str, Any] | None = None) -> dict[str, str]:
    """{exec, name, name_ar, comment, icon, categories, wm_class, terminal, desktop_id}.

    Everything here is read, nothing trusted. `pinned` carries what a reviewed catalogue recipe
    says (exec, icon, wm_class, categories, desktop_id, name, name_ar); it outranks the guesses,
    and its paths must still lie inside the tree.
    """
    pinned = pinned or {}
    resolved_root = root.resolve()
    entries = [p for p in root.rglob("*.desktop")
               if len(p.relative_to(root).parts) <= 4 and not p.is_symlink()]
    entries.sort(key=lambda p: (len(p.relative_to(root).parts), p.name))
    fields = _desktop_fields(entries[0]) if entries else {}

    def inside(candidate: Path) -> Path | None:
        try:
            real = candidate.resolve(strict=True)
        except OSError:
            return None
        return real if _inside(resolved_root, real) and real.is_file() else None

    executable: Path | None = None
    if pinned.get("exec"):
        wanted = _pinned_path(root, pinned["exec"])
        executable = inside(wanted) if wanted is not None else None
        if executable is None or not os.access(executable, os.X_OK):
            raise DropError("nothing_to_launch", f"the catalogue's program {pinned['exec']!r} is not in the download")
    if executable is None and (root / "AppRun").exists():
        executable = inside(root / "AppRun")
    if executable is None and fields.get("Exec"):
        word = re.split(r"\s+", fields["Exec"].strip())[0].strip('"')
        for candidate in (root / word, root / "bin" / Path(word).name, root / "usr/bin" / Path(word).name,
                          root / Path(word).name):
            executable = inside(candidate)
            if executable:
                break
    if executable is None:
        wanted = {slug, slug.replace("-", ""), name.lower().replace(" ", ""), name.lower().replace(" ", "-")}
        shallow = [p for p in root.rglob("*") if len(p.relative_to(root).parts) <= 3
                   and p.is_file() and not p.is_symlink() and os.access(p, os.X_OK) and _is_elf_or_script(p)]
        named = [p for p in shallow if p.stem.lower() in wanted or p.name.lower() in wanted]
        pool = named or [p for p in shallow if p.suffix not in {".so", ".sh"} and ".so." not in p.name]
        pool.sort(key=lambda p: (len(p.relative_to(root).parts), -p.stat().st_size))
        if len(named) >= 1 or len(pool) == 1:
            executable = inside(pool[0])
    if executable is None:
        raise DropError("nothing_to_launch", "no AppRun, desktop entry or single program was found")

    icon: Path | None = None
    if pinned.get("icon"):
        # A pinned icon that is missing is cosmetic, unlike a missing program: fall back to looking.
        wanted = _pinned_path(root, pinned["icon"])
        icon = inside(wanted) if wanted is not None else None
    wanted_icon = Path(fields.get("Icon", "")).name
    icons = [p for p in root.rglob("*") if p.suffix.lower() in {".png", ".svg", ".svgz"}
             and len(p.relative_to(root).parts) <= 8]
    if icon is None and wanted_icon:
        matches = [p for p in icons if p.stem == Path(wanted_icon).stem]
        matches.sort(key=lambda p: (p.suffix.lower() != ".svg", -p.stat().st_size if p.is_file() else 0))
        icon = next((inside(p) for p in matches if inside(p)), None)
    if icon is None and (root / ".DirIcon").exists():
        icon = inside(root / ".DirIcon")
    if icon is None and icons:
        icons.sort(key=lambda p: -p.stat().st_size if p.is_file() else 0)
        icon = next((inside(p) for p in icons[:20] if inside(p)), None)

    raw_categories = pinned.get("categories")
    if isinstance(raw_categories, list):
        raw_categories = ";".join(str(value) for value in raw_categories)
    if not isinstance(raw_categories, str) or not raw_categories:
        raw_categories = fields.get("Categories", "")
    categories = [c for c in raw_categories.split(";") if c in MAIN_CATEGORIES]
    wm_class = pinned.get("wm_class") if isinstance(pinned.get("wm_class"), str) else ""
    wm_class = wm_class or fields.get("StartupWMClass", "")

    # The application's own id, so the launcher's file name can match its native window.
    desktop_id = pinned.get("desktop_id") if isinstance(pinned.get("desktop_id"), str) else ""
    if not DESKTOP_ID.fullmatch(desktop_id):
        desktop_id = ""
    if not desktop_id and entries and DESKTOP_ID.fullmatch(entries[0].name[: -len(".desktop")]):
        desktop_id = entries[0].name[: -len(".desktop")]
    if not desktop_id:
        desktop_id = _metainfo_desktop_id(root)
    return {
        "exec": str(executable),
        "name": _clean(str(pinned.get("name") or ""), 80) or _clean(fields.get("Name", ""), 80) or name,
        "name_ar": _clean(str(pinned.get("name_ar") or ""), 80),
        "comment": _clean(fields.get("Comment", ""), 160),
        "icon": str(icon) if icon else "",
        "categories": ";".join(categories or ["Utility"]) + ";",
        "wm_class": re.sub(r"[^A-Za-z0-9._ -]", "", wm_class)[:80],
        "terminal": "true" if fields.get("Terminal", "").lower() == "true" else "false",
        "desktop_id": desktop_id[:200],
    }


def _quote_exec(path: str) -> str:
    """Desktop Entry spec: quote the argument and escape \\ " ` $ inside it; % is doubled."""
    return '"' + re.sub(r'(["`$\\])', r"\\\1", path).replace("%", "%%") + '"'


def desktop_entry(launcher: dict[str, str], slug: str) -> str:
    for value in launcher.values():
        _refuse_control(value)
    lines = ["[Desktop Entry]", "Type=Application", f"Name={launcher['name']}"]
    if launcher.get("name_ar"):
        lines.append(f"Name[ar]={launcher['name_ar']}")
    if launcher["comment"]:
        lines.append(f"Comment={launcher['comment']}")
    lines += [f"Exec={_quote_exec(launcher['exec'])} %U", f"TryExec={launcher['exec']}",
              f"Icon={launcher['icon'] or 'application-x-executable'}",
              f"Terminal={launcher['terminal']}", f"Categories={launcher['categories']}"]
    if launcher["wm_class"]:
        lines.append(f"StartupWMClass={launcher['wm_class']}")
    lines += [f"{MARKER}={slug}", ""]
    return "\n".join(lines)


def _xdg_application_dirs() -> list[Path]:
    """Every folder a launcher id resolves in: the person's, the system's and both export trees."""
    folders = [desktop_dir()]
    for entry in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
        if entry and os.path.isabs(entry):
            folders.append(Path(entry) / "applications")
    folders += [data_home() / "flatpak/exports/share/applications",
                Path("/var/lib/flatpak/exports/share/applications")]
    unique: list[Path] = []
    for folder in folders:
        if folder not in unique:
            unique.append(folder)
    return unique


def _ours(entry: Path, slug: str) -> bool:
    """A launcher App Drop wrote for `slug`: a plain file carrying its marker line."""
    if entry.is_symlink() or not entry.is_file():
        return False
    try:
        with entry.open("rb") as handle:
            text = handle.read(65536).decode("utf-8", "replace")
    except OSError:
        return False
    return f"{MARKER}={slug}" in text.splitlines()


def launcher_file_name(slug: str, desktop_id: str) -> str:
    """`<desktop_id>.desktop` when that id is free everywhere, else `appdrop-<slug>.desktop`.

    Free means no file of that name in any XDG applications folder, except the one App Drop wrote
    for this same app last time. Otherwise a Flatpak export, a system launcher or one the person
    made would be shadowed by ours — or, in their own folder, overwritten.
    """
    fallback = f"appdrop-{slug}.desktop"
    if not desktop_id or not DESKTOP_ID.fullmatch(desktop_id) or len(desktop_id) > 200:
        return fallback
    name = f"{desktop_id}.desktop"
    for folder in _xdg_application_dirs():
        candidate = folder / name
        if candidate.exists() or candidate.is_symlink():
            if folder == desktop_dir() and _ours(candidate, slug):
                continue
            return fallback
    return name


def _refresh_menu() -> None:
    """Best effort: a menu that refreshes late is not a reason to undo or fail an install."""
    for argv in (["update-desktop-database", str(desktop_dir())], ["kbuildsycoca6", "--noincremental"]):
        if shutil.which(argv[0]):
            try:
                subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=60, check=False)
            except (OSError, subprocess.SubprocessError):
                pass


# ── install / remove / list ──────────────────────────────────────────────────
def read_record(slug: str) -> dict[str, Any]:
    """The record App Drop wrote for `slug`, or {} — data to compare, never paths to trust."""
    if not SLUG.fullmatch(slug or ""):
        return {}
    try:
        data = json.loads((manifest_dir() / f"{slug}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("id") == slug else {}


def _write_atomic(path: Path, text: str, mode: int) -> None:
    temporary = path.with_name(f".{path.name}.new")
    temporary.write_text(text, encoding="utf-8")
    temporary.chmod(mode)
    temporary.replace(path)


def install(plan: Plan, *, progress: Callable[[str, int | None], None] = lambda _stage, _pct: None,
            cancelled: Callable[[], bool] = lambda: False,
            run: Callable[..., Any] = subprocess.run,
            pinned: dict[str, Any] | None = None,
            record_extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Install an `appimage` or `archive` plan. Atomic: the old version stays until the new one works.

    `pinned` is a reviewed catalogue recipe's launcher fields (see find_launcher); `record_extra`
    adds the catalogue's facts to the record (catalog_id, version, url) so Mo Store can tell an
    installed version from the one it now offers.
    """
    if plan.kind not in ("appimage", "archive") or plan.target is None:
        raise DropError("not_installable_here", plan.kind)
    apps = applications_dir()
    apps.mkdir(mode=0o755, parents=True, exist_ok=True)
    staging = apps / f".{plan.slug}.installing"
    shutil.rmtree(staging, ignore_errors=True)
    budget = _Budget(plan.size, cancelled,
                     lambda done: progress("extracting_file", None))
    progress("inspecting_file", None)
    digest = hashlib.sha256()
    with plan.path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    previous = apps / f".{plan.slug}.previous"
    old_record = read_record(plan.slug) if plan.replaces else {}
    swapped = False
    entry: Path | None = None
    old_entry_text: str | None = None
    try:
        progress("extracting_file", None)
        if plan.kind == "appimage":
            extract_appimage(plan.path, staging, budget, run)
        else:
            staging.mkdir()
            if zipfile.is_zipfile(plan.path):
                extract_zip(plan.path, staging, budget)
            else:
                extract_tar(plan.path, staging, budget)
            # `app-1.2/…` inside the archive: the app is the single folder, not a folder of one.
            children = [p for p in staging.iterdir()]
            if len(children) == 1 and children[0].is_dir() and not children[0].is_symlink():
                inner = staging.parent / f".{plan.slug}.inner"
                shutil.rmtree(inner, ignore_errors=True)
                children[0].rename(inner)
                staging.rmdir()
                inner.rename(staging)
        if cancelled():
            raise DropError("cancelled")
        progress("integrating_app", None)
        launcher = find_launcher(staging, plan.name, plan.slug, pinned)
        # Swap in: keep the working version until the new one is in place.
        shutil.rmtree(previous, ignore_errors=True)
        if plan.target.exists():
            plan.target.rename(previous)
        staging.rename(plan.target)
        swapped = True
        launcher = find_launcher(plan.target, plan.name, plan.slug, pinned)      # paths now final
        desktop_dir().mkdir(parents=True, exist_ok=True)
        entry_name = launcher_file_name(plan.slug, launcher["desktop_id"])
        entry = desktop_dir() / entry_name
        if _ours(entry, plan.slug):
            old_entry_text = entry.read_text(encoding="utf-8", errors="replace")
        _write_atomic(entry, desktop_entry(launcher, plan.slug), 0o644)
        manifest = {"schema": 1, "id": plan.slug, "name": launcher["name"], "kind": plan.kind,
                    "source": plan.path.name, "sha256": digest.hexdigest(), "directory": str(plan.target),
                    "desktop": str(entry), "launcher": entry_name,
                    "desktop_id": entry_name[: -len(".desktop")] if entry_name != f"appdrop-{plan.slug}.desktop"
                    else "",
                    "exec": launcher["exec"], "installed_at": int(time.time())}
        for key, value in (record_extra or {}).items():
            if key not in manifest:
                manifest[key] = value
        manifest_dir().mkdir(parents=True, exist_ok=True)
        _write_atomic(manifest_dir() / f"{plan.slug}.json",
                      json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", 0o644)
        # The record is the commit point. What follows is tidying, and it may not undo the install.
        swapped = False
        # The previous version may have used the other launcher name; one app, one menu entry.
        for stale in _launcher_candidates(plan.slug, old_record):
            if stale.name != entry_name and _ours(stale, plan.slug):
                try:
                    stale.unlink()
                except OSError:
                    pass
        shutil.rmtree(previous, ignore_errors=True)
        _refresh_menu()
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(apps / f".{plan.slug}.inner", ignore_errors=True)
        if swapped:
            # The new version is in place but could not be finished: the one that worked comes
            # back, launcher included; a first install leaves nothing behind.
            failed = apps / f".{plan.slug}.failed"
            shutil.rmtree(failed, ignore_errors=True)
            if plan.target.is_dir() and not plan.target.is_symlink():
                plan.target.rename(failed)
            if previous.exists():
                previous.rename(plan.target)
            shutil.rmtree(failed, ignore_errors=True)
            if entry is not None:
                if old_entry_text is not None:
                    _write_atomic(entry, old_entry_text, 0o644)
                elif _ours(entry, plan.slug):
                    entry.unlink(missing_ok=True)        # this run created it; nothing had it before
        elif previous.exists() and not plan.target.exists():
            previous.rename(plan.target)                 # the version that worked comes back
        raise


def refresh_menu() -> None:
    """Tell the menu about launchers Mo Store wrote; best effort, like App Drop's own."""
    _refresh_menu()


def launcher_path(slug: str) -> Path | None:
    """The launcher App Drop wrote for `slug`, when it is still there and still carries the marker."""
    record = read_record(slug)
    if not record:
        return None
    candidates = _launcher_candidates(slug, record)
    named = record.get("launcher")
    candidates.sort(key=lambda entry: entry.name != named)      # the one the record names first
    return next((entry for entry in candidates if _ours(entry, slug)), None)


def _launcher_candidates(slug: str, record: dict[str, Any]) -> list[Path]:
    """Where App Drop may have written `slug`'s launcher, recomputed — never a stored path."""
    candidates = [desktop_dir() / f"appdrop-{slug}.desktop"]
    desktop_id = record.get("desktop_id") if isinstance(record, dict) else None
    if isinstance(desktop_id, str) and DESKTOP_ID.fullmatch(desktop_id) and len(desktop_id) <= 200:
        candidates.append(desktop_dir() / f"{desktop_id}.desktop")
    return candidates


def installed() -> list[dict[str, Any]]:
    found = []
    if manifest_dir().is_dir():
        for record in sorted(manifest_dir().glob("*.json")):
            try:
                data = json.loads(record.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("id") == record.stem:
                found.append(data)
    return found


def remove(slug: str) -> bool:
    """Remove exactly what install() wrote for `slug`, and only inside the places it owns."""
    if not SLUG.fullmatch(slug or ""):
        raise DropError("bad_id", slug)
    record = manifest_dir() / f"{slug}.json"
    if not record.is_file():
        return False
    # Never trust the paths stored in the manifest: recompute them from the id. The launcher may
    # carry the app's own id as its name, so it goes only when it carries App Drop's marker for
    # this app — a launcher the person or another installer owns keeps its file.
    directory = applications_dir() / slug
    if directory.is_dir() and not directory.is_symlink():
        shutil.rmtree(directory)
    for entry in _launcher_candidates(slug, read_record(slug)):
        if _ours(entry, slug):
            entry.unlink(missing_ok=True)
    record.unlink()
    _refresh_menu()
    return True

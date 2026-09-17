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
        return "android" if lower.endswith((".apk", ".xapk", ".apks")) else "archive"
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
    slug = slugify(name, path.name)
    plan = Plan(path=path, kind=kind, name=name, slug=slug, size=path.stat().st_size,
                supported=kind in SUPPORTED, handoff=HANDOFF.get(kind, ""))
    if kind == "flatpakref":
        plan.flatpak_id = read_flatpakref(path)
        plan.name = plan.flatpak_id.rsplit(".", 1)[-1]
    elif kind in ("appimage", "archive"):
        plan.target = applications_dir() / slug
        plan.replaces = (manifest_dir() / f"{slug}.json").is_file()
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


def _safe_member_path(root: Path, name: str) -> Path:
    pure = PurePosixPath(name.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise DropError("unsafe_archive", f"path leaves the archive: {name!r}")
    return root.joinpath(*pure.parts)


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
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            target = _safe_member_path(root, info.filename)
            mode = (info.external_attr >> 16) & 0o177777
            if stat.S_ISLNK(mode):
                link = bundle.read(info).decode("utf-8", "replace")
                resolved = (target.parent / link).resolve() if not os.path.isabs(link) else Path(link)
                if os.path.isabs(link) or not _inside(root.resolve(), resolved):
                    raise DropError("unsafe_archive", f"link leaves the archive: {info.filename!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(link)
                budget.add(0)
                continue
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            budget.add(info.file_size)
            with bundle.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink, 1024 * 1024)
            # Keep the executable bit and nothing else: never setuid, never world-writable.
            target.chmod(0o755 if mode & 0o111 else 0o644)


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


def sandbox_argv(appimage: Path, out: Path) -> list[str]:
    """Run an AppImage's own extractor with no network, no home and no way to reach the session."""
    argv = [BWRAP, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/sbin", "/sbin",
            "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/run"]
    for optional in ("/etc/ld.so.cache", "/etc/ld.so.conf", "/etc/ld.so.conf.d"):
        if Path(optional).exists():
            argv += ["--ro-bind", optional, optional]
    argv += ["--ro-bind", str(appimage), "/in/app.AppImage", "--bind", str(out), "/out", "--chdir", "/out",
             "--clearenv", "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/out",
             "--setenv", "TMPDIR", "/tmp", "/in/app.AppImage", "--appimage-extract"]
    return argv


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


def find_launcher(root: Path, name: str, slug: str) -> dict[str, str]:
    """{exec, name, comment, icon, categories, wm_class, terminal} — all read, none trusted."""
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
    if (root / "AppRun").exists():
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
    wanted_icon = Path(fields.get("Icon", "")).name
    icons = [p for p in root.rglob("*") if p.suffix.lower() in {".png", ".svg", ".svgz"}
             and len(p.relative_to(root).parts) <= 8]
    if wanted_icon:
        matches = [p for p in icons if p.stem == Path(wanted_icon).stem]
        matches.sort(key=lambda p: (p.suffix.lower() != ".svg", -p.stat().st_size if p.is_file() else 0))
        icon = next((inside(p) for p in matches if inside(p)), None)
    if icon is None and (root / ".DirIcon").exists():
        icon = inside(root / ".DirIcon")
    if icon is None and icons:
        icons.sort(key=lambda p: -p.stat().st_size if p.is_file() else 0)
        icon = next((inside(p) for p in icons[:20] if inside(p)), None)

    categories = [c for c in fields.get("Categories", "").split(";") if c in MAIN_CATEGORIES]
    return {
        "exec": str(executable),
        "name": _clean(fields.get("Name", ""), 80) or name,
        "comment": _clean(fields.get("Comment", ""), 160),
        "icon": str(icon) if icon else "",
        "categories": ";".join(categories or ["Utility"]) + ";",
        "wm_class": re.sub(r"[^A-Za-z0-9._ -]", "", fields.get("StartupWMClass", ""))[:80],
        "terminal": "true" if fields.get("Terminal", "").lower() == "true" else "false",
    }


def _quote_exec(path: str) -> str:
    """Desktop Entry spec: quote the argument and escape \\ " ` $ inside it; % is doubled."""
    return '"' + re.sub(r'(["`$\\])', r"\\\1", path).replace("%", "%%") + '"'


def desktop_entry(launcher: dict[str, str], slug: str) -> str:
    lines = ["[Desktop Entry]", "Type=Application", f"Name={launcher['name']}"]
    if launcher["comment"]:
        lines.append(f"Comment={launcher['comment']}")
    lines += [f"Exec={_quote_exec(launcher['exec'])} %U", f"TryExec={launcher['exec']}",
              f"Icon={launcher['icon'] or 'application-x-executable'}",
              f"Terminal={launcher['terminal']}", f"Categories={launcher['categories']}"]
    if launcher["wm_class"]:
        lines.append(f"StartupWMClass={launcher['wm_class']}")
    lines += [f"X-MoOS-AppDrop={slug}", ""]
    return "\n".join(lines)


def _refresh_menu() -> None:
    for argv in (["update-desktop-database", str(desktop_dir())], ["kbuildsycoca6", "--noincremental"]):
        if shutil.which(argv[0]):
            subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=60, check=False)


# ── install / remove / list ──────────────────────────────────────────────────
def install(plan: Plan, *, progress: Callable[[str, int | None], None] = lambda _stage, _pct: None,
            cancelled: Callable[[], bool] = lambda: False,
            run: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    """Install an `appimage` or `archive` plan. Atomic: the old version stays until the new one works."""
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
        launcher = find_launcher(staging, plan.name, plan.slug)
        # Swap in: keep the working version until the new one is in place.
        shutil.rmtree(previous, ignore_errors=True)
        if plan.target.exists():
            plan.target.rename(previous)
        staging.rename(plan.target)
        launcher = find_launcher(plan.target, plan.name, plan.slug)      # paths now final
        desktop_dir().mkdir(parents=True, exist_ok=True)
        entry = desktop_dir() / f"appdrop-{plan.slug}.desktop"
        temporary = entry.with_suffix(".desktop.new")
        temporary.write_text(desktop_entry(launcher, plan.slug), encoding="utf-8")
        temporary.chmod(0o644)
        temporary.replace(entry)
        manifest = {"schema": 1, "id": plan.slug, "name": launcher["name"], "kind": plan.kind,
                    "source": plan.path.name, "sha256": digest.hexdigest(), "directory": str(plan.target),
                    "desktop": str(entry), "exec": launcher["exec"], "installed_at": int(time.time())}
        manifest_dir().mkdir(parents=True, exist_ok=True)
        record = manifest_dir() / f"{plan.slug}.json"
        record.with_suffix(".json.new").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
        record.with_suffix(".json.new").replace(record)
        shutil.rmtree(previous, ignore_errors=True)
        _refresh_menu()
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(apps / f".{plan.slug}.inner", ignore_errors=True)
        if previous.exists() and not plan.target.exists():
            previous.rename(plan.target)                 # the version that worked comes back
        raise


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
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", slug or ""):
        raise DropError("bad_id", slug)
    record = manifest_dir() / f"{slug}.json"
    if not record.is_file():
        return False
    # Never trust the paths stored in the manifest: recompute them from the id.
    directory = applications_dir() / slug
    if directory.is_dir() and not directory.is_symlink():
        shutil.rmtree(directory)
    (desktop_dir() / f"appdrop-{slug}.desktop").unlink(missing_ok=True)
    record.unlink()
    _refresh_menu()
    return True

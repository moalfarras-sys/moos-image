#!/usr/bin/env python3
"""Prepare MoOS's Plasma seams for a new Plasma: fetch, compare, three-way merge.

    python3 scripts/plasma-next/rederive_seams.py 6.7.5 6.7.90

OLD is a Plasma version a seam set was reviewed against; NEW is the upstream version to move to.
For each seam in build_files/plasma-seams/seams.json this downloads the x86_64 RPMs of both
versions (Fedora updates/releases, then KDE SIG's beta/final COPRs), compares the
upstream bytes, and for every changed seam writes into ~/.cache/moos-plasma-next/rederive/<NEW>/:

    <name>.upstream.diff   what upstream changed between OLD and NEW
    <name>.merged          MoOS's copy with upstream's change merged in (git merge-file)

It changes nothing in the repository. Resolving conflicts, the lock-screen probe and recording
digests are a person's job (build_files/plasma-seams/README.md). Needs rpm2cpio, cpio and git;
on a MoOS workstation run it on the host (flatpak-spawn --host) where they exist.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEAMS = ROOT / "build_files" / "plasma-seams"
FEDORA = ("https://dl.fedoraproject.org/pub/fedora/linux/updates/{rel}/Everything/x86_64/",
          "https://dl.fedoraproject.org/pub/fedora/linux/releases/{rel}/Everything/x86_64/os/")
COPR = tuple("https://download.copr.fedorainfracloud.org/results/@kdesig/" + lane +
             "/fedora-{rel}-x86_64/" for lane in ("kde-beta", "kde-final"))
NS = {"c": "http://linux.duke.edu/metadata/common"}


def primary(base: str) -> ET.Element | None:
    try:
        repomd = urllib.request.urlopen(base + "repodata/repomd.xml", timeout=60).read().decode()
    except OSError:
        return None
    match = re.search(r'<data type="primary">.*?<location href="([^"]+)"', repomd, re.S)
    if not match:
        return None
    blob = urllib.request.urlopen(base + match.group(1), timeout=300).read()
    return ET.fromstring(decompress(blob))


def decompress(blob: bytes) -> bytes:
    """Fedora's repodata is zstd, COPR's is gzip; tell them apart by magic, not by name."""
    if blob[:2] == b"\x1f\x8b":
        return gzip.decompress(blob)
    if blob[:4] == b"\x28\xb5\x2f\xfd":
        try:
            from compression import zstd  # Python 3.14+
            return zstd.decompress(blob)
        except ImportError:
            return subprocess.run(["zstd", "-dc"], input=blob, check=True,
                                  capture_output=True).stdout
    return blob


def local_rpm(directory: Path, package: str, version: str) -> str:
    """Review historical signed inputs after live repository metadata moves on."""
    candidates = []
    for path in directory.glob(f"{package}-{version}-*.rpm"):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("local RPM input is not a regular file")
        fields = subprocess.check_output(
            ["rpm", "-qp", "--qf", "%{NAME} %{VERSION} %{ARCH}", str(path)], text=True).split()
        if fields != [package, version, "x86_64"]:
            raise RuntimeError("local RPM metadata does not match the requested input")
        signature = subprocess.check_output(
            ["rpmkeys", "--checksig", "--verbose", str(path)], text=True)
        if not re.search(r"signature.*: OK", signature, re.I) or "NOKEY" in signature:
            raise RuntimeError("local RPM input has no verified trusted signature")
        candidates.append(path.resolve().as_uri())
    if len(candidates) != 1:
        raise RuntimeError("local RPM input missing or ambiguous: " + package + " " + version)
    return candidates[0]


def find_rpm(package: str, version: str, release: str, cache: dict,
             rpm_directory: Path | None = None) -> str:
    if rpm_directory is not None:
        return local_rpm(rpm_directory, package, version)
    for base in [b.format(rel=release) for b in (*FEDORA, *COPR)]:
        if base not in cache:
            cache[base] = primary(base)
        root = cache[base]
        if root is None:
            continue
        for pkg in root.findall("c:package", NS):
            if pkg.find("c:name", NS).text != package or pkg.find("c:arch", NS).text != "x86_64":
                continue
            if pkg.find("c:version", NS).attrib["ver"] == version:
                return base + pkg.find("c:location", NS).attrib["href"]
    raise SystemExit(f"{package} {version} not found for Fedora {release} (updates, releases, kde-beta, kde-final)")


def extract(url: str, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    rpm_file = dest / url.rsplit("/", 1)[1]
    if not rpm_file.exists():
        with urllib.request.urlopen(url, timeout=600) as resp, open(rpm_file, "wb") as out:
            shutil.copyfileobj(resp, out)
    tree = dest / "tree"
    if not tree.exists():
        tree.mkdir()
        payload = subprocess.run(["rpm2cpio", str(rpm_file)], check=True, capture_output=True).stdout
        subprocess.run(["cpio", "-idm", "--quiet"], input=payload, cwd=tree, check=True)
    return tree


def moos_copy(path: str, set_id: str, registry: dict) -> Path | None:
    chosen = next(s for s in registry["sets"] if s["id"] == set_id)
    # A newly registered destination may have no reviewed implementation in
    # OLD. Do not invent an old copy or merge an adapter into an unrelated
    # upstream file. The new surface needs its own native owner review.
    seam = next(s for s in registry["seams"] if s["path"] == path)
    if seam.get("sets") is not None and set_id not in seam["sets"]:
        return None
    source = chosen["sources"].get(path)
    return SEAMS / source if source else ROOT / "system_files" / path.lstrip("/")


def set_for(version: str, registry: dict) -> str:
    sys.path.insert(0, str(ROOT / "build_files"))
    import plasma_seams  # noqa: E402  (the build's own selector, so both agree)
    return plasma_seams.select_set(registry, version)["id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--fedora", default="44")
    ap.add_argument("--out", default=str(Path.home() / ".cache/moos-plasma-next/rederive"))
    ap.add_argument("--rpm-dir", type=Path,
                    help="directory of signed exact-version RPMs for historical/offline review")
    args = ap.parse_args()

    registry = json.loads((SEAMS / "seams.json").read_text(encoding="utf-8"))
    old_set = set_for(args.old, registry)
    out = Path(args.out) / args.new
    out.mkdir(parents=True, exist_ok=True)
    cache: dict = {}
    trees = {}
    for package in sorted({s["package"] for s in registry["seams"]}):
        for version in (args.old, args.new):
            url = find_rpm(package, version, args.fedora, cache, args.rpm_dir)
            trees[(package, version)] = extract(url, out.parent / "rpms" / f"{package}-{version}")

    changed = 0
    for seam in registry["seams"]:
        path, package = seam["path"], seam["package"]
        old = trees[(package, args.old)] / path.lstrip("/")
        new = trees[(package, args.new)] / path.lstrip("/")
        if not new.exists():
            print(f"GONE     {path}: {package} {args.new} no longer ships it")
            changed += 1
            continue
        digest = hashlib.sha256(new.read_bytes()).hexdigest()
        current = moos_copy(path, old_set, registry)
        if current is None:
            print(f"NEW      {path}  {digest}: no reviewed MoOS copy in {old_set}; review native owner")
            changed += 1
            continue
        if old.exists() and old.read_bytes() == new.read_bytes():
            print(f"same     {path}  {digest}")
            continue
        changed += 1
        name = Path(path).name
        diff = subprocess.run(["diff", "-u", str(old), str(new)], capture_output=True, text=True).stdout
        (out / f"{name}.upstream.diff").write_text(diff, encoding="utf-8")
        merged = out / f"{name}.merged"
        shutil.copyfile(current, merged)
        rc = subprocess.run(["git", "merge-file", "-L", f"moos-{old_set}", "-L", f"upstream-{args.old}",
                             "-L", f"upstream-{args.new}", str(merged), str(old), str(new)]).returncode
        state = "clean" if rc == 0 else f"{rc} conflict(s)" if rc > 0 else "merge error"
        print(f"CHANGED  {path}  {digest}  merge: {state}")
    print(f"\n{changed} seam(s) need review for Plasma {args.new}; files in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

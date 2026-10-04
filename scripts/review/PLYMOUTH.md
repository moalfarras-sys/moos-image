# Native Plymouth frame-lifetime proof

`plymouth-frame-lifetime.py` reproduces P0.7 against the exact vendor source RPM
and native event-loop library. It applies all 23 vendor patches, verifies the
resulting splash source digest, then compiles that real source with ASan. A due
frame timeout survives `ply_boot_splash_free()` in the unmodified source; the
proposed patch disarms it before freeing the splash. The fixture does not need
a display, renderer, device, privileged host command or reboot.

Use a disposable **native** Podman SDK image with `gcc`, `libasan`, `python3`,
`rpm-build`, `cpio`, `patch` and `plymouth-core-libs` at `24.004.60-24.fc44`.
The script refuses another library/source version. No host compilation is allowed.
The 2026-10-04 run used `localhost/moos-plymouth-repro:20261004`, built from the
native KCM review SDK with `libasan` and `patch` installed only in the container.

Download the [vendor source RPM](https://kojipkgs.fedoraproject.org/packages/plymouth/24.004.60/24.fc44/src/plymouth-24.004.60-24.fc44.src.rpm)
into a private artifact directory. Its SHA-256 is pinned in the script; a changed
download is refused before extraction. On a host shell, from the repository:

```sh
podman run --rm --network none --security-opt label=disable \
  -v "$PWD/scripts/review/plymouth-frame-lifetime.py:/proof.py:ro" \
  -v "$PWD/test-results/completion-20261004:/review" \
  localhost/moos-plymouth-repro:20261004 \
  python3 /proof.py --srpm /review/plymouth.src.rpm \
    --output /review/plymouth-proof
```

The output directory must be new. Expected evidence: three vendor trials exit
71 with a frame use-after-free, twenty patched trials exit 0, and `proof.json`
says `passed: true`. ASan abort/coredumps are disabled; an unexpected signal or
missing sanitizer report fails the proof. Logs and `proposed-frame-lifetime.patch`
remain in that artifact directory, never installed on the workstation.

This is **native regression evidence only**. It does not package the patch,
prove every quit path, change the boot image or close P0.7. Delivery still requires
reviewed package integration, the local image gates and signed artifact boot
acceptance recorded in the existing development plan and release contract.

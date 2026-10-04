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

## Package and pixel review

The `plymouth-build` stage now rebuilds the pinned vendor spec with all original
patches/flags plus `build_files/plymouth/frame-lifetime.patch`. Runtime output is
`24.004.60-24.1.moos1.fc44`; SDK/devel/debug packages stay outside the final image.
`verify_plymouth_package.py` separately exercises the actual rebuilt shared
library: three old controls lack cancellation, twenty fixed trials cancel it.
`verify_plymouth_script.py` loads the actual rebuilt script parser and requires
both the positive theme and the negative BOM result. Neither proof uses devices.

For native pixels, extend that disposable SDK with `plymouth-devel` and Xvfb,
then run the private review (repository read-only, artifacts on real disk):

```sh
podman run --rm --network none --security-opt label=disable --ulimit core=0 \
  -v "$PWD:/repo:ro" -v "$PWD/test-results/boot-polish-20261004:/evidence:rw" \
  --entrypoint bash localhost/moos-plymouth-render:20261004 \
  /repo/scripts/review/plymouth-render.sh
```

The wrapper refuses non-container execution and uses its own X server. It saves
native pixel buffers at 640×480, 1920×1080 and 3840×2160 plus a password prompt;
`plymouth-render.c` reports peak RSS and CPU consumed up to each capture. These
include the X11 review process/renderer costs, not a DRM boot or desktop idle.
The Oct 4 paired 1.2-second review samples at 1080p measured old/new peak RSS
173016/93392 KiB and process CPU 1.177/0.284 s. This is a sample comparison, not
an end-to-end boot speed guarantee. Full signed boot acceptance remains required.

Final image installation replaces only already-owned Plymouth subpackages and
refuses an unknown upstream NVR. After the last dracut, the image gate checks RPM
versions, root-library hash and the exact library bytes in the boot archive.
A new upstream version requires a reviewed rebase; never widen the pin or skip
that gate merely to make a build pass.

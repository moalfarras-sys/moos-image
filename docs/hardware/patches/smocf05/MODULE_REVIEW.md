# Native SMOCF05 module build

The exact upstream transport backport now has a repeatable native compilation
and signature review in `scripts/review/smocf05-module.py`. It consumes the pinned,
publisher-signed source and development RPMs in the adjacent JSON manifest. Run
it as the owner's user inside the existing development toolbox, with the exact matching kernel-devel,
GCC, make, elfutils-libelf-devel, dwarves, OpenSSL, Git, cpio and kmod available:

```sh
python3 scripts/review/smocf05-module.py --inputs /absolute/private/rpms \
    --output /absolute/private/new-review-directory
```

The inputs are the two exact RPM basenames in the manifest. Their official URLs
are `rpm_base_url` plus `src/` or `x86_64/` and the basename. The helper does not
download, install packages, modify the host, load a module or enroll a key.
Use `toolbox run -c moos-dev` or an explicitly mapped owner UID. Bare `podman exec`
selected container root in the first review and made private artifacts inaccessible
to the host owner; preserve that refusal and do not relax their permissions. An
unreadable certificate is unavailable input, not a valid wrong-key control.
It refuses an existing output directory, changed/unsigned input, modified devel
files, missing archive members, a vendor patch touching this driver, unexpected
patched source, changed ABI/dependency/namespace or additional alias changes.

Native result on2026-11-14: the signed7.3.3 source contains the same old transport
as our original fixture; its signed devel package passes `rpm -V`. Both old and
fixed transports compile using native kbuild. The fixed module adds precisely
`acpi*:SMOCF05:*`; all existing OF/I2C/ACPI identities remain. Core dependency,
namespace and exact7.3.3 vermagic match. Source header and archive/spec/vendor
patch bytes are pinned. The empty optional vendor test patch is retained.

The helper signs a copy using a **private review-only certificate**, checks the
actual detached PKCS#7 content with that exact certificate, and writes a receipt
with `kernel_trust=false`, `installed=false`, `loaded=false` and
`physical_sensor_acceptance=false`. The key is not enrolled, uploaded, committed
or suitable for production. OpenSSL's `-noverify` skips certificate-chain trust
only; `-nointern` prevents an embedded other signer from satisfying the exact
certificate check. Real changed-content/wrong-certificate/trailer controls are
in `tests/test_sensor_module_signature.py`. Merely seeing a `modinfo` signer does
not establish signature validity or kernel trust.

The first native builds report normal skipped BTF generation because this SDK
does not carry vmlinux. They are development artifacts, not complete production
RPMs or a reason to bypass required image metadata/boot gates. Compilation and
signing do not establish I2C probe, orientation or physical touch correctness.

## Delivery still required

Prefer a vendor-signed kernel containing the accepted fix. If a project module
backport is selected, preserve the original signed kernel and vendor module,
build/package against each exact supported kernel, sign through a dedicated
protected module key, and qualify the actual trusted key on the target. The
container-image signing key is a different authority. Never substitute a review
certificate or disable signature enforcement. A new machine-key enrollment needs
the owner's native administrator interaction and firmware confirmation; simply
placing a certificate in the image does not enroll it.

Before enabling an image path, require immutable RPM/module admission, exact
kernel/architecture/signature/depmod resolution, unmodified stock kernel and
recovery, all normal image/boot checks, and actual IIO/SensorProxy/four-orientation
KWin/touch/suspend acceptance. The candidate7.3.3 module cannot be loaded into the
currently booted7.2.15 kernel. Retire the override only when the vendor module
contains the fix and the native driver/readback passes.

The owner now conditions host update/reboot on the repaired sensor kernel. The
previous host-delivery waiter was stopped before any staging; existing source,
image and signed release proofs continue independently. Do not restart that
waiter based on a successful image lacking this fix.

References: [native module builds](https://docs.kernel.org/kbuild/modules.html),
[module signatures](https://docs.kernel.org/admin-guide/module-signing.html),
and the exact accepted upstream commit in `manifest.json`.

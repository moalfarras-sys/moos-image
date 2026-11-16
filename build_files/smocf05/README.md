# V3 SMOCF05 exact-kernel module package

This directory admits one additive transport RPM for kernel7.3.3-200.fc44.x86_64.
The upstream fix and original attribution remain in
`docs/hardware/patches/smocf05/`; the source/build inputs are pinned in
`scripts/review/smocf05-module.json`. Native old/fixed compilation precedes
packaging. The package includes the upstream COPYING and full GPL2 text and
preserves the source references in its provenance. It does not replace the
vendor kernel or vendor transport.

`package.py` runs as the mapped owner in the existing development toolbox. It
consumes the native fixed module/proof and an external protected0600 production
module key; strips debug before signing, verifies the exact signature, then
compresses and builds the RPM. Example:

```sh
python3 build_files/smocf05/package.py --module /private/fixed/st_lsm6dsx_i2c.ko \
  --proof /private/native/proof.json --key /protected/module.key \
  --output /private/new-package-directory
```

Only the public certificate and exact20,770-byte RPM are committed. The dedicated
certificate uses digitalSignature, codeSigning and the module-only
1.3.6.1.4.1.2312.16.1.2 usage, and is distinct from OCI and review signing keys.
Its SHA256 is `b8c98812edf59a6e3e96321a5dcd718cf70204baa25af00189d3fa8cc4d1a535`.
The RPM header itself is unsigned: admission pins the complete RPM digest and
verifies the module's actual PKCS#7 signature/content against this pinned key;
the final OS retains its normal cosign signature policy. Never present this as
an RPM signed by the vendor or substitute it into the host RPM installer.

`admit.py check-package RPM` verifies exact RPM metadata, payload set, regular
root-owned0644 entries, absent scripts/triggers, exact kernel/core dependencies,
license/provenance, module bytes/signature/ABI and certificate. `compose` is
restricted to an explicitly identified compose container. It records exact
vendor vmlinuz/core/transport bytes before and after the transaction, preserves
all existing aliases and proves the one additional SMOCF05 match. Native depmod
must select the exact updates/moos transport and existing vendor core.
`verify-installed` repeats byte/signature/package/resolution checks after full
image assembly. A base kernel or same-NVR byte change refuses for fresh review.
Cloud and ARM keep their existing native kernels without this x86 tablet module.

Native tests on the qualified868a12ae image install and verify the actual RPM;
a changed installed module is refused, and removing only this private container's
new RPM plus depmod restores the original vendor owner and aliases. The owner
deployment was not mounted. The first source-volume SELinux-label refusal is
retained; the private review uses an isolated unlabeled container without
relabeling the checkout or changing the host policy.

## Trust, acceptance and retirement

Cryptographic integrity is established by these checks. Machine trust requires
native enrollment/keyring readback and a real driver probe. The V3 currently
reports the public key **not enrolled**; its booted7.2.15 cannot load the7.3.3
module. Do not disable Secure Boot, signature enforcement or kernel ABI checks.
Production enrollment uses native administrator authentication and physical
firmware confirmation; the private key never enters the image or GitHub.

Host stage/reboot remains held under the owner's sensor-repair condition until
the matching signed image and native trust steps are ready. Four orientations,
tilt, internal-panel sizing, physical touch, rotation lock, external display and
suspend/reboot still require the real V3. CI/container success does not establish
these outcomes. Preserve the signed rollback and pinned recovery.

When a reviewed vendor signed kernel includes SMOCF05, qualify its real probe and
native rotation, then retire only this additive RPM/build lane. Never delete the
vendor module, reuse an old-kernel module or relax the stock-kernel/image gates.

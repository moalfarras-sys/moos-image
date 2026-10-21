# V3 compatibility source review — 21 October 2026

Scope: operator review of the runtime corrections and the exact vendor directory
correction below, together with preserved native controls. This is not an independent automated review,
signed artifact acceptance or physical cold-login acceptance.

The Claude advisory jobs `39489708654`, `39522611465` and `39561982601` have green job
conclusions, but their actual execution results have `is_error:true`, one turn,
empty model usage and `REVIEW_OUTCOME=failure`. No automated code-review
completion or findings are accepted from these runs. The logs do not establish
the underlying provider error; do not infer that the code passed review or that
a specific credential is expired. The existing nonblocking workflow and its
explicit warning are retained.

## Reviewed boundaries

| Area | Source reviewed and conclusion |
| --- | --- |
| Pristine transaction | `build_files/plasma_stable/runtime_state.py` records an empty identity and empty mutable input before package commands. Metadata, native creators, account authorities and catalogue bytes are checked before its cleanup. The input identity cannot be restored by a later standalone invocation. Existing identity, mount, link, unknown-state and authority refusals remain intact. |
| Native ARM input | `prepare_arm_compose_base.py` verifies its different empty vendor scaffolds before canonicalization. Only the two exact known writable NSS bodies receive root-only write permission, preserving names/IDs/bytes. The one writable native rpm-state creator has an exact full-file/owner/mode/rule pin; the shared x86 reader stays strict. |
| Vendor normalization | `finalize_canary_base.py` unlinks only the exact proven SELinux compatibility alias, preserving the configured policy store and matching boot policy. `finalize_root_home.py` protects unknown/credential entries. `finalize_dbus_state.py` preserves pristine identity and native runtime recreation. The general image and identity gates are unchanged. |
| Experimental base | `prepare_plasma_canary_base.py` constructs the shared transaction before every package mutation. Native command failures propagate. Only the optional kcm-fcitx5 module may be explicitly removed without autoremove. Both stable and experimental composers keep their command logs in private temporary directories, preventing native rotated build logs entering persistent state. Command stdout/stderr is retained; failures remain nonzero. Kernel exclusion preserves actual stock vmlinuz bytes and avoids unrelated same-NVR reinstall/dracut state; blind rpm-state erasure is removed. |
| Greeter directory | The sequential native canary exposed an empty service-owned01770 directory declared by the exact6.8.1 RPM (also reproduced for initial beta6.7.91 on CI's fresh stock), while the unchanged native tmpfiles creator requires0750. With systemd already upgraded, its global trigger does not correct that later RPM directory. `plasma_stable/login_state.py` checks the pristine transaction, exact NVR, unchanged runtime record, empty directory, owner/mode/type/mount, immutable creator scope and exact RPM directory metadata before restricting its permissions. Native metadata and account bytes stay unchanged; generic cleanup still enforces0750.19 directory controls retain unknown-version/state/authority refusals. The beta path receives the original transaction before any finalizer; explicit workflow copies include the helper. |
| Plasma input | Separate exact6.8.1 source/prepared/backend pins and narrow seam range preserve vendor authentication, null-geometry, shutdown and SIGHUP changes. All12 seam files compare unchanged. Native lock positive/broken/restored controls and compiled package checks are distinct from physical greeter acceptance. |
| Authority and delivery | Package work is confined to unbooted build containers; the actual installed-host negative refuses before mutation. No host kernel layering, forced hardware ID, EC write, signature/policy bypass or new canary publish permission is introduced. |

Native evidence exposed the generated identity, rotated DNF log, unrelated
kernel-state and sequential greeter-directory cases. Their exact corrections
and nonzero old controls are preserved. The new directory correction passes
native base readback; complete final-source image/CI qualification remains
required before integration. No completed automated review is inferred.

## Evidence and limits

- Final functional head9ede passes the maintained repository gate:2850 Python
  unittest cases across206 summaries, plus its other native/maintained checks.
- The complete local production image6ea58661 passes and its raw payload
  readback verifies the new greeter/RPM/source receipt, managed PAM/helper/unit
  hashes, enforcing SELinux, empty identity/state and absent build SDK/cache.
- The actual workflow-derived native experimental base11eef61a passes; its
  stock base layer prefix and vmlinuz bytes independently match the original.
  Seven command/failure controls and seven workflow controls pass.
- Subsequent canary run39522611368 correctly refuses the native01770 directory.
  The local old stable transition reproduces it, and a read-only audit identifies
  only that metadata mismatch. The corrected native transition3bdc4145 reaches
  exact6.8.1, retains the stock kernel bytes and vendor RPM/creator metadata, and
  returns to empty image identity/state. New direct installed-host negative
  refuses before package queries or permission changes.
- Source backup addenda restore the exact head/tree independently and full
  fsck succeeds. These are source backups, not installed rollback proof.

Exact final-head CI and one frozen signed artifact boot/promotion cycle remain
required. New6.8.1 physical automatic fingerprint and separate no-touch password
fallback, BIOS charge-limit plateau, suspend/resume and wider hardware acceptance
remain separate. The historical Qt screenRemoved crash and unsupported SMOCF05
rotation are unresolved; this review does not claim their repair.

## Exact177 fresh-input refusal

The177 local images and2868 maintained cases pass on the older stock input. Fresh
GitHub runs39561982511/39561982723 instead consume config
`sha256:ebc648e609aed2b44e0482019d19ce107141cfd5a004ec2adf5b0d9f866c22c0`,
independently matched to immutable platform manifest
`sha256:acf84c9768b7f6239f153c43d44811de22a38555978ef98e2ac21884986d204f`.
They refuse `var/log/dnf5.log.1` and the initial beta's empty01770 greeter
directory respectively. A native original stable transaction on that same stock
passes locally: this no-repro is retained, not reported as a reproduced failure.
The original beta transaction reproduces its exact6.7.91-1.fc44 metadata refusal.
Its immutable creator has SHA256
`6a2aa3937eee9c543ba995170ac683e64cf110b00ee21a9dfa66a722e4f5cd55`,
identical to the retained681 fixture. Stable logs now use private build tmp; beta
uses the same narrow reviewed permission reconciliation.42 focused controls pass.
A deliberate native1024-byte log-size fixture makes unchanged177 refuse its DNF-generated rotated logs and the corrected source pass. Corrected initial-beta composition passes too. Independent raw readers prove pristine identity/var, retained creator and unchanged stock kernel in the successful native fixtures. [Parity evidence](2026-10-21-compose-ci-parity-source-proof.json). Corrected complete images and exact-head CI remain required before integration; no signed release or host update is claimed here.

# V3 compatibility source review — 21 October 2026

Scope: operator review of the runtime corrections through `9ede461d`, together
with the preserved native controls. This is not an independent automated review,
signed artifact acceptance or physical cold-login acceptance.

The Claude advisory jobs `39489708654` and `39522611465` have green job
conclusions, but their actual execution results have `is_error:true`, one turn,
empty model usage and `REVIEW_OUTCOME=failure`. No automated code-review
completion or findings are accepted from either run. The logs do not establish
the underlying provider error; do not infer that the code passed review or that
a specific credential is expired. The existing nonblocking workflow and its
explicit warning are retained.

## Reviewed boundaries

| Area | Source reviewed and conclusion |
| --- | --- |
| Pristine transaction | `build_files/plasma_stable/runtime_state.py` records an empty identity and empty mutable input before package commands. Metadata, native creators, account authorities and catalogue bytes are checked before its cleanup. The input identity cannot be restored by a later standalone invocation. Existing identity, mount, link, unknown-state and authority refusals remain intact. |
| Native ARM input | `prepare_arm_compose_base.py` verifies its different empty vendor scaffolds before canonicalization. Only the two exact known writable NSS bodies receive root-only write permission, preserving names/IDs/bytes. The one writable native rpm-state creator has an exact full-file/owner/mode/rule pin; the shared x86 reader stays strict. |
| Vendor normalization | `finalize_canary_base.py` unlinks only the exact proven SELinux compatibility alias, preserving the configured policy store and matching boot policy. `finalize_root_home.py` protects unknown/credential entries. `finalize_dbus_state.py` preserves pristine identity and native runtime recreation. The general image and identity gates are unchanged. |
| Experimental base | `prepare_plasma_canary_base.py` constructs the shared transaction before every package mutation. Native command failures propagate. Only the optional kcm-fcitx5 module may be explicitly removed without autoremove. Private temporary DNF logs prevent rotated build logs entering persistent state. Kernel exclusion preserves actual stock vmlinuz bytes and avoids unrelated same-NVR reinstall/dracut state; blind rpm-state erasure is removed. |
| Plasma input | Separate exact6.8.1 source/prepared/backend pins and narrow seam range preserve vendor authentication, null-geometry, shutdown and SIGHUP changes. All12 seam files compare unchanged. Native lock positive/broken/restored controls and compiled package checks are distinct from physical greeter acceptance. |
| Authority and delivery | Package work is confined to unbooted build containers; the actual installed-host negative refuses before mutation. No host kernel layering, forced hardware ID, EC write, signature/policy bypass or new canary publish permission is introduced. |

No new blocking source defect was found in this reviewed scope. Native evidence
already exposed and corrected the original generated identity, rotated DNF log
and unrelated kernel-state cases; those nonzero controls remain preserved.

## Evidence and limits

- Final functional head9ede passes the maintained repository gate:2850 Python
  unittest cases across206 summaries, plus its other native/maintained checks.
- The complete local production image6ea58661 passes and its raw payload
  readback verifies the new greeter/RPM/source receipt, managed PAM/helper/unit
  hashes, enforcing SELinux, empty identity/state and absent build SDK/cache.
- The actual workflow-derived native experimental base11eef61a passes; its
  stock base layer prefix and vmlinuz bytes independently match the original.
  Seven command/failure controls and seven workflow controls pass.
- Source backup addenda restore the exact head/tree independently and full
  fsck succeeds. These are source backups, not installed rollback proof.

Exact final-head CI and one frozen signed artifact boot/promotion cycle remain
required. New6.8.1 physical automatic fingerprint and separate no-touch password
fallback, BIOS charge-limit plateau, suspend/resume and wider hardware acceptance
remain separate. The historical Qt screenRemoved crash and unsupported SMOCF05
rotation are unresolved; this review does not claim their repair.

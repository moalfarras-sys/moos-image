# Oracle repository integration — 2026-10-06

The owner requested integration of local and remote branches and worktrees,
followed by a signed system update and reboot. Source integration and delivery
are separate: the installed A1 still runs signed ARM `.710`, source `66653f76`,
while the station's reserved release at `97f4f121` is proving its artifacts.
Do not advance main until that release succeeds or fails.

## Reviewed source

`integrate/all-owner-20261006` starts from `97f4f121` and merges the exact
Remote v56 head `3b4c6d53` (#214), followed by the reviewed shared PIN-lockout
batch `233d6038` (#215). Login and PIN changes now share the persisted
five-attempt/two-minute lockout; HTTP 423 reports an active lockout. This
integration retains that branch's product source exactly. Its only additional configuration change
preserves the owner's local `Bash(git commit *)` and `Bash(git stash *)` allow
rules. All 22 pinned permission guards and the four approved MCP servers pass
the maintained configuration gate; no credential is introduced.

The A1's full check exposed a recorder race in
`tests/test_windows_installer_folder.py`: its background stub created the
result before writing JSON, and the parent observed an empty file. The stub
now publishes a closed record with `os.replace`. The two-second bound and
exact read-only, per-launch and cancellation assertions remain intact.

The three older local branch tips were reviewed individually and reconciled
with ancestry-only merges. Their old bytes must not replace maintained source:

| Historical branch | Reviewed successor or disposition |
| --- | --- |
| `feat/remote-oracle-experience-20260912` | Hardware-adapt completion `4e7c5bb6` is superseded by `4dd832a5` and the maintained bounded ARM proof. Fast-check cleanup `7ddfa4f0` was rewritten as `2f47ad92`. `47d73ada` is an obsolete alternative keyboard implementation: current Remote preserves physical positions with viewer characters and handles layout/lock state through its helper, including the later password-case correction `b99c0027`. Its Baloo fixes are maintained in `62522674`; isolated fixture changes also exist in the current gates. |
| `fix/a1-live-review-20260918` | ARM eligibility `543978d3` was rewritten as `5b161575` (#132); icons/search `8108caf2` as `7f7dcf01`. Phantom-install test isolation `26249bfe` is patch-equivalent to `e793d65f`. The old theme revision 68 is superseded by the current reviewed theme generation. |
| `oracle/stability-performance-20260907` | Index-policy implementation `b14695ac` was rewritten as `9e07b94c`, integrated through `66e2f7a1`, and corrected by `62522674`. Current source and its gates are retained. |

Before integration, the primary checkout, two standalone development clones,
and the Oracle documentation worktree were inventoried. Only the two allow
rules above were uncommitted. The documentation worktree's `317b9acb` is already
an ancestor of main. Backups include a verified all-refs Git bundle and binary
staged/unstaged patches under the owner's private integration state directory.

## Preserved experimental work

The translucent-dialog stash remains under its explicit archive tag
`archive/stash/translucent-dialogs-20260924`; it is unfinished visual work,
not an accepted theme update. The older Baloo stash is retained under
`archive/stash/baloo-index-policy-20260917`; its effective fixes already ship.
The standalone development clone's native-touch prototype remains backed up
and stashed. None of these prototypes is claimed to be active product code.
No stash, branch history, unrelated worktree or owner file is deleted.

## Hardware assessment

The A1 has two ARM OCPUs, 12 GB nominal RAM and a 200 GB disk. At the initial
integration measurement, 5.2 GiB RAM and 109 GiB disk were available; memory
pressure was zero, while CPU pressure was measurable. This identifies CPU
capacity as the first upgrade to evaluate for simultaneous desktop streaming,
an editor and media processing.

Workload estimates, not measured performance guarantees: 4 OCPUs / 24 GB is
a balanced target for this cloud workstation; 8 OCPUs / 32 GB provides more
headroom for parallel builds and video processing. The current 2 / 12 profile
remains usable with serialized background work and the documented service
limits. No paid cloud resize is performed by this repository integration.

Oracle's current published A1 Always Free allowance is equivalent to 2 OCPUs
and 12 GB, with 200 GB combined block storage; larger allocations may incur
charges. See [Oracle's resource documentation](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).
The existing media/code/file services, their limits and acceptance boundaries
are documented in [Oracle cloud workstation](ORACLE_CLOUD_WORKSTATION.md).

## Acceptance boundary

Run `just check` on the final integration tree and retain CI results for that
head. Existing #214/#215 image checks alone do not prove their eventual signed
release. The additional Oracle changes target the station's #215 integration
branch so the reviewed history and fixture fix can join its single final batch.
The station owns that signed cycle; the Oracle agent follows its proven ARM
release without dispatching a duplicate. Main must preserve the integrated ancestry; delivery then follows
`RELEASE.md`: exact signed candidates, successful artifact boots and promotion,
the host update authority, and post-reboot checks. Record final run IDs and the
actual booted digest only after they exist. Phone/WAN endurance, phone photo
background upload and an off-host backup of originals remain separate open
acceptance work.

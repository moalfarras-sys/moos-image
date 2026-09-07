# x86 release repair — Opus handoff

Task: restore the three x86 candidate builds from `55737753`, on
`gpt/fix-x86-build-20260907`. No merge, promotion or host deployment is part of
this task. Build/signature proof is separate from the remaining artifact boot
and hardware release gates.

## Root cause and isolation

Full logs were downloaded and inspected, including all three edition jobs:

| Run | Source | Result |
| --- | --- | --- |
| [x86 767](https://github.com/moalfarras-sys/moos-image/actions/runs/34127086466) | `b1586cef` | All three build, push, sign and verify successfully |
| [x86 768](https://github.com/moalfarras-sys/moos-image/actions/runs/34132046901) | `1c314747` | Generic fails on HTTP 504; cloud/NVIDIA succeed; only docs changed |
| [x86 769](https://github.com/moalfarras-sys/moos-image/actions/runs/34136263576) | `55737753` | All three fail at `install -d -m 0755 /usr/local/sbin`, exit 1 |
| [ARM 316](https://github.com/moalfarras-sys/moos-image/actions/runs/34136263591) | `55737753` | Native build, signed container, QCOW2 and promotion succeed |

The shared error in run 769 is `install: cannot create directory '/usr/local':
File exists`. The only x86 executable change since green run 767 is that new
unconditional directory repair. The ARM NFS omission cannot explain it.

Read-only inspection of the actual x86 base
`ghcr.io/ublue-os/kinoite-main@sha256:99e23a9207c1b81ac2bbaf9f1b5420248940c9c70c2c9f81a5072e20c00aeefa`
(amd64 image ID `e52bd5475fcc`) confirms `/usr/local -> ../var/usrlocal` and an
absent `/var/usrlocal`. By contrast, ARM's base has a real `/usr/local` directory.
Copying ARM's fix into x86 attempted to traverse a dangling symlink. Creating
its target during compose would also put machine-local state into the image.

The x86 base already ships the two necessary boot-time rules:

- `rpm-ostree-0-integration-opt-usrlocal.conf`: `d /var/usrlocal 0755 root root -`
- `rpm-ostree-0-integration.conf`: `d /usr/local/sbin 0755 root root -`

## Fix and regression

`build.sh` distinguishes the filesystem layout. For the Atomic symlink, it
preserves the link and checks both existing tmpfiles rules; unexpected targets
and missing rules fail the build. For an actual immutable directory, it retains
the build-time creation and directory check. `build-arm.sh` is unchanged,
including both the NFS/initrd omission and `/usr/local/sbin` repair.

`tests/test_usr_local_layout.py` executes the shipping shell block against
disposable filesystems. It covers a dangling symlink, existing local content,
real directories on both build paths, unexpected symlink targets and absent
boot-time rules. It also executes real `systemd-tmpfiles --root` to prove sbin
appears at boot while `/var` remains empty during compose. Fixture ownership is
left with the invoking user so the regression needs no root privileges.

The original block fails the dangling-link and local-content tests; the fixed
block passes all seven cases. The new gate is wired into `just check` and both
architecture workflows: 123 gate scripts, covering every workflow gate.
An additional rootless user-namespace probe copied the actual base's symlink
and two rules into an empty fixture: original block exit 1, fixed block exit 0,
empty `/var` at compose time, then root-owned `sbin` mode 0755 after normal
tmpfiles configuration discovery. Evidence: `base-reproduction.log`.

## Current validation checkpoint

- Baseline `just check`: passed on the host.
- Fixed regression: 7/7 passed on the host; final `just check` passed all 123
  gate scripts. Existing runtime skips: x264 encoder unavailable and three
  standalone QML motion cases lacking their harness runtime. No gate was removed.
- Native local ARM build: passed as rootless podman, image tag
  `localhost/moos-arm:x86-release-validation`, image ID
  `2f3abab5cb6adcef9a1388a458eb05b1b37aa9103a6a50fd8315af4fbded6173`.
  Finished-byte inspection confirms real root-owned `/usr/local/sbin` mode
  0755, and neither `nfs` nor `99-nfs-start-rpc.sh` in the deployed initramfs
  (103,501,091 bytes, kernel `7.1.13-200.fc44.aarch64`). `bootc` lint exits 0
  with 11 checks passed, one skipped and two warnings about package-generated
  runtime/var content; this is not a claim of a warning-free image.
- Branch x86 build/push/sign/verify: pending; dispatch `build.yml` on this
  branch after source validation. It publishes only run/SHA-bound candidate
  tags and does not move production tags.
- Signed branch ARM candidate/boot proof: pending.

Full downloaded logs and local validation logs are retained outside the repo at
`/var/home/moos/x86-release-20260907/`; `logs-sha256.txt` records downloaded log
hashes. No signing secret was read; signing uses the existing Actions secret
and verification uses the public key enforced by the OS.

Before handoff, replace pending entries with actual run IDs, source commit,
per-edition digests, signing/verification results and local build output.
Do not treat this repair as proof of NVIDIA hardware boot, ISO installation,
rollback or promotion eligibility; those existing release gates remain open.

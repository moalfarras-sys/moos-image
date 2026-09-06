# Oracle MoOS storage and desktop maintenance — 2026-09-05

## Verified live

The owner authorized expansion, reboot, health checks and application updates.
Oracle Cloud Shell enumerated the single home/subscribed region (Frankfurt), all
three availability domains and the root compartment. There was one running A1
instance and one 50 GB boot volume, with no data volumes or existing backups.
The attachment was matched to the running MoOS instance before changing it.

A full backup `moos-before-resize-20260905` reached AVAILABLE before the original
boot volume was expanded to 200 GB, retaining 10 VPU/GB. No cloud resources were
deleted. This is the 200 GB Always Free boot/block allotment; the one backup uses
one of the separate five backup slots, not space in MoOS's disk. Retained for
recovery; deleting it would not increase local free space.
Source: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

Host operations: SCSI rescan, `growpart /dev/sda 3`, then
`btrfs filesystem resize max /var`. EFI and /boot partitions, all starts and UUIDs
were preserved. The machine rebooted at approximately 17:16 UTC. The independent
postboot report at `/var/lib/moos-storage-maintenance/postboot-result.json`
returned `passed: true`, including changed boot ID, 200 GiB disk, expanded
198.5 GiB filesystem, unchanged OS deployment, write/read probe and active
network/desktop/Remote services. About 155–156 GiB remains available.
A read-only Btrfs scrub completed in 7m13s: 43.48 GiB checked, no errors.
The one-shot verification timer/service was removed after success; reports remain.

## Maintenance applied

- Restored the exact legacy keyboard profile from `de,ara` to `de,us,ara`;
  preserved the previous file in the local maintenance directory. Live KWin
  readback confirms all three languages. KConfig's change notification is needed;
  generic KWin reconfigure does not reload its keyboard watcher.
- Installed the missing ARM AppStream service locally in `/etc/systemd/system`,
  enabled its existing delayed timer, and verified the actual service exited 0.
  The corresponding image fix and gate are in commit d65b723d. Remove the local
  service override once a signed deployment ships that same service under /usr.
- System and user Flatpak updates completed (Chrome, Chromium and associated
  runtime updates). A subsequent system update reported nothing to update.
- Updated user-installed tools: npm 12.0.2, Corepack 0.36.0, Hermes Agent 0.21.0,
  OpenCode 1.18.29. Node 24.20.0 satisfies declared engine requirements;
  version commands executed successfully. Hermes's separate git-ahead notice
  was not treated as permission to replace the package's pinned runtime with HEAD.
- The image-update resolver reports current at signed digest
  `sha256:c41e5fdadc5a6beab5b981f606b86ef5ff35ca15b6de83e2790a67ca752f2ccc`.
  No OS rebase or second reboot was needed.
- Live `moos-selfcheck`: 48 passed, no failures; `post-update-check.sh`: 49 passed,
  zero failed. The theme migration tests ran with real host KF6: 14 passed.

## Remote Arabic repair

The already-running portal cached `ara=1` from the old `de,ara` ring. Inserting
US made group 1 English, so Arabic positional strokes became Latin gibberish.
`select_group()` now refreshes live layouts before resolving a target or taking
its current-group fast path; it fails closed if the compositor cannot be queried.
The saved home language follows its code across ring reordering.

The Python helper was installed into the active local v38 deployment with its
previous helper retained, and only `mo-remote-personal.service` was restarted.
The primary service returned portal readiness and retained its existing account
configuration. This is a local fix, not a newly published signed OS image.

Five executable regressions cover insertion, external switching, home remapping,
missing Arabic and unavailable compositor. They run through the existing portal
ordering gate. Real authenticated loopback Remote input into a dedicated focused
GTK entry read back `مرحبا بالعالم`; pointer click and Backspace also succeeded.
A second test changed `de,ara` ↔ `de,us,ara` between committed Arabic runs with
one connection alive and read back `مرحبا بالعالم كيف الحال العربية` exactly.
Temporary test services were stopped; the primary Remote service remains active.

## Limits and follow-up

These checks do not prove every application function or every phone keyboard.
The physical mobile client still needs the owner's confirmation. A mixed
Arabic/Latin stress run lost an initial Latin character; an emoji-containing
probe did not insert its text. Those paths remain open and were not represented
as passed by the successful Arabic-only native-path regression.
Early-boot NFS/rpcbind messages and an attempted tmpfiles mkdir at read-only
`/usr/local/sbin` were observed; no corresponding failed services or kernel I/O
errors remained. No invasive boot or mount changes were made to hide them.
No complete new image build or registry publication was performed in this pass.

Local raw reports and reversible maintenance files are under
`~/oracle-storage-maintenance` and `/var/lib/moos-storage-maintenance`.
Cloud inventory/backup/resize JSON remains in the owner's Cloud Shell home.
No tokens, PINs, account OCIDs or private browser screenshots are committed.

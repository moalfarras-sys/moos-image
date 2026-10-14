# Proposed Store corrections — review artifacts

These patches make the [measured review](../STORE_20261014_AR.md) reproducible
without editing files reserved by the active station agent. They are not built,
installed or automatically applied. Remove each artifact when its reviewed
correction is integrated into the station's authoritative source; Git preserves
this evidence afterward.

| Artifact | Exact SHA-256 | Reviewed scope |
| --- | --- | --- |
| `install-safety.patch` | `2d525b2faf2086adbab1ad865b47ad6bd3cdd0be1065a6004033cac4aef20390` | `93a9019e` backend/vendor module; five old/fixed file-preservation/recovery controls |
| `android-inventory.patch` | `da4bfc77f075e5d7211670fc9085a44a99f33ac8a72b091eacd126558bc8417b` | `93a9019e` index and ARM fixture constraints; new APK receipt controls |
| `ui-contracts-and-layout.patch` | `25cac247a5c842aa54b8d161acdf6ea2eba4a3068a1e74ec15af2f7786d635d6` | Captured 20-file `store/ui-split` snapshot, with pending main.qml; six UI files |

Read-only `git apply --check` succeeded for both backend/index artifacts on the
native station's working branch and the UI artifact on its active split
worktree during handoff. This does not authorize overwriting later edits:
compare the new tip, review overlap, then integrate through normal ownership.
Register the new Android test in maintained gates. UI changes require the
existing THEME_REV/cache fingerprint migration and real interaction review.
Run `just check` on the complete resulting tree, followed by the image/boot
release contract. The private patch suites do not replace those gates.

The identical handoff, receipts and two reviewed frames are available on the
owner's NVIDIA machine in `~/.cache/moos-store-oracle-review-20261014/`.
`HANDOFF_AR.md` explains each correction. No owner application or repository
file was changed by the handoff.

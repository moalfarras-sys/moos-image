# Oracle deep storage maintenance — 2026-11-10

The owner's approved cache/archive retirement and subsequent explicit request
to remove unused backups increase observed available space from 56.97 GiB to
about 92 GiB while the newly published signed ARM917 update is being staged.
This is live workstation maintenance, not a new source/image qualification.

The metadata inventory covers 1,277,602 files, 156,958 directories and 54,589
non-followed links; managed container layers are audited separately through
Podman. Eleven independent repositories pass full Git integrity checks. Five
personal images are healthy. Credentials, private source and photo/database
data remain intact.

Exact retirements include the 1011/1127 ISO payloads, redundant Git bundles,
unused old native binaries/install archives, duplicate AABs and two obsolete
image build chains plus three old service images. Every other tagged image and
every live container ancestor is independently protected. The1127 hash/signature
and historical release proofs remain; there is no new1133 public ISO claim.

Three legacy source archives retain all non-object file bytes and metadata in
about228 MiB. Their Git objects are verified in the canonical repository, with
three old branch tips and thirteen otherwise unreachable objects rescued and
protected under archive refs. These compact snapshots depend on that canonical
object store; they are not standalone full Git backups. Native full fsck passes.

Baloo's native LMDB compact copy preserves all twelve logical tables, flags and
entry counts. The index falls from3.37 GiB to about136 MiB at publication; native
Arabic create/search/atomic-save/search/delete acceptance passes. Runtime-only
indexer/runner masks are retired and the original unit activity is restored.

Official Claude2.1.322 and compatible Sharp0.35.5 are verified. Native image
processing passes in both Alhasakah root tool environments. Code's qualified
Codex pin remains26.1007.21434. The stable updater's Flutter/Gradle prerelease
downgrades are retained as a refusal and corrected with the official extension
manager; Roo's marketplace absence remains an exception. No editor session is
terminated to manufacture compatibility.

Both web lock audits have zero high/critical findings, with seven moderate.
Compatible Android dependency repairs remove the critical finding and reduce
high findings from15 to7; twelve moderate/eight low remain. No forced framework
downgrade is applied. Native typecheck/lint pass and all22 existing tests pass
on an unchanged-command retry; the first one-test hook timeout is preserved.
No website, Play, APK or signed OS source release is inferred from these checks.

A new encrypted configuration/database backup and canonical user/system app
update checks pass. The owner now explicitly authorizes reboot. Signed917
staging and its new-boot/rollback/service readbacks are recorded separately;
the pre-reboot signed911 boot alone is not acceptance of917.

Private evidence and the Arabic owner report:
`~/.local/state/moos-maintenance/20261110-storage-explanation-110222/`.
Earlier inventory/approval receipts remain in `20261110-deep-clean-094545/`.
SMART on the cloud block volume and full app/account/hardware journeys remain
unavailable or unqualified; historical diagnostic failures are not erased.

# Native login frontend integration

The login settings catalogue also registers the existing `org.moos.ui2.greeter`
scene. Upstream's fixed list otherwise omits the image's own default plugin and
renders an empty wallpaper-type field. `moos-login-scene.patch` adds only that
owned ID, preserving the vendor list and all authentication/executor behavior.
The native appearance export also includes the effective `General.ColorScheme`
and `Icons.Theme` selectors: KDE can inherit these from `kdedefaults`, while the
original export reads only the first partial `kdeglobals` file. The remaining
raw settings and seven-file export stay with the vendor implementation. A
private snapshot-storage failure refuses before the existing KAuth request.
The frontend gives the existing save/sync/reset requests a finite five-minute
timeout: the native default25s expired during the physical owner's administrator
prompt. The same actions, helper, arguments and authorization remain; the sync
terminal log records only the numeric job result, including failure/cancellation.
The scene's native `config.qml` exposes the18 installed appearances through the
existing KDE property/default bindings and KAuth save. Opening it changes no
setting; custom owner image values remain intact. The rebuilt package release
is `1.2.moos1`, and final image verification checks the KCM binary against both
its receipt and its RPM payload alongside the greeter.

The reviewed Plasma Login Manager 6.8.1 starts PAM only after submitting the
form. A reader match in `fprintd-verify` or the lock screen does not change that.
This additive frontend correction submits the existing empty-response login
request once when an enrolled, selected local account becomes visible. It never
accepts a fingerprint itself or invents an authentication result.

## Source and delivery boundary

`sources.json` accepts one vendor source NVR and x86_64 architecture. The SDK
downloads the exact SRPM, verifies its SHA256 and trusted OpenPGP signature,
retains the vendor spec, flags and patches, then adds `automatic-fingerprint.patch`
and `moos-login-scene.patch`. Fourteen prepared frontend files have exact hashes:
the original eleven, the scene registry, native export caller and snapshot header.
The 6.8.1 review retains the vendor placeholder-screen guard and native shutdown/SIGHUP fixes. The helper/daemon aggregate is compared with 6.8.1 vendor inputs, not the historical 6.8.0 aggregate. All files in `src/auth`, `src/helper`
and `src/daemon` must remain byte-identical to the reviewed vendor source.
The two rebuilt runtime RPMs are installed before the authoritative MoOS overlay;
the SDK and test tools never enter the finished image. The final check compares
both the greeter and KCM binaries with their RPM database payloads and build receipt.

This is a functional native package correction, not an authentication-bearing
theme seam or a replacement for KDE. A changed upstream source, architecture,
signer, backend, installed package origin or payload stops the build for review.
ARM retains its independently qualified native provider; cloud does not install
this desktop frontend correction. The host stays on its signed deployment until
the ordinary candidate/boot/promotion/update path completes.

## Availability and fallback

An optional root display-manager pre-start helper publishes only account names
with existing enrollment. It reads `GetDevices` and `ListEnrolledFingers`, never
templates, `Claim` or `VerifyStart`. Collection is bounded and unavailable readers
keep the ordinary password UI. Metadata is root-controlled, atomically replaced,
size-limited and tied to the current boot. Enrollment added after collection
requires the next display-manager start; no idle enrollment polling is added.

Only the real greeter enables this metadata. The settings module and mock/test
backend do not consume the owner's enrollment. Across screens, one shared claim
allows one automatic attempt per selected enrolled account. A typed password,
hidden form, disconnected daemon or ongoing authentication prevents that request.
The selected account's native form is revealed on the first screen. The native
daemon and PAM remain the sole authentication and session authorities.

The greeter-only PAM derivative preserves the generated authselect stack except
for swapping adjacent sufficient `pam_unix` and `pam_fprintd` alternatives and
bounding the reader to one try/eight seconds. A supplied valid password therefore
finishes before the reader. An empty response can reach fingerprint verification;
failure restores the existing password form without an automatic retry loop.
This is a bounded initial scan, not simultaneous password/fingerprint PAM or an
always-on reader. Custom policies, lockout/remote/U2F stacks and custom reader
options are refused rather than silently rewritten. Global authselect stacks and
vendor account/password/session rules stay intact. `--check` is read-only.

## Evidence required

`native-proof.sh` runs the real C++ metadata reader, including FIFO/symlink/owner/
permissions/stale-boot negatives, actual Qt request and QQuickView reveal probes
with disconnected-path and original screen-lookup failures, and private native
PAM control-engine tests. Package preflight tests refuse drift before any DNF
mutation. None of these synthetic probes qualifies a physical fingerprint match,
password fallback, cold login or a signed image. Those need separate receipts.
The real KConfig snapshot probe preserves the original inherited-selector
omission, tests inherited and explicit owner selectors, verifies palette/font/
unknown input preservation and refuses a non-directory storage destination.
Both executed old-omission and fixed-snapshot markers are required; an exit0
from stale copied build inputs is not acceptance.
It also executes the real KAuth Action default and finite-timeout API for all
three appearance operations. This is not a grant or a live sync result: the
actual KCM request must still complete through its installed helper and record
its terminal outcome. Preserve the original physical25s NoReply failure.

The first live profile exposed a QQuickView `window.screen` lookup error that the
mock greeter could not reach; the attached `Screen.name` correction has a native
old/fixed regression probe. The initial ambiguous fallback was reported to request the reader again. After
correction, native no-arrow match and a distinct no-touch timeout/password-only
attempt pass with owner confirmation and actual PAM grantors; cold login and
signed feature delivery remain separate. Logs record only empty-response/password route,
never a credential or its length. The historical QtQuick screen-removal crash
is a separate unresolved defect; this patch is not its repair.

To retire this correction, qualify an upstream implementation against the same
native and physical controls, remove the package stage/receipt/optional activation
together, and migrate only exact known managed PAM bytes. Do not widen source
pins, edit a host RPM database or keep a `/run` review override as release delivery.

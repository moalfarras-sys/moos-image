# MoOS Community — مجتمع MoOS

Native, Arabic-first support conversations on Oracle, with public suggestions
only by the author's explicit choice. Only the original suggestion text and
display name become public; replies and every image remain author/team private.
This component is independently prepared on the owner milestone branch. Source
acceptance does not mean it is shipped in an OS image or installed on a station.

## Run and verify

Python 3.14; production dependencies are fully hash-pinned. Client Qt comes from
the MoOS native PySide6/Kirigami/UI2 runtime, not a separately layered desktop.

```sh
python3 -m venv ~/.local/share/moos-community/venv
~/.local/share/moos-community/venv/bin/pip install --require-hashes -r community/requirements.lock
# Development API lane, using requirements-test.lock in a private test venv:
COMMUNITY_PYTHON=/path/to/test-venv/bin/python just community-check
# Native MoOS Qt lane, with the API dependencies available to that interpreter:
just community-native-check
python3 -m community.client --service-url https://SERVICE-HOST:10000
```

Native tests require private HOME/XDG/session bus and offscreen software Qt.
Missing Qt fails an explicit native check. CI runs the same maintained API lane;
its backend success never substitutes for native rendered/input acceptance.

## Oracle deployment contract

Use a dedicated loopback backend (`127.0.0.1:8939`) and a separately configured
TLS proxy endpoint. Do not reset an existing Tailscale Serve configuration or
reuse occupied 443/8443/8444/8445 listeners. The current Oracle access is one
verified Tailscale SSH session. Its existing services and owner data stay intact.

The server requires the connecting proxy's full kernel socket tuple and reviewed
UID before trusting X-Forwarded-For. Missing identity fails closed. Tailscale
1.102.5 replaces that header with the actual transport source; neither loopback
nor a client-supplied header proves this. `proxy.py` is separate from the existing
Mo AI local-UID guard. Confirm UID and header replacement through the actual
proxy, including a forged-header negative control, before public registration.

```sh
# Private, owner-only directory. The operator token is never printed.
python -m community.run --data PRIVATE_DATA operator-session --output PRIVATE_DATA/operator.json
python -m community.run --data PRIVATE_DATA serve \
  --public-origin https://SERVICE-HOST:10000 --proxy-uid 0 --registration-open
# Native team client on Oracle; 0600 operator session expires after one hour:
python3 -m community.client --service-url https://SERVICE-HOST:10000 \
  --operator-session PRIVATE_DATA/operator.json
```

Never put operator sessions, databases, pictures or passwords in Git, URLs,
service argv/environment or public logs. The public service has no OS action
route, cloud key, screenshot capture, automatic log upload or browser cookie.
Passwords use Argon2id; opaque tokens are hashed in SQLite, expire after seven
days and revoke on logout/ban. Each account retains at most five sessions.
Registration is closed unless explicitly opened with an existing maintainer.
Per-client/per-account rate limits and bounded authentication/image workers
prevent treating registration as unlimited work. Process core dumps are disabled
with PR_SET_DUMPABLE, not just a zero RLIMIT_CORE on a piped collector.

## Data and receipts

- Account-private 0700 directories and 0600, owned, regular single-link SQLite.
  Never mount the owner's Home Assistant database or system bus here.
- Every POST has a stable UUID retry key; the server commits receipt/content
  together and refuses changed payloads reusing a key. A socket timeout is not a
  delivery receipt. Retrying cannot duplicate a accepted report/message/image.
- An accepted text with a pending image remains visibly pending. Report/reply
  image handoff is one local SQLite transaction and survives restart.
- Unsent report/reply composers persist per account and service origin; passwords
  and tokens do not. Sign-out removes private decoded image caches and ignores
  late work from the previous account. A separate selection generation prevents
  the old conversation replacing the newly selected one.
- Upload limits: 2 MiB, 4 million pixels, still PNG/JPEG/WebP, max 1920 edge after
  orientation. Decode after authorization. Strip EXIF/GPS/text/ICC; flatten alpha
  over white so hidden RGB cannot become visible. Server quota 64 MiB/account;
  client cache max 32 MiB. Bodies max 2 MiB+64 KiB, reads bounded to 30 seconds.
- Explicit conversation deletion removes that report/messages/images/notifications;
  a local draft discard only removes the local retry copy. The UI distinguishes
  these and asks for the destructive action the member chooses.
- Maintainers triage/respond/moderate; members cannot select a privileged role.
  Public suggestions never expose private attachment routes/content to visitors.

## A fix released is not a fix installed

`POST /v1/releases` accepts only the current official edition `:latest` digest,
matching OCI version and successful cosign verification against the OS release
public key. It reads promotion again after signature verification; a changed
promotion fails closed. The server never imports an arbitrary repository/key or
ignores transparency checks. Only that verified receipt can transition a report
to `released`. The member sees edition/version and an in-app notification; this
is distinct from booted deployment readback on their own computer.

## Design handoff and remaining delivery

Uses the existing `org.moos.ui` Locale/Tokens/Button, Kirigami theme roles, plain
text and bounded native layouts. Quiet text is text ink at 0.78 alpha. No parallel
theme, foreign identity, decorative constant animation or automatic screenshot.
Inputs have Arabic/English accessible names and explicit public-sharing consent.
Native image previews are reencoded rasters in a private cache, never arbitrary
selected file URLs. Source native frames belong in the owner's private journey
gallery or a sanitized CI artifact, not Git.

Before OS integration: add the native launcher/AppStream/route to all editions,
ship this exact source and maintained dependencies, register actual QML launch
and interaction checks, then run the standard signed candidate and boot proofs.
No source branch, local override or merely listening API closes that acceptance.
Public custom DNS, password recovery, audited team identity onboarding, OS-native
notification preference, retention/support terms and broad hardware/accessibility
qualification remain explicit product decisions/evidence in P6.9.

# Remote before account login — design and implementation contract

This extends **MoOS UI — Liquid Glass**, using the existing Graphite/Tidal
controller components. Its source implementation is under review, not evidence of delivery.
The execution backlog and release acceptance remain P2.17 in
[`DEVELOPMENT_PLAN.md`](../../docs/DEVELOPMENT_PLAN.md).

## Purpose and hierarchy

The owner opens the same private Remote address after a reboot, authenticates
Remote, chooses their account in the actual MoOS greeter, and types the account
password. Upstream PAM and greeter authentication remain authoritative.

1. The connection indicator states whether a picture and input are available.
2. “تسجيل الدخول إلى MoOS” / “Sign in to MoOS” identifies the greeter profile.
3. A short instruction explains account selection, password entry and Enter.
4. The password keyboard is the primary action. Account passwords are transient
   native input: masked, cleared on blur/close/disconnect, never a saved draft.
5. Pointer mode, picture settings and connection controls remain available.

Files, clipboard, sound, desktop commands, power and trusted-device inventory
are unavailable before account login. The backend refuses these endpoints;
hiding a control alone is insufficient.

## Existing design tokens

Use the controller's existing CSS custom properties, including the light
variant, without duplicating a palette in a component.

| Role | Existing dark token value |
| --- | --- |
| Canvas | `#14191c` |
| Surface | `#1d2529` |
| Primary ink | `#e8f1ef` |
| Secondary ink | `#9cafac` |
| Tidal accent | `#4ed7c8` |
| Secondary accent | `#78afff` |

Retain the Arabic-capable font stack, the existing spacing/radius scale,
logical layout properties and focus treatment. The native greeter keeps the
shared session design; no password/authentication QML is forked. No additional
continuous animation or blur is introduced. Reduced motion remains effective.

## Profile and failure states

| State | Behaviour |
| --- | --- |
| Remote PIN required | Existing accessible keypad; device trust is explicit |
| PIN refused/locked out | Existing bounded refusal and retry/lockout UI |
| Greeter connected | Profile instruction, masked live-only keyboard |
| Keyboard unavailable | Password action disabled; no clipboard/fallback typing |
| Capture unavailable | Connection state must not imply a decoded picture |
| Ordinary PAM refusal | Native greeter retains its own password error |
| Account/session changes | Retire the stream and re-authenticate the new profile |
| Logout/cold boot | Greeter credentials remain separate from every account |
| Owner disables feature | No automatic restoration of the greeter service |

Browser storage is scoped by the backend's opaque credential scope. Greeter
credentials never consume legacy desktop credentials. Legacy desktop migration
occurs only after successful validation by the current account. A refused or
signed-out profile must preserve another account's saved credentials.

## Review and handoff

`controller/tests/browser-input.test.mjs` exercises the shipped bundle in
isolated Chromium contexts: AR/EN portrait and landscape, unavailable desktop
actions, a masked native-only password packet and clearing on keyboard close.
The transport is intercepted; its screenshots are **UI evidence, not native
greeter/password-login evidence**. Existing disconnect/late-paste refusal
controls continue to run.

Native acceptance must separately use a private signed-base guest, synthetic
credentials, real decoded greeter frames, wrong/correct PAM password entry,
session ownership readback, logout return and repeated cold boot. Release
evidence must identify the source SHA and signed image, and production opt-in
must be administrator-controlled, off by default and revocable.

Implementation owners: `PreLoginRequestPolicy` owns the closed HTTP surface;
`StreamSession`/Linux input own transient keyboard delivery; the EIS device's
actual XKB map owns password character mapping; `App`/`api` own credential
scoping; `RemoteScreen` and existing dock/settings components own presentation.
Do not add a second controller, public listener or parallel authentication path.

The native control centre adds one Liquid Glass card, “الدخول بعد إعادة التشغيل”
/ “Sign in after reboot”, beside existing Remote controls. Enabling needs an
active Remote account and private HTTPS address, then a masked six-digit PIN
and confirmation. Native polkit explains the administrator action in AR/EN.
The greeter PIN and every account credential remain independent. Stop revokes
greeter enrollment/trust as well as disabling the account service; enabling
Remote again leaves the greeter off. Busy/cancel/refusal states never claim a
successful change, and slow commands remain off GTK’s rendering thread.

Native source review on a 640×507 and 1440×900 private desktop verifies scrolling,
masked PIN entries, mismatch refusal, matched confirmation and clearing on close.
The shared GTK secondary-ink correction overrides inherited dimming; all sixteen
schemes pass effective-ink contrast, and the old opacity fails every scheme.
These screenshots use a private fixture, not the owner’s desktop or credentials.

Final source checks and the full local image `13ce614c0461` pass; 31 changed
overlay/portal/controller files match the built bytes. Read-only validation of
the owner's existing account route passes actual Tailscale Serve JSON and a
certificate-verified HTTPS status request. It does not enroll the greeter; real
production greeter enrollment, phone endurance and signed hardware acceptance
remain separate P2.17 exit evidence.

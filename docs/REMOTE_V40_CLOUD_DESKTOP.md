# Mo PC Remote v40 — the cloud desktop you actually use

The Oracle A1 has no monitor. Mo PC Remote is not a convenience on that machine, it is the
display, and this pass treats it that way: everything below was measured on the shipped bundle
in a real Chromium, or read off the live agent on the A1 itself.

## What was wrong

### The mouse wheel scrolled backwards in every browser

One controller, two agents, two conventions.

| | convention | why |
| --- | --- | --- |
| `agent-linux/InputInjector.cs` | positive = **down** | the portal's `NotifyPointerAxis` is positive-down, like `wl_pointer`, libinput and `WheelEvent`; it negates separately for the uinput fallback, because evdev `REL_WHEEL` is positive-up |
| `agent/Core/InputInjector.cs` | positive = **up** | it passed the value straight to Win32 `MOUSEEVENTF_WHEEL`, which counts forward, away from the user |

The same packet therefore scrolled opposite ways on the two platforms, and the repair was made
in the shared middle: `RemoteScreen` sent `conn.scroll(dx, -dy)` from its real-mouse path. That
lined Windows up and left every MoOS session scrolling backwards — a second negation on top of a
correct one. Read off the production bundle, one intent, two signs:

```text
finger swipe UP (natural scrolling — "scroll down")     dy = +0.42
wheel turned DOWN (deltaY +100 — also "scroll down")    dy = -6.67
```

The platform difference now lives at the platform boundary: the Windows injector negates for
`MOUSEEVENTF_WHEEL`, the controller forwards the browser's own sign untouched, and the touch path
keeps its separate, user-visible natural-scroll preference.

### A phone in portrait showed 28% of a desktop

A 16:9 desktop fitted to a 9:19.5 phone held upright is 390×219 inside a 390×766 stage — **28.6%**
of it, measured. The rest is black and the desktop's text is about a pixel tall.

Auto deliberately does not turn the picture. That shipped once and the owner reported it as a
fault ("الشاشة عم تعمل عرضي" — a phone held upright showing a sideways desktop), so nothing
rotates behind the user's back and that has not changed. What was missing was not the rotation,
it was the **offer** of it: one glass pill in the dead space, one tap, **28.6% → 90.5%**.

It appears only while the dead space is real (never in landscape, never in desktop mode, never
while typing), withdraws the moment it is accepted, and a dismissal outlives the tab.

- [the offer](evidence/remote-cloud-20260912/phone-portrait-offer-ar.png)
- [one tap later](evidence/remote-cloud-20260912/phone-portrait-filled-ar.png)

### The host's encode ceiling had no reader

`moos-visual-tier` is MoOS's single authority on "what is this machine", and it publishes a
budget whose `remote_encode` key is described in its own source as *"Mo PC Remote software-encode
ceiling: a host with no GPU encodes H.264 on the CPU, so cap resolution × fps to keep interacting
with the desktop from starving the encoder."*

```console
$ cat ~/.local/state/moos-visual-tier.json
  "budget": { ..., "remote_encode": "1280x720@30" }
$ tail ~/.local/share/MoRemotePersonal/log.txt
  Video stream: 1920x1080 (source 1920x1080)
```

`grep -rn remote_encode` found the tool that writes it, two docs and its own test. No consumer.
Meanwhile the portal helper sat at ~15% of one core **of two**, continuously, encoding pixels the
machine had already said it could not spare — on the box whose two cores are also running the
desktop being streamed.

`Core/HostBudget.cs` reads the state file (only the host can), `hello` carries the value, and
Auto respects it **two ways, deliberately separate**:

* the ladder stops at a rung the host can serve, because frame rate belongs to the preset (a
  30 fps host cannot serve Ultra at any width);
* the requested **width** is clamped, because pixels do not. Demoting Sharp to Data saver to fit
  1280 would send 1024 px at quality 52 — a picture *worse* than the host's own limit. Clamping
  keeps Sharp's quality at exactly the pixels the box said it can make.

A preset chosen by hand still wins, and the Display sheet names the limit
([Arabic](evidence/remote-cloud-20260912/display-host-ceiling-ar.png)). A ceiling that acted
invisibly would read as the app being bad at its job.

### A viewer giving up on H.264 took the room down silently

One pipeline feeds every viewer, so H.264 is only safe while every client can decode it. A client
that gives up mid-session therefore drops **the whole room** to JPEG — and until now it did so
with no record of why: the agent logged `Video codec: jpeg` and the reason lived in the browser
and died with the tab. The live log shows this roughly 80 s into session after session. The
reason now travels with the vote and is logged once, on the transition.

This does not claim to fix the decode failure. It makes the next one explain itself.

## Why none of it was caught

`coordinates.test.ts` asserted the inversion by regex. `desktop.test.ts` exercised `DesktopInput`
alone — correct in isolation, wired up backwards. And the one test that runs the real bundle in a
real browser, `browser-input.test.mjs`, **had no runner in the repository**: it was run by hand
and therefore was not run, and its own wire filter omitted `scroll` entirely, so no assertion
could have seen the sign in any case.

* `npm run test:browser` (`scripts/browser-test.mjs`) serves the committed bundle, launches
  Chromium and runs it.
* The browser test now reads the sign that leaves the page for a wheel turn **and** a finger
  swipe and requires them to agree; measures the phone's picture coverage before and after the
  offer; and checks the encode width under Auto, under a manual preset, and with no ceiling
  advertised at all. Every one of those fails on the old code.
* `tests/test_remote_scroll_direction.py` holds the one convention across the controller, the
  portal helper and both injectors.
* `tests/test_moos_visual_tier.py` proves `remote_encode` reaches the agent and the controller,
  and pins the set of budget keys that still have **no** reader so wiring one, or adding another,
  comes back to that test.

## Three ARM units that were never switched on

`system_files/` is copied byte-identical into every edition — that is the identity contract. The
`systemctl enable` lines are not: `build.sh` builds the three x86 editions, `build-arm.sh` builds
aarch64, and nothing compared them. On the A1, image `44.20260912.353`:

```console
$ systemctl is-enabled moos-hardware-adapt.timer moos-visual-tier.service moos-verify-origin.timer
disabled
disabled
disabled
$ mokernel | grep adapted
  ! this machine has not been adapted yet
```

Correct `[Install]` sections, present in the image, wanted by nothing. The edition that needs
them most had none of them: the tier that picks a motion profile for hardware that cannot afford
blur, the pass that plants MoOS into the machine it is installed on, and the audit that the booted
deployment is still the signed MoOS origin.

`build-arm.sh` enables all three. Five more that `build.sh` enables stay off, each for a reason
about ARM rather than an oversight, and `tests/test_arm_unit_enablement.py` requires every one of
those divergences to be written down.

## What is NOT proven here

* **No signed image has been built with these changes yet.** The three ARM enables are verified
  as *source*, against the mechanism proven by their neighbours in the same script
  (`moos-auto-update.timer`, enabled three lines above, does reach the shipped image's
  `usr/etc/systemd/system/timers.target.wants/`). The definitive proof is the next ARM build:
  inspect `usr/etc/systemd/system/graphical.target.wants/` and `timers.target.wants/` in it.
* **The live A1 still has them disabled** at the time of writing; enabling them on the running
  machine was not performed.
* **The H.264 give-up is diagnosed, not fixed.** The reason is now logged; the cause is not known.
* **Screenshots are the rendered controller**, taken against an isolated intercepted transport
  with the repository's existing desktop frame. They prove layout and behaviour, not frame rate,
  cellular speed or a live clipboard round trip. Headless Chromium does not composite a
  `desynchronized` 2D canvas into a screenshot, so the capture harness strips that one flag; the
  app is unchanged.
* **No physical-phone pass.** The Safari/Android matrix, IME on a real soft keyboard, and weak
  connections remain the open gate carried over from v38/v39.

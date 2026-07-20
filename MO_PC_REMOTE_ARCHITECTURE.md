# Mo PC Remote architecture

Phone-to-MoOS control, shipped as a first-class system app. The control center never embeds a
remote desktop and never launches a browser; the service is opt-in and scoped to the user
session; activation must not block boot.

> This document previously described a planned Sunshine/Moonlight stack. That was never built.
> What ships — and what is described below — is the portal-based implementation.

```text
Native GTK control center  (/usr/bin/mo-pc-remote)
  ├─ systemd user lifecycle (mo-remote-personal.service) — opt-in, never auto-enabled
  ├─ live health: firewall, PipeWire, desktop portal, input permission, backend
  └─ the phone's address, and the agent's recent errors

Agent  (/usr/lib/mo-remote/MoRemotePersonal — self-contained .NET, user session only)
  ├─ serves the PWA controller and one WebSocket per phone
  ├─ PIN + token auth, Tailscale/LAN network guard, idle timeout
  └─ owns the portal helper below

Portal helper  (/usr/lib/mo-remote/mo-remote-portal.py)
  └─ ONE xdg-desktop-portal session — RemoteDesktop + ScreenCast together — carrying
     both halves of remote control:
       video : PipeWire node → GStreamer (pipewiresrc ! videorate ! videoscale !
               videoconvert ! jpegenc ! appsink) → length-prefixed JPEG over a unix socket
       input : NotifyPointerMotionAbsolute / Button / Axis / KeyboardKeycode / Keysym

Phone (PWA, any browser)
  └─ draws the frames and the cursor; sends normalized absolute coordinates

Fallbacks (only when the portal is unavailable)
  ├─ input : ydotoold on a private per-user uinput socket (relative motion only)
  └─ video : spectacle, one screenshot per frame — correct, but ~700ms a frame
```

## Why it is built this way

**Capture must not be a screenshot loop.** The first implementation spawned `spectacle` for
every frame. Measured: 630ms per frame, so the phone saw roughly one frame per second. That is
what "the mouse is very slow" actually was — the pointer was fine, the *screen* was a second
behind. PipeWire delivers 20–30fps of the same desktop, and frames are damage-driven, so a
still desktop costs nothing at all.

**Coordinates are absolute, in the portal's logical space.** The portal validates absolute
pointer positions against the *logical* desktop it advertises (1396×785 on a 3840×2160 screen
at 2.75× scale) — not against the pixel size of the video stream. Anything else comes back as
"Invalid position". Absolute positioning is what makes a tap land exactly where it was tapped;
the old relative path accumulated drift and re-zeroed the cursor into a screen corner on every
click.

**The cursor is hidden in the stream, and the phone draws its own.** Painting the real cursor
into the video means every pointer move damages the screen and forces a full-frame JPEG
re-encode — measured at +8.5 Mbit/s purely to move the mouse. With `cursor_mode = HIDDEN`,
pointer motion produces no frames at all, and the phone draws the cursor at the position it
just commanded: free, and instant, because it never waits for a round trip. Set
`embedCursor: true` in `settings.json` to get the true in-stream cursor back.

**The helper dies loudly.** If the portal grant is revoked ("Stop sharing"), the pipeline
errors, or the frame socket breaks, the helper exits and the agent respawns it — restoring from
the saved permission token, so no dialog reappears. The failure mode this avoids is the silent
one: a helper that stays alive on a dead session, serving a frozen frame and swallowing every
click while still reporting healthy. A permission dialog the user *declines* backs off for five
minutes instead of re-prompting once a second, forever.

## TLS is `tailscale serve`, and the agent must stay plain HTTP

The phone reaches `https://moos-3.<tailnet>.ts.net` on port 443. That is **`tailscale serve`**
terminating TLS with a certificate Tailscale manages and renews, proxying to the agent:

```text
phone ── https :443 ──► tailscale serve ── http ──► agent :8765
```

Two consequences, both learned the hard way:

**Never enable Kestrel-side HTTPS.** `TlsManager` can load a `tailscale cert` and serve HTTPS on
8765 directly. Turning that on breaks everything: `tailscale serve` proxies *plain HTTP* to 8765,
an HTTPS listener answers that with a TLS handshake, and the only URL the phone has starts
returning `502 Bad Gateway`. It is also redundant — serve already supplies the certificate, on a
nicer URL with no port number, and renews it with nobody owning a timer. `TlsManager` stays dormant
unless something writes `tls/host.txt`; nothing in the image should.

**The phone is therefore already in a secure context.** That is what makes WebCodecs — and so the
H.264 path — and the native clipboard available at all. Any reasoning that starts "the agent is
plain http, so we are stuck on JPEG" is describing a topology this has not had for a while.

## Encoding

H.264 when the phone can decode it, JPEG when it cannot. The phone declares which on connect
(`{"type":"video","h264":…}`) and the agent never guesses: a browser outside a secure context
answers false and correctly keeps JPEG. That declaration once had no handler and was silently
discarded, which pinned every phone to JPEG at ~1.18 MB a frame regardless of what it could decode.

JPEG has no temporal compression, so a *changing* screen is expensive (~20–40 Mbit/s at 1280px
on a busy desktop) while a still one is free. The quality preset is the real resolution knob:
it selects the encoder's output width (0.5 → 960px, 1.0 → 1920px). A scale change rebuilds the
pipeline rather than renegotiating caps on a live one, which collapses the stream to under
1fps.

If lower bandwidth is ever wanted, the path is HTTPS + WebCodecs + VP8 (`vp8enc` is already in
the image), which would cut the moving-picture case by roughly 15×. It is not shipped because
it would put a certificate warning between the user and their own desktop.

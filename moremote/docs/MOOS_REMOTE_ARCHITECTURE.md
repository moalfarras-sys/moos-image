# Mo PC Remote — integrated architecture and acceptance contract

Mo PC Remote is a MoOS system surface, not a web wrapper installed beside the system. Its user
service, portal helper, controller bundle, update lifecycle and rollback all ship in the signed
immutable image. A green compile is therefore only a prerequisite; acceptance requires a live
Wayland session, a real encoded picture and real input into ordinary applications.

## Shipping path

```text
KWin RemoteDesktop + ScreenCast portal
        │  PipeWire frames + ordered input
        ▼
mo-remote-portal.py ── H.264 (NVENC/VAAPI/OpenH264) or bounded JPEG fallback
        │  access units + health + input acknowledgements
        ▼
ASP.NET session broker ── authenticated HTTPS/WSS over Tailscale Serve
        │
        ▼
React PWA ── WebCodecs canvas + Pointer Events + native mobile text input
```

The helper sends a one-second PipeWire keepalive even when the desktop is unchanged. If five
keepalives pass without a delivered access unit, it exits with a lost-session status so the owner
service obtains a fresh portal session. A GStreamer error falls back only when the failing element
is a known H.264 encoder; source, scaling and unknown failures restart the portal instead of looping
inside an unrelated encoder fallback.

Both producer and consumer are recovery-aware. A server queue overflow discards reference-broken
delta frames until the next IDR. A browser decode backlog retires the old `VideoDecoder`, starts a
new generation and rejects late callbacks from the old generation. Automatic quality tops out at
Sharp; Ultra is manual because RTT is latency, not available uplink bandwidth.

## Input and clipboard contract

- One bounded FIFO consumer owns all input. Full queues apply backpressure; a new mouse-up or key
  event can never run inline ahead of older events.
- Pointer Events drive Touch, Trackpad, Direct and desktop modes. A double tap produces exactly two
  clicks in total. Fine-pointer detection keeps mouse and physical keyboard active on touchscreen
  laptops.
- ASCII uses the user's active layout when possible. Arabic and printable US symbols use named,
  verified keyboard groups and physical positions. A missing group takes the exact-text path;
  a failed in-stream group switch fails closed instead of typing the wrong positions.
- Text that the installed portal protocol cannot represent (accents, German characters, emoji,
  composed sequences) is classified without splitting grapheme clusters. If any grapheme in a
  gathered browser commit needs that path, the complete commit is written to Wayland, read back
  byte-for-byte, then pasted as one synchronous ordered action. Multiple clipboard owners inside
  one commit are forbidden because applications may fetch an earlier Paste asynchronously. The
  explicit clipboard remains that value; a delayed restore would create the same race.
- Text and PNG clipboard writes are acknowledged only after exact read-back. **Send & Paste** waits
  for that acknowledgement; failure means no Paste event, never stale content.
- Windows follows the same acknowledgement rule on its STA clipboard: text is compared exactly and
  image content is compared after deterministic 32-bit PNG normalization. The shared Web API must
  compile against both implementations.

## Desktop presence contract

An authenticated controller cannot remain invisible on the MoOS desktop. The shared `SessionState`
publishes exactly one regular runtime marker after authentication:
`$XDG_RUNTIME_DIR/mo-remote/presence-active-N` or `presence-paused-N`, where `N` is the current
controller count. Registration, pause/resume, disconnect and clean shutdown all update or remove it.
Isolated test/cloud instances never overwrite the signed-in desktop's marker.

The MoOS context island watches the directory listing rather than the frame socket. This is
deliberate: `FolderListModel` does not expose Unix sockets, while changing marker filenames produces
a real listing event without permanent polling. Remote presence takes visual priority over media and
opens the native control center; service-active alone is never presented as a live viewer.

## Controller layout contract

The encoded desktop and controller chrome are sibling grid tracks. Portrait phones reserve a
safe-area-aware bottom dock; phone landscape, tablet and desktop reserve a right rail. Hiding the
controls keeps the track stable, and every visible target is at least 44 × 44 CSS pixels. The
remote Horizon Bar is never under a controller hit target. Reduced Motion removes decorative
transitions, while connection, recovery, pause and locked states remain explicit.

iPhone Safari cannot programmatically hide all browser chrome from a normal tab. The supported
immersive route is **Add to Home Screen**, where the controller runs as an installed PWA and uses
dynamic viewport and safe-area insets.

## Release acceptance

Every release must prove all of the following, not merely compile:

1. Controller unit tests, TypeScript, production bundle freshness and tracked generated assets.
2. Linux agent build and behavioural tests for decoder generations, IDR recovery, portal
   starvation, encoder/source error classification, FIFO ordering, gestures, keyboard groups,
   exact Unicode and clipboard confirmation.
3. A real Wayland Unicode round trip into an ordinary application using Arabic, German, accents,
   emoji, English and symbols.
4. Browser renders at phone portrait, phone landscape and desktop geometry with zero intersection
   between the streamed stage and controller chrome, all hit targets at least 44 × 44.
5. A live H.264 session under repeated viewport rotation with no empty frame, codec collapse,
   reconnect or portal rebuild.
6. A full image compose with the identity, boot, QML, bundle and `bootc container lint` gates.
7. Signed registry images, staged update, reboot proof, zero failed units and an intact previous
   deployment for rollback before the work is called shipped.

## Deliberate next architecture

The current H.264-over-WebSocket transport is repaired and bounded, but all viewers in a room still
share one capture/encode choice. A slow phone can therefore constrain a sharp desktop viewer. The
next major version should keep the same portal source and move media to GStreamer's WebRTC stack,
with one video transport per viewer (or simulcast layers), two ordered/unordered RTCDataChannels,
and measured adaptation from outbound goodput, frame drops and decoder queue headroom. Input should
move to the portal's EIS/libei path when the shipped libei/libeis version exposes UTF-8 text at both
ends; clipboard remains the explicit compatibility route until then.

Primary references used for that decision:

- XDG RemoteDesktop portal: <https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html>
- XDG ScreenCast portal: <https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html>
- GStreamer `webrtcsink`: <https://gstreamer.freedesktop.org/documentation/rswebrtc/webrtcsink.html>
- WebRTC statistics: <https://www.w3.org/TR/webrtc-stats/>
- Pointer Events: <https://www.w3.org/TR/pointerevents/>
- Input Events Level 2: <https://www.w3.org/TR/input-events-2/>
- libei sender API: <https://libinput.pages.freedesktop.org/libei/api/group__libei-sender.html>
- WebKit safe areas and dynamic viewport units:
  <https://webkit.org/blog/7929/designing-websites-for-iphone-x/> and
  <https://webkit.org/blog/12445/new-webkit-features-in-safari-15-4/>

## v38 input and recovery refinements

`hello.cursorEmbedded` advertises the Linux capture cursor. With that cursor,
trackpad movement sends coalesced relative deltas and current-position clicks;
the controller suppresses its synthetic cursor and automatic cursor-centered
keyboard zoom because the portal does not supply absolute cursor telemetry.
Older servers retain the absolute-coordinate fallback. Pointer-lock button
releases remember their press path even if pointer lock ends first.

Gesture cancellation drops queued movement and releases held input. Native IME
composition and ordinary text use the same Unicode scalar diff. The accepted
baseline and offline draft remain separate until an authenticated reconnect.
This does not provide exactly-once delivery of packets lost after socket send:
there is no server edit acknowledgement protocol. Complex grapheme deletion is
also target-application-dependent and needs the physical keyboard matrix.

A hidden viewer no longer receives or queues frames just because another viewer
keeps the encoder alive. Resume waits for a fresh IDR. Input-loop failure closes
its connection, fragmented UTF-8 is decoded statefully, and pause serializes with
input execution before releasing held keys. Unauthenticated/view-only disconnects
do not release another controller's keys. Active controllers still share one
injector; per-controller ownership is a remaining acceptance item.

Set `MOREMOTE_INPUT_DIAGNOSTICS=1` only for targeted diagnosis; ordinary pointer
and text packets no longer cause synchronous per-input log writes. See
[verification and browser test setup](../../docs/REMOTE_V38_VERIFICATION.md).

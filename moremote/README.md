# Mo Remote Personal

A **private**, local-only remote control for your own Windows PC, driven from your iPhone (or any browser) over **Tailscale**. View your screen and control the mouse + keyboard by touch — no VPS, no cloud, no database, no domain, no open router ports.

> ⚠️ **Personal use only.** This tool is deliberately **not stealthy**: it always shows a red "Remote control active" banner on the PC and has an instant Stop button. Use it only on computers you own or are authorized to control.

---

## 🇸🇦 البداية السريعة (عربي)

1. **ثبّت Tailscale** على الكمبيوتر والآيفون من [tailscale.com/download](https://tailscale.com/download) وسجّل الدخول بنفس الحساب على الجهازين.
2. على الكمبيوتر، افتح PowerShell داخل مجلد المشروع ونفّذ:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
   ```
   سيبني التطبيق، يثبّته، يشغّله مع بداية Windows، ويضع أيقونة بجانب الساعة.
3. اضغط بزر الفأرة الأيمن على الأيقونة → **Copy access URL** (مثلاً `http://100.x.y.z:8765`).
4. على الآيفون، افتح هذا الرابط في **Safari**، وأنشئ **PIN** عند أول تشغيل.
5. شارك ▸ **Add to Home Screen** لتثبيته كتطبيق.
6. أدخل الـPIN → شاهد الشاشة وتحكّم باللمس. لإيقاف التحكم فوراً: زر **Stop** على شريط الكمبيوتر أو من الأيقونة.

لتغيير الـPIN: من أيقونة الساعة → **Change PIN**. لتغيير المنفذ: عدّل `settings.json` في `%LOCALAPPDATA%\MoRemotePersonal`.

---

## Features

- **Windows tray agent** — runs at startup, lives in the system tray, no console window.
- **Live screen streaming** over WebSocket (adaptive JPEG; Low / Balanced / High presets). Never changes the PC's resolution. Uses **DXGI Desktop Duplication** (GPU-composited — smooth, and captures hardware-accelerated windows, video and games that plain screen-grab renders black) and falls back to GDI automatically.
- **Multi-monitor** — pick which display to view/control from the phone (View ▸ Monitor); clicks land on the right screen.
- **Remote power** — Lock / Sleep / Sign out / Restart / Shut down the PC from the phone (More ▸ Power), with a confirm on the drastic ones.
- **Data-saving + Auto quality** — identical frames are never resent (a still screen uses almost no data/battery); an **Auto** quality mode adapts JPEG quality/scale to your network latency.
- **Optional HTTPS** — serve over a real Tailscale certificate (tray ▸ *Enable HTTPS*) to unlock the phone's native clipboard and offline PWA install.
- **Optional SYSTEM service** *(experimental)* — run across the lock/login screen (see below).
- **Three smart touch modes** — **Touch** (tap = click, swipe = scroll, long-press = right-click), **Trackpad** (relative cursor), **Direct** (press-and-drag). Double-tap = double click. Pinch-zoom + pan the view. A live cursor indicator shows the pointer.
- **Display controls** — Fit-to-screen / Original 100% / Zoom in-out / Fullscreen, with accurate touch coordinates at any zoom.
- **Full keyboard** — opens the native iPhone keyboard; types Arabic + English + symbols straight into Windows. Shortcut bar: Ctrl / Alt / Shift / Win, Ctrl+C / Ctrl+V / Ctrl+A, Alt+Tab, Esc, Tab, arrows, Home/End/Del, plus Ctrl+Alt+Del (safe).
- **Clipboard sync** (button-only, never automatic) — *Get PC Clipboard* pulls the PC's text to the phone; *Set PC Clipboard* pushes the phone's text to the PC.
- **Non-overlapping adaptive controls** — a thumb dock below the picture on phones and a right rail on landscape/desktop. Every control lives outside the encoded desktop, so the MoOS Horizon Bar remains visible and clickable.
- **Text and image clipboard** (explicit, never background polling) — set only, or send and paste after exact read-back. Desktop Ctrl/Cmd+V transfers the browser's text or image first, then pastes remotely; a failed transfer never pastes stale PC content.
- **Security** — first-run PIN (Argon2id-hashed), short-lived session tokens, 5-attempts → 5-minute lockout, **idle-timeout disconnect**, DPAPI-encrypted local config.
- **Tailscale-only** — accepts connections only from `100.64.0.0/10` + loopback. Never exposed to the internet.
- **Anti-stealth, by design** — a persistent red banner + tray indicator whenever a session is active, with instant Pause / Stop.
- **Installable PWA** — Add to Home Screen on iPhone for a full-screen, app-like experience.

---

## How it connects

```
 iPhone (Safari / PWA)                     Your Windows PC
 ┌───────────────────┐                    ┌──────────────────────────────┐
 │  React PWA         │   Tailscale (WG)   │  MoRemotePersonal.exe         │
 │  http://100.x:8765 │ ◄────────────────► │  ASP.NET Core (Kestrel)       │
 │  • canvas stream   │   encrypted P2P    │  • JPEG capture (BitBlt)      │
 │  • touch + keys    │                    │  • SendInput (mouse/keyboard) │
 └───────────────────┘                    │  • WinForms tray + banner     │
                                           └──────────────────────────────┘
```

Everything is local. The only network in play is your private Tailscale tailnet.

---

## Requirements

- **Windows 10 or 11** (x64).
- **Linux / MoOS (KDE Wayland)** is supported by the native Linux agent in `agent-linux/`. It uses
  one restored XDG RemoteDesktop + ScreenCast portal session, a persistent PipeWire stream,
  hardware H.264 when available, explicit `wl-clipboard`, and portal input injection.
- **[Tailscale](https://tailscale.com/download)** on the PC and the phone (same account).
- To **build** from source: [.NET SDK 10+](https://dotnet.microsoft.com/download) and [Node.js 18+](https://nodejs.org).
  *(The built app is self-contained — the .NET runtime is bundled, so running it needs no install.)*

---

## Install (recommended)

From the project folder on the PC:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

### Linux / MoOS

```sh
sh scripts/install-linux.sh
```

This installs the app in `~/.local/lib/mo-remote-personal`, creates the same launcher and
icon, and enables the `mo-remote-personal.service` user service at login. The `ydotool`
package must be installed on the host for remote mouse and keyboard input.

This builds the PWA + a self-contained Windows app, copies it to `%LOCALAPPDATA%\MoRemotePersonal\app`, adds a Start-Menu shortcut, enables start-with-Windows, and launches it.

**To uninstall:**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1        # keep PIN/settings
powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -Purge # remove everything
```

### Optional: build a real `.exe` installer (Inno Setup)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\MoRemotePersonal.iss
```
Output: `installer\Output\MoRemotePersonal-Setup.exe` (per-user, no admin needed).

> Note: with **Smart App Control** on, an unsigned `Setup.exe` may itself be blocked. The `install.ps1` script avoids this entirely (it's just a script copying files), so it's the recommended install path.

---

## Build & run from source

```powershell
# install JS deps + generate icons (first time only)
cd controller
npm install
npm run gen-icons
cd ..

# Dev mode: agent on :8765 + hot-reloading UI on :5173 (UI proxies to the agent)
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

# Production build -> .\dist\MoRemotePersonal.exe (self-contained)
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

Common commands inside `controller/`:

| Command          | What it does                               |
| ---------------- | ------------------------------------------ |
| `npm install`    | Install frontend dependencies              |
| `npm run dev`    | Vite dev server on :5173 (proxies to agent)|
| `npm run build`  | Build the PWA into `agent/wwwroot`         |
| `npm run gen-icons` | Regenerate icons + `app.ico` from `Logo.png` |

---

## Set up Tailscale & find your IP

1. Install Tailscale on the **PC** and the **iPhone**, sign in with the **same** account on both.
2. Find the PC's Tailscale IP (it looks like `100.x.y.z`):
   - **Easiest:** right-click the tray icon → **Copy access URL**.
   - **Tailscale app:** open it → your machine shows its `100.x.y.z` address.
   - **Command line:** `tailscale ip -4`
3. Make sure both devices show as "Connected" in the Tailscale app.

> The agent listens on all interfaces but **accepts connections only from the Tailscale range (`100.64.0.0/10`) + loopback** — everything else is rejected. This means it becomes reachable automatically as soon as Tailscale connects, with no restart needed even if Tailscale starts after the app or its IP changes. On Windows 11 with Smart App Control, `install.ps1` also adds the required Windows Firewall rule (one UAC prompt).

---

## Connect from your iPhone

1. On the PC, copy the access URL (tray → **Copy access URL**), e.g. `http://100.101.102.103:8765`.
2. On the iPhone (connected to Tailscale), open that URL in **Safari**.
3. **First time:** create a PIN (6+ digits, entered twice).
4. **Add to Home Screen** (Share ▸ Add to Home Screen) to launch it full-screen like an app.
5. Enter your PIN → you'll see the live screen and can control it by touch.

---

## Touch, keyboard & clipboard guide

Tap the **Mouse mode** button on the toolbar to switch between three modes:

| Gesture          | Touch (default)        | Trackpad                | Direct                  |
| ---------------- | ---------------------- | ----------------------- | ----------------------- |
| Tap              | Left click             | Left click              | Left click              |
| Double-tap       | Double click           | Double click            | Double click            |
| Long-press       | Right click            | Right click             | Right click             |
| One-finger drag  | **Scroll** (swipe)     | Move cursor (relative)  | Press-and-drag (windows / select) |
| Two-finger drag  | Pan when zoomed        | Scroll                  | Scroll                  |
| Pinch            | Zoom the view          | Zoom the view           | Zoom the view           |

A small ring shows the current pointer position. The PC's resolution is **never** changed — zoom only affects your phone view.

**View** button: **Fit** (whole screen) / **100%** (original size, pan around) / Zoom in-out / quality **Auto / Low / Balanced / High** (Auto adapts to your network) / **Monitor** picker (multi-display).

**Controls** (auto-hide; tap **Controls** to reveal): **Type · Clipboard · Mouse mode · Display · Zoom · Sound · Fullscreen · More**. On a phone they occupy a reserved bottom dock; in landscape and desktop browsers they occupy a reserved right rail. They never sit on top of the remote picture. *More* has Ctrl+Alt+Del, Copy, Paste, Refresh stream, Disconnect, and a **Power** section. *Display* has a monitor picker when the PC has more than one display.

**Keyboard:** tap **Type** to open the native phone keyboard. MoOS types ASCII and Arabic through real keyboard groups, and uses a confirmed exact-text compatibility path for German characters, accents, emoji and composed Unicode that the installed input protocol cannot represent. The shortcut row has sticky **Ctrl / Alt / Shift / Win**, one-tap **Ctrl+C / Ctrl+V / Ctrl+A / Alt+Tab**, and Esc, Tab, arrows, Home, End, Del.

**Clipboard**: **Get from PC** fetches text or a PNG preview. For outgoing text use **Set only** or **Send & Paste**; for a photo use **Set image only** or **Photo & Paste**. On a desktop browser Ctrl/Cmd+V over the remote picture transfers local text or the first image and waits for the PC to serve the exact payload before sending Paste. Nothing is synchronized automatically.

> **About Ctrl+Alt+Del:** Windows blocks software from injecting the real Secure Attention Sequence (a security feature). The button sends **Ctrl+Shift+Esc** (Task Manager) as the safe equivalent.

---

## Managing the agent (tray icon)

Right-click the tray icon near the clock:

- **Status** — Online / Active / Paused.
- **Copy access URL** / **Open in browser**.
- **Pause session** / **Resume session**.
- **Stop session now** — instantly disconnects the phone.
- **Change PIN…** — set a new PIN (disconnects all sessions).
- **Start with Windows** — toggle auto-start.
- **Never lock — stay reachable** — keeps the PC awake and stops it locking/blanking so the phone can always see the screen (Windows hides the lock screen from every app). Per-user, reversible, no admin. Persists across restarts.
- **Enable admin control (UAC apps)** — restarts the agent **elevated** so the phone can control administrator windows and UAC-elevated apps (Windows blocks input to those from a normal process). One UAC prompt to set it up; afterwards it auto-starts elevated at logon with no prompt. Toggle it off from the same menu.
- **Enable HTTPS (Tailscale cert)** — obtains a real cert via `tailscale cert` and serves `https://<machine>.<tailnet>.ts.net`. Unlocks the phone's native clipboard and offline PWA install. Needs MagicDNS + HTTPS enabled in the Tailscale admin console. Restart the app to switch. Toggle off from the same menu.
- **Show log folder** — opens `%LOCALAPPDATA%\MoRemotePersonal`.
- **Exit**.

### Service mode (experimental) — see the login/lock screen

By default (and by design) the agent can't capture the Windows **lock / login screen** — and it always shows the red "control active" banner. If you specifically need to reach the PC *at the login screen* (e.g. after a full sign-out), you can install a **LocalSystem Windows Service** that runs the agent across the secure desktop:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-service.ps1     # install (admin)
powershell -ExecutionPolicy Bypass -File scripts\uninstall-service.ps1   # remove + restore normal mode
```

> ⚠️ **Tradeoffs — read first.** In service mode there is **no on-screen banner** (it runs as SYSTEM across desktops), the security surface is larger, and it uses its **own PIN** (created on the first phone connection in this mode). It's opt-in and fully reversible with the uninstall script above. Normal mode (banner + per-user) remains the recommended default.

While a session is active, a red **"Remote control active"** banner sits at the top of the screen with its own **Pause** and **Stop** buttons.

---

## Settings

Settings live in `%LOCALAPPDATA%\MoRemotePersonal\settings.json` (plain text, editable). Restart the agent after editing.

| Key                | Default | Meaning                                                        |
| ------------------ | ------- | -------------------------------------------------------------- |
| `port`             | 8765    | Web server port                                                |
| `allowLan`         | false   | `true` also allows same-Wi-Fi LAN (for testing). Internet is always blocked. |
| `jpegQuality`      | 60      | Default stream quality (10–95)                                 |
| `maxFps`           | 18      | Capture frame-rate cap (1–30)                                  |
| `tokenTtlMinutes`  | 60      | Session token lifetime (sliding)                               |
| `idleTimeoutMinutes` | 20    | Disconnect a session after this many minutes of no input       |
| `showRemoteCursor` | true    | Draw the mouse cursor into the stream                          |

The PIN is **never** stored here — it's Argon2id-hashed and the whole `config.dat` is DPAPI-encrypted to your Windows account.

---

## Security model

- **No login, no access.** First run forces a PIN.
- **PINs are hashed** with Argon2id; the config blob is DPAPI-encrypted to the current Windows user.
- **Session tokens** are random 256-bit values, in-memory only (a restart forces re-login), with a sliding expiry.
- **Brute-force protection:** 5 wrong attempts → 5-minute lockout.
- **Tailscale-only:** connections are accepted only from `100.64.0.0/10` (Tailscale) + loopback. The agent binds to the Tailscale IP; the public internet is never reachable.
- **No telemetry, no external calls.** Nothing leaves your machine.
- **Always visible:** the on-screen banner + tray indicator make hidden control impossible.

---

## Troubleshooting

- **Windows blocks the app ("An application control policy has blocked this file"):** this is **Smart App Control** (Windows 11), which blocks unsigned apps. `build.ps1` already publishes the SAC-compatible (Debug) configuration, which runs even with SAC on. If a future Windows update still blocks it, you can turn SAC off: **Windows Security ▸ App & browser control ▸ Smart App Control ▸ Off** (this is a one-way switch until a Windows reset). Code-signing the binary is the only other way to satisfy SAC.
- **Phone can't connect / "Cannot reach the PC":** confirm both devices are Connected in Tailscale; verify the URL/port; make sure the agent is running (tray icon present). If you started Tailscale *after* the agent, relaunch the agent.
- **"Port in use" on start:** change `port` in `settings.json` and restart, or free the port.
- **Black / frozen frame:** the Windows lock screen and the secure desktop can't be captured (OS security). Turn on tray → **Never lock — stay reachable** so the PC never locks while you're away. Regular hardware-accelerated windows, video and games are now captured via DXGI; DRM-protected content may still appear black.
- **UAC prompt / admin app looks frozen from the phone:** a normal process can't send input to elevated windows. Turn on tray → **Enable admin control (UAC apps)** so the agent runs elevated and can control them.
- **“Copy” on the phone did nothing:** fixed — copying the PC's clipboard text to the phone now works over Tailscale (plain HTTP), not only over HTTPS.
- **Mouse position slightly off on a scaled display:** the agent is per-monitor DPI-aware; if you changed display scaling, restart the agent.
- **Logs:** tray → **Show log folder** → `log.txt`.

---

## Project structure

```
MoPC/
├─ agent/            # C# / .NET 10 Windows agent (Kestrel + WinForms tray)
│  ├─ Core/          # config, security (Argon2id), capture (BitBlt), input (SendInput), network guard
│  ├─ Web/           # REST API + WebSocket streaming/control
│  ├─ Tray/          # tray menu, "Remote active" banner, change-PIN dialog
│  └─ wwwroot/       # built PWA (generated)
├─ controller/       # React + Vite + TypeScript PWA
│  └─ src/           # auth screens, remote canvas, gesture engine, toolbar
├─ scripts/          # build.ps1, dev.ps1, install.ps1, uninstall.ps1, install-service.ps1
├─ installer/        # Inno Setup script (.exe installer)
└─ Logo.png          # app logo (source for all icons)
```

## Tech stack

- **Agent:** C# / .NET 10 — ASP.NET Core (Kestrel) HTTP + WebSocket, WinForms tray, P/Invoke `SendInput`, **DXGI Desktop Duplication** (Vortice) with a GDI `BitBlt` fallback, Argon2id, DPAPI.
- **Controller:** React + Vite + TypeScript, PWA, canvas rendering, Pointer-Events gesture engine.
- **Transport:** WebSocket binary JPEG frames over Tailscale.

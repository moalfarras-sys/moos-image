# Mira on the Echo Dot (PC-off voice client)

`agent.py` runs on the owner's Echo Dot 2 (TECHO5 Dot Linux, busybox init, Python 3.14 in
the slot, venv in `/data/mira/venv`). While the desktop Mira app is running it sends a
signed heartbeat to port 8765 every 2 s, and this client stays in **standby**. In standby it
never opens the Echo's encrypted ESPHome API (6053). When the heartbeats stop, it takes the
voice satellite over and answers through Gemini Live itself. The model is whatever
`/data/mira/gemini.json` names.

| File | Where it runs | Purpose |
|---|---|---|
| `agent.py` | Dot, `/data/mira/agent.py` | the client: standby/hand-off, Gemini Live session, tools, `/status` `/heartbeat` `/sync` |
| `run.sh` | Dot, `/data/mira/run.sh` | the busybox-init supervisor (firewall rule, log cap, backoff, clean TERM) |
| `deploy.py` | PC | copies files over the USB serial console with sha256 checks; registers or rolls back the inittab line |
| `cloud_probe.py` | Dot | bounded Gemini connectivity probe (unchanged) |
| `../device_sync.py` | PC (desktop app) | `push()` for the profile, city and voice; returns the facts learned on the Echo |

## What the PC-off client does

- **Tools** (Gemini function calling over the raw WebSocket `toolCall`/`toolResponse` messages):
  `current_time` (the device clock, in the saved city's zone), `current_weather` (Open-Meteo,
  saved city by default), `set_speaker_volume` and `ring_light` (the Dot's own `speaker` and
  `ring` entities, with a state readback: `ok` only when the device reports the new state,
  otherwise `pending`), and `remember_owner_fact` (appends to `profile.txt` and queues the fact
  for the desktop). It refuses a fact that looks like a password, PIN or key. There is no home or
  computer control in this mode, and the persona tells the owner so plainly.
- **Persona**: Arabic, short spoken answers, plus the owner profile synced from the desktop
  (`profile.txt`). The profile is used as knowledge only and never grants a tool.
- **Follow-ups**: one Live session serves all the turns of a conversation. echod opens a
  follow-up turn right after each reply (`follow_up_1` = 20 s). Those turns reuse the open
  WebSocket. The session closes when a follow-up ends silent, after 25 s idle, on `goAway`, or
  after 8 minutes. The abort echod sends to close a *finished* run can reach the client after the
  next follow-up has started, so it is recognised (within 10 s of the reply) and ignored.
- **Audio**: 24 kHz to 16 kHz is a stateful two-phase FIR (Hann-windowed sinc: -12 dB at 8 kHz,
  -40 dB at 10 kHz). At start the agent measures the FIR on the Dot's CPU and falls back to the
  original linear decimation if the FIR costs more than 20% of real time. The log records the
  choice. Reply audio is paced against a clock with 0.25 s of lead.
- **Log** (`/data/mira/agent.log`, 0600): one line per turn, for example
  `turn 3 ok reused=yes connect=0.00s listen=2.1s first_audio=2.9s after_speech=0.8s total=7.4s reply_audio=4.2s tools=current_time:ok:0.0s resampler=fir`.
  It never contains audio, transcripts, keys or exception messages (class names only).
  It is capped at about 256 KB, rotating to `agent.log.1`.

## Wire protocol on port 8765 (LAN only)

- `GET /status` returns `{"state": ..., "at": ...}`: public state only.
- `POST /heartbeat` takes the headers `X-Mira-Time: <unix>` and
  `X-Mira-Signature: hex(HMAC-SHA256(psk, "heartbeat:<unix>"))`. It holds the client in
  standby for 6 s.
- `POST /sync` takes a JSON body of at most 16 KB, `{"profile": str (<=4000 chars),
  "weather_city": str|null, "voice": str|null}`. The signature is
  `hex(HMAC-SHA256(psk, "sync:<unix>:<sha256(body) hex>"))`. It is accepted within ±15 s,
  and each signature only once. `null` leaves a stored value unchanged, and `""` clears it. The
  body is stored as `profile.txt` and `settings.json` (both 0600). The reply is
  `{"ok": true, "learned": [..], "profile_chars": n, "weather_city": .., "voice": ..}`. The
  learned facts are removed from the queue only after that reply has been written; they also
  stay in the device profile until the next push replaces it. Errors are 400 (invalid field),
  403 (bad, stale or replayed signature), 411 and 413. The key is the Dot's
  `/data/misc/echolocal/psk`, which equals the PC's `~/.config/mo-dot/device.key`.
- Traffic is authenticated, not encrypted: the profile and the facts cross the home LAN in
  plain HTTP.

## Desktop integration (for the owners of `app.py` / `mira_bridge.py`)

```python
from device_sync import push, SyncError
from mira_memory import profile_text, remember_fact

def sync_echo(weather_city: str, voice_name: str) -> None:
    """Blocking (<= 3 s): call it from a worker thread or asyncio.to_thread."""
    try:
        reply = push(profile_text(), weather_city, voice_name)   # host 192.168.3.83, key ~/.config/mo-dot/device.key
    except SyncError:
        return            # the Echo is off or unreachable: try again at the next connect
    for fact in reply["learned"]:
        remember_fact(fact)                                     # facts the owner taught the Echo while the PC was off
```

Call it:

1. once each time the bridge connects to the Echo, after the first successful heartbeat
   (`mira_bridge.Bridge.connect`, `await asyncio.to_thread(sync_echo, city, self.voice_name)`);
2. after the owner saves the profile (`save_mira_profile`), the weather city
   (`save_weather_city`), or changes the voice.

Pass `str(settings.value('weather_city', ''))` so that an empty setting clears the city on the
Echo. Pass the voice only if it is one of the Gemini prebuilt voices (the app offers Aoede, Kore
and Leda).

**One desktop fix is required for a safe hand-off.** `Bridge.keep_device_standby()` is started
only when the *first* heartbeat succeeds. If the Echo's port 8765 is not reachable at that
moment, for example while the Echo is still booting, the desktop never heartbeats again during
that connection. The Echo would then take the voice as well. Start the heartbeat loop
unconditionally for as long as the desktop is connected. It already ignores individual
failures.

## Install on the Dot (first time)

Run on the PC with host Python. Only one process may use `/dev/ttyACM0` at a time.

```sh
cd mira/device
python3 deploy.py install      # agent.py + run.sh -> /data/mira (sha256-checked; old copies in /data/mira/backup/)
# stop a manually started agent, if any (it is a child of the console shell, not of init):
#   ps -o pid,ppid,args | grep agent.py   ->   kill <pid>
python3 deploy.py register     # backs up /etc/inittab to /data/mira/backup/inittab.<stamp>,
                               # appends ::respawn:/data/mira/run.sh, kill -HUP 1
python3 deploy.py status       # run.sh (PPID 1) -> python agent, firewall rule, status.json, log tail
```

The equivalent commands for `register`, to type on the console:

```sh
mkdir -p /data/mira/backup && cp -p /etc/inittab /data/mira/backup/inittab.$(date +%Y%m%dT%H%M%S)
sha256sum /etc/inittab /data/mira/backup/inittab.*
grep -qxF '::respawn:/data/mira/run.sh' /etc/inittab || echo '::respawn:/data/mira/run.sh' >> /etc/inittab
sync; kill -HUP 1
```

Updating the code later: `python3 deploy.py install && python3 deploy.py restart`. The restart
TERMs the agent, and `run.sh` starts the new one about 2 s later.

A firmware **slot update replaces `/etc/inittab`**, because `/` is the slot. `/data/mira` survives
the update, but the agent stops starting at boot until `deploy.py register` is run again.

## Rollback

```sh
python3 deploy.py rollback
```

This does exactly the following:

```sh
cp -p $(ls -1t /data/mira/backup/inittab.* | head -1) /etc/inittab && sync && kill -HUP 1
kill -TERM $(pgrep -f /data/mira/run.sh) $(pgrep -f /data/mira/agent.py)
```

busybox init re-reads the table and does not respawn a removed entry. `run.sh` passes the TERM
to the agent, which closes its Live session and the device API before it exits. To also return
to an older agent, copy `/data/mira/backup/agent.py.<stamp>` back to `/data/mira/agent.py`.

Other controls:

- To pause without editing the inittab: `mkdir -p /run/mira && touch /run/mira/hold`, then TERM
  the agent. `run.sh` waits while the file exists, and a reboot clears it.
- To force a resampler: `MIRA_RESAMPLER=linear` or `MIRA_RESAMPLER=fir` in `run.sh`'s
  environment.

## Checking the cloud path without the Echo's API

```sh
/data/mira/venv/bin/python /data/mira/agent.py --selftest "كم الساعة الآن؟" "وكيف الطقس؟"
```

This runs text turns through the real Live session, the tools and session reuse. It plays no
audio. The device tools answer `dry_run`, and it writes nothing except the place cache. It is safe
while the desktop owns the Echo.

## Tests

```sh
cd mira && python -m unittest test_device_agent
```

The tests use no network and no device. Fakes stand in for the ESPHome API and the Live socket.
They cover the tool dispatch and readbacks, the sync signature rules (valid, stale, future,
tampered, wrong key, oversize, missing length, replayed, bad voice/city/JSON), a `device_sync.push`
round-trip, follow-up session reuse including the late close-abort, the tool call → answer
ordering, idle close, type-only error logging, and the release of the API when a heartbeat
arrives during connect.

## Measured on the owner's Echo, 2026-09-28/29

- **Installed and supervised.** `deploy.py install` copied `agent.py` (sha256 `5275dbde…`) and
  `run.sh`; `register` appended `::respawn:/data/mira/run.sh` to `/etc/inittab` after backing it up
  to `/data/mira/backup/inittab.20260928T235048` (original sha256 `ea100def…`, new `666e4aed…`).
  The agent runs as `run.sh`'s child under init (PPID 1 → run.sh → python).
- **Reboot.** `reboot` at 00:01:03: API down at +4 s, this client answering on 8765 at +33 s,
  echod's API back at +35 s, standby for the desktop at +41 s, desktop app back to `ready` at +43 s.
- **Loopback was down after boot — fixed.** TECHO5 never brings `lo` up (`lo: <LOOPBACK> state
  DOWN`, no 127.0.0.1). The client reaches echod's API at the unit's own address, which the kernel
  routes through `lo`, so every takeover timed out (`api released why=TimeoutError`). `run.sh` now
  brings `lo` up before starting the agent. After that, stopping the desktop app handed the voice
  to this client in 5 s (`active: voice subscribed … entities=126`) and reopening it took the
  voice back in 2 s.
- **Sync.** A live `device_sync.push()` stored the 2,493-character profile, the city and the
  voice (0600) and returned the learned facts (none yet).
- **Serial access after a reboot.** `/dev/ttyACM0` is recreated and loses the owner's ACL; run
  `sudo setfacl -m u:moos:rw /dev/ttyACM0` in a host terminal (Konsole, not the VS Code sandbox)
  or add a udev rule for `18d1:4ee7` with `TAG+="uaccess"`.

## One API client at a time for the voice

echod hands a wake word's voice pipeline to the most recently connected API client. A second
client that is only reading (a log or state probe, or Home Assistant added later) therefore takes
the next wake word away from the desktop app, and the ring lights with no answer. This was
measured on 2026-09-29 with a log probe. Read echod's log over the serial console
(`/data/techo5-linux/echod.log`) instead of connecting another API client while testing voice.

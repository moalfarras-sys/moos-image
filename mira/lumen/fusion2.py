"""The motherboard's own lighting controller: Gigabyte RGB Fusion 2 (ITE IT8297/IT5701/IT5702).

Gigabyte boards from the B450/Z390 generation on carry an ITE microcontroller on the internal USB
bus (048d:5702, 048d:8297, 048d:8950). It drives the board's 12 V RGB headers (LED_C), its 5 V
addressable headers (D_LED) and any on-board light. It speaks 64-byte HID feature reports whose
first byte is the report id 0xCC; nothing it is sent here is written to its flash, so the board's
own saved lighting returns at the next power cycle, and MoOS puts the owner's choice back at login.

The wire protocol, as used here (documented by the OpenRGB project's reverse engineering, written
again here from that description; nothing of its code is used):

    CC 60                         identify; then GET feature 0xCC returns the identity report
    CC 20..27 00 00 / CC 28 FF 00 clear every effect register and apply (a clean start)
    CC 31 00                      the controller's own audio "beat" mode off
    CC 32 mask                    per addressable header: bit set = its built-in effect is off,
                                  so the header shows the colours streamed to it (direct mode)
    CC 34 a b c                   addressable LED count per header pair (0=32, 1=64, 2=256 …)
    CC <0x20+led> …               one zone's effect: type, brightness, colour (B,G,R,0), timing
    CC 28 <mask u32>              apply the effects written to the zones in the mask
    CC <0x58|0x59> off n rgb…     direct colours for D_LED1/D_LED2: byte offset, byte count,
                                  then up to 19 LEDs in the header's calibrated colour order

Only this file talks to the controller. `Fusion2.open()` returns None when there is none.
"""
from __future__ import annotations

import errno
import fcntl
import glob
import os
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

REPORT_ID = 0xCC
PACKET = 64
VENDOR = 0x048D
PRODUCTS = {0x5702: 'IT5702', 0x8297: 'IT8297', 0x8950: 'IT8950'}

# effect types the controller runs by itself
STATIC, PULSE, FLASH, CYCLE, WAVE = 1, 2, 3, 4, 6
EFFECTS = {'static': STATIC, 'breathe': PULSE, 'flash': FLASH, 'cycle': CYCLE, 'wave': WAVE}

# addressable headers: effect register index, direct-colour header, bit in the 0x32 mask
DLED = {'D_LED1': (5, 0x58, 0x01), 'D_LED2': (6, 0x59, 0x02)}
LEDS_PER_PACKET = 19
COUNT_STEPS = ((32, 0), (64, 1), (256, 2), (512, 3), (1024, 4))


def _ioc(nr: int, size: int) -> int:
    # _IOC(_IOC_READ|_IOC_WRITE, 'H', nr, size): HIDIOCSFEATURE is 0x06, HIDIOCGFEATURE 0x07
    return (3 << 30) | (size << 16) | (ord('H') << 8) | nr


@dataclass
class Zone:
    key: str                  # D_LED1, D_LED2, LED_C1, LED_C2 …
    kind: str                 # 'argb' (addressable 5 V) or 'rgb' (12 V, one colour)
    index: int                # effect register (0x20 + index)
    leds: int = 1             # addressable LEDs driven in direct mode


@dataclass
class Identity:
    product: str
    firmware: str
    chip: str
    description: str
    order: dict = field(default_factory=dict)   # header → (r, g, b) byte positions


# The zones a board exposes. Gigabyte's identity report does not list them; boards of one family
# share a layout. Every board with this controller has the two addressable headers; most add two
# 12 V headers at registers 1 and 4. A zone with nothing plugged in simply stays dark.
DEFAULT_LAYOUT = (
    Zone('D_LED1', 'argb', 5, 32),
    Zone('D_LED2', 'argb', 6, 32),
    Zone('LED_C1', 'rgb', 1),
    Zone('LED_C2', 'rgb', 4),
)


def find_devices(root: str = '/sys/class/hidraw') -> list[str]:
    """/dev/hidrawN nodes of supported controllers (interface 0 only)."""
    found = []
    for node in sorted(glob.glob(os.path.join(root, 'hidraw*'))):
        try:
            with open(os.path.join(node, 'device', 'uevent'), encoding='utf-8') as fh:
                uevent = dict(line.strip().split('=', 1) for line in fh if '=' in line)
        except OSError:
            continue
        hid = uevent.get('HID_ID', '')            # 0003:0000048D:00005702
        parts = hid.split(':')
        if len(parts) != 3:
            continue
        try:
            vendor, product = int(parts[1], 16), int(parts[2], 16)
        except ValueError:
            continue
        if vendor == VENDOR and product in PRODUCTS:
            found.append('/dev/' + os.path.basename(node))
    return found


def _order(cal: int) -> tuple[int, int, int]:
    """Byte positions of red, green and blue inside one LED's three bytes."""
    b, g, r = cal & 0xFF, (cal >> 8) & 0xFF, (cal >> 16) & 0xFF
    if sorted((r, g, b)) != [0, 1, 2]:
        return (1, 0, 2)          # GRB, the order nearly every addressable LED uses
    return (r, g, b)


def _count_step(leds: int) -> int:
    for limit, step in COUNT_STEPS:
        if leds <= limit:
            return step
    return COUNT_STEPS[-1][1]


class Fusion2:
    """One controller. Thread-safe: every write takes the lock."""

    def __init__(self, fd: int, path: str, layout=DEFAULT_LAYOUT):
        self.fd = fd
        self.path = path
        self.zones = {z.key: Zone(z.key, z.kind, z.index, z.leds) for z in layout}
        self.identity: Optional[Identity] = None
        self._lock = threading.Lock()
        self._direct_mask = 0
        self._ready = False

    # ── opening ──────────────────────────────────────────────────────
    @classmethod
    def open(cls, path: Optional[str] = None) -> Optional['Fusion2']:
        paths = [path] if path else find_devices()
        for candidate in paths:
            try:
                fd = os.open(candidate, os.O_RDWR | os.O_CLOEXEC)
            except OSError:
                continue
            ctl = cls(fd, candidate)
            try:
                ctl.identity = ctl.identify()
            except OSError:
                ctl.close()
                continue
            return ctl
        return None

    def close(self):
        if self.fd >= 0:
            try:
                os.close(self.fd)
            finally:
                self.fd = -1

    # ── the wire ─────────────────────────────────────────────────────
    def _send(self, payload: bytes) -> None:
        buf = bytearray(PACKET)
        buf[0] = REPORT_ID
        buf[1:1 + len(payload)] = payload[:PACKET - 1]
        for attempt in range(3):
            try:
                fcntl.ioctl(self.fd, _ioc(0x06, PACKET), bytes(buf))
                return
            except OSError as exc:
                if exc.errno not in (errno.EPIPE, errno.ETIMEDOUT, errno.EAGAIN) or attempt == 2:
                    raise
                time.sleep(0.01)

    def _get(self) -> bytes:
        buf = bytearray(PACKET)
        buf[0] = REPORT_ID
        fcntl.ioctl(self.fd, _ioc(0x07, PACKET), buf, True)
        return bytes(buf)

    def identify(self) -> Identity:
        with self._lock:
            self._send(bytes((0x60, 0x00)))
            report = self._get()
        fw = report[4:8]
        description = report[12:40].split(b'\0', 1)[0].decode('ascii', 'replace').strip()
        cal_strip0, cal_strip1, _rgb, chip = struct.unpack_from('<IIII', report, 44)
        product = description.split('-', 1)[0] if description.startswith('IT') else 'ITE'
        return Identity(product=product, firmware='.'.join(str(b) for b in fw),
                        chip='0x%08X' % chip, description=description,
                        order={'D_LED1': _order(cal_strip0), 'D_LED2': _order(cal_strip1)})

    # ── state ────────────────────────────────────────────────────────
    def start(self) -> None:
        """A clean start: every effect register cleared, the beat mode off, LED counts set."""
        with self._lock:
            self._start()

    def _start(self) -> None:
        # callers hold self._lock (it is not re-entrant: every public write takes it once)
        for reg in range(0x20, 0x28):
            self._send(bytes((reg, 0x00, 0x00)))
        self._send(bytes((0x28, 0xFF, 0x00)))
        self._send(bytes((0x31, 0x00)))
        d1 = _count_step(self.zones['D_LED1'].leds) if 'D_LED1' in self.zones else 0
        d2 = _count_step(self.zones['D_LED2'].leds) if 'D_LED2' in self.zones else 0
        self._send(bytes((0x34, (d2 << 4) | d1, 0x00, 0x00)))
        self._direct_mask = 0
        self._send(bytes((0x32, self._direct_mask)))
        self._ready = True

    def _ensure(self):
        if not self._ready:
            self._start()

    def _set_direct(self, key: str, on: bool):
        bit = DLED[key][2]
        mask = (self._direct_mask | bit) if on else (self._direct_mask & ~bit)
        if mask != self._direct_mask:
            self._direct_mask = mask
            self._send(bytes((0x32, mask)))

    def _effect(self, zone: Zone, effect: int, rgb, brightness: int, speed: int) -> int:
        """Write one zone's effect register; returns its bit for the apply mask."""
        r, g, b = (max(0, min(255, int(c))) for c in rgb)
        packet = bytearray(PACKET - 1)          # without the report id
        packet[0] = 0x20 + zone.index
        struct.pack_into('<II', packet, 1, 1 << zone.index, 0)
        packet[10] = effect
        packet[11] = max(0, min(255, int(brightness)))
        packet[12] = 0
        struct.pack_into('<I', packet, 13, (r << 16) | (g << 8) | b)   # little-endian: B, G, R, 0
        speed = max(0, min(9, int(speed)))
        if effect == PULSE:
            period = 400 + speed * 100 if speed <= 6 else 1000 + (speed - 6) * 200
            struct.pack_into('<HHH', packet, 21, period, period, 200)
        elif effect == FLASH:
            struct.pack_into('<HHH', packet, 21, 100, 100, speed * 200 + 700)
        elif effect == CYCLE:
            period = speed * 100 + 300 + (1300 * (speed - 8) if speed > 8 else 0)
            struct.pack_into('<HH', packet, 21, period, period - 200)
            packet[29] = 7
        elif effect == WAVE:
            period = ((speed + 1) ** 2 + (speed + 1) + 10) * 5 // 2
            struct.pack_into('<H', packet, 21, period)
            packet[29], packet[30] = 7, 1
        self._send(bytes(packet))
        return 1 << zone.index

    def _apply(self, mask: int):
        self._send(bytes((0x28,)) + struct.pack('<II', mask, 0))

    # ── what the engine calls ────────────────────────────────────────
    def set_effect(self, keys, effect: str = 'static', rgb=(255, 255, 255), brightness: int = 255,
                   speed: int = 4) -> None:
        """A colour or a built-in animation on these zones (the controller runs it by itself)."""
        kind = EFFECTS.get(effect, STATIC)
        with self._lock:
            self._ensure()
            mask = 0
            for key in keys:
                zone = self.zones.get(key)
                if zone is None:
                    continue
                if zone.kind == 'argb':
                    self._set_direct(key, False)
                mask |= self._effect(zone, kind, rgb, brightness, speed)
            if mask:
                self._apply(mask)

    def off(self, keys) -> None:
        self.set_effect(keys, 'static', (0, 0, 0), 0)

    def stream(self, frame: dict) -> None:
        """Direct colours, many times a second: {zone: [(r,g,b), …]} — one colour fills a zone.

        Addressable headers take one colour per LED in their calibrated order; a 12 V header takes
        the first colour as a static effect (it has one colour only)."""
        with self._lock:
            self._ensure()
            mask = 0
            for key, colours in frame.items():
                zone = self.zones.get(key)
                if zone is None or not colours:
                    continue
                if zone.kind != 'argb':
                    mask |= self._effect(zone, STATIC, colours[0], 255, 0)
                    continue
                self._set_direct(key, True)
                leds = list(colours) if len(colours) > 1 else [colours[0]] * zone.leds
                leds = (leds * (zone.leds // max(1, len(leds)) + 1))[:zone.leds]
                order = (self.identity.order.get(key) if self.identity else None) or (1, 0, 2)
                header = DLED[key][1]
                for start in range(0, len(leds), LEDS_PER_PACKET):
                    chunk = leds[start:start + LEDS_PER_PACKET]
                    packet = bytearray(PACKET - 1)
                    packet[0] = header
                    struct.pack_into('<HB', packet, 1, start * 3, len(chunk) * 3)
                    for i, (r, g, b) in enumerate(chunk):
                        base = 4 + i * 3
                        packet[base + order[0]] = max(0, min(255, int(r)))
                        packet[base + order[1]] = max(0, min(255, int(g)))
                        packet[base + order[2]] = max(0, min(255, int(b)))
                    self._send(bytes(packet))
            if mask:
                self._apply(mask)

    def describe(self) -> dict:
        ident = self.identity
        return {'path': self.path,
                'product': ident.product if ident else '',
                'firmware': ident.firmware if ident else '',
                'chip': ident.chip if ident else '',
                'zones': [{'key': z.key, 'kind': z.kind, 'leds': z.leds} for z in self.zones.values()]}

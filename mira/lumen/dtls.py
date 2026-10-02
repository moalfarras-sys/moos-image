"""DTLS 1.2 with a pre-shared key, spoken through the system's own GnuTLS.

The Hue Entertainment API streams colours as UDP datagrams to port 2100, inside DTLS 1.2 with
exactly one cipher suite, TLS_PSK_WITH_AES_128_GCM_SHA256. The PSK identity is the application
key and the PSK is the 16-byte "clientkey" the bridge hands out when it is paired. Python's `ssl`
has no DTLS and Mira may not grow a new package, but libgnutls.so.30 is part of every MoOS image
(glib2, NetworkManager and glib-networking require it). So this module binds the few GnuTLS calls
a DTLS client needs with ctypes, and nothing more.

What is deliberate:

* A blocking, connected UDP socket and a bounded handshake. DTLS runs over UDP, so a lost
  handshake flight is normal: GnuTLS retransmits it by itself, and `gnutls_handshake_set_timeout`
  bounds the whole exchange so an absent peer ends in a DtlsError instead of a hang. After the
  handshake each `send()` is exactly one datagram, written at once; nothing is queued, so a stale
  frame is never delivered late.
* The priority string names the bridge's suite and nothing else. Fedora's DEFAULT crypto policy
  runs GnuTLS in allowlist mode. Its version, cipher and MAC lists bind every priority string
  (DTLS 1.2, AES-128-GCM and AEAD are all on them); its key-exchange list does not name PSK, but
  GnuTLS filters the key exchanges of an explicit priority string only in blocklist mode
  (lib/priority.c). So "+PSK" works without touching the owner's policy; `test_lumen_hue` proves
  it against a real DTLS server under that policy.
* The constants are GnuTLS's ABI, read from <gnutls/gnutls.h> and <gnutls/dtls.h> of release
  3.8.13 — the release MoOS ships. The image carries no -devel headers, so they were read from
  the Freedesktop SDK copy of the same release. They belong to the libgnutls.so.30 ABI, so they
  cannot change without a new soname, and loading anything but .so.30 is refused.
* The key never leaves this object: it is in no repr, no error message and no log line.
"""
from __future__ import annotations

import ctypes
import os
import socket
import threading
import time

# gnutls_init() flags
GNUTLS_CLIENT = 1 << 1
GNUTLS_DATAGRAM = 1 << 2
# gnutls_credentials_type_t
GNUTLS_CRD_PSK = 4
# gnutls_psk_key_flags
GNUTLS_PSK_KEY_RAW = 0
# gnutls_close_request_t
GNUTLS_SHUT_WR = 1
# error codes
GNUTLS_E_AGAIN = -28
GNUTLS_E_INTERRUPTED = -52
GNUTLS_E_PUSH_ERROR = -53
GNUTLS_E_PULL_ERROR = -54
GNUTLS_E_TIMEDOUT = -319

# Exactly what the Hue bridge speaks. AEAD is the "MAC" of a GCM suite; SIGN-ALL and GROUP-ALL
# are harmless for PSK (no signature, no group) but GnuTLS refuses a list that names none.
PRIORITY = b'NONE:+VERS-DTLS1.2:+PSK:+AES-128-GCM:+AEAD:+SIGN-ALL:+GROUP-ALL:+COMP-NULL'
MTU = 1400                       # an Ethernet datagram, minus IP/UDP headers and some margin
RETRANSMIT_MS = 400              # first handshake retransmission; GnuTLS doubles it each time


class DtlsError(RuntimeError):
    """A DTLS failure, worded by GnuTLS itself when GnuTLS produced it."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class _Datum(ctypes.Structure):
    _fields_ = [('data', ctypes.c_void_p), ('size', ctypes.c_uint)]


_lib = None
_lib_lock = threading.Lock()


def _gnutls():
    """The library, loaded once and typed; DtlsError when the system has none."""
    global _lib
    with _lib_lock:
        if _lib is not None:
            return _lib
        try:
            lib = ctypes.CDLL('libgnutls.so.30', use_errno=True)
        except OSError as exc:
            raise DtlsError(f'GnuTLS is not available: {exc}') from None
        vp, i, u, p = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.POINTER
        sig = {
            'gnutls_global_init': (i, []),
            'gnutls_check_version': (ctypes.c_char_p, [ctypes.c_char_p]),
            'gnutls_strerror': (ctypes.c_char_p, [i]),
            'gnutls_error_is_fatal': (i, [i]),
            'gnutls_init': (i, [p(vp), u]),
            'gnutls_deinit': (None, [vp]),
            'gnutls_psk_allocate_client_credentials': (i, [p(vp)]),
            'gnutls_psk_free_client_credentials': (None, [vp]),
            'gnutls_psk_set_client_credentials': (i, [vp, ctypes.c_char_p, p(_Datum), i]),
            'gnutls_credentials_set': (i, [vp, i, vp]),
            'gnutls_priority_set_direct': (i, [vp, ctypes.c_char_p, p(ctypes.c_char_p)]),
            'gnutls_transport_set_int2': (None, [vp, i, i]),
            'gnutls_dtls_set_mtu': (None, [vp, u]),
            'gnutls_dtls_set_timeouts': (None, [vp, u, u]),
            'gnutls_handshake_set_timeout': (None, [vp, u]),
            'gnutls_handshake': (i, [vp]),
            'gnutls_record_send': (ctypes.c_ssize_t, [vp, ctypes.c_void_p, ctypes.c_size_t]),
            'gnutls_bye': (i, [vp, i]),
            'gnutls_protocol_get_version': (i, [vp]),
            'gnutls_protocol_get_name': (ctypes.c_char_p, [i]),
            'gnutls_kx_get': (i, [vp]),
            'gnutls_kx_get_name': (ctypes.c_char_p, [i]),
            'gnutls_cipher_get': (i, [vp]),
            'gnutls_cipher_get_name': (ctypes.c_char_p, [i]),
        }
        try:
            for name, (restype, argtypes) in sig.items():
                fn = getattr(lib, name)
                fn.restype, fn.argtypes = restype, argtypes
        except AttributeError as exc:
            raise DtlsError(f'this GnuTLS lacks a DTLS call Lumen needs: {exc}') from None
        if not lib.gnutls_check_version(b'3.6.0'):
            raise DtlsError('GnuTLS 3.6 or newer is needed for DTLS 1.2 with a pre-shared key')
        rc = lib.gnutls_global_init()
        if rc < 0:
            raise DtlsError(_text(lib, rc, 'GnuTLS did not initialise'), rc)
        _lib = lib
        return lib


def _text(lib, rc: int, what: str) -> str:
    detail = lib.gnutls_strerror(rc)
    text = f'{what}: {detail.decode("utf-8", "replace") if detail else rc}'
    if rc in (GNUTLS_E_PUSH_ERROR, GNUTLS_E_PULL_ERROR):
        # the socket said why (most often "Connection refused": nothing listens on that port)
        err = ctypes.get_errno()
        if err:
            text += f' ({os.strerror(err)})'
    return text


class DtlsPskClient:
    """One DTLS 1.2 PSK session to host:port. `send()` is safe from several threads."""

    def __init__(self, host: str, port: int, identity: str, key: bytes, timeout: float = 5.0):
        if not identity or not isinstance(identity, str):
            raise DtlsError('a PSK identity is required')
        try:
            self._identity = identity.encode('ascii')
        except UnicodeEncodeError:
            raise DtlsError('the PSK identity must be ASCII') from None
        if not isinstance(key, (bytes, bytearray)) or not key:
            raise DtlsError('a PSK key (bytes) is required')
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self._key = ctypes.create_string_buffer(bytes(key), len(key))
        self._sock: socket.socket | None = None
        self._session = ctypes.c_void_p()
        self._cred = ctypes.c_void_p()
        self._lock = threading.Lock()
        self.cipher = ''               # e.g. "DTLS1.2 PSK AES-128-GCM" once connected

    def __repr__(self) -> str:
        state = 'connected' if self.connected else 'closed'
        return f'<DtlsPskClient {self.host}:{self.port} {state}>'

    @property
    def connected(self) -> bool:
        return bool(self._session.value)

    def __enter__(self) -> 'DtlsPskClient':
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self) -> 'DtlsPskClient':
        with self._lock:
            if self._session.value:
                return self
            lib = _gnutls()
            try:
                self._open(lib)
            except BaseException:
                self._teardown(lib, bye=False)
                raise
        return self

    def _open(self, lib) -> None:
        try:
            family, kind, proto, _, addr = socket.getaddrinfo(
                self.host, self.port, type=socket.SOCK_DGRAM)[0]
            self._sock = socket.socket(family, kind, proto)
            self._sock.connect(addr)          # ICMP "port unreachable" now reaches send()
        except OSError as exc:
            raise DtlsError(f'cannot reach {self.host}:{self.port}: {exc}') from None

        def check(rc: int, what: str) -> None:
            if rc < 0:
                raise DtlsError(_text(lib, rc, what), rc)

        check(lib.gnutls_psk_allocate_client_credentials(ctypes.byref(self._cred)),
              'cannot allocate PSK credentials')
        datum = _Datum(ctypes.cast(self._key, ctypes.c_void_p), len(self._key))
        check(lib.gnutls_psk_set_client_credentials(self._cred, self._identity,
                                                    ctypes.byref(datum), GNUTLS_PSK_KEY_RAW),
              'the PSK was refused')
        check(lib.gnutls_init(ctypes.byref(self._session), GNUTLS_CLIENT | GNUTLS_DATAGRAM),
              'cannot start a DTLS session')
        err_pos = ctypes.c_char_p()
        check(lib.gnutls_priority_set_direct(self._session, PRIORITY, ctypes.byref(err_pos)),
              'GnuTLS refused the DTLS 1.2 PSK priority')
        check(lib.gnutls_credentials_set(self._session, GNUTLS_CRD_PSK, self._cred),
              'cannot attach the PSK')
        fd = self._sock.fileno()
        lib.gnutls_transport_set_int2(self._session, fd, fd)
        lib.gnutls_dtls_set_mtu(self._session, MTU)
        total_ms = max(1, int(self.timeout * 1000))
        lib.gnutls_dtls_set_timeouts(self._session, min(RETRANSMIT_MS, total_ms), total_ms)
        lib.gnutls_handshake_set_timeout(self._session, total_ms)

        deadline = time.monotonic() + self.timeout
        while True:
            rc = lib.gnutls_handshake(self._session)
            if rc >= 0:
                break
            transient = rc in (GNUTLS_E_AGAIN, GNUTLS_E_INTERRUPTED) or not lib.gnutls_error_is_fatal(rc)
            if transient and time.monotonic() < deadline:
                continue
            if rc == GNUTLS_E_TIMEDOUT:
                raise DtlsError(f'the DTLS handshake with {self.host}:{self.port} did not finish '
                                f'within {self.timeout:g} s (no answer, or the key was refused)', rc)
            check(rc, f'DTLS handshake with {self.host}:{self.port} failed')

        def name(get, get_name) -> str:
            raw = get_name(get(self._session))
            return raw.decode('ascii', 'replace') if raw else '?'
        self.cipher = ' '.join((name(lib.gnutls_protocol_get_version, lib.gnutls_protocol_get_name),
                                name(lib.gnutls_kx_get, lib.gnutls_kx_get_name),
                                name(lib.gnutls_cipher_get, lib.gnutls_cipher_get_name)))

    def send(self, data: bytes) -> int:
        """One encrypted datagram. Returns the number of plaintext bytes sent."""
        payload = bytes(data)
        with self._lock:
            if not self._session.value:
                raise DtlsError('the DTLS session is not connected')
            lib = _gnutls()
            buf = ctypes.create_string_buffer(payload, len(payload))
            for _ in range(5):
                rc = lib.gnutls_record_send(self._session, buf, len(payload))
                if rc >= 0:
                    return rc
                if rc not in (GNUTLS_E_AGAIN, GNUTLS_E_INTERRUPTED):
                    break
            raise DtlsError(_text(lib, rc, f'sending to {self.host}:{self.port} failed'), rc)

    def close(self) -> None:
        """Say goodbye (one close_notify, without waiting for the peer's) and free everything.
        Idempotent; never raises."""
        with self._lock:
            if self._session.value or self._cred.value or self._sock is not None:
                self._teardown(_lib, bye=True)

    def _teardown(self, lib, bye: bool) -> None:
        if lib is not None and self._session.value:
            if bye:
                lib.gnutls_bye(self._session, GNUTLS_SHUT_WR)
            lib.gnutls_deinit(self._session)
        self._session = ctypes.c_void_p()
        if lib is not None and self._cred.value:
            lib.gnutls_psk_free_client_credentials(self._cred)
        self._cred = ctypes.c_void_p()
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
        self.cipher = ''

    def __del__(self):
        try:
            self.close()
        except Exception:      # interpreter shutdown: nothing useful left to report
            pass

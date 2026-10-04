"""Kernel-owned identity for Mo AI's IPv4 loopback HTTP clients.

Origin/custom headers defend against browser requests, not another local UID.
Match the *client* socket's full reversed tuple in this network namespace;
checking the accepted server socket instead would always return our own UID.
No client-supplied UID, forwarded header, cached port, or missing record is trusted.
Linux format: https://docs.kernel.org/networking/proc_net_tcp.html
"""
import os
import socket
import struct


def _address(endpoint):
    address, port = endpoint
    return f"{struct.unpack('=I', socket.inet_aton(address))[0]:08X}:{port:04X}"


def _client_uid(rows, peer, local):
    for row in rows:
        fields = row.split()
        if (len(fields) >= 10 and fields[1] == peer and fields[2] == local
                and fields[3] == '01'):
            try:
                return int(fields[7]) if int(fields[9]) > 0 else None
            except ValueError:
                return None
    return None


def same_user(connection):
    """Fail closed if the real connected client cannot be attributed to this UID."""
    try:
        if connection.family != socket.AF_INET:
            return False
        peer, local = connection.getpeername(), connection.getsockname()
        if peer[0] != '127.0.0.1' or local[0] != '127.0.0.1':
            return False
        with open('/proc/net/tcp', encoding='ascii') as rows:
            return _client_uid(rows, _address(peer), _address(local)) == os.geteuid()
    except (OSError, ValueError, AttributeError):
        return False

"""Attribute the full connecting socket before accepting proxy IP headers.

Tailscale 1.102.5 replaces X-Forwarded-For with its transport source address.
The public listener must terminate there, and its backend must be IPv4 loopback.
Never infer a proxy from its headers or the accepted server socket's UID.
"""
import ipaddress
import socket
import struct


def address(endpoint):
    host, port = endpoint
    if host != '127.0.0.1' or not 0 < port < 65536:
        raise ValueError('IPv4 loopback required')
    return f"{struct.unpack('=I', socket.inet_aton(host))[0]:08X}:{port:04X}"


def peer_uid(scope):
    try:
        peer, local = address(scope['client']), address(scope['server'])
        with open('/proc/net/tcp', encoding='ascii') as rows:
            for row in rows:
                fields = row.split()
                if (len(fields) >= 10 and fields[1] == peer and fields[2] == local
                        and fields[3] == '01' and int(fields[9]) > 0):
                    return int(fields[7])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def forwarded_ip(scope, headers, expected_uid):
    if peer_uid(scope) != expected_uid:
        return None
    values = [v for k, v in headers if k == b'x-forwarded-for']
    if len(values) != 1:
        return None
    try:
        return str(ipaddress.ip_address(values[0].decode('ascii')))
    except (ValueError, UnicodeError):
        return None

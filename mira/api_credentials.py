"""Credential input bounds shared by Mira's settings and existing API owners.

An API key is opaque provider data, not a vendor prefix or a shell command.
Keep punctuation unchanged; only surrounding pasted whitespace is removed.
This module neither imports an SDK nor reads, stores or sends credentials.
"""


def normalize_api_key(value):
    """Return a bounded printable ASCII key or raise a secret-free ValueError."""
    if isinstance(value, str):
        key = value.strip()
        if 1 <= len(key) <= 4096 and all(33 <= ord(char) <= 126 for char in key):
            return key
    raise ValueError('API key is missing or has an invalid format')

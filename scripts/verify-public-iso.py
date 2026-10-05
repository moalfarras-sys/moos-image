#!/usr/bin/env python3
"""Verify public delivery of an already boot-proven, MoOS-signed ISO.

Checks the entire anonymous download, not just HEAD or a successful redirect.
This does not upload files, publish a release, or qualify new hardware.
"""
import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def public_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("A public HTTPS URL without embedded credentials is required")
    if parsed.fragment:
        raise ValueError("Download URLs must not contain fragments")
    return url


class HttpsRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        public_url(newurl)
        return super().redirect_request(request, response, code, message, headers, newurl)


def verify_signed_iso(path, signature, *, public_key=None):
    """Verify the CI's detached ECDSA/SHA-256 signature and hash the SAME bytes.

    MoOS's pinned public key is P-256; cosign sign-blob emits a base64 DER
    signature over SHA-256. The legacy cosign verifier reads the whole blob
    into RAM. OpenSSL verifies this same signature through a bounded pipe.
    Release workflows and their cosign/transparency checks remain unchanged.
    """
    public_key = public_key or ROOT / "cosign.pub"
    with signature.open("rb") as file:
        encoded = file.read(16385)
    if len(encoded) > 16384:
        raise ValueError("The detached ISO signature is oversized")
    try:
        decoded = base64.b64decode(b"".join(encoded.split()), validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("The detached ISO signature is not valid base64") from error
    digest, received = hashlib.sha256(), 0
    with tempfile.TemporaryDirectory(prefix="moos-iso-signature-") as temporary:
        der = Path(temporary) / "signature.der"
        der.write_bytes(decoded)
        process = subprocess.Popen([
            "openssl", "dgst", "-sha256", "-verify", str(public_key), "-signature", str(der),
        ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with path.open("rb") as file:
                for block in iter(lambda: file.read(1024 * 1024), b""):
                    process.stdin.write(block)
                    digest.update(block)
                    received += len(block)
        except BaseException as error:
            process.kill()
            process.wait()
            if isinstance(error, OSError):
                raise ValueError("The ISO signature could not be verified with the MoOS public key") from error
            raise
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.wait():
            raise ValueError("The ISO signature could not be verified with the MoOS public key")
    return {"sha256": digest.hexdigest(), "sizeBytes": received, "signatureVerified": True}


def verify_transfer(url, size, sha256, *, opener=None, timeout=60):
    public_url(url)
    if not isinstance(size, int) or size <= 0:
        raise ValueError("The trusted ISO size must be positive")
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise ValueError("The trusted ISO SHA-256 must contain 64 lowercase hex characters")
    opener = opener or urllib.request.build_opener(HttpsRedirects())
    headers = {"User-Agent": "MoOS-Download-Verification/1.0", "Accept-Encoding": "identity"}
    def read_range(start, end):
        probe = urllib.request.Request(url, headers={**headers, "Range": f"bytes={start}-{end}"})
        with opener.open(probe, timeout=timeout) as response:
            public_url(response.geturl())
            if response.status != 206:
                raise ValueError("The host does not support byte-range downloads (HTTP 206)")
            if response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}":
                raise ValueError("The host returned an incorrect Content-Range")
            body = response.read(end - start + 2)
            if len(body) != end - start + 1:
                raise ValueError("The byte-range response is incomplete or oversized")
            return body
    sample_size = min(size, 65536)
    first_bytes = read_range(0, sample_size - 1)
    # A host accepting only ranges starting at zero cannot resume a large ISO.
    last_bytes = read_range(size - sample_size, size - 1) if size > sample_size else first_bytes
    request = urllib.request.Request(url, headers=headers)
    digest = hashlib.sha256()
    received = 0
    first_block = True
    tail = b""
    with opener.open(request, timeout=timeout) as response:
        public_url(response.geturl())
        if response.status != 200:
            raise ValueError("A full anonymous download must return HTTP 200")
        if response.headers.get("Content-Length") != str(size):
            raise ValueError("The full download does not report the exact trusted ISO size")
        if response.headers.get("Content-Encoding", "identity") != "identity":
            raise ValueError("The host transformed the ISO with content encoding")
        for block in iter(lambda: response.read(1024 * 1024), b""):
            if first_block:
                # urllib may return a short first read; compare just those bytes.
                if block[:len(first_bytes)] != first_bytes[:len(block)]:
                    raise ValueError("The host changed the file between the range and full download")
                first_block = False
            received += len(block)
            if received > size:
                raise ValueError("The download exceeds the trusted ISO size")
            digest.update(block)
            tail = (tail + block)[-sample_size:]
    if received != size or digest.hexdigest() != sha256:
        raise ValueError("The downloaded bytes do not match the trusted ISO SHA-256 and size")
    if tail != last_bytes:
        raise ValueError("The resume range does not match the signed ISO")
    return {
        "url": url, "sizeBytes": received, "sha256": digest.hexdigest(),
        "http": 200, "rangeHttp": 206, "anonymous": True, "fullHashVerified": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, required=True, help="Exact proven CI ISO, downloaded locally")
    parser.add_argument("--signature", type=Path, required=True, help="The CI ISO's .sig file")
    parser.add_argument("--url", required=True, help="Anonymous public HTTPS URL for the same ISO")
    parser.add_argument("--output", type=Path, required=True, help="Local JSON evidence report")
    args = parser.parse_args()
    if not args.iso.is_file() or not args.signature.is_file():
        parser.error("The ISO and its CI signature must both exist")
    try:
        public_url(args.url)
        signed = verify_signed_iso(args.iso, args.signature)
        report = verify_transfer(args.url, signed["sizeBytes"], signed["sha256"])
        report.update({
            "schema": 1, "checkedAt": datetime.now(timezone.utc).isoformat(),
            "signatureVerified": True,
            "scope": "Delivery only; match the ISO's successful boot/install and promotion proofs before publication.",
        })
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Readers must never see a partially written PASS report.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                             prefix=args.output.name + ".", delete=False) as file:
                temporary = Path(file.name)
                file.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            os.replace(temporary, args.output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f"PASS: exact signed ISO, anonymous HTTP 200, byte ranges and SHA-256; {args.output}")
    except (ValueError, OSError, urllib.error.URLError) as error:
        # Do not expose a signed redirect URL or an error response body.
        parser.exit(1, f"FAIL: {str(error) if isinstance(error, ValueError) else type(error).__name__}\n")


if __name__ == "__main__":
    main()

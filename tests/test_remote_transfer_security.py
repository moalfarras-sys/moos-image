#!/usr/bin/env python3
"""Gate bearer-safe downloads and bounded, atomic uploads."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
api = (ROOT / "moremote/agent/Web/WebApi.cs").read_text(encoding="utf-8")
files = (ROOT / "moremote/agent/Core/FileService.cs").read_text(encoding="utf-8")
tickets = (ROOT / "moremote/agent/Core/AccessTicketStore.cs").read_text(encoding="utf-8")
client = (ROOT / "moremote/controller/src/lib/api.ts").read_text(encoding="utf-8")

checks = {
    "downloads still put a reusable bearer token in the URL":
        "download?path=" not in client and "&token=" not in client,
    "download tickets are not authenticated and single-use":
        'download-ticket' in api and 'Tickets.Consume(ticket, "download"' in api,
    "upload size is not rejected before reading the request":
        "ContentLength > FileService.MaxUploadBytes" in api and "statusCode: 413" in api,
    "uploads are not written through an isolated temporary file":
        ".moremote-upload-" in files and "File.Move(temp, target)" in files,
    "partial uploads are not removed on disconnect/failure":
        "File.Delete(temp)" in files,
    "upload streaming does not reserve space for the running OS":
        "FreeSpaceReserve" in files and "AvailableSpaceFor(dir)" in files,
    "ticket issuance is unbounded or performs a full dictionary sweep per request":
        "MaxTickets = 1024" in tickets and "ConcurrentQueue<string>" in tickets
        and "foreach (var pair in _tickets)" not in tickets,
}
failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("remote transfer security gate failed:\n- " + "\n- ".join(failed))
print("remote transfer security gate passed")

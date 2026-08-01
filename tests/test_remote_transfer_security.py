#!/usr/bin/env python3
"""Gate bearer-safe downloads and bounded, atomic uploads."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
api = (ROOT / "moremote/agent/Web/WebApi.cs").read_text(encoding="utf-8")
files = (ROOT / "moremote/agent/Core/FileService.cs").read_text(encoding="utf-8")
tickets = (ROOT / "moremote/agent/Core/AccessTicketStore.cs").read_text(encoding="utf-8")
sessions = (ROOT / "moremote/agent/Core/UploadSessionStore.cs").read_text(encoding="utf-8")
client = (ROOT / "moremote/controller/src/lib/api.ts").read_text(encoding="utf-8")

checks = {
    "downloads still put a reusable bearer token in the URL":
        "download?path=" not in client and "&token=" not in client,
    "downloads do not use a bounded resource-specific retry lease":
        'download-ticket' in api and 'IssueLease(' in api
        and 'UseLease(ticket, "download"' in api and "maxUses: 32" in api,
    "downloads advertise no HTTP Range or stable validators":
        "enableRangeProcessing: true" in api and "EntityTagHeaderValue" in api
        and "lastModified: modified" in api,
    "upload size is not rejected before reading the request":
        "ContentLength > FileService.MaxUploadBytes" in api and "statusCode: 413" in api,
    "uploads are not written through an isolated temporary file":
        ".moremote-upload-" in files and "File.Move(temp, target)" in files,
    "partial uploads are not removed on disconnect/failure":
        "File.Delete(temp)" in files,
    "upload streaming does not reserve space for the running OS":
        "FreeSpaceReserve" in files and "AvailableSpaceFor(dir)" in files,
    "clipboard images are buffered before their size limit is enforced":
        "ReadBoundedAsync" in files and "remaining + 1" in files
        and "ContentLength is > MaxClipboardImageBytes" in api
        and "CopyToAsync(ms)" not in api,
    "directory listings can allocate and serialize without a bound":
        "MaxListingEntries = 500" in files and "truncated = true" in files
        and "Take(MaxListingEntries + 1)" in files,
    "resumable uploads have no bounded sequential atomic protocol":
        "MaxChunkBytes = 4 * 1024 * 1024" in sessions
        and "MaxSessions = 64" in sessions and "Offset mismatch:" in sessions
        and "flushToDisk: true" in sessions and "File.Move(session.TempPath, target)" in sessions
        and 'MapMethods("/api/files/upload/chunk", ["PATCH"]' in api,
    "abandoned upload sessions have no expiry or cleanup":
        "TimeSpan.FromMinutes(30)" in sessions and "CleanupAbandonedFiles" in sessions
        and "File.Delete(session.TempPath)" in sessions and "new System.Threading.Timer" in sessions
        and "SweepExpired()" in sessions and "IDisposable" in sessions,
    "phone client does not persist and recover the server upload offset":
        "mo_remote_pending_upload_v2" in client and "uploadStatus" in client
        and "file.slice(offset, end)" in client and "select the same file to resume" in client,
    "resume identity trusts filename metadata without sampling file content":
        'crypto.subtle.digest("SHA-256"' in client and "pending.fingerprint === fingerprint" in client,
    "ticket issuance is unbounded or performs a full dictionary sweep per request":
        "MaxTickets = 1024" in tickets and "ConcurrentQueue<string>" in tickets
        and "foreach (var pair in _tickets)" not in tickets,
}
failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("remote transfer security gate failed:\n- " + "\n- ".join(failed))
print("remote transfer security gate passed")

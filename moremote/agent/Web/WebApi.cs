using System.Net;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Net.Http.Headers;

namespace MoRemote;

public static class WebApi
{
    public record SetupReq(string? pin, bool trustDevice = false, string? deviceName = null);
    public record LoginReq(string? pin, bool trustDevice = false, string? deviceName = null);
    public record DeviceResumeReq(string? deviceId, string? deviceToken);
    public record DeviceRevokeReq(string? deviceId);
    public record LogoutReq(bool revokeDevice = true);
    public record ChangePinReq(string? currentPin, string? newPin);
    public record ClipboardReq(string? text);
    public record PowerReq(string? action);
    public record DownloadTicketReq(string? path);
    public record UploadStartReq(string? dir, string? name, long size);
    public record UploadSessionReq(string? id);

    private const int MinPinLength = 6;
    private const int MaxPinLength = 64;
    private const int MaxClipboardImageBytes = 25_000_000;

    /// <summary>moos-cloud-audio listens this far above the agent's port (8765 -> 8775).</summary>
    private const int AudioPortOffset = 10;

    /// <summary>Hard network gate: Tailscale (+ optional LAN) + loopback only. Register first.</summary>
    public static void UseNetworkGuard(WebApplication app, AgentServices svc)
    {
        app.Use(async (ctx, next) =>
        {
            if (!NetworkGuard.IsAllowed(ctx.Connection.RemoteIpAddress, svc.Config.AllowLan))
            {
                Log.Warn($"Blocked connection from {ctx.Connection.RemoteIpAddress} (not allowed).");
                ctx.Response.StatusCode = StatusCodes.Status403Forbidden;
                await ctx.Response.WriteAsync("Forbidden: this device is only reachable over Tailscale.");
                return;
            }
            await next();
        });
    }

    public static void Map(WebApplication app, AgentServices svc)
    {
        // ---- Public status (needed to pick setup vs login vs lockout screen) ----
        app.MapGet("/api/status", () => Results.Json(new
        {
            name = AppInfo.Name,
            version = AppInfo.Version,
            firstRun = svc.Sessions.FirstRun,
            locked = svc.Sessions.LockoutRemainingSeconds() > 0,
            lockoutSeconds = svc.Sessions.LockoutRemainingSeconds(),
            hostPowerAllowed = PowerActions.HostPowerAllowed,
        }));
        app.MapGet("/api/local-diagnostic-token",(HttpContext ctx)=>
        {
            if(Environment.GetEnvironmentVariable("MOREMOTE_LOCAL_DIAGNOSTICS")!="1"||ctx.Connection.RemoteIpAddress is not { } ip||!IPAddress.IsLoopback(ip))return Results.NotFound();
            return Results.Json(new {token=svc.Sessions.IssueLocalDiagnosticToken()});
        });

        // ---- First-run PIN creation ----
        app.MapPost("/api/setup", async (HttpContext ctx) =>
        {
            if (!svc.Sessions.FirstRun)
                return Results.Json(new { error = "already_configured" }, statusCode: 409);
            var req = await ReadJson<SetupReq>(ctx);
            var pin = req?.pin ?? "";
            if (!IsValidPin(pin))
                return Results.Json(new { error = "weak_pin", minLength = MinPinLength }, statusCode: 400);
            AuthGrant grant;
            try
            {
                grant = svc.Sessions.SetupPin(pin, req!.trustDevice
                    ? (string.IsNullOrWhiteSpace(req.deviceName) ? "Trusted device" : req.deviceName)
                    : null);
            }
            catch (InvalidOperationException)
            {
                return Results.Json(new { error = "already_configured" }, statusCode: 409);
            }
            return Results.Json(new {
                token = grant.Token, deviceId = grant.DeviceId, deviceToken = grant.DeviceToken,
                ttlMinutes = svc.Config.TokenTtlMinutes
            });
        });

        // ---- Login ----
        app.MapPost("/api/login", async (HttpContext ctx) =>
        {
            if (svc.Sessions.FirstRun)
                return Results.Json(new { error = "needs_setup" }, statusCode: 409);
            var req = await ReadJson<LoginReq>(ctx);
            var result = svc.Sessions.Login(req?.pin ?? "",
                req?.trustDevice == true
                    ? (string.IsNullOrWhiteSpace(req.deviceName) ? "Trusted device" : req.deviceName)
                    : null, out var grant);
            return result switch
            {
                LoginResult.Ok => Results.Json(new {
                    token = grant.Token, deviceId = grant.DeviceId, deviceToken = grant.DeviceToken,
                    ttlMinutes = svc.Config.TokenTtlMinutes
                }),
                LoginResult.LockedOut => Results.Json(
                    new { error = "locked", lockoutSeconds = svc.Sessions.LockoutRemainingSeconds() },
                    statusCode: 423),
                _ => Results.Json(new { error = "invalid_pin" }, statusCode: 401),
            };
        });

        // ---- Trusted devices: persistent credential -> short in-memory session ----
        app.MapPost("/api/devices/resume", async (HttpContext ctx) =>
        {
            var req = await ReadJson<DeviceResumeReq>(ctx);
            return svc.Sessions.ResumeTrustedDevice(req?.deviceId, req?.deviceToken, out var token)
                ? Results.Json(new { token, ttlMinutes = svc.Config.TokenTtlMinutes })
                : Results.Json(new { error = "untrusted_device" }, statusCode: 401);
        });
        app.MapGet("/api/session", (HttpContext ctx) =>
            IsAuthed(ctx, svc) ? Results.Json(new { ok = true })
                               : Results.Json(new { error = "unauthorized" }, statusCode: 401));
        app.MapGet("/api/devices", (HttpContext ctx) =>
        {
            var token = BearerToken(ctx);
            if (!svc.Sessions.ValidateAndTouch(token))
                return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            return Results.Json(new { devices = svc.Sessions.ListTrustedDevices(token) });
        });
        app.MapPost("/api/devices/revoke", async (HttpContext ctx) =>
        {
            var token = BearerToken(ctx);
            var req = await ReadJson<DeviceRevokeReq>(ctx);
            return svc.Sessions.RevokeTrustedDevice(token, req?.deviceId)
                ? Results.Json(new { ok = true })
                : Results.Json(new { error = "not_found" }, statusCode: 404);
        });

        // ---- Change PIN (requires a valid token) ----
        app.MapPost("/api/pin", async (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var req = await ReadJson<ChangePinReq>(ctx);
            if (!IsValidPin(req?.newPin ?? ""))
                return Results.Json(new { error = "weak_pin", minLength = MinPinLength }, statusCode: 400);
            var ok = svc.Sessions.ChangePin(req!.currentPin ?? "", req.newPin ?? "");
            return ok ? Results.Json(new { ok = true })
                      : Results.Json(new { error = "invalid_pin" }, statusCode: 401);
        });

        // ---- Logout ----
        app.MapPost("/api/logout", async (HttpContext ctx) =>
        {
            var token = BearerToken(ctx);
            var req = await ReadJson<LogoutReq>(ctx);
            var deviceId = svc.Sessions.DeviceIdFor(token);
            if (req?.revokeDevice != false && deviceId != null)
                svc.Sessions.RevokeTrustedDevice(token, deviceId);
            else
                svc.Sessions.Revoke(token);
            return Results.Json(new { ok = true });
        });

        // ---- Clipboard sync (text + images; only on an explicit button press) ----
        app.MapGet("/api/clipboard", (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var c = ClipboardBridge.GetContent();
            return c.Kind switch
            {
                "image" => Results.Json(new { kind = "image", dataUrl = "data:image/png;base64," + Convert.ToBase64String(c.ImagePng!) }),
                "text" => Results.Json(new { kind = "text", text = c.Text ?? "" }),
                _ => Results.Json(new { kind = "empty" }),
            };
        });
        app.MapPost("/api/clipboard", async (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var req = await ReadJson<ClipboardReq>(ctx);
            return ClipboardBridge.SetTextConfirmed(req?.text ?? "")
                ? Results.Json(new { ok = true })
                : Results.Json(new { error = "clipboard_unavailable" }, statusCode: 503);
        });
        app.MapPost("/api/clipboard/image", async (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            if (ctx.Request.ContentLength is > MaxClipboardImageBytes)
                return Results.Json(new { error = "bad_size" }, statusCode: 413);
            byte[] image;
            try
            {
                image = await FileService.ReadBoundedAsync(
                    ctx.Request.Body, MaxClipboardImageBytes, ctx.RequestAborted);
            }
            catch (InvalidDataException)
            {
                return Results.Json(new { error = "bad_size" }, statusCode: 413);
            }
            if (image.Length == 0) return Results.Json(new { error = "bad_size" }, statusCode: 400);
            return ClipboardBridge.SetImagePngConfirmed(image)
                ? Results.Json(new { ok = true })
                : Results.Json(new { error = "clipboard_unavailable" }, statusCode: 503);
        });

        // ---- Remote power / session actions (explicit, authenticated button press) ----
        app.MapPost("/api/power", async (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var req = await ReadJson<PowerReq>(ctx);
            var action = req?.action ?? "";
            Log.Warn($"Power action '{action}' requested from {ctx.Connection.RemoteIpAddress}.");
            if (!PowerActions.CanRun(action))
                return Results.Json(new { error = "unavailable_on_edition" }, statusCode: 403);
            var ok = PowerActions.Run(action);
            return ok ? Results.Json(new { ok = true }) : Results.Json(new { error = "failed" }, statusCode: 400);
        });

        // ---- File transfer: browse the PC, download to phone, upload to PC ----
        app.MapGet("/api/files", (HttpContext ctx, string? path) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            try { return Results.Json(FileService.List(path)); }
            catch (Exception ex) { return Results.Json(new { error = ex.Message }, statusCode: 400); }
        });
        app.MapPost("/api/files/download-ticket", async (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var req = await ReadJson<DownloadTicketReq>(ctx);
            var path = req?.path ?? "";
            if (!File.Exists(path)) return Results.Json(new { error = "not_found" }, statusCode: 404);
            return Results.Json(new { ticket = svc.Tickets.IssueLease(
                "download", Path.GetFullPath(path), maxUses: 32, lifetime: TimeSpan.FromMinutes(5)) });
        });
        app.MapGet("/api/files/download", (string? ticket) =>
        {
            if (!svc.Tickets.UseLease(ticket, "download", out var path))
                return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            if (!File.Exists(path)) return Results.Json(new { error = "not_found" }, statusCode: 404);
            var file = new FileInfo(path);
            var modified = new DateTimeOffset(file.LastWriteTimeUtc);
            var etag = new EntityTagHeaderValue($"\"{file.Length:x}-{file.LastWriteTimeUtc.Ticks:x}\"");
            return Results.File(path, "application/octet-stream", Path.GetFileName(path),
                enableRangeProcessing: true, lastModified: modified, entityTag: etag);
        });
        app.MapPost("/api/files/upload", async (HttpContext ctx, string dir, string name) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            if (ctx.Request.ContentLength > FileService.MaxUploadBytes)
                return Results.Json(new { error = "too_large", maxBytes = FileService.MaxUploadBytes }, statusCode: 413);
            try
            {
                var target = await FileService.SaveUploadAsync(
                    ctx.Request.Body, dir, name, ctx.RequestAborted);
                return Results.Json(new { ok = true, saved = Path.GetFileName(target) });
            }
            catch (InvalidDataException ex) { return Results.Json(new { error = ex.Message }, statusCode: 413); }
            catch (Exception ex) { return Results.Json(new { error = ex.Message }, statusCode: 400); }
        });

        // ---- Resumable upload v2: explicit offset + atomic commit ----
        app.MapPost("/api/files/upload/start", async (HttpContext ctx) =>
        {
            var token = BearerToken(ctx);
            if (!svc.Sessions.ValidateAndTouch(token))
                return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var req = await ReadJson<UploadStartReq>(ctx);
            try
            {
                var started = svc.Uploads.Start(token!, req?.dir ?? "", req?.name ?? "", req?.size ?? 0);
                return Results.Json(new { id = started.Id, offset = started.Offset, totalBytes = started.TotalBytes,
                    chunkBytes = UploadSessionStore.MaxChunkBytes });
            }
            catch (InvalidDataException ex) { return Results.Json(new { error = ex.Message }, statusCode: 413); }
            catch (Exception ex) { return Results.Json(new { error = ex.Message }, statusCode: 400); }
        });
        app.MapGet("/api/files/upload/status", (HttpContext ctx, string? id) =>
        {
            var token = BearerToken(ctx);
            if (!svc.Sessions.ValidateAndTouch(token))
                return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            try { return Results.Json(svc.Uploads.Status(token!, id)); }
            catch (UnauthorizedAccessException) { return Results.Json(new { error = "not_found" }, statusCode: 404); }
            catch (TimeoutException) { return Results.Json(new { error = "expired" }, statusCode: 410); }
        });
        app.MapMethods("/api/files/upload/chunk", ["PATCH"], async (HttpContext ctx, string? id, long offset) =>
        {
            var token = BearerToken(ctx);
            if (!svc.Sessions.ValidateAndTouch(token))
                return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            if (ctx.Request.ContentLength is > UploadSessionStore.MaxChunkBytes)
                return Results.Json(new { error = "chunk_too_large" }, statusCode: 413);
            try { return Results.Json(await svc.Uploads.AppendAsync(token!, id, offset,
                ctx.Request.Body, ctx.RequestAborted)); }
            catch (InvalidOperationException ex) when (ex.Message.StartsWith("Offset mismatch:"))
            {
                return Results.Json(new { error = "offset_mismatch",
                    offset = long.Parse(ex.Message["Offset mismatch:".Length..]) }, statusCode: 409);
            }
            catch (InvalidDataException ex) { return Results.Json(new { error = ex.Message }, statusCode: 413); }
            catch (UnauthorizedAccessException) { return Results.Json(new { error = "not_found" }, statusCode: 404); }
            catch (TimeoutException) { return Results.Json(new { error = "expired" }, statusCode: 410); }
        });
        app.MapPost("/api/files/upload/commit", async (HttpContext ctx) =>
        {
            var token = BearerToken(ctx);
            if (!svc.Sessions.ValidateAndTouch(token))
                return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var req = await ReadJson<UploadSessionReq>(ctx);
            try
            {
                var saved = svc.Uploads.Commit(token!, req?.id);
                return Results.Json(new { ok = true, saved = Path.GetFileName(saved) });
            }
            catch (InvalidOperationException ex) { return Results.Json(new { error = "incomplete", detail = ex.Message }, statusCode: 409); }
            catch (UnauthorizedAccessException) { return Results.Json(new { error = "not_found" }, statusCode: 404); }
            catch (TimeoutException) { return Results.Json(new { error = "expired" }, statusCode: 410); }
        });
        app.MapPost("/api/files/upload/cancel", async (HttpContext ctx) =>
        {
            var token = BearerToken(ctx);
            if (!svc.Sessions.ValidateAndTouch(token))
                return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var req = await ReadJson<UploadSessionReq>(ctx);
            return svc.Uploads.Cancel(token!, req?.id)
                ? Results.Json(new { ok = true })
                : Results.Json(new { error = "not_found" }, statusCode: 404);
        });

        // ---- Desktop audio, behind the SAME door as everything else ----
        //
        // The machine's sound is produced by a separate service (moos-cloud-audio, the default
        // sink's monitor as Opus-in-WebM on Port+10) which has no authentication of its own and
        // says so in its own header. That was survivable while it only listened on loopback.
        //
        // It stopped being survivable when `mo-pc-remote` published it with
        // `tailscale serve --set-path=/audio`, because that put an unauthenticated live
        // microphone-adjacent stream on the same hostname, the same port and the same
        // certificate as a desktop that demands a 6-digit PIN. Measured on the maintainer's
        // machine on 2026-07-29:
        //
        //     POST /api/login  (wrong PIN)        -> 401
        //     GET  /audio/stream.webm (no creds)  -> 200 audio/webm, a live Opus stream
        //
        // Anyone on the tailnet could listen to every call, meeting and video, silently, with
        // no indication on the desktop. The flaw was architectural rather than a missing `if`:
        // the audio was published as a SIBLING of the authenticated app instead of a part of
        // it, so it inherited none of its protection. Two doors, one of them with no lock.
        //
        // This is the one door. Reaching the audio now means passing UseNetworkGuard (Tailscale
        // or loopback only) and holding a valid session token, exactly like the clipboard, the
        // files and the input channel.
        //
        app.MapPost("/api/audio/ticket", (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            return Results.Json(new { ticket = svc.Tickets.Issue("audio") });
        });
        // Media elements cannot attach Authorization headers. Give them a 45-second,
        // single-use capability instead of exposing a reusable session bearer in the URL.
        app.MapGet("/api/audio/stream.webm", async (HttpContext ctx, string? ticket) =>
        {
            if (!svc.Tickets.Consume(ticket, "audio", out _))
            {
                ctx.Response.StatusCode = StatusCodes.Status401Unauthorized;
                await ctx.Response.WriteAsync("unauthorized");
                return;
            }

            // No timeout: this is an endless stream, and HttpClient's 100s default would cut the
            // sound off mid-sentence every 100 seconds.
            using var upstream = new HttpClient { Timeout = Timeout.InfiniteTimeSpan };
            var url = $"http://127.0.0.1:{svc.Config.Port + AudioPortOffset}/stream.webm";
            try
            {
                // ResponseHeadersRead, or HttpClient buffers an infinite stream into memory and
                // the listener hears nothing while the process grows without bound.
                using var res = await upstream.GetAsync(
                    url, HttpCompletionOption.ResponseHeadersRead, ctx.RequestAborted);
                if (!res.IsSuccessStatusCode)
                {
                    ctx.Response.StatusCode = StatusCodes.Status502BadGateway;
                    await ctx.Response.WriteAsync("audio service unavailable");
                    return;
                }
                ctx.Response.ContentType = res.Content.Headers.ContentType?.ToString() ?? "audio/webm";
                // The service spawns one encoder per listener and kills it on disconnect, so a
                // cached response is a DEAD stream that plays silence with no error.
                ctx.Response.Headers.CacheControl = "no-store, no-cache, must-revalidate";
                await using var body = await res.Content.ReadAsStreamAsync(ctx.RequestAborted);
                await body.CopyToAsync(ctx.Response.Body, ctx.RequestAborted);
            }
            catch (OperationCanceledException)
            {
                // The listener hung up. Normal, and the upstream encoder dies with the socket.
            }
            catch (HttpRequestException)
            {
                // moos-cloud-audio is not running. A 502 is the honest answer; the phone's Sound
                // button then fails the way a stopped service fails, not the way a bug does.
                if (!ctx.Response.HasStarted)
                {
                    ctx.Response.StatusCode = StatusCodes.Status502BadGateway;
                    await ctx.Response.WriteAsync("audio service unavailable");
                }
            }
        });

        // ---- WebSocket: screen stream + input control ----
        app.Map("/ws", async (HttpContext ctx) =>
        {
            var origin=ctx.Request.Headers.Origin.ToString();
            if(!string.IsNullOrEmpty(origin)&&(!Uri.TryCreate(origin,UriKind.Absolute,out var originUri)||!string.Equals(originUri.Host,ctx.Request.Host.Host,StringComparison.OrdinalIgnoreCase)))
            { ctx.Response.StatusCode=StatusCodes.Status403Forbidden;return; }
            if (!ctx.WebSockets.IsWebSocketRequest)
            {
                ctx.Response.StatusCode = StatusCodes.Status400BadRequest;
                return;
            }
            using var socket = await ctx.WebSockets.AcceptWebSocketAsync();
            var remote = ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            await new StreamSession(svc, socket, remote).RunAsync(ctx.RequestAborted);
        });
    }

    // -------- helpers --------

    private static bool IsValidPin(string pin) =>
        !string.IsNullOrWhiteSpace(pin) && pin.Length >= MinPinLength && pin.Length <= MaxPinLength;

    private static async Task<T?> ReadJson<T>(HttpContext ctx)
    {
        try { return await ctx.Request.ReadFromJsonAsync<T>(); }
        catch { return default; }
    }

    private static string? BearerToken(HttpContext ctx)
    {
        var h = ctx.Request.Headers.Authorization.ToString();
        return h.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase) ? h["Bearer ".Length..].Trim() : null;
    }

    private static bool IsAuthed(HttpContext ctx, AgentServices svc) =>
        svc.Sessions.ValidateAndTouch(BearerToken(ctx));
}

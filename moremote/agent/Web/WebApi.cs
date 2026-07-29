using System.Net;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace MoRemote;

public static class WebApi
{
    public record SetupReq(string? pin);
    public record LoginReq(string? pin);
    public record ChangePinReq(string? currentPin, string? newPin);
    public record ClipboardReq(string? text);
    public record PowerReq(string? action);

    private const int MinPinLength = 6;
    private const int MaxPinLength = 64;

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
            var token = svc.Sessions.SetupPin(pin);
            return Results.Json(new { token, ttlMinutes = svc.Config.TokenTtlMinutes });
        });

        // ---- Login ----
        app.MapPost("/api/login", async (HttpContext ctx) =>
        {
            if (svc.Sessions.FirstRun)
                return Results.Json(new { error = "needs_setup" }, statusCode: 409);
            var req = await ReadJson<LoginReq>(ctx);
            var result = svc.Sessions.Login(req?.pin ?? "", out var token);
            return result switch
            {
                LoginResult.Ok => Results.Json(new { token, ttlMinutes = svc.Config.TokenTtlMinutes }),
                LoginResult.LockedOut => Results.Json(
                    new { error = "locked", lockoutSeconds = svc.Sessions.LockoutRemainingSeconds() },
                    statusCode: 423),
                _ => Results.Json(new { error = "invalid_pin" }, statusCode: 401),
            };
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
        app.MapPost("/api/logout", (HttpContext ctx) =>
        {
            svc.Sessions.Revoke(BearerToken(ctx));
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
            ClipboardBridge.SetText(req?.text ?? "");
            return Results.Json(new { ok = true });
        });
        app.MapPost("/api/clipboard/image", async (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            using var ms = new MemoryStream();
            await ctx.Request.Body.CopyToAsync(ms);
            if (ms.Length == 0 || ms.Length > 25_000_000) return Results.Json(new { error = "bad_size" }, statusCode: 400);
            ClipboardBridge.SetImagePng(ms.ToArray());
            return Results.Json(new { ok = true });
        });

        // ---- Remote power / session actions (explicit, authenticated button press) ----
        app.MapPost("/api/power", async (HttpContext ctx) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            var req = await ReadJson<PowerReq>(ctx);
            var action = req?.action ?? "";
            Log.Warn($"Power action '{action}' requested from {ctx.Connection.RemoteIpAddress}.");
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
        app.MapGet("/api/files/download", (HttpContext ctx, string path, string? token) =>
        {
            // accept token via query so a native browser download (large files) works without a header
            if (!svc.Sessions.ValidateAndTouch(token ?? BearerToken(ctx)))
                return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            if (!File.Exists(path)) return Results.Json(new { error = "not_found" }, statusCode: 404);
            return Results.File(File.OpenRead(path), "application/octet-stream", Path.GetFileName(path));
        });
        app.MapPost("/api/files/upload", async (HttpContext ctx, string dir, string name) =>
        {
            if (!IsAuthed(ctx, svc)) return Results.Json(new { error = "unauthorized" }, statusCode: 401);
            try
            {
                Directory.CreateDirectory(dir);
                var target = FileService.UniquePath(dir, name);
                await using (var fs = File.Create(target)) await ctx.Request.Body.CopyToAsync(fs);
                return Results.Json(new { ok = true, saved = Path.GetFileName(target) });
            }
            catch (Exception ex) { return Results.Json(new { error = ex.Message }, statusCode: 400); }
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
        // The token arrives in the query string, and that is not laziness — it is the same
        // reason /api/files/download takes it that way. This URL is consumed by an <audio>
        // element, and a media element cannot be given an Authorization header. A bearer header
        // is still accepted for anything that can send one.
        app.MapGet("/api/audio/stream.webm", async (HttpContext ctx, string? token) =>
        {
            if (!svc.Sessions.ValidateAndTouch(token ?? BearerToken(ctx)))
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

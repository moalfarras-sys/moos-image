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

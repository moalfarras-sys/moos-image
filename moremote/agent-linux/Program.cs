using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using MoRemote;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

Log.Init();

// ---- set-pin: the account recovery path a headless server has to have --------------------------
//
// THE HOLE THIS FILLS, AND WHY IT IS NOT A CONVENIENCE
//
// The PIN can be created exactly once, through the browser, by whoever reaches the URL first
// (/api/setup answers 409 "already_configured" for ever after). Changing it needs /api/pin, which
// needs a valid session token, which needs the PIN you are trying to change. So on a MoOS Cloud
// account there was NO way back: forget the PIN and that desktop is gone — the service is healthy,
// the stream is running, the machine is fine, and the owner cannot get in. Measured on the live
// server before this existed: moalfarras had FailedAttempts=2 against a PIN nobody could reset.
//
// It is also a claim problem, not only a recovery one. A cloud account's agent comes up in
// first-run state and answers /api/setup to ANYONE who can reach it — and on a tailnet with phones,
// laptops and a second developer on it, "first to open the URL owns the desktop" is not an
// authentication model. Being able to set the PIN from a root shell on the box means the desktop is
// claimed before it is ever published.
//
// STDIN, NEVER ARGV. /proc/<pid>/cmdline is world-readable, so a PIN passed as an argument is
// visible in `ps` to every account on a shared server — which is exactly the kind of machine this
// command exists for. It is also why there is no `--pin=` form to be tempted by.
if (args.Length > 0 && args[0] == "--set-pin")
{
    var cfgForPin = AppConfig.Load();
    var pin = (Console.In.ReadToEnd() ?? "").Trim();
    if (pin.Length is < 6 or > 64)
    {
        Console.Error.WriteLine("set-pin: the PIN must be 6..64 characters (this is the same rule the browser enforces).");
        return 2;
    }
    cfgForPin.PinHash = PinHasher.Hash(pin);
    // Clear the lockout with it. Somebody resetting a PIN has almost always just failed to guess the
    // old one several times, so leaving the counter armed would lock them out of the PIN they have
    // this second chosen — the least explicable possible outcome of a successful reset.
    cfgForPin.FailedAttempts = 0;
    cfgForPin.LockoutUntilUnix = 0;
    cfgForPin.Save();
    Console.WriteLine("PIN set. Restart mo-remote-personal.service for it to take effect:");
    Console.WriteLine("  systemctl --user restart mo-remote-personal.service");
    return 0;
}

// The normal desktop remains single-instance. An explicitly isolated absolute
// data directory represents a separate container/test service and therefore
// gets its own deterministic mutex without weakening the default boundary.
var isolatedDataDir = Environment.GetEnvironmentVariable("MOREMOTE_DATA_DIR");
var mutexName = "MoRemotePersonal_Linux";
if (!string.IsNullOrEmpty(isolatedDataDir))
{
    // Paths.DataDir performs the absolute-path validation before this point.
    var digest = Convert.ToHexString(
        SHA256.HashData(Encoding.UTF8.GetBytes(Paths.DataDir)))[..16];
    mutexName += "_" + digest;
}
using var mutex = new Mutex(true, mutexName, out var first);
if (!first) return 0;
var config=AppConfig.Load(); UserSettings.Apply(config);
var tls=TlsManager.TryLoad();
// One portal session backs both the video stream and input injection.
using var portal=new PortalBridge();
using var capture=new ScreenCapture(portal); using var input=new InputInjector(portal,capture);
using var svc=new AgentServices{Config=config,Sessions=new SessionManager(config),State=new SessionState(),Capture=capture,Input=input,HttpsHost=tls?.Host};
var builder=WebApplication.CreateBuilder(new WebApplicationOptions{ContentRootPath=AppContext.BaseDirectory,Args=args});
builder.Logging.ClearProviders(); builder.Services.AddSingleton(svc);
// Linux is published through `tailscale serve`, which terminates HTTPS on the MagicDNS name and
// proxies to this loopback socket. Do not also leave a cleartext wildcard listener behind: the
// firewall is defence in depth, not authority to publish the agent on Wi-Fi/public interfaces.
// Windows has a separate entry point and retains its direct Tailscale/LAN modes.
builder.WebHost.ConfigureKestrel(o=>{o.Limits.MaxRequestBodySize=FileService.MaxUploadBytes;o.ListenLocalhost(config.Port,lo=>{if(tls!=null)lo.UseHttps(tls.Certificate);});});
var app=builder.Build(); WebApi.UseNetworkGuard(app,svc); // Both values, because the interval alone is another gate that never fires. KeepAliveTimeout defaults
// to InfiniteTimeSpan, so ASP.NET sent a keep-alive ping every two minutes and then waited forever for
// a reply that a wedged peer was never going to send — the connection stayed "open" indefinitely, which
// is the server-side half of the stall the client watchdog was added to catch.
app.UseWebSockets(new WebSocketOptions {
    KeepAliveInterval = TimeSpan.FromSeconds(15),
    KeepAliveTimeout  = TimeSpan.FromSeconds(20),
}); app.UseDefaultFiles(); app.UseStaticFiles(); WebApi.Map(app,svc); app.MapFallbackToFile("index.html");
Log.Info($"Linux server listening on loopback: http://127.0.0.1:{config.Port} (publish with Tailscale Serve)");
await app.StartAsync();

// Publish the endpoint only after Kestrel has bound it.  The native MoOS panel
// consumes this small runtime fact instead of guessing the default port or
// independently re-parsing settings.json.  It lives in XDG_RUNTIME_DIR, so a
// stale endpoint cannot survive a reboot; the finally block also removes it on
// a clean stop.  Isolated test/cloud instances deliberately do not overwrite
// the desktop instance's well-known endpoint.
string? endpointPath = null;
try
{
    var runtimeDir = Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR");
    if (string.IsNullOrEmpty(isolatedDataDir)
        && !string.IsNullOrEmpty(runtimeDir)
        && Path.IsPathFullyQualified(runtimeDir))
    {
        var endpointDir = Path.Combine(runtimeDir, "mo-remote");
        Directory.CreateDirectory(endpointDir);
        endpointPath = Path.Combine(endpointDir, "endpoint.json");
        var endpointTmp = endpointPath + $".{Environment.ProcessId}.tmp";
        File.WriteAllText(endpointTmp, JsonSerializer.Serialize(new
        {
            schema = 1,
            pid = Environment.ProcessId,
            port = config.Port,
        }));
        if (OperatingSystem.IsLinux())
            File.SetUnixFileMode(endpointTmp, UnixFileMode.UserRead | UnixFileMode.UserWrite);
        File.Move(endpointTmp, endpointPath, true);
    }
    await app.WaitForShutdownAsync();
}
finally
{
    if (endpointPath is not null)
    {
        try { File.Delete(endpointPath); }
        catch (IOException ex) { Log.Warn("Could not remove the runtime endpoint: " + ex.Message); }
    }
}
// The entry point returns int now (--set-pin above needs a distinct exit code for "that PIN is too
// short" so a script can tell it from success), so every path has to produce one.
return 0;

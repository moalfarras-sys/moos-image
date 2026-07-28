using System.Windows.Forms;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using MoRemote;

// An explicit [STAThread] entry point is required: WinForms clipboard / OLE calls
// (e.g. "Copy access URL") only work on a single-threaded-apartment UI thread.
internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        // --service: run as the LocalSystem Windows Service supervisor (Session 0, no tray). Blocks.
        if (args.Contains("--service", StringComparer.OrdinalIgnoreCase))
        {
            Log.Init();
            try { ServiceHost.Run(); }
            catch (Exception ex) { Log.Error("Service host crashed.", ex); }
            return;
        }

        // --worker: the headless capture/input/web instance the service spawns inside the active
        // session (as SYSTEM). No tray/banner; input follows the current input desktop.
        bool worker = args.Contains("--worker", StringComparer.OrdinalIgnoreCase);

        // One-shot elevated actions (triggered from the tray, then relaunched via UAC).
        bool applyAdmin = args.Contains("--apply-admin", StringComparer.OrdinalIgnoreCase);
        bool removeAdmin = args.Contains("--remove-admin", StringComparer.OrdinalIgnoreCase);

        // Single instance — auto-start could otherwise launch twice. The service worker skips this:
        // the supervisor guarantees a single worker and may respawn it on desktop switches.
        Mutex? mutex = null;
        if (!worker)
        {
            mutex = new Mutex(true, @"Global\MoRemotePersonal_SingleInstance", out bool isFirst);
            if (!isFirst && (applyAdmin || removeAdmin))
            {
                // We were relaunched elevated while the old (non-elevated) instance is still exiting —
                // wait briefly for it to release the mutex (and free the port) before taking over.
                try { isFirst = mutex.WaitOne(TimeSpan.FromSeconds(10)); }
                catch (AbandonedMutexException) { isFirst = true; }
            }
            if (!isFirst)
            {
                MessageBox.Show("Mo Remote Personal is already running (see the tray icon).",
                    AppInfo.Name, MessageBoxButtons.OK, MessageBoxIcon.Information);
                mutex.Dispose();
                return;
            }
        }
        if (worker) InputInjector.FollowInputDesktop = true;

        Log.Init();
        AppDomain.CurrentDomain.UnhandledException += (_, e) =>
            Log.Error("Unhandled exception: " + (e.ExceptionObject as Exception)?.ToString());

        // Apply the requested admin-autostart change now that we're elevated.
        if (applyAdmin) { try { ElevationManager.ApplyAdminAutostart(); } catch (Exception ex) { Log.Error("Apply admin failed.", ex); } }
        if (removeAdmin) { try { ElevationManager.RemoveAdminAutostart(); } catch (Exception ex) { Log.Error("Remove admin failed.", ex); } }

        var config = AppConfig.Load();
        UserSettings.Apply(config); // apply user-editable settings.json (port, allowLan, …)

        // Restore the "Never lock — stay reachable" state chosen last time.
        if (config.NeverLock)
        {
            PowerManager.SetAlwaysAwake(true);
            PowerManager.PreventLock(true);
        }

        var tls = TlsManager.TryLoad(); // optional HTTPS via a Tailscale cert (else plain HTTP)
        var capture = new ScreenCapture();
        var services = new AgentServices
        {
            Config = config,
            Sessions = new SessionManager(config),
            State = new SessionState(),
            Capture = capture,
            Input = new InputInjector(capture),
            HttpsHost = tls?.Host,
        };

        // ---------------- Web host (Kestrel) ----------------
        var builder = WebApplication.CreateBuilder(new WebApplicationOptions
        {
            ContentRootPath = AppContext.BaseDirectory, // wwwroot sits next to the exe
        });
        builder.Logging.ClearProviders(); // tray app: log to our own file instead
        builder.Services.AddSingleton(services);
        LogTailscale();
        // Bind all interfaces (the NetworkGuard middleware is the real boundary). Use the Tailscale
        // cert for HTTPS when configured, else plain HTTP.
        builder.WebHost.ConfigureKestrel(o =>
        {
            o.Limits.MaxRequestBodySize = 2_000_000_000; // allow large file uploads
            o.ListenAnyIP(config.Port, lo => { if (tls != null) lo.UseHttps(tls.Certificate); });
        });

        var app = builder.Build();
        WebApi.UseNetworkGuard(app, services);   // gate everything, incl. static files

        // Never cache index.html / manifest / service worker so UI updates always reach the
        // phone (JS/CSS assets are content-hashed, so the browser caches those safely).
        app.Use(async (ctx, next) =>
        {
            ctx.Response.OnStarting(() =>
            {
                var p = ctx.Request.Path.Value ?? "";
                if (p == "/" || p.EndsWith(".html") || p.EndsWith("manifest.webmanifest") || p.EndsWith("sw.js"))
                    ctx.Response.Headers["Cache-Control"] = "no-cache, no-store, must-revalidate";
                return Task.CompletedTask;
            });
            await next();
        });

        // See the Linux Program.cs for the reasoning: KeepAliveTimeout defaults to InfiniteTimeSpan, so
        // the interval on its own sends a ping and then waits for ever. Both, or neither works.
        app.UseWebSockets(new WebSocketOptions {
            KeepAliveInterval = TimeSpan.FromSeconds(15),
            KeepAliveTimeout  = TimeSpan.FromSeconds(20),
        });
        app.UseDefaultFiles();
        app.UseStaticFiles();
        WebApi.Map(app, services);
        app.MapFallbackToFile("index.html");     // SPA routing fallback

        try
        {
            app.Start();
        }
        catch (Exception ex)
        {
            Log.Error("Web server failed to start.", ex);
            if (!worker)
                MessageBox.Show(
                    $"Could not start the server on port {config.Port}.\n\n{ex.Message}\n\n" +
                    "The port may be in use. Change it in settings.json or free the port, then restart.",
                    AppInfo.Name, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        Log.Info($"Server listening. Access URL: {services.AccessUrl}");

        if (worker)
        {
            // Headless service worker (spawned by the supervisor as SYSTEM in the active session).
            // No tray/banner in this mode; run until the supervisor terminates us on a session/desktop switch.
            Log.Info("Running headless as service worker.");
            AppDomain.CurrentDomain.ProcessExit += (_, _) =>
            { try { app.StopAsync(TimeSpan.FromSeconds(2)).GetAwaiter().GetResult(); } catch { } };
            new ManualResetEventSlim(false).Wait();
            return;
        }

        // ---------------- Tray UI (WinForms message loop, STA) ----------------
        // DPI awareness comes from app.manifest (PerMonitorV2, applied at load).
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        using var tray = new TrayApp(services, shutdownHost: () =>
        {
            try { app.StopAsync(TimeSpan.FromSeconds(2)).GetAwaiter().GetResult(); } catch { }
        });

        Application.Run(tray); // blocks until tray Exit

        services.Input.Dispose();
        services.Capture.Dispose();
        mutex?.Dispose();
        Log.Info("Shut down.");
    }

    // ---------------- helpers ----------------
    private static void LogTailscale()
    {
        // We bind ALL interfaces (see ConfigureKestrel). The real security boundary is the
        // NetworkGuard middleware, which accepts only Tailscale (100.64.0.0/10) + loopback (and
        // private LAN only when AllowLan). Binding to 0.0.0.0 means the agent becomes reachable
        // the moment Tailscale connects — no restart if Tailscale starts after the app or its IP changes.
        var tsIp = NetworkGuard.DetectTailscaleIPv4();
        if (tsIp != null) Log.Info($"Listening on all interfaces. Tailscale IP: {tsIp}.");
        else Log.Warn("Listening on all interfaces. Tailscale not detected yet — it will work as soon as Tailscale connects.");
    }
}

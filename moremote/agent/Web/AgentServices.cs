namespace MoRemote;

/// <summary>The shared singletons, bundled for DI + the tray.</summary>
public sealed class AgentServices
{
    public required AppConfig Config { get; init; }
    public required SessionManager Sessions { get; init; }
    public required SessionState State { get; init; }
    public required ScreenCapture Capture { get; init; }
    public required InputInjector Input { get; init; }
    public AccessTicketStore Tickets { get; } = new();

    /// <summary>When HTTPS is enabled, the Tailscale MagicDNS name the cert is valid for (else null).</summary>
    public string? HttpsHost { get; init; }

    /// <summary>The URL the user opens from the phone (HTTPS MagicDNS name, else Tailscale IP over HTTP).</summary>
    public string AccessUrl
    {
        get
        {
            // Over HTTPS we must use the cert's MagicDNS name (connecting by IP would fail cert validation).
            if (!string.IsNullOrEmpty(HttpsHost)) return $"https://{HttpsHost}:{Config.Port}";
            var ip = NetworkGuard.DetectTailscaleIPv4();
            var host = ip?.ToString() ?? "127.0.0.1";
            return $"http://{host}:{Config.Port}";
        }
    }
}

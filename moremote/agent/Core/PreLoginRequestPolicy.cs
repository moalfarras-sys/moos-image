using System.Text.RegularExpressions;

namespace MoRemote;

/// <summary>Closed HTTP surface for the account greeter. New desktop endpoints
/// remain unavailable until separately reviewed; authentication still belongs
/// to the ordinary Remote session manager and WebSocket handshake.</summary>
public static class PreLoginRequestPolicy
{
    private static readonly Regex Bundle = new(
        @"\A(?:/assets/[A-Za-z0-9][A-Za-z0-9_-]*\.(?:js|css)|/workbox-[A-Za-z0-9_-]+\.js)\z",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    public static bool Allows(string method, string? path)
    {
        if (method == "GET" && path is not null && Bundle.IsMatch(path)) return true;
        return (method, path) is
            ("GET", "/" or "/index.html" or "/manifest.webmanifest" or "/sw.js"
                or "/notification-sw.js" or "/icons/icon-192.png" or "/icons/icon-512.png"
                or "/icons/maskable-512.png" or "/icons/apple-touch-icon.png" or "/icons/favicon.ico"
                or "/icons/favicon-64.png" or "/icons/brand-logo.png"
                or "/ws" or "/api/status" or "/api/session") or
            ("POST", "/api/login" or "/api/devices/resume" or "/api/logout");
    }
}

using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace MoRemote;

/// <summary>
/// Enforces "Tailscale-only" access. Tailscale hands out IPs in the CGNAT range
/// 100.64.0.0/10. We always allow that range + loopback, optionally LAN for testing,
/// and never the public internet.
/// </summary>
public static class NetworkGuard
{
    /// <summary>The machine's Tailscale IPv4 (100.64.0.0/10), or null if Tailscale isn't up.</summary>
    public static IPAddress? DetectTailscaleIPv4()
    {
        try
        {
            IPAddress? namedMatch = null;
            IPAddress? anyMatch = null;

            foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (nic.OperationalStatus != OperationalStatus.Up) continue;
                bool looksTailscale =
                    nic.Name.Contains("tailscale", StringComparison.OrdinalIgnoreCase) ||
                    nic.Description.Contains("tailscale", StringComparison.OrdinalIgnoreCase);

                foreach (var ua in nic.GetIPProperties().UnicastAddresses)
                {
                    if (ua.Address.AddressFamily != AddressFamily.InterNetwork) continue;
                    if (!IsCgnat(ua.Address)) continue;
                    if (looksTailscale) { namedMatch ??= ua.Address; }
                    else { anyMatch ??= ua.Address; }
                }
            }
            return namedMatch ?? anyMatch;
        }
        catch (Exception ex)
        {
            Log.Error("Tailscale IP detection failed.", ex);
            return null;
        }
    }

    /// <summary>Is this remote endpoint allowed to talk to us?</summary>
    public static bool IsAllowed(IPAddress? remote, bool allowLan)
    {
        if (remote == null) return false;
        if (remote.IsIPv4MappedToIPv6) remote = remote.MapToIPv4();

        if (IPAddress.IsLoopback(remote)) return true;
        if (IsTailscale(remote)) return true;
        if (allowLan && IsPrivateLan(remote)) return true;
        return false;
    }

    public static bool IsTailscale(IPAddress ip)
    {
        if (ip.IsIPv4MappedToIPv6) ip = ip.MapToIPv4();
        if (ip.AddressFamily == AddressFamily.InterNetwork) return IsCgnat(ip);
        if (ip.AddressFamily == AddressFamily.InterNetworkV6)
        {
            // Tailscale ULA: fd7a:115c:a1e0::/48
            var b = ip.GetAddressBytes();
            return b[0] == 0xfd && b[1] == 0x7a && b[2] == 0x11 && b[3] == 0x5c && b[4] == 0xa1 && b[5] == 0xe0;
        }
        return false;
    }

    // 100.64.0.0/10  ->  first octet 100, second octet 64..127
    private static bool IsCgnat(IPAddress ip)
    {
        var b = ip.GetAddressBytes();
        return b.Length == 4 && b[0] == 100 && b[1] >= 64 && b[1] <= 127;
    }

    private static bool IsPrivateLan(IPAddress ip)
    {
        var b = ip.GetAddressBytes();
        if (b.Length != 4) return false;
        if (b[0] == 10) return true;                          // 10.0.0.0/8
        if (b[0] == 172 && b[1] >= 16 && b[1] <= 31) return true; // 172.16.0.0/12
        if (b[0] == 192 && b[1] == 168) return true;          // 192.168.0.0/16
        if (b[0] == 169 && b[1] == 254) return true;          // link-local
        return false;
    }
}

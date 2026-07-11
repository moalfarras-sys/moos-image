using System.Diagnostics;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;

namespace MoRemote;

public sealed class TlsInfo
{
    public required X509Certificate2 Certificate { get; init; }
    public required string Host { get; init; } // MagicDNS name the cert is valid for
}

/// <summary>
/// Optional HTTPS using a real certificate from Tailscale (`tailscale cert`). Serving over
/// https://&lt;machine&gt;.&lt;tailnet&gt;.ts.net unlocks secure-context browser APIs on the phone
/// (native clipboard, offline PWA / service worker) and encrypts on top of Tailscale's own
/// encryption. Off by default; the cert lives in %LOCALAPPDATA%\MoRemotePersonal\tls.
/// </summary>
public static class TlsManager
{
    public static string TlsDir => Path.Combine(Paths.DataDir, "tls");
    private static string CertPath => Path.Combine(TlsDir, "cert.crt");
    private static string KeyPath => Path.Combine(TlsDir, "cert.key");
    private static string HostPath => Path.Combine(TlsDir, "host.txt");

    public static bool IsConfigured() => File.Exists(CertPath) && File.Exists(KeyPath) && File.Exists(HostPath);

    /// <summary>Load the cert for Kestrel, or null (→ plain HTTP) if not configured / unreadable.</summary>
    public static TlsInfo? TryLoad()
    {
        try
        {
            if (!IsConfigured()) return null;
            var host = File.ReadAllText(HostPath).Trim();
            // PEM → ephemeral cert → re-import as PKCS#12 so Windows/SChannel accepts the private key.
            using var ephemeral = X509Certificate2.CreateFromPemFile(CertPath, KeyPath);
            var cert = X509CertificateLoader.LoadPkcs12(ephemeral.Export(X509ContentType.Pkcs12), null);
            Log.Info($"HTTPS enabled for https://{host}.");
            return new TlsInfo { Certificate = cert, Host = host };
        }
        catch (Exception ex)
        {
            Log.Error("TLS certificate load failed; serving plain HTTP.", ex);
            return null;
        }
    }

    /// <summary>Obtain/refresh the cert via the Tailscale CLI. Returns (ok, host-or-error-message).</summary>
    public static (bool ok, string msg) Provision()
    {
        try
        {
            var host = GetMagicDnsName();
            if (string.IsNullOrEmpty(host))
                return (false, "Couldn't read the Tailscale MagicDNS name. Enable MagicDNS + HTTPS in the Tailscale admin console, then try again.");

            Directory.CreateDirectory(TlsDir);
            var psi = new ProcessStartInfo("tailscale",
                $"cert --cert-file \"{CertPath}\" --key-file \"{KeyPath}\" {host}")
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardError = true,
                RedirectStandardOutput = true,
            };
            using var p = Process.Start(psi);
            if (p == null) return (false, "Couldn't launch the tailscale CLI. Is Tailscale installed and on PATH?");
            var err = p.StandardError.ReadToEnd();
            p.WaitForExit(30_000);
            if (p.ExitCode != 0)
                return (false, "tailscale cert failed:\n" + err.Trim());

            File.WriteAllText(HostPath, host);
            Log.Info($"HTTPS cert provisioned for {host}.");
            return (true, host);
        }
        catch (Exception ex) { return (false, ex.Message); }
    }

    /// <summary>Stop serving HTTPS (keeps the cert files; just no longer loaded on next start).</summary>
    public static void Disable()
    {
        try { if (File.Exists(HostPath)) File.Delete(HostPath); }
        catch (Exception ex) { Log.Warn("TLS disable failed: " + ex.Message); }
    }

    private static string? GetMagicDnsName()
    {
        try
        {
            var psi = new ProcessStartInfo("tailscale", "status --json")
            { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true };
            using var p = Process.Start(psi);
            if (p == null) return null;
            var json = p.StandardOutput.ReadToEnd();
            p.WaitForExit(10_000);
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("Self", out var self) &&
                self.TryGetProperty("DNSName", out var dns))
                return dns.GetString()?.TrimEnd('.');
            return null;
        }
        catch { return null; }
    }
}

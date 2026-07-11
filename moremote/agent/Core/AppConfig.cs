using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MoRemote;

/// <summary>
/// All settings + security state. Persisted locally, DPAPI-encrypted to the current
/// Windows user. Nothing here ever leaves the machine.
/// </summary>
public sealed class AppConfig
{
    // ---- Network ----
    public int Port { get; set; } = 8765;

    /// <summary>
    /// false (default, most secure): bind to the Tailscale IP only and accept connections
    /// solely from the Tailscale CGNAT range (100.64.0.0/10) + loopback.
    /// true: also bind LAN and accept private LAN ranges — handy for same-Wi-Fi testing.
    /// The public internet is never accepted in either mode.
    /// </summary>
    public bool AllowLan { get; set; } = false;

    // ---- Security ----
    public string PinHash { get; set; } = "";          // Argon2id encoded string ("" => first run)
    public int TokenTtlMinutes { get; set; } = 60;     // sliding session token lifetime
    public int IdleTimeoutMinutes { get; set; } = 20;  // disconnect a session after this much no-input idle
    public int FailedAttempts { get; set; } = 0;       // brute-force counter
    public long LockoutUntilUnix { get; set; } = 0;    // epoch seconds; 0 = not locked

    // ---- Streaming defaults (the controller may override per session) ----
    public int JpegQuality { get; set; } = 60;         // 1..100
    public int MaxFps { get; set; } = 18;              // capture cap
    public bool ShowRemoteCursor { get; set; } = true;

    // ---- Convenience ----
    /// <summary>"Never lock — stay reachable" toggle (tray). Applied on startup when true.</summary>
    public bool NeverLock { get; set; } = false;

    [JsonIgnore] public bool FirstRun => string.IsNullOrEmpty(PinHash);

    // ---------------------------------------------------------------------

    private static readonly object Gate = new();
    // Extra DPAPI entropy so the blob is bound to this app, not just the user account.
    private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("MoRemotePersonal::config::v1");

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public static AppConfig Load()
    {
        lock (Gate)
        {
            try
            {
                if (File.Exists(Paths.ConfigFile))
                {
                    var encrypted = File.ReadAllBytes(Paths.ConfigFile);
                    var json = ProtectedData.Unprotect(encrypted, Entropy, DataProtectionScope.CurrentUser);
                    var cfg = JsonSerializer.Deserialize<AppConfig>(json, JsonOpts);
                    if (cfg != null)
                    {
                        Log.Info("Config loaded.");
                        return cfg;
                    }
                }
            }
            catch (Exception ex)
            {
                Log.Error("Failed to load config (starting fresh).", ex);
            }

            var fresh = new AppConfig();
            fresh.Save();
            Log.Info("Created new config (first run).");
            return fresh;
        }
    }

    public void Save()
    {
        lock (Gate)
        {
            try
            {
                Directory.CreateDirectory(Paths.DataDir);
                var json = JsonSerializer.SerializeToUtf8Bytes(this, JsonOpts);
                var encrypted = ProtectedData.Protect(json, Entropy, DataProtectionScope.CurrentUser);
                // Atomic-ish write: temp then move.
                var tmp = Paths.ConfigFile + ".tmp";
                File.WriteAllBytes(tmp, encrypted);
                File.Copy(tmp, Paths.ConfigFile, overwrite: true);
                File.Delete(tmp);
            }
            catch (Exception ex)
            {
                Log.Error("Failed to save config.", ex);
            }
        }
    }
}

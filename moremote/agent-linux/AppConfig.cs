using System.Text.Json;
using System.Text.Json.Serialization;

namespace MoRemote;

public sealed class AppConfig
{
    public int Port { get; set; } = 8765;
    public bool AllowLan { get; set; }
    public string PinHash { get; set; } = "";
    public int TokenTtlMinutes { get; set; } = 60;
    public int IdleTimeoutMinutes { get; set; } = 20;
    public int FailedAttempts { get; set; }
    public long LockoutUntilUnix { get; set; }
    public int JpegQuality { get; set; } = 62;
    public int MaxFps { get; set; } = 30;
    public bool ShowRemoteCursor { get; set; } = true;

    /// <summary>
    /// Paint the real cursor into the video. Costs a full-frame re-encode on every pointer move
    /// (~8 Mbit/s of pure cursor), so by default we hide it and the phone draws its own at the
    /// position it commanded — which is both free and instant.
    /// </summary>
    public bool EmbedCursor { get; set; }

    public bool NeverLock { get; set; }
    [JsonIgnore] public bool FirstRun => string.IsNullOrEmpty(PinHash);

    /// <summary>The config the process started with — read by PortalBridge when it spawns the helper.</summary>
    [JsonIgnore] public static AppConfig Current { get; private set; } = new();
    private static readonly object Gate = new();
    private static readonly JsonSerializerOptions Opts = new() { WriteIndented = true };

    public static AppConfig Load()
    {
        lock (Gate)
        {
            try
            {
                if (File.Exists(Paths.ConfigFile))
                    return Current = JsonSerializer.Deserialize<AppConfig>(File.ReadAllBytes(Paths.ConfigFile), Opts) ?? new();
            }
            catch (Exception ex) { Log.Error("Failed to load config.", ex); }
            var cfg = new AppConfig(); cfg.Save(); return Current = cfg;
        }
    }
    public void Save()
    {
        lock (Gate)
        {
            Directory.CreateDirectory(Paths.DataDir);
            var tmp = Paths.ConfigFile + ".tmp";
            File.WriteAllBytes(tmp, JsonSerializer.SerializeToUtf8Bytes(this, Opts));
            if (OperatingSystem.IsLinux()) File.SetUnixFileMode(tmp, UnixFileMode.UserRead | UnixFileMode.UserWrite);
            File.Move(tmp, Paths.ConfigFile, true);
        }
    }
}

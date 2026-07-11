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
    public int JpegQuality { get; set; } = 60;
    public int MaxFps { get; set; } = 8;
    public bool ShowRemoteCursor { get; set; } = true;
    public bool NeverLock { get; set; }
    [JsonIgnore] public bool FirstRun => string.IsNullOrEmpty(PinHash);
    private static readonly object Gate = new();
    private static readonly JsonSerializerOptions Opts = new() { WriteIndented = true };

    public static AppConfig Load()
    {
        lock (Gate)
        {
            try { if (File.Exists(Paths.ConfigFile)) return JsonSerializer.Deserialize<AppConfig>(File.ReadAllBytes(Paths.ConfigFile), Opts) ?? new(); }
            catch (Exception ex) { Log.Error("Failed to load config.", ex); }
            var cfg = new AppConfig(); cfg.Save(); return cfg;
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

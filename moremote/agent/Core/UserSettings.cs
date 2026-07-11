using System.Text.Json;
using System.Text.Json.Serialization;

namespace MoRemote;

/// <summary>
/// A plain-text, user-editable settings file (DataDir\settings.json) for non-secret options
/// like the port. The PIN hash lives only in the DPAPI-encrypted config.dat — never here.
/// Read at every launch; created with current defaults if missing.
/// </summary>
public sealed class UserSettings
{
    [JsonPropertyName("_comment")]
    public string Comment { get; set; } =
        "Mo Remote Personal settings. Edit and restart the app. The PIN is stored separately and encrypted.";

    [JsonPropertyName("port")] public int port { get; set; }
    [JsonPropertyName("allowLan")] public bool allowLan { get; set; }
    [JsonPropertyName("jpegQuality")] public int jpegQuality { get; set; }
    [JsonPropertyName("maxFps")] public int maxFps { get; set; }
    [JsonPropertyName("tokenTtlMinutes")] public int tokenTtlMinutes { get; set; }
    [JsonPropertyName("idleTimeoutMinutes")] public int idleTimeoutMinutes { get; set; }
    [JsonPropertyName("showRemoteCursor")] public bool showRemoteCursor { get; set; }

    private static string FilePath => Path.Combine(Paths.DataDir, "settings.json");

    /// <summary>Apply settings.json onto the config (creating the file from defaults if absent).</summary>
    public static void Apply(AppConfig cfg)
    {
        try
        {
            Directory.CreateDirectory(Paths.DataDir);
            if (File.Exists(FilePath))
            {
                var opts = new JsonSerializerOptions
                {
                    ReadCommentHandling = JsonCommentHandling.Skip,
                    AllowTrailingCommas = true,
                    PropertyNameCaseInsensitive = true,
                };
                var s = JsonSerializer.Deserialize<UserSettings>(File.ReadAllText(FilePath), opts);
                if (s != null)
                {
                    if (s.port is > 0 and < 65536) cfg.Port = s.port;
                    cfg.AllowLan = s.allowLan;
                    if (s.jpegQuality is >= 10 and <= 95) cfg.JpegQuality = s.jpegQuality;
                    if (s.maxFps is >= 1 and <= 30) cfg.MaxFps = s.maxFps;
                    if (s.tokenTtlMinutes is >= 5 and <= 1440) cfg.TokenTtlMinutes = s.tokenTtlMinutes;
                    if (s.idleTimeoutMinutes is >= 1 and <= 1440) cfg.IdleTimeoutMinutes = s.idleTimeoutMinutes;
                    cfg.ShowRemoteCursor = s.showRemoteCursor;
                    Log.Info($"Applied settings.json (port={cfg.Port}, allowLan={cfg.AllowLan}).");
                }
            }
            else
            {
                Write(cfg);
                Log.Info("Created default settings.json.");
            }
        }
        catch (Exception ex)
        {
            Log.Error("Failed to read settings.json (using defaults).", ex);
        }
    }

    private static void Write(AppConfig cfg)
    {
        var s = new UserSettings
        {
            port = cfg.Port,
            allowLan = cfg.AllowLan,
            jpegQuality = cfg.JpegQuality,
            maxFps = cfg.MaxFps,
            tokenTtlMinutes = cfg.TokenTtlMinutes,
            idleTimeoutMinutes = cfg.IdleTimeoutMinutes,
            showRemoteCursor = cfg.ShowRemoteCursor,
        };
        File.WriteAllText(FilePath, JsonSerializer.Serialize(s, new JsonSerializerOptions { WriteIndented = true }));
    }
}

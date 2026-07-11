using System.Text;

namespace MoRemote;

/// <summary>
/// Minimal thread-safe file logger. Writes to %LOCALAPPDATA%\MoRemotePersonal\log.txt.
/// A tray app has no console, so a log file is how the user troubleshoots.
/// </summary>
public static class Log
{
    private static readonly object Gate = new();
    private static string _path = Path.Combine(Paths.DataDir, "log.txt");

    public static void Init()
    {
        try
        {
            Directory.CreateDirectory(Paths.DataDir);
            // Roll the log if it grows past ~1 MB.
            if (File.Exists(_path) && new FileInfo(_path).Length > 1_000_000)
                File.Delete(_path);
            Info($"==== Mo Remote Personal starting (v{AppInfo.Version}) ====");
        }
        catch { /* logging must never crash the app */ }
    }

    public static void Info(string msg) => Write("INFO", msg);
    public static void Warn(string msg) => Write("WARN", msg);
    public static void Error(string msg) => Write("ERROR", msg);

    public static void Error(string msg, Exception ex) =>
        Write("ERROR", msg + " :: " + ex.GetType().Name + ": " + ex.Message);

    private static void Write(string level, string msg)
    {
        var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} [{level}] {msg}{Environment.NewLine}";
        lock (Gate)
        {
            try { File.AppendAllText(_path, line, Encoding.UTF8); } catch { }
        }
    }
}

public static class AppInfo
{
    public const string Version = "1.0.0";
    public const string Name = "Mo Remote Personal";
}

/// <summary>Well-known local paths. Everything stays on this machine.</summary>
public static class Paths
{
    public static string DataDir { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "MoRemotePersonal");

    public static string ConfigFile => Path.Combine(DataDir, "config.dat");
}

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
    /// <summary>
    /// Where the PIN hash and the settings live.
    ///
    /// WHY THIS IS NOT ONE LINE ANY MORE, AND WHY THE ONE LINE WAS A SECURITY BUG ON A NEW ACCOUNT
    ///
    /// It used to be Path.Combine(GetFolderPath(LocalApplicationData), "MoRemotePersonal"). That is
    /// correct right up until GetFolderPath returns "" — and measured on .NET 10 / Fedora 44, it
    /// returns exactly that when XDG_DATA_HOME is unset and $HOME/.local/share DOES NOT YET EXIST:
    ///
    ///     HOME=/tmp/nolocal  XDG_DATA_HOME=(unset)
    ///       LocalApplicationData = ''   rooted=False
    ///
    /// Path.Combine("", "MoRemotePersonal") is not an error. It is the RELATIVE path
    /// "MoRemotePersonal", so the agent reads and writes its config in whatever directory it was
    /// started from. And the consequence is not a missing file, which would at least be loud — it is
    /// a BRAND NEW EMPTY CONFIG. No PinHash means FirstRun is true, which means /api/setup stops
    /// answering 409 and starts accepting a new PIN from whoever reaches the URL first. The desktop
    /// keeps running and streaming, and is now claimable by anyone who can route to it.
    ///
    /// The trigger is "a home directory that has never had a .local/share made in it", which is not
    /// an exotic state: it is EVERY freshly created account, which is exactly what moos-cloud-dev
    /// makes. So the machine class this matters most on is the one MoOS Cloud is built out of.
    ///
    /// (Note for anyone re-testing: with HOME unset ENTIRELY, .NET falls back to getpwuid and does
    /// return a rooted path, so that case was never the broken one and the throw below is defence in
    /// depth rather than an observed path. The broken case is a HOME that exists and is bare.)
    ///
    /// So: try the platform answer, fall back to the XDG spec's own default, and if neither yields
    /// an ABSOLUTE path, throw. A config path the process cannot name is not something to guess at.
    /// </summary>
    public static string DataDir { get; } = ResolveDataDir();

    private static string ResolveDataDir()
    {
        // Explicit service/container boundary. HOME is not a reliable isolation
        // knob for a process whose uid still resolves to an existing passwd
        // entry: .NET may return that account's real LocalApplicationData even
        // when HOME/XDG_DATA_HOME were replaced. Accept only an absolute path so
        // tests and isolated cloud units can never fall back to the working tree.
        var explicitDir = Environment.GetEnvironmentVariable("MOREMOTE_DATA_DIR");
        if (!string.IsNullOrEmpty(explicitDir))
        {
            if (!Path.IsPathFullyQualified(explicitDir))
                throw new InvalidOperationException(
                    "MOREMOTE_DATA_DIR must be an absolute path; refusing a relative " +
                    "configuration directory that could expose first-run setup.");
            return Path.GetFullPath(explicitDir);
        }
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (string.IsNullOrEmpty(local))
        {
            // The XDG Base Directory spec's own default, which is what GetFolderPath is trying to
            // report in the first place.
            var xdg = Environment.GetEnvironmentVariable("XDG_DATA_HOME");
            var home = Environment.GetEnvironmentVariable("HOME");
            local = !string.IsNullOrEmpty(xdg) ? xdg
                  : !string.IsNullOrEmpty(home) ? Path.Combine(home, ".local", "share")
                  : "";
        }
        var dir = string.IsNullOrEmpty(local) ? "" : Path.Combine(local, "MoRemotePersonal");
        if (!Path.IsPathRooted(dir))
            throw new InvalidOperationException(
                "Mo Remote cannot determine where to keep its configuration: neither " +
                "XDG_DATA_HOME nor HOME is set. Refusing to fall back to the current directory — " +
                "that would create an unconfigured config and leave the PIN open to whoever asks first.");
        return dir;
    }

    public static string ConfigFile => Path.Combine(DataDir, "config.dat");
}

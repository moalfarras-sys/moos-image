using System.Diagnostics;

namespace MoRemote;

/// <summary>
/// Fixed-argument session and power actions for the MoOS Plasma session.
/// Never use a shell here: this endpoint is remotely reachable after authentication.
/// </summary>
public static class PowerActions
{
    private const string EditionFile = "/usr/lib/moos/edition";
    public readonly record struct Command(string FileName, string[] Arguments);

    public static bool HostPowerAllowed => HostPowerAllowedAt(EditionFile);

    internal static bool HostPowerAllowedAt(string editionFile)
    {
        try
        {
            return !File.Exists(editionFile)
                || File.ReadAllText(editionFile).Trim() != "moos-cloud";
        }
        catch
        {
            // A marker that exists but cannot be verified is not permission to power off a
            // potentially multi-user host. Desktop images install a readable marker at build time.
            return !File.Exists(editionFile);
        }
    }

    public static bool CanRun(string action)
    {
        var normalized = action.ToLowerInvariant();
        return Resolve(normalized) is not null
            && (HostPowerAllowed || normalized is "lock" or "signout" or "logoff");
    }

    public static Command? Resolve(string action) => action.ToLowerInvariant() switch
    {
        // The agent already owns the user's Plasma session bus. Asking Plasma to lock/log out
        // targets that exact desktop; loginctl without a session id is unreliable from a
        // lingering systemd --user service, and lock-sessions would affect other cloud users.
        "lock" => new("/usr/bin/qdbus-qt6",
            ["org.freedesktop.ScreenSaver", "/ScreenSaver", "Lock"]),
        "signout" or "logoff" => new("/usr/bin/qdbus-qt6",
            ["org.kde.Shutdown", "/Shutdown", "logout"]),

        // --no-block makes logind queue the operation and return an exit status before suspend
        // or shutdown tears down this HTTP request. Polkit still applies its normal policy.
        "sleep" => new("/usr/bin/systemctl", ["--no-block", "suspend"]),
        "restart" => new("/usr/bin/systemctl", ["--no-block", "reboot"]),
        "shutdown" => new("/usr/bin/systemctl", ["--no-block", "poweroff"]),
        _ => null,
    };

    public static bool Run(string action)
    {
        if (!CanRun(action))
        {
            Log.Warn($"Power action '{action}' is unavailable on this MoOS edition.");
            return false;
        }
        var command = Resolve(action);
        if (command is null)
        {
            Log.Warn($"Unknown power action '{action}'.");
            return false;
        }

        return Execute(command.Value, action);
    }

    internal static bool Execute(Command command, string action, int timeoutMs = 5_000)
    {
        try
        {
            using var process = Process.Start(new ProcessStartInfo
            {
                FileName = command.FileName,
                UseShellExecute = false,
                CreateNoWindow = true,
            }.WithArguments(command.Arguments));

            if (process is null)
                return false;
            if (!process.WaitForExit(timeoutMs))
            {
                process.Kill(entireProcessTree: true);
                Log.Warn($"Power action '{action}' timed out before it was accepted.");
                return false;
            }
            if (process.ExitCode != 0)
            {
                Log.Warn($"Power action '{action}' was rejected (exit {process.ExitCode}).");
                return false;
            }
            return true;
        }
        catch (Exception ex)
        {
            Log.Error($"Power action '{action}' failed.", ex);
            return false;
        }
    }

    private static ProcessStartInfo WithArguments(this ProcessStartInfo startInfo,
        IEnumerable<string> arguments)
    {
        foreach (var argument in arguments)
            startInfo.ArgumentList.Add(argument);
        return startInfo;
    }
}

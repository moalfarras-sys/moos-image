using System.Diagnostics;
using System.Runtime.InteropServices;

namespace MoRemote;

/// <summary>
/// Remote power / session actions. Only ever run on an explicit, authenticated button press
/// from the phone (over Tailscale + PIN). The drastic ones (restart / shutdown / sign-out)
/// are confirmed on the phone before they reach here.
/// </summary>
public static class PowerActions
{
    internal readonly record struct Command(string FileName, string[] Arguments);

    public static bool HostPowerAllowed => true;

    public static bool CanRun(string action) => action.ToLowerInvariant() is
        "lock" or "sleep" or "signout" or "logoff" or "restart" or "shutdown";

    public static bool Run(string action)
    {
        if (!CanRun(action)) return false;
        try
        {
            switch (action.ToLowerInvariant())
            {
                case "lock": return LockWorkStation();
                case "sleep": return SetSuspendState(false, false, false);
                case "signout":
                case "logoff": return Execute(ShutdownCommand("/l"), action);
                case "restart": return Execute(ShutdownCommand("/r", "/t", "0"), action);
                case "shutdown": return Execute(ShutdownCommand("/s", "/t", "0"), action);
                default:
                    Log.Warn($"Unknown power action '{action}'.");
                    return false;
            }
        }
        catch (Exception ex) { Log.Error($"Power action '{action}' failed.", ex); return false; }
    }

    private static Command ShutdownCommand(params string[] arguments) =>
        new(Path.Combine(Environment.SystemDirectory, "shutdown.exe"), arguments);

    internal static bool Execute(Command command, string action, int timeoutMs = 5_000)
    {
        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = command.FileName,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (var argument in command.Arguments)
                startInfo.ArgumentList.Add(argument);

            using var process = Process.Start(startInfo);
            if (process is null)
            {
                Log.Warn($"Power action '{action}' could not start.");
                return false;
            }
            if (!process.WaitForExit(timeoutMs))
            {
                try { process.Kill(entireProcessTree: true); } catch { }
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

    [DllImport("user32.dll", SetLastError = true)] private static extern bool LockWorkStation();
    [DllImport("powrprof.dll", SetLastError = true)]
    private static extern bool SetSuspendState(bool hibernate, bool forceCritical, bool disableWakeEvent);
}

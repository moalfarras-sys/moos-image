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
                case "logoff": Shell("shutdown", "/l"); return true;
                case "restart": Shell("shutdown", "/r /t 0"); return true;
                case "shutdown": Shell("shutdown", "/s /t 0"); return true;
                default:
                    Log.Warn($"Unknown power action '{action}'.");
                    return false;
            }
        }
        catch (Exception ex) { Log.Error($"Power action '{action}' failed.", ex); return false; }
    }

    private static void Shell(string file, string args) =>
        Process.Start(new ProcessStartInfo(file, args) { UseShellExecute = false, CreateNoWindow = true });

    [DllImport("user32.dll", SetLastError = true)] private static extern bool LockWorkStation();
    [DllImport("powrprof.dll", SetLastError = true)]
    private static extern bool SetSuspendState(bool hibernate, bool forceCritical, bool disableWakeEvent);
}

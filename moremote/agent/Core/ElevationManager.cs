using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;

namespace MoRemote;

/// <summary>
/// Optional "Admin control" mode. Windows UIPI blocks a normal (non-elevated) process from
/// sending mouse/keyboard into windows that run *as administrator* (installers, Task Manager,
/// UAC-elevated apps) — so from the phone those windows look frozen. Running the agent
/// elevated removes that wall. Enabling it registers an elevated **logon Scheduled Task** so
/// the app auto-starts with admin rights at every logon WITHOUT a UAC prompt each time.
/// Off by default (safe). Requires the current user to be a local administrator.
/// </summary>
public static class ElevationManager
{
    private const string TaskName = "MoRemotePersonal Admin Autostart";

    /// <summary>Is this process currently running elevated (admin token)?</summary>
    public static bool IsElevated()
    {
        try
        {
            using var id = WindowsIdentity.GetCurrent();
            return new WindowsPrincipal(id).IsInRole(WindowsBuiltInRole.Administrator);
        }
        catch { return false; }
    }

    /// <summary>Does the elevated logon task exist? (Cheap enough to call once at startup.)</summary>
    public static bool IsAdminAutostartEnabled()
    {
        try { return RunSchtasks($"/Query /TN \"{TaskName}\"") == 0; }
        catch { return false; }
    }

    /// <summary>
    /// Relaunch this exe elevated (UAC), passing an action arg. Returns false if the user
    /// declined the UAC prompt (or it failed) — the caller should stay put in that case.
    /// </summary>
    public static bool RelaunchElevated(string arg)
    {
        var exe = Environment.ProcessPath;
        if (exe == null) return false;
        try
        {
            Process.Start(new ProcessStartInfo(exe)
            {
                UseShellExecute = true, // required for the "runas" verb
                Verb = "runas",
                Arguments = arg,
            });
            return true;
        }
        catch (Win32Exception) { return false; } // 1223 = user cancelled the UAC prompt
        catch (Exception ex) { Log.Error("RelaunchElevated failed.", ex); return false; }
    }

    /// <summary>Must run elevated: create the logon task + drop the per-user Run key (avoid double start).</summary>
    public static void ApplyAdminAutostart()
    {
        var exe = Environment.ProcessPath;
        if (exe == null) return;
        var user = $"{Environment.UserDomainName}\\{Environment.UserName}";
        // ONLOGON + RL HIGHEST => starts elevated in the user's interactive session at logon,
        // with no UAC nag. The escaped inner quotes wrap a path that may contain spaces.
        int rc = RunSchtasks(
            $"/Create /F /RL HIGHEST /SC ONLOGON /RU \"{user}\" /TN \"{TaskName}\" /TR \"\\\"{exe}\\\"\"");
        if (rc == 0)
        {
            StartupManager.Disable(); // the elevated task now handles startup
            Log.Info("Admin autostart enabled (elevated logon task created).");
        }
        else Log.Error($"schtasks /Create failed (exit {rc}).");
    }

    /// <summary>Must run elevated: remove the logon task and restore normal per-user autostart.</summary>
    public static void RemoveAdminAutostart()
    {
        int rc = RunSchtasks($"/Delete /F /TN \"{TaskName}\"");
        StartupManager.Enable(); // back to the normal (non-elevated) Run-key autostart
        Log.Info(rc == 0
            ? "Admin autostart disabled (task removed, normal autostart restored)."
            : $"schtasks /Delete returned {rc} (task may not have existed).");
    }

    private static int RunSchtasks(string args)
    {
        var psi = new ProcessStartInfo("schtasks.exe", args)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        using var p = Process.Start(psi);
        if (p == null) return -1;
        p.WaitForExit(10_000);
        return p.HasExited ? p.ExitCode : -1;
    }
}

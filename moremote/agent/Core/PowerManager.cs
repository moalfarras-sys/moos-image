using System.Runtime.InteropServices;
using Microsoft.Win32;

namespace MoRemote;

/// <summary>
/// Keeps the PC awake / reachable. Two independent sources are OR-ed together:
///   • session    — on while a control session is live (never sleep mid-session).
///   • always     — the user's "Never lock — stay reachable" toggle (persists).
/// Plus <see cref="PreventLock"/> stops the PC from locking/blanking so the phone can
/// always see the screen (Windows hides the lock screen from every app, by design).
/// All settings here are per-user (HKCU) — no admin required, and fully reversible.
/// </summary>
public static class PowerManager
{
    [DllImport("kernel32.dll")]
    private static extern uint SetThreadExecutionState(uint esFlags);

    private const uint ES_CONTINUOUS = 0x80000000;
    private const uint ES_SYSTEM_REQUIRED = 0x00000001;
    private const uint ES_DISPLAY_REQUIRED = 0x00000002;

    private static bool _sessionAwake;
    private static bool _alwaysAwake;
    private static bool _applied;

    /// <summary>On while a control session is active (called from the UI thread).</summary>
    public static void SetSessionAwake(bool on)
    {
        if (on == _sessionAwake) return;
        _sessionAwake = on;
        Apply();
    }

    /// <summary>The persistent "keep reachable" toggle.</summary>
    public static void SetAlwaysAwake(bool on)
    {
        if (on == _alwaysAwake) return;
        _alwaysAwake = on;
        Apply();
    }

    private static void Apply()
    {
        bool want = _sessionAwake || _alwaysAwake;
        if (want == _applied) return;
        _applied = want;
        try
        {
            SetThreadExecutionState(want
                ? ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                : ES_CONTINUOUS);
            Log.Info(want ? "Stay-awake ON." : "Stay-awake OFF.");
        }
        catch (Exception ex) { Log.Warn("SetThreadExecutionState failed: " + ex.Message); }
    }

    /// <summary>
    /// Prevent (or restore) the PC locking, blanking, or running a secure screensaver — so a
    /// remote phone can always see the screen. Per-user only; reversible when toggled off.
    /// </summary>
    public static void PreventLock(bool on)
    {
        try
        {
            using (var desktop = Registry.CurrentUser.CreateSubKey(@"Control Panel\Desktop"))
            {
                // Turn the screensaver off (and its "resume shows the lock screen" flag).
                desktop?.SetValue("ScreenSaveActive", on ? "0" : "1", RegistryValueKind.String);
                desktop?.SetValue("ScreenSaverIsSecure", on ? "0" : "1", RegistryValueKind.String);
            }
            using (var sys = Registry.CurrentUser.CreateSubKey(
                @"Software\Microsoft\Windows\CurrentVersion\Policies\System"))
            {
                // Disable Win+L / Start-menu Lock while reachable (per-user policy, no admin).
                sys?.SetValue("DisableLockWorkstation", on ? 1 : 0, RegistryValueKind.DWord);
            }
            Log.Info(on ? "Never-lock ON (stay reachable)." : "Never-lock OFF (normal locking restored).");
        }
        catch (Exception ex) { Log.Warn("PreventLock failed: " + ex.Message); }
    }
}

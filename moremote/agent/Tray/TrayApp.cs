using System.Diagnostics;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;

namespace MoRemote;

/// <summary>
/// The tray icon + menu and the lifetime owner of the UI. Runs on the WinForms message
/// loop (STA). Exposes status, instant Stop/Pause, Copy URL, Change PIN, start-with-Windows.
/// </summary>
public sealed class TrayApp : ApplicationContext
{
    private readonly AgentServices _svc;
    private readonly Action _shutdownHost;
    private readonly SynchronizationContext _ui;

    private readonly NotifyIcon _tray;
    private readonly SessionBanner _banner;

    private readonly Icon _idleIcon;
    private readonly Icon _activeIcon;

    private ToolStripMenuItem _statusItem = null!;
    private ToolStripMenuItem _pauseItem = null!;
    private ToolStripMenuItem _stopItem = null!;
    private ToolStripMenuItem _startupItem = null!;
    private ToolStripMenuItem _neverLockItem = null!;
    private ToolStripMenuItem _adminItem = null!;
    private ToolStripMenuItem _httpsItem = null!;

    // Cached once at startup — querying the Scheduled Task is a little slow to do every refresh.
    private bool _adminAutostart;

    public TrayApp(AgentServices svc, Action shutdownHost)
    {
        _svc = svc;
        _shutdownHost = shutdownHost;
        _ui = SynchronizationContext.Current ?? new WindowsFormsSynchronizationContext();

        _idleIcon = LoadAppIcon();
        _activeIcon = BuildActiveIcon(_idleIcon);

        _banner = new SessionBanner(onStop: StopSession, onTogglePause: TogglePause);

        _tray = new NotifyIcon
        {
            Icon = _idleIcon,
            Text = AppInfo.Name,
            Visible = true,
            ContextMenuStrip = BuildMenu(),
        };
        _tray.DoubleClick += (_, _) => CopyAccessUrl();

        _adminAutostart = ElevationManager.IsAdminAutostartEnabled();

        _svc.State.Changed += OnSessionChanged;
        RefreshUi();

        _tray.ShowBalloonTip(4000, AppInfo.Name,
            $"Running. Open {_svc.AccessUrl} from your iPhone.", ToolTipIcon.Info);
    }

    // ---------------- menu ----------------

    private ContextMenuStrip BuildMenu()
    {
        var menu = new ContextMenuStrip { ShowImageMargin = false };

        var header = new ToolStripMenuItem(AppInfo.Name) { Enabled = false };
        _statusItem = new ToolStripMenuItem("Status: starting…") { Enabled = false };

        var copyUrl = new ToolStripMenuItem("Copy access URL", null, (_, _) => CopyAccessUrl());
        var openBrowser = new ToolStripMenuItem("Open in browser", null, (_, _) => OpenInBrowser());

        _pauseItem = new ToolStripMenuItem("Pause session", null, (_, _) => TogglePause());
        _stopItem = new ToolStripMenuItem("Stop session now", null, (_, _) => StopSession());

        var changePin = new ToolStripMenuItem("Change PIN…", null, (_, _) => ChangePin());
        _startupItem = new ToolStripMenuItem("Start with Windows", null, (_, _) => ToggleStartup())
        { CheckOnClick = false };

        // Keep the PC awake + unlocked so the phone can always see the screen (Windows hides
        // the lock screen from every app). Persists across restarts.
        _neverLockItem = new ToolStripMenuItem("Never lock — stay reachable", null, (_, _) => ToggleNeverLock())
        { CheckOnClick = false };

        // Run elevated so the phone can control admin / UAC windows (see ElevationManager).
        _adminItem = new ToolStripMenuItem("Enable admin control (UAC apps)", null, (_, _) => ToggleAdminControl())
        { CheckOnClick = false };

        // Serve over HTTPS with a real Tailscale cert (unlocks native clipboard + offline PWA).
        _httpsItem = new ToolStripMenuItem("Enable HTTPS (Tailscale cert)", null, (_, _) => ToggleHttps())
        { CheckOnClick = false };

        var showLog = new ToolStripMenuItem("Show log folder", null, (_, _) => OpenLogFolder());
        var exit = new ToolStripMenuItem("Exit", null, (_, _) => ExitApp());

        menu.Items.AddRange(new ToolStripItem[]
        {
            header, _statusItem, new ToolStripSeparator(),
            copyUrl, openBrowser, new ToolStripSeparator(),
            _pauseItem, _stopItem, new ToolStripSeparator(),
            changePin, _startupItem, _neverLockItem, _adminItem, _httpsItem, new ToolStripSeparator(),
            showLog, exit,
        });
        return menu;
    }

    // ---------------- session change -> UI ----------------

    private void OnSessionChanged() => _ui.Post(_ => RefreshUi(), null);

    private bool _wasActive;

    private void RefreshUi()
    {
        bool active = _svc.State.IsActive;
        bool paused = _svc.State.IsPaused;
        int count = _svc.State.ActiveCount;
        string remotes = string.Join(", ", _svc.State.ActiveRemotes);

        _statusItem.Text = active
            ? (paused ? $"Status: PAUSED ({count} device)" : $"Status: ACTIVE ({count} device)")
            : "Status: Online — waiting";

        _pauseItem.Enabled = active;
        _pauseItem.Text = paused ? "Resume session" : "Pause session";
        _stopItem.Enabled = active;
        _startupItem.Checked = StartupManager.IsEnabled() || _adminAutostart;
        _neverLockItem.Checked = _svc.Config.NeverLock;

        bool admin = ElevationManager.IsElevated();
        _adminItem.Checked = admin || _adminAutostart;
        _adminItem.Text = admin
            ? "Admin control: ON — disable"
            : (_adminAutostart ? "Admin control armed — disable" : "Enable admin control (UAC apps)");

        bool https = TlsManager.IsConfigured();
        _httpsItem.Checked = https;
        _httpsItem.Text = https ? "HTTPS: ON — disable" : "Enable HTTPS (Tailscale cert)";

        _tray.Icon = active ? _activeIcon : _idleIcon;
        _tray.Text = active ? $"{AppInfo.Name} — control active" : $"{AppInfo.Name} — online";

        // keep the PC awake + display on while controlling (no sleep/screensaver/lock mid-session)
        PowerManager.SetSessionAwake(active && !paused);

        if (active)
        {
            _banner.UpdateState(count, paused, remotes);
            if (!_banner.Visible) _banner.Show();
            if (!_wasActive)
                _tray.ShowBalloonTip(3000, AppInfo.Name,
                    $"Remote control session started from {remotes}.", ToolTipIcon.Warning);
        }
        else if (_banner.Visible)
        {
            _banner.Hide();
        }
        _wasActive = active;
    }

    // ---------------- actions ----------------

    private void CopyAccessUrl()
    {
        try
        {
            Clipboard.SetText(_svc.AccessUrl);
            _tray.ShowBalloonTip(2500, AppInfo.Name, $"Copied: {_svc.AccessUrl}", ToolTipIcon.Info);
        }
        catch (Exception ex) { Log.Error("Copy URL failed.", ex); }
    }

    private void OpenInBrowser()
    {
        try { Process.Start(new ProcessStartInfo(_svc.AccessUrl) { UseShellExecute = true }); }
        catch (Exception ex) { Log.Error("Open browser failed.", ex); }
    }

    private void TogglePause()
    {
        _svc.State.TogglePaused();
        RefreshUi();
    }

    private void StopSession()
    {
        _svc.State.SetPaused(false);
        _svc.State.StopAll();
    }

    private void ChangePin()
    {
        using var dlg = new ChangePinDialog();
        if (dlg.ShowDialog() == DialogResult.OK && dlg.NewPin != null)
        {
            _svc.Sessions.ForceSetPin(dlg.NewPin);
            _svc.State.StopAll(); // disconnect anyone using the old PIN
            _tray.ShowBalloonTip(2500, AppInfo.Name, "PIN updated. All sessions were disconnected.", ToolTipIcon.Info);
        }
    }

    private void ToggleStartup()
    {
        bool now = StartupManager.Toggle();
        _startupItem.Checked = now || _adminAutostart;
        _tray.ShowBalloonTip(2000, AppInfo.Name,
            now ? "Will start automatically with Windows." : "Auto-start disabled.", ToolTipIcon.Info);
    }

    private void ToggleNeverLock()
    {
        bool on = !_svc.Config.NeverLock;
        _svc.Config.NeverLock = on;
        _svc.Config.Save();
        PowerManager.SetAlwaysAwake(on);
        PowerManager.PreventLock(on);
        _neverLockItem.Checked = on;
        _tray.ShowBalloonTip(2800, AppInfo.Name, on
            ? "The PC will stay awake and won't lock — reachable from your phone anytime."
            : "Normal lock / sleep behavior restored.", ToolTipIcon.Info);
    }

    private void ToggleAdminControl()
    {
        // ---- Turn OFF (already elevated or armed) ----
        if (_adminAutostart || ElevationManager.IsElevated())
        {
            if (ElevationManager.IsElevated())
            {
                ElevationManager.RemoveAdminAutostart(); // we already have the rights to do it
                _adminAutostart = false;
                RefreshUi();
                _tray.ShowBalloonTip(3000, AppInfo.Name,
                    "Admin control disabled. It takes full effect after the next restart.", ToolTipIcon.Info);
            }
            else if (ElevationManager.RelaunchElevated("--remove-admin"))
            {
                ExitApp(); // hand off to the elevated instance, which removes the task
            }
            else
            {
                _tray.ShowBalloonTip(2500, AppInfo.Name, "Admin control unchanged (UAC declined).", ToolTipIcon.Warning);
            }
            return;
        }

        // ---- Turn ON ----
        var res = MessageBox.Show(
            "Enable Admin control?\n\n" +
            "This lets the phone control administrator windows and UAC-elevated apps (which Windows " +
            "otherwise blocks). The app will restart with admin rights and start elevated automatically " +
            "from now on — no UAC prompt each time.\n\n" +
            "Approve the one Windows (UAC) prompt to continue.",
            AppInfo.Name, MessageBoxButtons.OKCancel, MessageBoxIcon.Question);
        if (res != DialogResult.OK) return;

        if (ElevationManager.RelaunchElevated("--apply-admin"))
            ExitApp(); // hand off to the elevated instance (it re-registers autostart + takes over)
        else
            _tray.ShowBalloonTip(2500, AppInfo.Name, "Admin control was not enabled (UAC declined).", ToolTipIcon.Warning);
    }

    private void ToggleHttps()
    {
        if (TlsManager.IsConfigured())
        {
            TlsManager.Disable();
            RefreshUi();
            _tray.ShowBalloonTip(3000, AppInfo.Name,
                "HTTPS turned off. Restart the app (tray ▸ Exit, then relaunch) to serve over HTTP again.", ToolTipIcon.Info);
            return;
        }

        Cursor.Current = Cursors.WaitCursor;
        var (ok, msg) = TlsManager.Provision(); // runs `tailscale cert` (a few seconds)
        Cursor.Current = Cursors.Default;

        if (ok)
        {
            RefreshUi();
            MessageBox.Show(
                $"HTTPS is ready.\n\nNew address:\n    https://{msg}:{_svc.Config.Port}\n\n" +
                "Restart Mo Remote (tray ▸ Exit, then relaunch) to switch to HTTPS, then open the new address " +
                "on your phone. This makes the native clipboard and offline install work properly.",
                AppInfo.Name, MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        else
        {
            MessageBox.Show(
                "Couldn't set up HTTPS:\n\n" + msg + "\n\n" +
                "HTTPS needs MagicDNS + HTTPS certificates enabled for your tailnet " +
                "(Tailscale admin console ▸ DNS / HTTPS). Plain HTTP keeps working meanwhile.",
                AppInfo.Name, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    private void OpenLogFolder()
    {
        try
        {
            Directory.CreateDirectory(Paths.DataDir);
            Process.Start(new ProcessStartInfo(Paths.DataDir) { UseShellExecute = true });
        }
        catch (Exception ex) { Log.Error("Open log folder failed.", ex); }
    }

    private void ExitApp()
    {
        Log.Info("Exit requested from tray.");
        try { _svc.State.StopAll(); } catch { }
        try { _shutdownHost(); } catch { }
        _tray.Visible = false;
        _banner.Hide();
        ExitThread();
        Application.Exit();
    }

    // ---------------- icons ----------------

    private static Icon LoadAppIcon()
    {
        // Load the multi-resolution app.ico shipped next to the exe and pick the frame that
        // matches the DPI-scaled tray size — crisp at any DPI. (Icon.ExtractAssociatedIcon
        // only ever returns a single 32px frame, which the tray then downscales → blurry.)
        try
        {
            var path = Path.Combine(AppContext.BaseDirectory, "app.ico");
            if (File.Exists(path))
            {
                int sz = Math.Max(16, SystemInformation.SmallIconSize.Width);
                return new Icon(path, sz, sz);
            }
        }
        catch { }
        try
        {
            var exe = Environment.ProcessPath;
            if (exe != null)
            {
                var ico = Icon.ExtractAssociatedIcon(exe);
                if (ico != null) return ico;
            }
        }
        catch { }
        return SystemIcons.Application;
    }

    private static Icon BuildActiveIcon(Icon baseIcon)
    {
        try
        {
            using var bmp = baseIcon.ToBitmap();
            using var g = Graphics.FromImage(bmp);
            int d = Math.Max(8, bmp.Width / 3);
            using var red = new SolidBrush(Color.FromArgb(239, 68, 68));
            using var ring = new Pen(Color.White, Math.Max(1, bmp.Width / 16f));
            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            var rect = new Rectangle(bmp.Width - d - 1, bmp.Height - d - 1, d, d);
            g.FillEllipse(red, rect);
            g.DrawEllipse(ring, rect);
            // GetHicon allocates an HICON that Icon.FromHandle does NOT own; clone to a
            // self-contained Icon, then free the GDI handle to avoid leaking it.
            IntPtr h = bmp.GetHicon();
            try { using var tmp = Icon.FromHandle(h); return (Icon)tmp.Clone(); }
            finally { DestroyIcon(h); }
        }
        catch { return baseIcon; }
    }

    [DllImport("user32.dll")]
    private static extern bool DestroyIcon(IntPtr handle);

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _svc.State.Changed -= OnSessionChanged;
            _tray.Dispose();
            _banner.Dispose();
        }
        base.Dispose(disposing);
    }
}

/// <summary>Start-with-Windows via the per-user Run key (no admin needed).</summary>
public static class StartupManager
{
    private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string ValueName = "MoRemotePersonal";

    private static string ExePath => Environment.ProcessPath ?? "";

    public static bool IsEnabled()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey, false);
            var val = key?.GetValue(ValueName) as string;
            return !string.IsNullOrEmpty(val);
        }
        catch { return false; }
    }

    public static bool Toggle() => IsEnabled() ? !Disable() : Enable();

    public static bool Enable()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey, true)
                            ?? Registry.CurrentUser.CreateSubKey(RunKey);
            key!.SetValue(ValueName, $"\"{ExePath}\"");
            Log.Info("Auto-start enabled.");
            return true;
        }
        catch (Exception ex) { Log.Error("Enable auto-start failed.", ex); return false; }
    }

    public static bool Disable()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey, true);
            key?.DeleteValue(ValueName, false);
            Log.Info("Auto-start disabled.");
            return true;
        }
        catch (Exception ex) { Log.Error("Disable auto-start failed.", ex); return false; }
    }
}

using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Text;

namespace MoRemote;

/// <summary>
/// Injects mouse + keyboard input via the Win32 SendInput API. Coordinates arrive
/// normalized (0..1) inside the selected monitor. All injection runs on one dedicated
/// thread so it can (in service mode) attach to the current *input desktop* — that lets a
/// SYSTEM worker also control the lock / login / UAC secure desktop.
/// </summary>
public sealed class InputInjector : IDisposable
{
    public bool IsReady => true;
    public string BackendName => "Win32 SendInput";
    public string LastError => "";
    /// <summary>Set true when running as the SYSTEM service worker, so injection follows the input desktop.</summary>
    public static bool FollowInputDesktop;

    private readonly object _gate = new();
    private readonly ScreenCapture _capture;
    private double _scrollRemX, _scrollRemY;

    private readonly BlockingCollection<INPUT[]> _queue = new();
    private readonly Thread _pump;
    private IntPtr _desktop = IntPtr.Zero;
    private string _desktopName = "";

    public InputInjector(ScreenCapture capture)
    {
        _capture = capture;
        _pump = new Thread(Pump) { IsBackground = true, Name = "input-inject" };
        _pump.Start();
    }

    // ---------------- injection thread ----------------

    private void Pump()
    {
        try
        {
            foreach (var batch in _queue.GetConsumingEnumerable())
            {
                try
                {
                    if (FollowInputDesktop) AttachToInputDesktop();
                    SendRaw(batch);
                }
                catch (Exception ex) { Log.Warn("Input pump: " + ex.Message); }
            }
        }
        catch (ObjectDisposedException) { }
    }

    // Re-point this thread at whatever desktop currently has input focus (Default, or Winlogon
    // during a lock/UAC prompt). No-op unless the desktop actually changed. Best-effort: if the
    // process lacks rights (normal user mode), we leave the thread on its inherited desktop.
    private void AttachToInputDesktop()
    {
        IntPtr d = OpenInputDesktop(0, false, MAXIMUM_ALLOWED);
        if (d == IntPtr.Zero) return;
        var name = GetDesktopName(d);
        if (name == _desktopName) { CloseDesktop(d); return; }
        if (SetThreadDesktop(d))
        {
            if (_desktop != IntPtr.Zero) CloseDesktop(_desktop);
            _desktop = d; _desktopName = name;
            Log.Info("Input following desktop: " + name);
        }
        else CloseDesktop(d);
    }

    // ---------------- Mouse ----------------

    public void MouseMove(double nx, double ny)
    {
        var move = MakeMove(nx, ny);
        Send(move);
    }
    public void MouseMoveRelative(double dx,double dy,double sensitivity=1) => Send(new INPUT { type=INPUT_MOUSE, U=new InputUnion { mi=new MOUSEINPUT { dx=(int)Math.Round(dx*sensitivity),dy=(int)Math.Round(dy*sensitivity),dwFlags=MOUSEEVENTF_MOVE } } });

    public void MouseButton(string button, bool down, double nx, double ny)
    {
        var (dn, up) = ButtonFlags(button);
        Send(MakeMove(nx, ny), MakeMouse(down ? dn : up));
    }
    public void MouseButtonCurrent(string button,bool down){var(dn,up)=ButtonFlags(button);Send(MakeMouse(down?dn:up));}

    public void Click(string button, double nx, double ny)
    {
        var (dn, up) = ButtonFlags(button);
        Send(MakeMove(nx, ny), MakeMouse(dn), MakeMouse(up));
    }
    public void ClickCurrent(string button){var(dn,up)=ButtonFlags(button);Send(MakeMouse(dn),MakeMouse(up));}

    public void DoubleClick(double nx, double ny)
    {
        var (dn, up) = ButtonFlags("left");
        Send(MakeMove(nx, ny), MakeMouse(dn), MakeMouse(up), MakeMouse(dn), MakeMouse(up));
    }
    public void DoubleClickCurrent(){var(dn,up)=ButtonFlags("left");Send(MakeMouse(dn),MakeMouse(up),MakeMouse(dn),MakeMouse(up));}

    /// <param name="dx">horizontal notches (right = positive)</param>
    /// <param name="dy">vertical notches (up = positive)</param>
    public void Scroll(double dx, double dy)
    {
        lock (_gate)
        {
            _scrollRemY += dy * WHEEL_DELTA;
            _scrollRemX += dx * WHEEL_DELTA;
            int ty = (int)_scrollRemY; _scrollRemY -= ty;
            int tx = (int)_scrollRemX; _scrollRemX -= tx;
            var inputs = new List<INPUT>();
            if (ty != 0) inputs.Add(MakeMouse(MOUSEEVENTF_WHEEL, (uint)ty));
            if (tx != 0) inputs.Add(MakeMouse(MOUSEEVENTF_HWHEEL, (uint)tx));
            if (inputs.Count > 0) Send(inputs.ToArray());
        }
    }
    public void Scroll(double dx,double dy,double sensitivity)=>Scroll(dx*sensitivity,dy*sensitivity);
    public void ReleaseAll(){foreach(var k in new[]{"Control","Alt","Shift","Meta"})KeyUp(k);MouseButtonCurrent("left",false);MouseButtonCurrent("right",false);MouseButtonCurrent("middle",false);}

    // ---------------- Keyboard ----------------

    public void KeyTap(string key)
    {
        if (!KeyMap.TryGetValue(key, out var vk)) return;
        Send(MakeKey(vk, false), MakeKey(vk, true));
    }

    public void KeyDown(string key) { if (KeyMap.TryGetValue(key, out var vk)) Send(MakeKey(vk, false)); }
    public void KeyUp(string key) { if (KeyMap.TryGetValue(key, out var vk)) Send(MakeKey(vk, true)); }

    /// <summary>Press a chord (e.g. Control+Shift+Escape): down in order, up in reverse.</summary>
    public void Combo(IReadOnlyList<string> keys)
    {
        var vks = new List<ushort>();
        foreach (var k in keys) if (KeyMap.TryGetValue(k, out var vk)) vks.Add(vk);
        if (vks.Count == 0) return;
        var inputs = new List<INPUT>();
        foreach (var vk in vks) inputs.Add(MakeKey(vk, false));
        for (int i = vks.Count - 1; i >= 0; i--) inputs.Add(MakeKey(vks[i], true));
        Send(inputs.ToArray());
    }

    /// <summary>Type a Unicode string (handles any character incl. Arabic, emoji).</summary>
    public void TypeText(string text)
    {
        if (string.IsNullOrEmpty(text)) return;
        var inputs = new List<INPUT>(text.Length * 2);
        foreach (var ch in text)
        {
            inputs.Add(MakeUnicode(ch, false));
            inputs.Add(MakeUnicode(ch, true));
        }
        Send(inputs.ToArray());
    }

    // ---------------- builders ----------------

    // Map a 0..1 point inside the *selected monitor* to absolute virtual-desktop coordinates.
    // MOUSEEVENTF_VIRTUALDESK makes the 0..65535 range span every monitor, so clicks land on
    // the right screen in a multi-monitor setup (plain ABSOLUTE only ever hits the primary).
    private INPUT MakeMove(double nx, double ny)
    {
        nx = Math.Clamp(nx, 0, 1);
        ny = Math.Clamp(ny, 0, 1);
        var b = _capture.SelectedBounds;
        int vx = GetSystemMetrics(SM_XVIRTUALSCREEN), vy = GetSystemMetrics(SM_YVIRTUALSCREEN);
        int vw = Math.Max(1, GetSystemMetrics(SM_CXVIRTUALSCREEN));
        int vh = Math.Max(1, GetSystemMetrics(SM_CYVIRTUALSCREEN));
        double px = b.Left + nx * b.Width;
        double py = b.Top + ny * b.Height;
        return new INPUT
        {
            type = INPUT_MOUSE,
            U = new InputUnion
            {
                mi = new MOUSEINPUT
                {
                    dx = (int)Math.Round((px - vx) / Math.Max(1, vw - 1) * 65535.0),
                    dy = (int)Math.Round((py - vy) / Math.Max(1, vh - 1) * 65535.0),
                    dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
                }
            }
        };
    }

    private static INPUT MakeMouse(uint flags, uint mouseData = 0) => new()
    {
        type = INPUT_MOUSE,
        U = new InputUnion { mi = new MOUSEINPUT { dwFlags = flags, mouseData = mouseData } }
    };

    private static INPUT MakeKey(ushort vk, bool up) => new()
    {
        type = INPUT_KEYBOARD,
        U = new InputUnion { ki = new KEYBDINPUT { wVk = vk, dwFlags = up ? KEYEVENTF_KEYUP : 0 } }
    };

    private static INPUT MakeUnicode(char ch, bool up) => new()
    {
        type = INPUT_KEYBOARD,
        U = new InputUnion
        {
            ki = new KEYBDINPUT
            {
                wVk = 0,
                wScan = ch,
                dwFlags = KEYEVENTF_UNICODE | (up ? KEYEVENTF_KEYUP : 0u),
            }
        }
    };

    private static (uint down, uint up) ButtonFlags(string button) => button.ToLowerInvariant() switch
    {
        "right" => (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        "middle" => (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        _ => (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    };

    // Public API enqueues; the pump thread performs the actual SendInput on the input desktop.
    private void Send(params INPUT[] inputs)
    {
        if (inputs.Length == 0) return;
        try { _queue.Add(inputs); } catch (Exception ex) { Log.Warn("Input enqueue failed: " + ex.Message); }
    }

    private static void SendRaw(INPUT[] inputs)
    {
        var n = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<INPUT>());
        if (n != inputs.Length)
            Log.Warn($"SendInput injected {n}/{inputs.Length} (err {Marshal.GetLastWin32Error()}).");
    }

    public void Dispose()
    {
        try { _queue.CompleteAdding(); } catch { }
        try { if (_desktop != IntPtr.Zero) CloseDesktop(_desktop); } catch { }
    }

    // ---------------- key name -> virtual-key map ----------------

    private static readonly Dictionary<string, ushort> KeyMap = BuildKeyMap();

    private static Dictionary<string, ushort> BuildKeyMap()
    {
        var m = new Dictionary<string, ushort>(StringComparer.OrdinalIgnoreCase)
        {
            ["Enter"] = 0x0D, ["Return"] = 0x0D,
            ["Escape"] = 0x1B, ["Esc"] = 0x1B,
            ["Backspace"] = 0x08, ["Tab"] = 0x09,
            ["Delete"] = 0x2E, ["Del"] = 0x2E, ["Insert"] = 0x2D,
            ["Space"] = 0x20, [" "] = 0x20,
            ["ArrowUp"] = 0x26, ["ArrowDown"] = 0x28, ["ArrowLeft"] = 0x25, ["ArrowRight"] = 0x27,
            ["Up"] = 0x26, ["Down"] = 0x28, ["Left"] = 0x25, ["Right"] = 0x27,
            ["Home"] = 0x24, ["End"] = 0x23, ["PageUp"] = 0x21, ["PageDown"] = 0x22,
            ["Control"] = 0x11, ["Ctrl"] = 0x11,
            ["Alt"] = 0x12, ["Menu"] = 0x12,
            ["Shift"] = 0x10,
            ["Meta"] = 0x5B, ["Win"] = 0x5B, ["Windows"] = 0x5B, ["Super"] = 0x5B,
            ["CapsLock"] = 0x14, ["PrintScreen"] = 0x2C,
        };
        for (char c = 'A'; c <= 'Z'; c++) m[c.ToString()] = (ushort)c;
        for (char c = '0'; c <= '9'; c++) m[c.ToString()] = (ushort)c;
        for (int i = 1; i <= 12; i++) m["F" + i] = (ushort)(0x70 + (i - 1)); // VK_F1..F12
        return m;
    }

    // ---------------- Win32 ----------------
    private const int INPUT_MOUSE = 0;
    private const int INPUT_KEYBOARD = 1;

    private const uint MOUSEEVENTF_MOVE = 0x0001;
    private const uint MOUSEEVENTF_ABSOLUTE = 0x8000;
    private const uint MOUSEEVENTF_VIRTUALDESK = 0x4000;
    private const int SM_XVIRTUALSCREEN = 76, SM_YVIRTUALSCREEN = 77, SM_CXVIRTUALSCREEN = 78, SM_CYVIRTUALSCREEN = 79;
    private const uint MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004;
    private const uint MOUSEEVENTF_RIGHTDOWN = 0x0008, MOUSEEVENTF_RIGHTUP = 0x0010;
    private const uint MOUSEEVENTF_MIDDLEDOWN = 0x0020, MOUSEEVENTF_MIDDLEUP = 0x0040;
    private const uint MOUSEEVENTF_WHEEL = 0x0800, MOUSEEVENTF_HWHEEL = 0x1000;
    private const int WHEEL_DELTA = 120;

    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const uint KEYEVENTF_UNICODE = 0x0004;

    [StructLayout(LayoutKind.Sequential)]
    private struct MOUSEINPUT { public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)]
    private struct HARDWAREINPUT { public uint uMsg; public ushort wParamL; public ushort wParamH; }
    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)] public MOUSEINPUT mi;
        [FieldOffset(0)] public KEYBDINPUT ki;
        [FieldOffset(0)] public HARDWAREINPUT hi;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT { public uint type; public InputUnion U; }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [DllImport("user32.dll")] private static extern int GetSystemMetrics(int nIndex);

    // ---- input-desktop attach (for controlling the secure / lock / login desktop) ----
    private const uint MAXIMUM_ALLOWED = 0x02000000;
    private const int UOI_NAME = 2;

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr OpenInputDesktop(uint dwFlags, bool fInherit, uint dwDesiredAccess);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetThreadDesktop(IntPtr hDesktop);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool CloseDesktop(IntPtr hDesktop);
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool GetUserObjectInformation(IntPtr hObj, int nIndex, byte[] pvInfo, int nLength, out int lpnLengthNeeded);

    private static string GetDesktopName(IntPtr hDesktop)
    {
        try
        {
            var buf = new byte[256];
            if (GetUserObjectInformation(hDesktop, UOI_NAME, buf, buf.Length, out int len) && len > 2)
                return Encoding.Unicode.GetString(buf, 0, len - 2); // drop the null terminator
        }
        catch { }
        return hDesktop.ToString();
    }
}

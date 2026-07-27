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
    // Physical keys are tracked so a browser that vanishes mid-chord cannot leave one held down on
    // the remote machine. The named-key path never needed this because it only ever reached the four
    // modifiers below, which were released unconditionally; a table of 100 keys does need it.
    private readonly HashSet<Scan> _heldScans = new();

    public void ReleaseAll(){
        Scan[] held;
        lock(_gate){held=_heldScans.ToArray();_heldScans.Clear();}
        foreach(var s in held)Send(MakeScan(s.Code,s.Extended,up:true));
        foreach(var k in new[]{"Control","Alt","Shift","Meta"})KeyUp(k);MouseButtonCurrent("left",false);MouseButtonCurrent("right",false);MouseButtonCurrent("middle",false);}

    // ---------------- Keyboard ----------------

    public void KeyTap(string key)
    {
        if (!KeyMap.TryGetValue(key, out var vk)) return;
        Send(MakeKey(vk, false), MakeKey(vk, true));
    }

    public void KeyDown(string key) { if (KeyMap.TryGetValue(key, out var vk)) Send(MakeKey(vk, false)); }
    public void KeyUp(string key) { if (KeyMap.TryGetValue(key, out var vk)) Send(MakeKey(vk, true)); }

    /// <summary>
    /// Press or release a key by PHYSICAL position (a browser `KeyboardEvent.code`), as a SCANCODE
    /// rather than a virtual key.
    ///
    /// A virtual key is a meaning ("VK_Z"); a scancode is a place. The browser measured a place,
    /// so passing it on as a place is a lossless hand-off and the remote applies its own keyboard
    /// layout on top — which is what makes a German keymap on the server behave like a German
    /// keymap regardless of what the viewer is typing on. Sending VK codes instead would re-impose
    /// the VIEWER's layout, the same class of bug the Linux agent's Keys table carries a comment
    /// about.
    ///
    /// Deliberately incomplete: Pause (its make code is the three-byte E1 1D 45 sequence, not a
    /// scancode) and the international/media keys are absent. A key that does nothing gets
    /// reported; a key wired to the wrong scancode gets lived with.
    /// </summary>
    public void KeyCode(string code, bool down)
    {
        if (!PhysicalScan.TryGetValue(code, out var s)) return;
        // A held key fires keydown over and over at the BROWSER's repeat rate. Forwarding every one
        // would race the remote's own repeat timer and double characters, so only the edges go out
        // and the desktop repeats at its own configured rate — as it does for a real keyboard.
        lock (_gate)
        {
            if (down) { if (!_heldScans.Add(s)) return; }
            else if (!_heldScans.Remove(s)) return;
        }
        Send(MakeScan(s.Code, s.Extended, up: !down));
    }

    public void KeyTapCode(string code)
    {
        if (!PhysicalScan.TryGetValue(code, out var s)) return;
        Send(MakeScan(s.Code, s.Extended, up: false), MakeScan(s.Code, s.Extended, up: true));
    }

    private readonly record struct Scan(ushort Code, bool Extended);

    /// <summary>PS/2 set-1 make codes. `Extended` keys are the ones the wire prefixes with 0xE0.</summary>
    private static readonly Dictionary<string, Scan> PhysicalScan = new(StringComparer.Ordinal)
    {
        ["Escape"] = new(0x01, false),
        ["Digit1"] = new(0x02, false), ["Digit2"] = new(0x03, false), ["Digit3"] = new(0x04, false),
        ["Digit4"] = new(0x05, false), ["Digit5"] = new(0x06, false), ["Digit6"] = new(0x07, false),
        ["Digit7"] = new(0x08, false), ["Digit8"] = new(0x09, false), ["Digit9"] = new(0x0A, false),
        ["Digit0"] = new(0x0B, false), ["Minus"] = new(0x0C, false), ["Equal"] = new(0x0D, false),
        ["Backspace"] = new(0x0E, false), ["Tab"] = new(0x0F, false),
        ["KeyQ"] = new(0x10, false), ["KeyW"] = new(0x11, false), ["KeyE"] = new(0x12, false),
        ["KeyR"] = new(0x13, false), ["KeyT"] = new(0x14, false), ["KeyY"] = new(0x15, false),
        ["KeyU"] = new(0x16, false), ["KeyI"] = new(0x17, false), ["KeyO"] = new(0x18, false),
        ["KeyP"] = new(0x19, false), ["BracketLeft"] = new(0x1A, false), ["BracketRight"] = new(0x1B, false),
        ["Enter"] = new(0x1C, false), ["ControlLeft"] = new(0x1D, false),
        ["KeyA"] = new(0x1E, false), ["KeyS"] = new(0x1F, false), ["KeyD"] = new(0x20, false),
        ["KeyF"] = new(0x21, false), ["KeyG"] = new(0x22, false), ["KeyH"] = new(0x23, false),
        ["KeyJ"] = new(0x24, false), ["KeyK"] = new(0x25, false), ["KeyL"] = new(0x26, false),
        ["Semicolon"] = new(0x27, false), ["Quote"] = new(0x28, false), ["Backquote"] = new(0x29, false),
        ["ShiftLeft"] = new(0x2A, false), ["Backslash"] = new(0x2B, false),
        ["KeyZ"] = new(0x2C, false), ["KeyX"] = new(0x2D, false), ["KeyC"] = new(0x2E, false),
        ["KeyV"] = new(0x2F, false), ["KeyB"] = new(0x30, false), ["KeyN"] = new(0x31, false),
        ["KeyM"] = new(0x32, false), ["Comma"] = new(0x33, false), ["Period"] = new(0x34, false),
        ["Slash"] = new(0x35, false), ["ShiftRight"] = new(0x36, false),
        ["NumpadMultiply"] = new(0x37, false), ["AltLeft"] = new(0x38, false),
        ["Space"] = new(0x39, false), ["CapsLock"] = new(0x3A, false),
        ["F1"] = new(0x3B, false), ["F2"] = new(0x3C, false), ["F3"] = new(0x3D, false),
        ["F4"] = new(0x3E, false), ["F5"] = new(0x3F, false), ["F6"] = new(0x40, false),
        ["F7"] = new(0x41, false), ["F8"] = new(0x42, false), ["F9"] = new(0x43, false),
        ["F10"] = new(0x44, false), ["NumLock"] = new(0x45, false), ["ScrollLock"] = new(0x46, false),
        ["Numpad7"] = new(0x47, false), ["Numpad8"] = new(0x48, false), ["Numpad9"] = new(0x49, false),
        ["NumpadSubtract"] = new(0x4A, false), ["Numpad4"] = new(0x4B, false),
        ["Numpad5"] = new(0x4C, false), ["Numpad6"] = new(0x4D, false),
        ["NumpadAdd"] = new(0x4E, false), ["Numpad1"] = new(0x4F, false),
        ["Numpad2"] = new(0x50, false), ["Numpad3"] = new(0x51, false),
        ["Numpad0"] = new(0x52, false), ["NumpadDecimal"] = new(0x53, false),
        ["IntlBackslash"] = new(0x56, false), ["F11"] = new(0x57, false), ["F12"] = new(0x58, false),
        ["F13"] = new(0x64, false), ["F14"] = new(0x65, false), ["F15"] = new(0x66, false),
        ["F16"] = new(0x67, false), ["F17"] = new(0x68, false), ["F18"] = new(0x69, false),
        ["F19"] = new(0x6A, false), ["F20"] = new(0x6B, false), ["F21"] = new(0x6C, false),
        ["F22"] = new(0x6D, false), ["F23"] = new(0x6E, false), ["F24"] = new(0x6F, false),
        // 0xE0-prefixed: same make code as a non-extended key, told apart only by the flag.
        ["NumpadEnter"] = new(0x1C, true), ["ControlRight"] = new(0x1D, true),
        ["NumpadDivide"] = new(0x35, true), ["AltRight"] = new(0x38, true),
        ["PrintScreen"] = new(0x37, true),
        ["Home"] = new(0x47, true), ["ArrowUp"] = new(0x48, true), ["PageUp"] = new(0x49, true),
        ["ArrowLeft"] = new(0x4B, true), ["ArrowRight"] = new(0x4D, true),
        ["End"] = new(0x4F, true), ["ArrowDown"] = new(0x50, true), ["PageDown"] = new(0x51, true),
        ["Insert"] = new(0x52, true), ["Delete"] = new(0x53, true),
        ["MetaLeft"] = new(0x5B, true), ["MetaRight"] = new(0x5C, true), ["ContextMenu"] = new(0x5D, true),
        // Volume and media, also 0xE0-prefixed. These exist on the Linux side, and a table that has
        // them there and not here is the same kind of asymmetry as a feature that works for one
        // account and not the other — it just shows up as "the volume keys do nothing on Windows".
        ["AudioVolumeMute"] = new(0x20, true), ["AudioVolumeDown"] = new(0x2E, true),
        ["AudioVolumeUp"] = new(0x30, true),
        ["MediaPlayPause"] = new(0x22, true), ["MediaStop"] = new(0x24, true),
        ["MediaTrackNext"] = new(0x19, true), ["MediaTrackPrevious"] = new(0x10, true),
        ["BrowserBack"] = new(0x6A, true), ["BrowserForward"] = new(0x69, true),
        ["BrowserRefresh"] = new(0x67, true),
        // The keys ISO/JIS boards have and ANSI does not. Non-extended.
        ["IntlRo"] = new(0x73, false), ["IntlYen"] = new(0x7D, false), ["NumpadEqual"] = new(0x59, false),
        // Still deliberately absent: Pause. Its make code is the three-byte E1 1D 45 sequence, not a
        // scancode, so there is nothing correct to put in this table for it — and a key wired to the
        // wrong scancode is worse than one that does nothing, because the dead one gets reported.
    };

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

    // wVk MUST be 0 here. With KEYEVENTF_SCANCODE set, Windows takes wScan as the truth and a
    // stray wVk is what silently re-imposes the local layout — the exact thing this path exists
    // to avoid.
    private static INPUT MakeScan(ushort scan, bool extended, bool up) => new()
    {
        type = INPUT_KEYBOARD,
        U = new InputUnion
        {
            ki = new KEYBDINPUT
            {
                wVk = 0,
                wScan = scan,
                dwFlags = KEYEVENTF_SCANCODE
                          | (extended ? KEYEVENTF_EXTENDEDKEY : 0u)
                          | (up ? KEYEVENTF_KEYUP : 0u),
            }
        }
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

    private const uint KEYEVENTF_EXTENDEDKEY = 0x0001;
    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const uint KEYEVENTF_UNICODE = 0x0004;
    private const uint KEYEVENTF_SCANCODE = 0x0008;

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

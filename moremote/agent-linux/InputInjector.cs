using System.Buffers.Binary;
using System.Net.Sockets;

namespace MoRemote;

/// <summary>
/// Input goes through the portal's RemoteDesktop session, which accepts *absolute* pointer
/// positions — so a tap lands exactly where the finger was, with no cursor tracking, no drift
/// and no corner-recalibration jump. ydotoold/uinput stays as a fallback for when the portal
/// is unavailable; it can only do relative motion, so it estimates the cursor position.
/// </summary>
public sealed class InputInjector : IDisposable
{
    private const ushort EvSyn = 0, EvKey = 1, EvRel = 2;
    private const ushort SynReport = 0, RelX = 0, RelY = 1, RelHWheel = 6, RelWheel = 8;
    private const ushort BtnLeft = 0x110, BtnRight = 0x111, BtnMiddle = 0x112;

    private readonly PortalBridge _portal;
    private readonly ScreenCapture _capture;
    private readonly object _gate = new();
    private readonly HashSet<ushort> _pressed = [];
    private Socket? _socket;
    private string _lastError = "";
    private DateTimeOffset _lastConnectAttempt;
    private bool _cursorKnown;
    private int _cursorX, _cursorY;

    // Position we last commanded, normalized. The client also tracks this, but keeping it here
    // lets *Current()-style calls (click where the cursor already is) work on the portal path.
    private double _lastX = 0.5, _lastY = 0.5;

    private static readonly Dictionary<string, ushort> Keys = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Control"] = 29, ["Ctrl"] = 29, ["Alt"] = 56, ["Shift"] = 42, ["Meta"] = 125, ["Super"] = 125, ["Win"] = 125,
        ["Enter"] = 28, ["Escape"] = 1, ["Esc"] = 1, ["Tab"] = 15, ["Backspace"] = 14, ["Delete"] = 111,
        ["ArrowUp"] = 103, ["ArrowDown"] = 108, ["ArrowLeft"] = 105, ["ArrowRight"] = 106,
        ["Home"] = 102, ["End"] = 107, ["PageUp"] = 104, ["PageDown"] = 109, ["Insert"] = 110, ["Space"] = 57,
        ["a"] = 30, ["c"] = 46, ["v"] = 47, ["x"] = 45, ["z"] = 44,
        ["F1"] = 59, ["F2"] = 60, ["F3"] = 61, ["F4"] = 62, ["F5"] = 63, ["F6"] = 64,
        ["F7"] = 65, ["F8"] = 66, ["F9"] = 67, ["F10"] = 68, ["F11"] = 87, ["F12"] = 88,
    };

    public InputInjector(PortalBridge portal, ScreenCapture capture)
    {
        _portal = portal;
        _capture = capture;
        EnsureConnected(force: true);
    }

    public bool IsReady => _portal.IsReady || EnsureConnectedLocked();
    public string BackendName => _portal.IsReady
        ? "KDE RemoteDesktop portal (absolute)"
        : "ydotoold/uinput fallback (relative)";
    public string LastError
    {
        get { lock (_gate) return _portal.IsReady ? "" : _lastError; }
    }

    private static string SocketPath => Environment.GetEnvironmentVariable("YDOTOOL_SOCKET")
        ?? Path.Combine(Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR") ?? "/tmp", ".ydotool_socket");

    // ---------------------------------------------------------------- pointer

    public void MouseMove(double x, double y)
    {
        Remember(x, y);
        if (_portal.Send(new { type = "absolute", x, y })) return;
        FallbackMoveAbsolute(x, y, recalibrate: false);
    }

    public void MouseMoveRelative(double dx, double dy, double sensitivity = 1)
    {
        int x = (int)Math.Round(Math.Clamp(dx * sensitivity, -500, 500));
        int y = (int)Math.Round(Math.Clamp(dy * sensitivity, -500, 500));
        if (x == 0 && y == 0) return;
        if (_portal.Send(new { type = "relative", dx = x, dy = y }))
        {
            var b = _capture.InputBounds;
            if (b.Width > 0 && b.Height > 0)
                Remember(Math.Clamp(_lastX + (double)x / b.Width, 0, 1),
                         Math.Clamp(_lastY + (double)y / b.Height, 0, 1));
            return;
        }
        lock (_gate)
        {
            if (!EnsureConnected()) return;
            try
            {
                SendEvent(EvRel, RelX, x); SendEvent(EvRel, RelY, y); SendEvent(EvSyn, SynReport, 0);
                if (_cursorKnown)
                {
                    var b = _capture.InputBounds;
                    _cursorX = Math.Clamp(_cursorX + x, 0, Math.Max(0, b.Width - 1));
                    _cursorY = Math.Clamp(_cursorY + y, 0, Math.Max(0, b.Height - 1));
                }
            }
            catch (Exception ex) { Drop(ex); }
        }
    }

    public void Click(string button, double x, double y) { MouseMove(x, y); ClickCode(Button(button)); }
    public void ClickCurrent(string button) => ClickCode(Button(button));
    public void DoubleClick(double x, double y) { MouseMove(x, y); DoubleClickCurrent(); }
    public void DoubleClickCurrent() { ClickCode(BtnLeft); Thread.Sleep(40); ClickCode(BtnLeft); }
    public void MouseButton(string button, bool down, double x, double y) { MouseMove(x, y); Set(Button(button), down); }
    public void MouseButtonCurrent(string button, bool down) => Set(Button(button), down);

    private void ClickCode(ushort code) { Set(code, true); Thread.Sleep(25); Set(code, false); }
    private static ushort Button(string b) =>
        b.Equals("right", StringComparison.OrdinalIgnoreCase) ? BtnRight :
        b.Equals("middle", StringComparison.OrdinalIgnoreCase) ? BtnMiddle : BtnLeft;

    /// <summary>dx/dy arrive in wheel notches, positive = right / down.</summary>
    public void Scroll(double dx, double dy, double sensitivity = 1)
    {
        double x = Math.Clamp(dx * sensitivity, -20, 20), y = Math.Clamp(dy * sensitivity, -20, 20);
        // The portal's axis is in libinput's smooth-scroll pixels, where one wheel detent is ~15.
        // Passing notches straight through would move the page by a pixel or two per swipe.
        const double PixelsPerNotch = 15.0;
        if (_portal.Send(new { type = "axis", dx = x * PixelsPerNotch, dy = y * PixelsPerNotch })) return;
        int ix = (int)Math.Round(x), iy = (int)Math.Round(-y); // uinput REL_WHEEL is in notches, +ve = up
        lock (_gate)
        {
            if (!EnsureConnected()) return;
            try
            {
                if (ix != 0) SendEvent(EvRel, RelHWheel, ix);
                if (iy != 0) SendEvent(EvRel, RelWheel, iy);
                if (ix != 0 || iy != 0) SendEvent(EvSyn, SynReport, 0);
            }
            catch (Exception ex) { Drop(ex); }
        }
    }

    // ---------------------------------------------------------------- keyboard

    public void KeyTap(string k)
    {
        if (Keys.TryGetValue(k, out var c)) { Set(c, true); Thread.Sleep(12); Set(c, false); }
        else if (k.Length >= 1) TypeText(k);
    }
    public void KeyDown(string k) { if (Keys.TryGetValue(k, out var c)) Set(c, true); }
    public void KeyUp(string k) { if (Keys.TryGetValue(k, out var c)) Set(c, false); }

    public void Combo(IReadOnlyList<string> keys)
    {
        var codes = keys.Select(k => Keys.TryGetValue(k, out var c) ? c : (ushort)0).Where(c => c > 0).ToArray();
        foreach (var c in codes) Set(c, true);
        foreach (var c in codes.Reverse()) Set(c, false);
    }

    /// <summary>
    /// Types text by keysym, so it is independent of the PC's keyboard layout and handles any
    /// character the phone's keyboard can produce (accents, Arabic, emoji-free symbols…).
    /// The old clipboard+Ctrl-V trick is kept only for the ydotool fallback, since uinput can
    /// only send layout-dependent scancodes.
    /// </summary>
    public void TypeText(string text)
    {
        if (string.IsNullOrEmpty(text)) return;

        // Keysyms are typed one at a time with a small gap, so a long paste would crawl. Above a
        // paragraph or so, one clipboard paste is far quicker and the user is pasting anyway.
        if (_portal.IsReady && text.Length <= BulkPasteThreshold)
        {
            bool ok = true;
            foreach (var rune in text.EnumerateRunes())
            {
                int keysym = KeysymFor(rune.Value);
                if (!_portal.Send(new { type = "keysym", keysym, down = true }) ||
                    !_portal.Send(new { type = "keysym", keysym, down = false }))
                { ok = false; break; }
                Thread.Sleep(2); // let the compositor's virtual keyboard keep up
            }
            if (ok) return;
        }
        ClipboardBridge.SetText(text);
        Combo(["Control", "V"]);
    }

    private const int BulkPasteThreshold = 64;

    /// <summary>X11 keysym for a unicode codepoint: Latin-1 maps directly, the rest via 0x01000000.</summary>
    private static int KeysymFor(int codepoint) =>
        codepoint is >= 0x20 and <= 0x7e or >= 0xa0 and <= 0xff ? codepoint : 0x01000000 + codepoint;

    // ---------------------------------------------------------------- shared

    private void Remember(double x, double y)
    {
        lock (_gate) { _lastX = Math.Clamp(x, 0, 1); _lastY = Math.Clamp(y, 0, 1); }
    }

    private void Set(ushort code, bool down)
    {
        lock (_gate)
        {
            if (down) { if (!_pressed.Add(code)) return; }
            else { if (!_pressed.Remove(code)) return; }
        }
        bool isButton = code >= BtnLeft;
        var msg = isButton
            ? (object)new { type = "button", button = (int)code, down }
            : new { type = "key", code = (int)code, down };
        if (_portal.Send(msg)) return;
        Emit(EvKey, code, down ? 1 : 0);
    }

    public void ReleaseAll()
    {
        ushort[] pressed;
        lock (_gate) pressed = _pressed.ToArray();
        foreach (var code in pressed) Set(code, false);
    }

    // ---------------------------------------------------------------- ydotool fallback

    private bool EnsureConnectedLocked() { lock (_gate) return EnsureConnected(); }

    private bool EnsureConnected(bool force = false)
    {
        if (_socket != null) return true;
        if (!force && DateTimeOffset.UtcNow - _lastConnectAttempt < TimeSpan.FromSeconds(1)) return false;
        _lastConnectAttempt = DateTimeOffset.UtcNow;
        try
        {
            if (!File.Exists(SocketPath)) throw new IOException($"ydotoold socket not found: {SocketPath}");
            var socket = new Socket(AddressFamily.Unix, SocketType.Dgram, ProtocolType.Unspecified);
            socket.Connect(new UnixDomainSocketEndPoint(SocketPath));
            _socket = socket;
            _lastError = "";
            return true;
        }
        catch (Exception ex) { _lastError = ex.Message; return false; }
    }

    private void FallbackMoveAbsolute(double x, double y, bool recalibrate)
    {
        var b = _capture.InputBounds;
        int px = (int)Math.Round(Math.Clamp(x, 0, 1) * Math.Max(0, b.Width - 1));
        int py = (int)Math.Round(Math.Clamp(y, 0, 1) * Math.Max(0, b.Height - 1));
        lock (_gate)
        {
            if (!EnsureConnected()) return;
            try
            {
                // uinput is relative-only: park the cursor in the far corner once, then track it.
                if (recalibrate || !_cursorKnown)
                {
                    SendEvent(EvRel, RelX, 4096); SendEvent(EvRel, RelY, 4096); SendEvent(EvSyn, SynReport, 0);
                    _cursorX = Math.Max(0, b.Width - 1); _cursorY = Math.Max(0, b.Height - 1);
                    _cursorKnown = true;
                }
                int dx = px - _cursorX, dy = py - _cursorY;
                if (dx != 0) SendEvent(EvRel, RelX, dx);
                if (dy != 0) SendEvent(EvRel, RelY, dy);
                if (dx != 0 || dy != 0) SendEvent(EvSyn, SynReport, 0);
                _cursorX = px; _cursorY = py;
            }
            catch (Exception ex) { Drop(ex); }
        }
    }

    private bool Emit(ushort type, ushort code, int value)
    {
        lock (_gate)
        {
            if (!EnsureConnected()) return false;
            try { SendEvent(type, code, value); SendEvent(EvSyn, SynReport, 0); return true; }
            catch (Exception ex) { Drop(ex); return false; }
        }
    }

    private void SendEvent(ushort type, ushort code, int value)
    {
        Span<byte> data = stackalloc byte[24]; // timeval(16), type(2), code(2), value(4) — LE, x86_64
        BinaryPrimitives.WriteUInt16LittleEndian(data[16..], type);
        BinaryPrimitives.WriteUInt16LittleEndian(data[18..], code);
        BinaryPrimitives.WriteInt32LittleEndian(data[20..], value);
        if (_socket!.Send(data) != data.Length) throw new IOException("short ydotoold datagram write");
    }

    private void Drop(Exception ex)
    {
        _lastError = ex.Message;
        try { _socket?.Dispose(); } catch { }
        _socket = null;
        _cursorKnown = false;
        Log.Warn("Input socket failed: " + ex.Message);
    }

    public void Dispose()
    {
        ReleaseAll();
        lock (_gate) { _socket?.Dispose(); _socket = null; }
    }
}

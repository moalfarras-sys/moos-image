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

    /// <summary>Keys that modify another key rather than producing a character of their own.</summary>
    private static readonly Dictionary<string, ushort> Modifiers = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Control"] = 29, ["Ctrl"] = 29, ["Alt"] = 56, ["Shift"] = 42,
        ["Meta"] = 125, ["Super"] = 125, ["Win"] = 125, ["AltGr"] = 100,
    };

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

    /// <summary>
    /// A browser's `KeyboardEvent.code` to the evdev keycode in the same physical place.
    ///
    /// WHY THIS TABLE EXISTS AND WHY IT IS NOT A LAYOUT BUG WAITING TO HAPPEN
    ///
    /// The `Keys` table above carries five letters (a/c/v/x/z) and a comment explaining that they
    /// are QWERTY-shaped and therefore wrong on the owner's German keymap. That comment is right
    /// about `Keys` and does NOT apply here, because the two tables are keyed on different things:
    ///
    ///   Keys       is keyed on a CHARACTER the phone decided to send ("z"), so mapping it to a
    ///              position is a guess about the remote layout — and the guess was wrong.
    ///   this table is keyed on a POSITION the browser already measured ("KeyZ" means the key
    ///              one right of Shift, whatever is printed on it), and evdev keycodes are also
    ///              positions. Position to position needs no layout knowledge at all: the remote
    ///              compositor applies its own keymap on top, exactly as it does for a real
    ///              keyboard plugged into the machine.
    ///
    /// This is what a real remote-desktop protocol sends, and it is the only path that can support
    /// the three things the character path structurally cannot:
    ///
    ///   * HELD keys. `text` types a character once. Holding W to walk, or holding Backspace to
    ///     delete a line, needs a down that stays down — and key repeat then comes from the
    ///     REMOTE compositor's own repeat timer, which is the correct place for it.
    ///   * arbitrary shortcuts. Combo() resolves letters by keysym, which only reaches shift
    ///     level 1 of the active group; Ctrl+Shift+P and Alt+F4 need real positions.
    ///   * keys with no character at all: CapsLock, PrintScreen, the numeric keypad as distinct
    ///     from the digit row, ContextMenu, the media keys.
    ///
    /// Codes are from linux/input-event-codes.h. Entries the browser can report but Linux has no
    /// key for are deliberately absent rather than mapped to something close — a wrong key is
    /// worse than a dead one, because a dead one gets reported and a wrong one gets lived with.
    /// </summary>
    private static readonly Dictionary<string, ushort> PhysicalCodes = new(StringComparer.Ordinal)
    {
        // letter row block
        ["KeyA"] = 30, ["KeyB"] = 48, ["KeyC"] = 46, ["KeyD"] = 32, ["KeyE"] = 18, ["KeyF"] = 33,
        ["KeyG"] = 34, ["KeyH"] = 35, ["KeyI"] = 23, ["KeyJ"] = 36, ["KeyK"] = 37, ["KeyL"] = 38,
        ["KeyM"] = 50, ["KeyN"] = 49, ["KeyO"] = 24, ["KeyP"] = 25, ["KeyQ"] = 16, ["KeyR"] = 19,
        ["KeyS"] = 31, ["KeyT"] = 20, ["KeyU"] = 22, ["KeyV"] = 47, ["KeyW"] = 17, ["KeyX"] = 45,
        ["KeyY"] = 21, ["KeyZ"] = 44,
        // digit row
        ["Digit1"] = 2, ["Digit2"] = 3, ["Digit3"] = 4, ["Digit4"] = 5, ["Digit5"] = 6,
        ["Digit6"] = 7, ["Digit7"] = 8, ["Digit8"] = 9, ["Digit9"] = 10, ["Digit0"] = 11,
        ["Minus"] = 12, ["Equal"] = 13, ["Backquote"] = 41,
        // punctuation
        ["BracketLeft"] = 26, ["BracketRight"] = 27, ["Backslash"] = 43, ["Semicolon"] = 39,
        ["Quote"] = 40, ["Comma"] = 51, ["Period"] = 52, ["Slash"] = 53,
        // the 102nd key: present on ISO keyboards, absent on ANSI
        ["IntlBackslash"] = 86, ["IntlRo"] = 89, ["IntlYen"] = 124,
        // editing and whitespace
        ["Enter"] = 28, ["Escape"] = 1, ["Backspace"] = 14, ["Tab"] = 15, ["Space"] = 57,
        ["CapsLock"] = 58, ["Delete"] = 111, ["Insert"] = 110,
        // modifiers — LEFT and RIGHT are distinct keys and some apps care which one
        ["ShiftLeft"] = 42, ["ShiftRight"] = 54, ["ControlLeft"] = 29, ["ControlRight"] = 97,
        ["AltLeft"] = 56, ["AltRight"] = 100, ["MetaLeft"] = 125, ["MetaRight"] = 126,
        ["ContextMenu"] = 127,
        // navigation
        ["ArrowUp"] = 103, ["ArrowDown"] = 108, ["ArrowLeft"] = 105, ["ArrowRight"] = 106,
        ["Home"] = 102, ["End"] = 107, ["PageUp"] = 104, ["PageDown"] = 109,
        // function row
        ["F1"] = 59, ["F2"] = 60, ["F3"] = 61, ["F4"] = 62, ["F5"] = 63, ["F6"] = 64,
        ["F7"] = 65, ["F8"] = 66, ["F9"] = 67, ["F10"] = 68, ["F11"] = 87, ["F12"] = 88,
        ["F13"] = 183, ["F14"] = 184, ["F15"] = 185, ["F16"] = 186, ["F17"] = 187, ["F18"] = 188,
        ["F19"] = 189, ["F20"] = 190, ["F21"] = 191, ["F22"] = 192, ["F23"] = 193, ["F24"] = 194,
        // system keys
        ["PrintScreen"] = 99, ["ScrollLock"] = 70, ["Pause"] = 119,
        // the keypad, which is NOT the digit row: Numpad1 and Digit1 are different keys and
        // spreadsheets, games and NumLock-sensitive apps all tell them apart.
        ["NumLock"] = 69, ["NumpadDivide"] = 98, ["NumpadMultiply"] = 55, ["NumpadSubtract"] = 74,
        ["NumpadAdd"] = 78, ["NumpadEnter"] = 96, ["NumpadDecimal"] = 83, ["NumpadEqual"] = 117,
        ["Numpad0"] = 82, ["Numpad1"] = 79, ["Numpad2"] = 80, ["Numpad3"] = 81, ["Numpad4"] = 75,
        ["Numpad5"] = 76, ["Numpad6"] = 77, ["Numpad7"] = 71, ["Numpad8"] = 72, ["Numpad9"] = 73,
        // media and volume: a laptop keyboard has these and a remote desktop should honour them
        ["AudioVolumeMute"] = 113, ["AudioVolumeDown"] = 114, ["AudioVolumeUp"] = 115,
        ["MediaPlayPause"] = 164, ["MediaStop"] = 166,
        ["MediaTrackNext"] = 163, ["MediaTrackPrevious"] = 165,
        ["BrowserBack"] = 158, ["BrowserForward"] = 159, ["BrowserRefresh"] = 173,
    };

    /// <summary>True when this physical key is one we can actually press.</summary>
    public static bool HasPhysical(string code) => PhysicalCodes.ContainsKey(code);

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
        // A lone printable character must type layout-independently via keysym. The single-letter
        // entries in Keys (a/c/v/x/z) exist only for Ctrl-combos and are German-QWERTZ-dependent:
        // tapping them as characters swaps y/z and mangles symbols on the owner's German keymap
        // (the reported "types wrong" bug). Named keys (Enter, Tab, arrows, F-keys) and modifiers
        // keep the keycode path; combos still resolve letters through Keys via Combo().
        if (k.Length == 1 && k[0] is >= ' ' and <= '~') { TypeText(k); return; }
        if (Keys.TryGetValue(k, out var c)) { Set(c, true); Thread.Sleep(12); Set(c, false); }
        else if (k.Length >= 1) TypeText(k);
    }
    public void KeyDown(string k) { if (Keys.TryGetValue(k, out var c)) Set(c, true); }
    public void KeyUp(string k) { if (Keys.TryGetValue(k, out var c)) Set(c, false); }

    /// <summary>
    /// Press or release a key by PHYSICAL position (a browser `KeyboardEvent.code`).
    ///
    /// Set() deduplicates against _pressed, which is exactly right for a browser: a held key fires
    /// keydown over and over at the local repeat rate, and forwarding each one would either double
    /// every character or fight the remote's own repeat timer. The first down goes through, the
    /// repeats are dropped, and the desktop repeats at ITS configured rate — the same thing that
    /// happens with a keyboard plugged into the machine.
    ///
    /// It also means ReleaseAll() already covers these keys, so a browser tab closed mid-chord
    /// cannot leave Ctrl stuck down on the server.
    /// </summary>
    public void KeyCode(string code, bool down)
    {
        if (PhysicalCodes.TryGetValue(code, out var c)) Set(c, down);
    }

    public void KeyTapCode(string code)
    {
        if (!PhysicalCodes.TryGetValue(code, out var c)) return;
        Set(c, true);
        Thread.Sleep(12);
        Set(c, false);
    }

    /// <summary>
    /// Modifiers are physical keys, so they go by keycode. The key they modify is a CHARACTER, so
    /// it goes by keysym: the keycode table above is QWERTY, and the owner's keymap is German
    /// QWERTZ, where evdev 44 is 'y' — which is why Ctrl+Z was performing redo instead of undo.
    /// A keysym lets the compositor find the right physical key for whatever layout is loaded.
    /// </summary>
    public void Combo(IReadOnlyList<string> keys)
    {
        var mods = new List<ushort>();
        var rest = new List<Stroke>();
        foreach (var k in keys)
        {
            if (Modifiers.TryGetValue(k, out var mod)) { if (!mods.Contains(mod)) mods.Add(mod); }
            else if (k.Length == 1 && k[0] is > ' ' and <= '~')
                rest.Add(Stroke.Keysym(char.ToLowerInvariant(k[0])));
            else if (Keys.TryGetValue(k, out var code))
                rest.Add(Stroke.Code(code));
        }

        // Only release what THIS combo pressed.
        //
        // Set() is a no-op for a key already in _pressed, so a modifier the user is physically holding
        // is correctly not re-pressed on the way in — but the unconditional release on the way out sent
        // a real key-up for it. So tapping Ctrl+C on the on-screen bar while holding Ctrl on a real
        // keyboard RELEASED the user's Ctrl, and the desktop input layer still had that key in its own
        // held set, so it would never send another down: Ctrl stuck up until they let go and pressed
        // again. The two keyboard paths share one _pressed, which is what makes them interfere.
        var pressedHere = new List<ushort>();
        lock (_gate)
        {
            foreach (var m in mods) if (!_pressed.Contains(m)) pressedHere.Add(m);
        }
        foreach (var m in mods) Set(m, true);            // tracked, so ReleaseAll can undo them
        var events = new List<object>();
        foreach (var s in rest) events.Add(s.Event(down: true));
        for (int i = rest.Count - 1; i >= 0; i--) events.Add(rest[i].Event(down: false));
        if (events.Count > 0 && !_portal.Send(new { type = "keysyms", events }))
            FallbackCombo(keys);
        for (int i = pressedHere.Count - 1; i >= 0; i--) Set(pressedHere[i], false);
    }

    /// <summary>One press in an ordered batch: a keysym (a character) or a raw evdev code (a key).</summary>
    private readonly record struct Stroke(int Value, bool IsKeysym)
    {
        public static Stroke Keysym(char c) => new(TextKeysym.ForCodepoint(c), true);
        public static Stroke Code(ushort code) => new(code, false);
        public object Event(bool down) => IsKeysym
            ? new { keysym = Value, down }
            : (object)new { code = Value, down };
    }

    /// <summary>ydotool has no keysyms; on that path the QWERTY table is all there is.</summary>
    private void FallbackCombo(IReadOnlyList<string> keys)
    {
        var codes = keys.Select(k => Keys.TryGetValue(k, out var c) ? c : (ushort)0).Where(c => c > 0).ToArray();
        foreach (var c in codes) Set(c, true);
        for (int i = codes.Length - 1; i >= 0; i--) Set(codes[i], false);
    }

    /// <summary>
    /// Types text, choosing between two paths because KWin's keysym injection only reaches the
    /// FIRST shift level of the ACTIVE layout group. Measured against a live KWin 6.7 session on
    /// the owner's `de,ara` keymap:
    ///   'a'  -> 'a'                              (level 1 of the active group: correct)
    ///   'Z'  -> 'z'                              (the shift level is never applied)
    ///   'م'  -> keycode 247, keyval 0x1008ffb5   (a keysym from an inactive group: garbage)
    /// So the fast path is restricted to characters that are level 1 on any Latin layout, with
    /// capitals produced by holding a real Shift keycode around the lowercase keysym. Everything
    /// else — Arabic, punctuation that needs a shift level, emoji — goes through the clipboard,
    /// which is layout-independent and carries any Unicode exactly.
    /// </summary>
    public void TypeText(string text)
    {
        if (string.IsNullOrEmpty(text)) return;

        // Keysyms are typed one at a time, so a long run would crawl. Above a paragraph or so one
        // clipboard paste is far quicker, and the user is pasting anyway.
        if (_portal.IsReady && text.Length <= BulkPasteThreshold && TryDirectStrokes(text, out var events)
            && _portal.Send(new { type = "keysyms", events })) return;

        PasteText(text);
    }

    private const int BulkPasteThreshold = 64;

    /// <summary>
    /// Builds an ordered press/release batch, or fails if any character cannot be typed correctly
    /// by keysym on an arbitrary Latin layout.
    /// </summary>
    private static bool TryDirectStrokes(string text, out List<object> events)
    {
        events = [];
        foreach (var rune in text.EnumerateRunes())
        {
            int c = rune.Value;
            if (c is >= 'a' and <= 'z' or >= '0' and <= '9' || c == ' ')
            {
                events.Add(new { keysym = c, down = true });
                events.Add(new { keysym = c, down = false });
            }
            else if (c is >= 'A' and <= 'Z')
            {
                // The capital's own keysym resolves to the same physical key but types lowercase,
                // so the shift has to be a real key press around it.
                int lower = c + ('a' - 'A');
                events.Add(new { code = (int)ShiftCode, down = true });
                events.Add(new { keysym = lower, down = true });
                events.Add(new { keysym = lower, down = false });
                events.Add(new { code = (int)ShiftCode, down = false });
            }
            else { events = []; return false; }
        }
        return events.Count > 0;
    }

    private const ushort ShiftCode = 42;

    // ---------------------------------------------------------------- clipboard typing

    private readonly object _clipGate = new();
    private ClipContent? _borrowedClip;
    private int _pasteGeneration;

    /// <summary>
    /// Types by borrowing the clipboard. Shift+Insert rather than Ctrl+V: Ctrl+V is not paste in a
    /// terminal (Konsole needs Ctrl+Shift+V), which is why typing Arabic into a shell did nothing
    /// at all. Shift+Insert is paste in Konsole, GTK, Qt and browsers alike.
    /// </summary>
    private void PasteText(string text)
    {
        int gen = Interlocked.Increment(ref _pasteGeneration);
        lock (_clipGate)
        {
            // Snapshot once per burst. Re-reading between consecutive chunks would "save" the text
            // we just pasted and hand the user that instead of what they had.
            _borrowedClip ??= ClipboardBridge.GetContent();
        }
        ClipboardBridge.SetText(text);
        Combo(["Shift", "Insert"]);
        ScheduleClipboardReturn(gen);
    }

    /// <summary>Hand the clipboard back once typing has settled, so a borrow is not a theft.</summary>
    private void ScheduleClipboardReturn(int gen)
    {
        _ = Task.Delay(TimeSpan.FromMilliseconds(700)).ContinueWith(_ =>
        {
            // More text arrived; that paste now owns the borrow and will return it.
            if (Volatile.Read(ref _pasteGeneration) != gen) return;
            ClipContent? saved;
            lock (_clipGate) { saved = _borrowedClip; _borrowedClip = null; }
            if (saved is null) return;
            try
            {
                if (saved.Kind == "text" && !string.IsNullOrEmpty(saved.Text)) ClipboardBridge.SetText(saved.Text);
                else if (saved.Kind == "image" && saved.ImagePng is { Length: > 0 } png) ClipboardBridge.SetImagePng(png);
            }
            catch (Exception ex) { Log.Warn("Clipboard restore failed: " + ex.Message); }
        });
    }

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

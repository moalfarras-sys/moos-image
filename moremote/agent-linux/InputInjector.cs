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

    // A button press moves the caret, so it must land AFTER any text still waiting in
    // the paste gather — exactly like KeyTap/KeyDown/Combo already do. Without this,
    // a tap that arrives inside the gather window executes first and the gathered word
    // is pasted into whatever that tap just focused. MouseMove is deliberately NOT
    // flushed: moving the pointer alone changes no caret, and flushing on every motion
    // event would defeat the gather entirely.
    public void Click(string button, double x, double y) { FlushPendingText(); MouseMove(x, y); ClickCode(Button(button)); }
    public void ClickCurrent(string button) { FlushPendingText(); ClickCode(Button(button)); }
    public void DoubleClick(double x, double y) { FlushPendingText(); MouseMove(x, y); DoubleClickCurrent(); }
    public void DoubleClickCurrent() { ClickCode(BtnLeft); Thread.Sleep(40); ClickCode(BtnLeft); }
    public void MouseButton(string button, bool down, double x, double y) { FlushPendingText(); MouseMove(x, y); Set(Button(button), down); }
    public void MouseButtonCurrent(string button, bool down) { FlushPendingText(); Set(Button(button), down); }

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
        // Deliver anything still gathering first: Enter/Backspace/arrows act ON the
        // text, so letting a key overtake a pending paste would reorder the edit.
        FlushPendingText();
        // A lone printable character must type layout-independently via keysym. The single-letter
        // entries in Keys (a/c/v/x/z) exist only for Ctrl-combos and are German-QWERTZ-dependent:
        // tapping them as characters swaps y/z and mangles symbols on the owner's German keymap
        // (the reported "types wrong" bug). Named keys (Enter, Tab, arrows, F-keys) and modifiers
        // keep the keycode path; combos still resolve letters through Keys via Combo().
        if (k.Length == 1 && k[0] is >= ' ' and <= '~') { TypeText(k); return; }
        // Backspace arrives in bursts when the phone diffs an autocorrect rewrite;
        // 12 ms of hold per repeat serialized a 30-key burst into ~0.7 s of injection.
        // Apps register a 4 ms hold fine for repeats of the same edit key.
        if (Keys.TryGetValue(k, out var c)) { Set(c, true); Thread.Sleep(k == "Backspace" || k == "Delete" ? 4 : 12); Set(c, false); }
        else if (k.Length >= 1) TypeText(k);
    }
    public void KeyDown(string k) { FlushPendingText(); if (Keys.TryGetValue(k, out var c)) Set(c, true); }
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
        // Same ordering rule as KeyTap — and with no exemption now. Shift+Insert used to be
        // exempt because typing WAS a paste; it no longer is, so the combo is just a shortcut.
        FlushPendingText();
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
    /// Types text by pressing the keys that carry it, on the keymap group that carries them.
    ///
    /// WHY THE CLIPBOARD IS GONE
    ///
    /// KWin resolves an injected keysym against the ACTIVE keymap group only, and only at shift
    /// level one. Measured on a live KWin 6.7 session with the owner's `de,us,ara` keymap sitting
    /// in the German group:
    ///   'a'  -> 'a'                              (level 1 of the active group: correct)
    ///   'Z'  -> 'z'                              (the shift level is never applied)
    ///   'م'  -> keycode 247, keyval 0x1008ffb5   (a keysym from an inactive group: garbage)
    /// So Arabic used to be typed by borrowing the clipboard and pasting it. That mechanism was
    /// the source of every scrambling report this file has a comment about: the clipboard is ONE
    /// shared slot, wl-copy returns before the selection is servable, and the application fetches
    /// it asynchronously — three separate races around a resource that belongs to the user.
    ///
    /// The group is not fixed, though. org.kde.KeyboardLayouts.setLayout selects it, and with the
    /// Arabic group active the Arabic letters ARE level one — on their own physical keys. So the
    /// honest mechanism is the one a real keyboard uses: select the group, then press positions.
    /// Nothing is borrowed, nothing is pasted, and any character the layout carries is reachable
    /// at any shift level rather than only level one.
    ///
    /// WHAT MAKES THIS SAFE, HAVING MEASURED WHAT MAKES IT UNSAFE
    ///
    /// A layout switch and a keystroke travel to KWin as two independent messages, and the switch
    /// can OVERTAKE keys already queued. Measured on the live session, switching and injecting with
    /// a sub-millisecond gap: 0 of 25 runs correct — 'مرحبا' arrived as 'lvpfhab', which is the
    /// GERMAN reading of those same positions. Neither available signal rescues it: setLayout's own
    /// D-Bus reply and the layoutChanged signal (0.15 ms median) both report a switch that has been
    /// ACCEPTED, not one that has been APPLIED, and typing straight after either is still wrong.
    ///
    /// The fix is to stop having two channels. A run is delivered as ONE ordered batch in which the
    /// switch is an element like any other, and the helper executes that batch strictly
    /// sequentially, awaiting each call before issuing the next (see mo-remote-portal.py). Ordering
    /// then comes from the single stream rather than from a delay nobody can size honestly — the
    /// same reasoning that killed "paste anyway" in ClipboardBridge.
    /// </summary>
    public void TypeText(string text)
    {
        if (string.IsNullOrEmpty(text)) return;

        lock (_textBuf)
        {
            if (_pending.Length > 0)
            {
                _pending.Append(text);
                // A word joining the gather completes it — and the age cap means even a stream
                // of single letters whose gaps never reach the window delivers within 700 ms.
                if (text.Length > 1 || _pending.Length >= TextCoalesceMax ||
                    Environment.TickCount64 - _pendingSince >= TextMaxHoldMs) { FlushTextLocked(); }
                else { _textTimer?.Change(TextCoalesceMs, Timeout.Infinite); }
                return;
            }
            QueueTextLocked(text);
        }
    }

    // ---------------------------------------------------------------- text coalescing
    //
    // Gathering no longer exists to amortise a clipboard cycle — there isn't one. It exists
    // because a GROUP SWITCH is the expensive act now: KWin announces every one of them to
    // plasmashell's OSD service, which paints a layout pill in the middle of the screen. On a
    // remote session that pill is re-encoded into the video stream, so a switch per letter would
    // strobe the picture. Gathering a word means one switch for the word instead of six.
    private readonly object _textBuf = new();
    private readonly System.Text.StringBuilder _pending = new();
    private Timer? _textTimer;

    /// <summary>Milliseconds of quiet before a gathered run is typed.</summary>
    private const int TextCoalesceMs = 140;
    /// <summary>Never gather more than this: typing must stay responsive.</summary>
    private const int TextCoalesceMax = 240;
    /// <summary>A re-arming gather never fires under continuous letters; nothing waits past this.
    /// Mirrors the client's own TEXT_COALESCE_MAX_MS — this was the half of the shipped
    /// "240 chars / 700 ms" bound that only existed on the client.</summary>
    private const int TextMaxHoldMs = 700;
    /// <summary>When the buffer last went empty→non-empty (Environment.TickCount64).</summary>
    private long _pendingSince;

    /// <summary>QueueText's body, for callers that already hold _textBuf.</summary>
    private void QueueTextLocked(string text)
    {
        if (_pending.Length == 0) _pendingSince = Environment.TickCount64;
        _pending.Append(text);
        // A multi-character chunk IS a gathered word: the phone already coalesced it (220 ms
        // of quiet, or a whole committed autocorrect). Holding it ANOTHER 140 ms here merged
        // nothing and put a fixed tax on every word — the window exists to merge
        // letter-at-a-time arrivals, so only single letters wait for company.
        if (text.Length > 1 || _pending.Length >= TextCoalesceMax ||
            Environment.TickCount64 - _pendingSince >= TextMaxHoldMs) { FlushTextLocked(); return; }
        _textTimer ??= new Timer(_ => FlushText(), null, Timeout.Infinite, Timeout.Infinite);
        _textTimer.Change(TextCoalesceMs, Timeout.Infinite);
    }

    private void FlushText()
    {
        lock (_textBuf) { FlushTextLocked(); }
    }

    private void FlushTextLocked()
    {
        if (_pending.Length == 0) return;
        var run = _pending.ToString();
        _pending.Clear();
        _textTimer?.Change(Timeout.Infinite, Timeout.Infinite);
        Deliver(run);
    }

    /// <summary>Deliver anything still gathered — called before a key that acts on the text.</summary>
    public void FlushPendingText() => FlushText();

    /// <summary>
    /// Appends an ordered press/release batch for text typed on a LATIN group, or fails if any
    /// character is not level 1 there. Keysyms rather than positions: the user's Latin layout may
    /// be any of them (this machine's is German QWERTZ), and a keysym lets the compositor find
    /// the right key for the layout it actually has — which is exactly what the Arabic path
    /// cannot do, and why that one names positions instead.
    /// </summary>
    private static bool TryDirectStrokes(string text, List<object> events)
    {
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
            else return false;
        }
        return true;
    }

    private const ushort ShiftCode = 42;

    // ---------------------------------------------------------------- layout-aware delivery

    /// <summary>
    /// Types a gathered run, splitting it where the required keymap group changes.
    ///
    /// A run is cut into maximal stretches that one group can type, and each stretch becomes a
    /// batch whose FIRST element names the group it needs. Characters that both groups carry —
    /// space, digits, Latin punctuation — deliberately do NOT decide a stretch: they join
    /// whichever one is already open. Letting a full stop between two Arabic words claim the
    /// Latin group would cost two switches, and every switch is an OSD pill painted across the
    /// picture the remote user is watching.
    /// </summary>
    private void Deliver(string run)
    {
        foreach (var (text, arabic) in SplitByGroup(run))
        {
            var events = new List<object> { new { layout = arabic ? "ara" : "home" } };
            bool built = arabic ? AraKeymap.TryStrokes(text, events)
                                : TryDirectStrokes(text, events);
            if (!built)
            {
                // Fail closed, exactly as the clipboard path learned to. A character with no key
                // on either group (an emoji, a symbol from a third script) cannot be typed by a
                // keyboard at all, and typing the REST of the run would silently reorder the
                // user's sentence around the hole.
                Log.Warn($"Typing skipped {text.Length} character(s) with no key on the available " +
                         "layouts; nothing was typed for that run.");
                continue;
            }
            if (!_portal.Send(new { type = "keysyms", events }))
                FallbackType(text, arabic);
        }
    }

    /// <summary>
    /// Cuts a run into (text, needsArabicGroup) stretches. Characters either group can produce
    /// extend the current stretch rather than starting a new one.
    /// </summary>
    internal static List<(string Text, bool Arabic)> SplitByGroup(string run)
    {
        var parts = new List<(string, bool)>();
        var buf = new System.Text.StringBuilder();
        bool? mode = null;
        foreach (var rune in run.EnumerateRunes())
        {
            bool? want = AraKeymap.NeedsArabicGroup(rune.Value) ? true
                       : IsLatinTypable(rune.Value) ? false
                       : (bool?)null;
            // A character neither group claims (emoji) still has to break the stretch, so the
            // undeliverable part is reported on its own instead of poisoning a good one.
            if (want is null)
            {
                if (buf.Length > 0) { parts.Add((buf.ToString(), mode ?? false)); buf.Clear(); }
                parts.Add((rune.ToString(), false));
                mode = null;
                continue;
            }
            if (mode is not null && want != mode && !Ambiguous(rune.Value))
            {
                parts.Add((buf.ToString(), mode.Value));
                buf.Clear();
                mode = want;
            }
            else if (mode is null) mode = want;
            buf.Append(rune.ToString());
        }
        if (buf.Length > 0) parts.Add((buf.ToString(), mode ?? false));
        return parts;
    }

    /// <summary>A character both groups can type, so it must not force a switch of its own.</summary>
    private static bool Ambiguous(int c) =>
        AraKeymap.Has(c) && IsLatinTypable(c) && c <= 0x7F;

    private static bool IsLatinTypable(int c) =>
        c is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' || c == ' ';

    /// <summary>
    /// The portal is down, so injection is uinput and there is no way to select a keymap group
    /// from here — ydotoold speaks positions to the kernel, and the group lives in the
    /// compositor. ASCII still types correctly on any Latin layout; Arabic cannot, and says so
    /// rather than delivering the Latin reading of those positions (which is exactly the
    /// 'lvpfhab' failure this design was built to prevent).
    /// </summary>
    private void FallbackType(string text, bool arabic)
    {
        if (arabic)
        {
            Log.Warn($"Cannot type {text.Length} Arabic character(s): the portal is unavailable and " +
                     "the uinput fallback cannot select a keymap group.");
            return;
        }
        foreach (var rune in text.EnumerateRunes())
        {
            int c = rune.Value;
            if (c is >= 'A' and <= 'Z')
            {
                Set(ShiftCode, true);
                TapAscii(c + ('a' - 'A'));
                Set(ShiftCode, false);
            }
            else TapAscii(c);
        }
    }

    private void TapAscii(int lower)
    {
        if (!AsciiCodes.TryGetValue(lower, out var code)) return;
        Set(code, true); Thread.Sleep(4); Set(code, false);
    }

    /// <summary>US-positional ASCII, for the fallback only — the portal path never uses it.</summary>
    private static readonly Dictionary<int, ushort> AsciiCodes = BuildAscii();

    private static Dictionary<int, ushort> BuildAscii()
    {
        var m = new Dictionary<int, ushort> { [' '] = 57 };
        const string row1 = "qwertyuiop", row2 = "asdfghjkl", row3 = "zxcvbnm";
        for (int i = 0; i < row1.Length; i++) m[row1[i]] = (ushort)(16 + i);
        for (int i = 0; i < row2.Length; i++) m[row2[i]] = (ushort)(30 + i);
        for (int i = 0; i < row3.Length; i++) m[row3[i]] = (ushort)(44 + i);
        m['1'] = 2; m['2'] = 3; m['3'] = 4; m['4'] = 5; m['5'] = 6;
        m['6'] = 7; m['7'] = 8; m['8'] = 9; m['9'] = 10; m['0'] = 11;
        return m;
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

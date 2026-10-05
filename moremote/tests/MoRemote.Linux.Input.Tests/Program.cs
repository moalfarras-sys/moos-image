using System.Text.Json;
using System.Buffers.Binary;
using System.Net.Sockets;
using MoRemote;

// Compile the production injector against an in-memory portal and a deliberately
// absent uinput socket. These tests cannot send keys to the machine running them.
try
{
Environment.SetEnvironmentVariable("YDOTOOL_SOCKET", Path.Combine(
    Path.GetTempPath(), "moremote-no-input-" + Guid.NewGuid(), "absent.sock"));
int passed = 0;
void Check(bool condition, string name)
{
    if (!condition) throw new Exception(name);
    passed++;
}

using (var portal = new PortalBridge())
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    portal.Keymap = Fixture(1);
    input.TypeText("a");
    input.DoubleClickCurrent();
    var sent = portal.Snapshot();
    Check(sent.Length == 5 && sent[0].GetProperty("type").GetString() == "keysyms",
        "touchpad double-click drains gathered text before selecting or changing focus");
    Check(!sent[0].GetProperty("secure").GetBoolean(),
        "ordinary committed typing retains its fast native input path");
    Check(sent.Skip(1).Select(e => e.GetProperty("down").GetBoolean())
        .SequenceEqual([true, false, true, false]), "double-click keeps both press/release pairs");
}

using (var portal = new PortalBridge())
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    portal.Keymap = Fixture(1);
    input.KeyCode("ControlLeft", true);
    input.TypeText("a");
    input.ReleaseAll();
    var sent = portal.Snapshot();
    Check(sent.Length == 3 && sent[1].GetProperty("type").GetString() == "keysyms"
        && !sent[2].GetProperty("down").GetBoolean(),
        "release drains accepted text before releasing held modifiers");
    Thread.Sleep(220);
    Check(portal.Snapshot().Length == sent.Length, "release leaves no delayed text timer output");
}

using (var portal = new PortalBridge())
{
    portal.Keymap = Fixture(1);
    var input = new InputInjector(portal, new ScreenCapture());
    input.TypeText("a");
    input.Dispose();
    Check(portal.Snapshot().Length == 1, "dispose drains accepted text before returning");
    Check(!input.IsReady, "a disposed injector is not advertised ready");
    input.TypeText("b");
    input.KeyCode("KeyC", true);
    Thread.Sleep(220);
    Check(portal.Snapshot().Length == 1, "disposed injector cannot emit delayed or new keys");
    input.Dispose();
}

using (var portal = new PortalBridge())
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    portal.Accept = false;
    input.KeyCode("KeyA", true);
    portal.Accept = true;
    input.KeyCode("KeyA", true);
    Check(portal.Snapshot().Length == 1, "failed down does not poison dedup after backend recovers");
    portal.Accept = false;
    input.KeyCode("KeyA", false);
    portal.Accept = true;
    input.ReleaseAll();
    Check(portal.Snapshot().Length == 2 && !portal.Snapshot()[1].GetProperty("down").GetBoolean(),
        "failed release remains tracked so recovery can release the held key");
}

using (var portal = new PortalBridge())
using (var input = new InputInjector(portal, new ScreenCapture()))
using (var enteredDown = new ManualResetEventSlim())
using (var unblockDown = new ManualResetEventSlim())
using (var releaseStarted = new ManualResetEventSlim())
{
    portal.BeforeSend = e =>
    {
        if (e.GetProperty("type").GetString() == "key" && e.GetProperty("down").GetBoolean())
        {
            enteredDown.Set();
            if (!unblockDown.Wait(TimeSpan.FromSeconds(5))) throw new TimeoutException("test send unblock");
        }
    };
    var press = Task.Run(() => input.KeyCode("ControlLeft", true));
    Check(enteredDown.Wait(TimeSpan.FromSeconds(5)), "test captured an in-flight key press");
    var release = Task.Run(() => { releaseStarted.Set(); input.ReleaseAll(); });
    try
    {
        Check(releaseStarted.Wait(TimeSpan.FromSeconds(5)), "concurrent release started");
        Check(!release.Wait(100), "concurrent release cannot overtake an in-flight key-down");
    }
    finally
    {
        unblockDown.Set();
        Task.WaitAll(press, release);
    }
    Check(portal.Snapshot().Select(e => e.GetProperty("down").GetBoolean())
        .SequenceEqual([true, false]), "wire order ends released after concurrent cleanup");
}

// A private datagram recorder exercises the real fallback without /dev/uinput.
var socketDir = Path.Combine(Path.GetTempPath(), "moremote-input-test-" + Guid.NewGuid());
Directory.CreateDirectory(socketDir);
var socketPath = Path.Combine(socketDir, "input.sock");
try
{
    using var recorder = new Socket(AddressFamily.Unix, SocketType.Dgram, ProtocolType.Unspecified);
    recorder.Bind(new UnixDomainSocketEndPoint(socketPath));
    recorder.ReceiveTimeout = 2000;
    Environment.SetEnvironmentVariable("YDOTOOL_SOCKET", socketPath);
    using var portal = new PortalBridge { Accept = false };
    using var input = new InputInjector(portal, new ScreenCapture());
    input.MouseButtonCurrent("left", true);
    var down = ReceiveKey(recorder);
    portal.Accept = true;
    input.MouseButtonCurrent("left", false);
    var up = ReceiveKey(recorder);
    Check(down == (0x110, 1) && up == (0x110, 0),
        "portal recovery releases the button in the fallback that accepted its press");
    Check(portal.Snapshot().Length == 0, "fallback release never goes to the newly ready portal");
    input.KeyCode("KeyA", true);
    portal.Accept = false;
    input.ReleaseAll();
    Check(!recorder.Poll(100000, SelectMode.SelectRead),
        "an unavailable portal's held key is not incorrectly released into fallback");
    portal.Accept = true;
    input.ReleaseAll();
    Check(portal.Snapshot().Select(e => e.GetProperty("down").GetBoolean())
        .SequenceEqual([true, false]), "portal release is retried against its original backend");
}
finally
{
    Environment.SetEnvironmentVariable("YDOTOOL_SOCKET", Path.Combine(socketDir, "absent.sock"));
    Directory.Delete(socketDir, true);
}

// Model the compositor with only the private socket's relative events. Portal and
// local moves deliberately happen behind the fallback estimate's back.
var pointerDir = Path.Combine(Path.GetTempPath(), "moremote-pointer-test-" + Guid.NewGuid());
Directory.CreateDirectory(pointerDir);
try
{
    using var recorder = new Socket(AddressFamily.Unix, SocketType.Dgram, ProtocolType.Unspecified);
    var pointerSocketPath = Path.Combine(pointerDir, "input.sock");
    recorder.Bind(new UnixDomainSocketEndPoint(pointerSocketPath));
    Environment.SetEnvironmentVariable("YDOTOOL_SOCKET", pointerSocketPath);
    using var portal = new PortalBridge { Accept = false };
    var capture = new ScreenCapture();
    using var input = new InputInjector(portal, capture);
    int actualX = 0, actualY = 0;
    List<(int Type, int Code, int Value)> Drain()
    {
        var events = new List<(int, int, int)>();
        while (recorder.Poll(10000, SelectMode.SelectRead))
        {
            byte[] data = new byte[24];
            Check(recorder.Receive(data) == 24, "private pointer event is complete");
            int type = BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(16));
            int code = BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(18));
            int value = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan(20));
            events.Add((type, code, value));
            if (type == 2 && code == 0) actualX = Math.Clamp(actualX + value, 0, capture.InputBounds.Width - 1);
            if (type == 2 && code == 1) actualY = Math.Clamp(actualY + value, 0, capture.InputBounds.Height - 1);
        }
        return events;
    }
    input.MouseMove(.2, .3); Drain();
    portal.Accept = true;
    input.MouseMove(.8, .7);
    actualX = 1535; actualY = 755;
    portal.Accept = false;
    input.MouseMove(.25, .25);
    var afterPortal = Drain();
    Check((actualX, actualY) == (480, 270), "absolute fallback reacquires after portal motion");
    Check(afterPortal.Any(e => e == (2, 0, 4096)), "portal handoff invalidates the old estimate");
    portal.Accept = true;
    input.MouseMoveRelative(100, -20);
    actualX += 100; actualY -= 20;
    portal.Accept = false;
    input.MouseMove(.5, .5); Drain();
    Check((actualX, actualY) == (960, 540), "relative portal motion also invalidates fallback tracking");
    actualX = 0; actualY = 0; // owner moved the physical mouse, with no Remote event
    input.Click("left", .5, .5);
    var click = Drain();
    Check((actualX, actualY) == (960, 540), "tap reacquires after external pointer movement");
    Check(click.Where(e => e.Type == 1).Select(e => e.Value).SequenceEqual([1, 0]),
        "recalibrated click still ends with one complete button pair");
    capture.InputBounds = (1536, 864);
    input.MouseMove(.5, .5); Drain();
    Check((actualX, actualY) == (768, 432), "fractional-scale workspace change invalidates the old extent");
    capture.InputBounds = (0, 0);
    Check(!input.IsReady, "unknown geometry is not advertised as ready");
    input.Click("left", .4, .4);
    Check(!recorder.Poll(10000, SelectMode.SelectRead), "unknown geometry never clicks a guessed target");
}
finally
{
    Environment.SetEnvironmentVariable("YDOTOOL_SOCKET", Path.Combine(pointerDir, "absent.sock"));
    Directory.Delete(pointerDir, true);
}

// ── Typing follows the live keymap. Fixture: real libxkbcommon output for MoOS's `ara,de` ring ──
// (tests/test_remote_live_keymap.py proves it against the compiler and the live Arabic measurement).
using (var portal = new PortalBridge { Keymap = Fixture(0) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    input.TypeText("Hallo");
    var sent = portal.Snapshot();
    Check(sent.Length == 1 && sent[0].GetProperty("type").GetString() == "keysyms",
        "English on the Arabic-active ring is one ordered batch");
    var (layout, group, keys) = Batch(sent[0]);
    Check(layout == "de" && group == 1,
        "Latin text selects the German group instead of injecting keysyms on the Arabic group (owner report)");
    Check(keys.SequenceEqual(Seq(Shifted(35), Tap(30, 38, 38, 24))), "Hallo is typed on real positions, Shift for H");
    Check(sent[0].GetProperty("text").GetBoolean(), "a typed run is marked as text so the helper neutralizes Caps Lock");
}

using (var portal = new PortalBridge { Keymap = Fixture(1) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    input.TypeText("Grüße");
    input.TypeText("a@b.de");
    var sent = portal.Snapshot();
    Check(sent.Length == 2 && ClipboardBridge.Published.Count == 0,
        "German umlauts, ß and @ type natively, never through the clipboard");
    Check(Batch(sent[0]).Keys.SequenceEqual(Seq(Shifted(34), Tap(19, 26, 12, 18))), "Grüße uses ü=26 and ß=12");
    Check(Batch(sent[1]).Keys.SequenceEqual(Seq(Tap(30), AltGr(16), Tap(48, 52, 32, 18))), "@ is AltGr+Q on German");
}

using (var portal = new PortalBridge { Keymap = Fixture(0) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    input.TypeText("مرحبا Welt");
    var sent = portal.Snapshot();
    Check(sent.Length == 2 && Batch(sent[0]).Layout == "ara" && Batch(sent[1]).Layout == "de",
        "mixed Arabic/German text switches group exactly once");
    var all = Batch(sent[0]).Keys.Concat(Batch(sent[1]).Keys).ToArray();
    Check(all.SequenceEqual(Seq(Tap(38, 47, 25, 33, 35, 57), Shifted(17), Tap(18, 38, 20))),
        "the Arabic word, one space and the German word keep their order and positions");
}

using (var portal = new PortalBridge { Keymap = Fixture(1) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    input.TypeText("é"); input.FlushPendingText();
    input.TypeText("é");
    input.TypeText("ä");
    input.TypeText("^"); input.FlushPendingText();
    var sent = portal.Snapshot();
    Check(sent.Length == 4 && ClipboardBridge.Published.Count == 0, "accents from phone keyboards type natively");
    Check(Batch(sent[0]).Keys.SequenceEqual(Tap(13, 18)), "precomposed é is German dead acute + e");
    Check(Batch(sent[1]).Keys.SequenceEqual(Tap(13, 18)), "decomposed e + U+0301 is the same two keys");
    Check(Batch(sent[2]).Keys.SequenceEqual(Tap(40)), "decomposed a + U+0308 uses the German ä key");
    Check(Batch(sent[3]).Keys.SequenceEqual(Tap(41, 57)) && Batch(sent[3]).Layout == "de",
        "^ stays on the active German group as dead circumflex + space");
}

using (var portal = new PortalBridge { Keymap = Fixture(1) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    ClipboardBridge.Published.Clear();
    input.TypeText("Hi 👍");
    var sent = portal.Snapshot();
    Check(ClipboardBridge.Published.SequenceEqual(["Hi 👍"]) && sent.Length == 1
        && sent[0].GetProperty("sync").GetBoolean(),
        "a grapheme on no group preserves the whole commit as one exact paste");
    portal.Keymap = null;
    input.TypeText("abc");
    Check(ClipboardBridge.Published.Count == 2 && ClipboardBridge.Published[1] == "abc",
        "without a reproducible keymap text is pasted exactly, never guessed onto positions");
    ClipboardBridge.Published.Clear();
}

// Passwords use native keys only: no clipboard transaction and no guessed fallback.
{
    using var portal = new PortalBridge { Keymap = Fixture(1), SessionLocked = true };
    using var input = new InputInjector(portal, new ScreenCapture());
    Check(input.TypeTextSecure("Hello123"), "a supported password is delivered as physical keys");
    Check(portal.Snapshot().Length > 0 && ClipboardBridge.Published.Count == 0,
        "secure typing never writes the clipboard");
    Check(portal.Snapshot().All(e => e.GetProperty("secure").GetBoolean()),
        "password batches preserve native modifier pacing in the helper");
    var before = portal.Snapshot().Length;
    Check(!input.TypeTextSecure("secret👍") && portal.Snapshot().Length == before
        && ClipboardBridge.Published.Count == 0, "an unsupported password fails before any prefix or paste");
    portal.Accept = false;
    Check(!input.TypeTextSecure("secret") && ClipboardBridge.Published.Count == 0,
        "a disconnected secure keyboard cannot silently paste through a fallback");
}

foreach (var current in new[] { 0, 1 })
{
    using var portal = new PortalBridge { Keymap = Fixture(current) };
    using var input = new InputInjector(portal, new ScreenCapture());
    input.Combo(["Control", "z"]);
    var sent = portal.Snapshot();
    var chord = sent.Single(e => e.GetProperty("type").GetString() == "keysyms");
    Check(Batch(chord).Keys.SequenceEqual(Tap(21)) && Batch(chord).Layout is null,
        $"Ctrl+Z presses the German Z position without switching group (active group {current})");
}

using (var portal = new PortalBridge { Keymap = Fixture(0) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    input.KeyCode("KeyA", true, "a");
    input.KeyCode("KeyA", false);
    var sent = portal.Snapshot();
    Check(sent.Length == 3 && Batch(sent[0]).Layout == "de" && Batch(sent[0]).Keys.Length == 0
        && sent[1].GetProperty("code").GetInt32() == 30 && sent[1].GetProperty("down").GetBoolean(),
        "a desktop viewer's A selects the group where A is `a` before the held press");
    Check(!sent[0].GetProperty("text").GetBoolean() && !sent[0].GetProperty("capsLock").GetBoolean(),
        "a physical key's preparation is not text and carries the viewer's lock (off for `a`)");

    input.KeyCode("KeyS", true, "س");
    Check(portal.Snapshot().Length == 4 && portal.Snapshot()[3].GetProperty("type").GetString() == "key",
        "an Arabic viewer keyboard on the Arabic group presses the position unchanged");
    input.ReleaseAll();
}

using (var portal = new PortalBridge { Keymap = Fixture(1) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    input.KeyCode("KeyQ", true, "é");
    input.KeyCode("KeyQ", false);
    input.FlushPendingText();
    var sent = portal.Snapshot();
    Check(sent.Length == 1 && Batch(sent[0]).Keys.SequenceEqual(Tap(13, 18)),
        "a character no group has on that key is typed as text, not as the wrong key");

    input.KeyCode("ControlLeft", true);
    input.KeyCode("KeyA", true, "a");
    Check(portal.Snapshot().Skip(1).All(e => e.GetProperty("type").GetString() == "key"),
        "a chord never selects a group");
    input.ReleaseAll();
}

using (var portal = new PortalBridge { Keymap = Fixture(1) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    input.KeyCode("ShiftLeft", true);
    input.TypeText("?");
    input.FlushPendingText();
    var sent = portal.Snapshot();
    Check(Batch(sent[1]).Keys.SequenceEqual(Seq([(42, false)], Shifted(12), [(42, true)])),
        "a held Shift is released around the group selection and restored after the run");
    input.ReleaseAll();
}

using (var portal = new PortalBridge { Keymap = Fixture(1) })
using (var input = new InputInjector(portal, new ScreenCapture()))
{
    input.KeyCode("KeyA", true, "A");
    input.KeyCode("KeyA", false);
    input.KeyCode("ShiftLeft", true);
    input.KeyCode("KeyB", true, "B");
    input.KeyCode("KeyB", false);
    input.KeyCode("ShiftLeft", false);
    input.KeyCode("Minus", true, "ß");
    input.KeyCode("Minus", false);
    var prepared = portal.Snapshot().Where(e => e.GetProperty("type").GetString() == "keysyms").ToArray();
    Check(prepared.Length == 2 && prepared[0].GetProperty("capsLock").GetBoolean()
        && !prepared[1].GetProperty("capsLock").GetBoolean(),
        "uppercase without Shift means the viewer's lock is on; with Shift it is off; ß carries none");
    Check(prepared.All(e => Batch(e).Layout is null && !e.GetProperty("text").GetBoolean()),
        "on the matching group, lock synchronization selects no group and is not text");
    Check(portal.Snapshot().Count(e => e.GetProperty("type").GetString() == "key") == 8,
        "every physical edge is still pressed and released by position");
}

Check(ClipboardBridge.Published.Count == 0, "keymap-typed tests never touched the clipboard");

static LiveKeymap Fixture(int current)
{
    var dir = AppContext.BaseDirectory;
    while (dir is not null && !Directory.Exists(Path.Combine(dir, "agent-linux")))
        dir = Path.GetDirectoryName(dir);
    var path = Path.Combine(dir ?? throw new Exception("could not locate the moremote tree"),
        "tests", "fixtures", "keymap-ara-de.json");
    using var doc = JsonDocument.Parse(File.ReadAllText(path));
    return LiveKeymap.Parse(doc.RootElement.GetProperty("keymaps"), doc.RootElement.GetProperty("compose"), current)
        ?? throw new Exception("the keymap fixture did not parse");
}

static (string? Layout, int Group, (int Code, bool Down)[] Keys) Batch(JsonElement message)
{
    string? layout = null;
    int group = -1;
    var keys = new List<(int, bool)>();
    foreach (var e in message.GetProperty("events").EnumerateArray())
    {
        if (e.TryGetProperty("layout", out var l)) { layout = l.GetString(); group = e.GetProperty("group").GetInt32(); }
        else keys.Add((e.GetProperty("code").GetInt32(), e.GetProperty("down").GetBoolean()));
    }
    return (layout, group, keys.ToArray());
}

static (int, bool)[] Tap(params int[] codes) => codes.SelectMany(c => new[] { (c, true), (c, false) }).ToArray();
static (int, bool)[] Shifted(int code) => [(42, true), (code, true), (code, false), (42, false)];
static (int, bool)[] AltGr(int code) => [(100, true), (code, true), (code, false), (100, false)];
static (int, bool)[] Seq(params (int, bool)[][] parts) => parts.SelectMany(p => p).ToArray();

static (int Code, int Value) ReceiveKey(Socket recorder)
{
    byte[] data = new byte[24];
    if (recorder.Receive(data) != 24) throw new Exception("short recorded input event");
    var result = ((int)BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(18)),
                  BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan(20)));
    if (BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(16)) != 1)
        throw new Exception("expected recorded key edge");
    if (recorder.Receive(data) != 24 || BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(16)) != 0)
        throw new Exception("expected recorded SYN_REPORT");
    return result;
}

Console.WriteLine($"PASS: {passed} Linux input ordering, recovery and disposal assertions (fake portal/private socket)");
}
catch (Exception error)
{
    // A regression is a test failure, not a crash report in the owner's journal.
    Console.Error.WriteLine(error);
    Environment.ExitCode = 1;
}

namespace MoRemote
{
    public sealed class PortalBridge : IDisposable
    {
        private readonly object _gate = new();
        private readonly List<JsonElement> _events = [];
        public bool Accept { get; set; } = true;
        public bool IsReady => Accept;
        public string BackendName => "private recorder";
        public string LastError => "";
        public bool? SessionLocked { get; set; }
        public Action<JsonElement>? BeforeSend { get; set; }
        public LiveKeymap? Keymap { get; set; }
        public bool Send(object message)
        {
            if (!Accept) return false;
            var parsed = JsonSerializer.SerializeToElement(message);
            BeforeSend?.Invoke(parsed);
            lock (_gate) _events.Add(parsed);
            return true;
        }
        public JsonElement[] Snapshot() { lock (_gate) return _events.ToArray(); }
        public void Dispose() { }
    }
    public sealed class ScreenCapture
    {
        public (int Width, int Height) InputBounds { get; set; } = (1920, 1080);
    }
    public static class ClipboardBridge
    {
        /// <summary>Every exact-paste transaction; keymap-typed text must never appear here.</summary>
        public static List<string> Published { get; } = [];
        public static bool SetTextConfirmed(string text) { Published.Add(text); return true; }
    }
    public static class Log
    {
        public static void Warn(string text) { }
    }
}

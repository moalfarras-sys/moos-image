using System.Text.Json;
using MoRemote;

// Compile the production injector against an in-memory portal and a deliberately
// absent uinput socket. These tests cannot send keys to the machine running them.
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

Console.WriteLine($"PASS: {passed} Linux input ordering, recovery and disposal assertions (fake portal only)");

namespace MoRemote
{
    public sealed class PortalBridge : IDisposable
    {
        private readonly object _gate = new();
        private readonly List<JsonElement> _events = [];
        public bool Accept { get; set; } = true;
        public bool IsReady => Accept;
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
        public (int Width, int Height) InputBounds => (1920, 1080);
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

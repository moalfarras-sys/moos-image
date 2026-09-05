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
        public bool HasLayout(string layout) => true;
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
        public static bool SetTextConfirmed(string text) => throw new Exception("test must not access clipboard");
    }
    public static class Log
    {
        public static void Warn(string text) { }
    }
}

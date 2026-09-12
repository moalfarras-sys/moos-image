using System.Text.Json;
using System.Net.Sockets;
using System.Text;
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
using (var input = new InputInjector(portal, new ScreenCapture(), () => false))
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
using (var input = new InputInjector(portal, new ScreenCapture(), () => false))
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
    var input = new InputInjector(portal, new ScreenCapture(), () => false);
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
using (var input = new InputInjector(portal, new ScreenCapture(), () => false))
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
using (var input = new InputInjector(portal, new ScreenCapture(), () => false))
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

foreach (bool? caps in new bool?[] { true, null })
using (var portal = new PortalBridge())
using (var input = new InputInjector(portal, new ScreenCapture(), () => caps))
{
    const string expected = "MoOS Arabic العربية 123";
    ClipboardBridge.Text = null;
    input.TypeText(expected);
    input.FlushPendingText();
    var sent = portal.Snapshot();
    Check(ClipboardBridge.Text == expected, "locked/unknown state preserves the complete commit");
    Check(sent.Length == 1 && sent[0].GetProperty("sync").GetBoolean(), "exact paste stays one ordered batch");
    Check(sent[0].GetProperty("events").EnumerateArray().Select(e => e.GetProperty("code").GetInt32())
        .SequenceEqual([42, 110, 110, 42]), "Caps Lock is never toggled to type committed text");
}

// Exercise the production wire reader against a private Unix socket, with no connection
// to the test runner's desktop. Byte-fragmented replies also cover partial socket reads.
foreach (int state in new[] {0, 1, 2, 3, -1, -2, -3})
{
    string directory = Path.Combine(Path.GetTempPath(), "mo-lock-" + Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(directory);
    string path = Path.Combine(directory, "wayland-test");
    try
    {
        using var listener = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.Unspecified);
        listener.Bind(new UnixDomainSocketEndPoint(path)); listener.Listen(1);
        var server = Task.Run(() =>
        {
            using var peer = listener.Accept();
            peer.ReceiveTimeout = peer.SendTimeout = 2000;
            byte[] Read(int n) { var b = new byte[n]; for(int i=0;i<n;) { int got=peer.Receive(b.AsSpan(i));
                if(got==0)throw new IOException("client closed"); i+=got; } return b; }
            (uint Id,uint Op,byte[] Body) Request() { var h=Read(8);uint w=BitConverter.ToUInt32(h,4);
                return(BitConverter.ToUInt32(h),w&65535,Read((int)(w>>16)-8)); }
            void Reply(uint id,uint op,byte[] body) {
                byte[] b=BitConverter.GetBytes(id).Concat(BitConverter.GetBytes((uint)((body.Length+8)<<16)|op)).Concat(body).ToArray();
                foreach(byte value in b)peer.Send(new[]{value});
            }
            var registry=Request(); var sync=Request();
            if(registry.Id!=1||registry.Op!=1||sync.Id!=1||sync.Op!=0)throw new Exception("reader must only query state");
            if(state==-3) { Thread.Sleep(450); return; }
            if(state==-2) { peer.Send(BitConverter.GetBytes(2u).Concat(BitConverter.GetBytes(4u<<16)).ToArray()); return; }
            if(state!=-1) {
                var name=Encoding.UTF8.GetBytes("org_kde_kwin_keystate\0");
                var padding=new byte[(name.Length+3)&~3]; name.CopyTo(padding,0);
                Reply(2,0,BitConverter.GetBytes(7u).Concat(BitConverter.GetBytes((uint)name.Length))
                    .Concat(padding).Concat(BitConverter.GetBytes(5u)).ToArray());
            }
            Reply(3,0,BitConverter.GetBytes(1u));
            if(state==-1)return;
            var bind=Request(); var fetch=Request(); var done=Request();
            if(bind.Id!=2||bind.Op!=0||fetch.Id!=4||fetch.Op!=0||fetch.Body.Length!=0||done.Id!=1||done.Op!=0)
                throw new Exception("unexpected state-changing request");
            Reply(4,0,BitConverter.GetBytes(0u).Concat(BitConverter.GetBytes((uint)state)).ToArray());
            Reply(5,0,BitConverter.GetBytes(2u));
        });
        bool? expected = state is 0 ? false : state is 1 or 2 ? true : null;
        Check(KeyboardLockState.ReadCapsLock(path) == expected, $"compositor state {state} is read without guessing");
        server.GetAwaiter().GetResult();
    }
    finally { Directory.Delete(directory, true); }
}
Check(KeyboardLockState.ReadCapsLock("/nonexistent/moos-wayland-test") == null, "absent compositor is unknown");

Console.WriteLine($"PASS: {passed} Linux input ordering, lock state, recovery and disposal assertions (isolated sockets/portal)");

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
        public static string? Text;
        public static bool SetTextConfirmed(string text) { Text = text; return true; }
    }
    public static class Log
    {
        public static void Warn(string text) { }
    }
}

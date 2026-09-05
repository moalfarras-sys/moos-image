using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading.Channels;

namespace MoRemote;

// Production StreamSession driven through its real WebSocket loops. The capture and input doubles
// never touch the desktop, portal, network, or active Remote session.
static class Program
{
    static async Task Main(string[] args)
    {
        if (args.Length == 0 || args.Contains("unicode")) await SplitUnicode();
        if (args.Length == 0 || args.Contains("jpeg")) await HiddenViewer("jpeg");
        if (args.Length == 0 || args.Contains("h264")) await HiddenViewer("h264");
        if (args.Length == 0 || args.Contains("input")) await FailedInputLoop();
        if (args.Length == 0 || args.Contains("auth")) await RejectedAuth();
        if (args.Length == 0 || args.Contains("pause")) await PausedInputQueue();
        Console.WriteLine("PASS: Unicode WebSocket fragments, per-viewer stream suspension, IDR resume and input-loop teardown");
    }

    static void Check(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    static async Task Until(Func<bool> condition, string message)
    {
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(3));
        while (!condition())
        {
            if (deadline.IsCancellationRequested) throw new Exception(message);
            await Task.Delay(5);
        }
    }

    static async Task<(AgentServices Services, TestSocket Socket, Task Running)> Start(string codec = "jpeg")
    {
        var services = new AgentServices();
        services.Capture.Codec = codec;
        var socket = new TestSocket();
        socket.Text("""{"type":"auth","token":"test"}""");
        var running = new StreamSession(services, socket, "isolated-test").RunAsync(CancellationToken.None);
        await Until(() => socket.Has("hello") && socket.Has("codec"), "session handshake did not complete");
        return (services, socket, running);
    }

    static async Task Stop(TestSocket socket, Task running)
    {
        socket.ReceiveClose();
        await running.WaitAsync(TimeSpan.FromSeconds(3));
    }

    static async Task Barrier(TestSocket socket, int number)
    {
        socket.Text($$"""{"type":"ping","t":{{number}}}""");
        await Until(() => socket.Messages.Any(m => m.Contains($"\"t\":{number}")), "control ping blocked");
    }

    static async Task SplitUnicode()
    {
        var (services, socket, running) = await Start();
        const string value = "سلام 😀 مرحباً";
        var bytes = Encoding.UTF8.GetBytes($$"""{"type":"text","value":"{{value}}"}""");
        // Every non-ASCII scalar crosses a ReceiveAsync boundary, including the four-byte emoji.
        for (int i = 0; i < bytes.Length; i++) socket.Fragment([bytes[i]], i == bytes.Length - 1);
        await Until(() => !services.Input.Texts.IsEmpty, "fragmented text did not reach the input loop");
        Check(services.Input.Texts.TryPeek(out var actual) && actual == value,
            "WebSocket fragmentation corrupted Arabic/emoji text");
        Check(!Log.Messages.Any(message => message.Contains("Input sample")),
            "ordinary input must not trigger synchronous diagnostic disk logging");
        await Stop(socket, running);
    }

    static readonly byte[] Idr = [0, 0, 0, 1, 0x67, 0x42, 0, 0x1e, 0, 0, 0, 1, 0x65, 0x88];
    static readonly byte[] Delta = [0, 0, 0, 1, 0x41, 0x9a];

    static async Task HiddenViewer(string codec)
    {
        var (services, socket, running) = await Start(codec);
        if (codec == "h264") services.Capture.Emit(Idr);
        await Until(() => socket.Frames.Count > 0, "visible viewer received no frame");
        socket.Text("""{"type":"video","watching":false}""");
        await Barrier(socket, 123);
        // An already-started send may finish; after that the hidden viewer must receive nothing.
        await Task.Delay(40);
        int before = socket.Frames.Count;
        int requests = services.Capture.KeyframeRequests;
        for (int i = 0; i < 30; i++) services.Capture.Emit(Delta);
        services.Capture.Emit(Idr);
        await Task.Delay(250);
        Check(socket.Frames.Count == before, $"hidden {codec} viewer still receives video");
        Check(services.Capture.KeyframeRequests == requests, "hidden backlog requested a shared encoder keyframe");
        await Barrier(socket, 456);
        socket.Text("""{"type":"video","watching":true}""");
        await Barrier(socket, 789);
        if (codec == "h264")
        {
            services.Capture.Emit(Delta);
            await Task.Delay(60);
            Check(socket.Frames.Count == before, "resume sent a delta without its reference history");
            services.Capture.Emit(Idr);
        }
        await Until(() => socket.Frames.Count > before, $"{codec} viewer did not resume");
        if (codec == "h264")
            Check(socket.Frames.ToArray()[before].SequenceEqual(Idr), "resume must start from an IDR");
        await Stop(socket, running);
        Check(services.Input.Releases == 0, "closing a view-only session released another controller's held input");
    }

    static async Task FailedInputLoop()
    {
        var (services, socket, running) = await Start();
        services.Input.FailClicks = true;
        socket.Text("""{"type":"click","x":0.5,"y":0.5}""");
        await Until(() => running.IsCompleted, "dead input consumer left a streaming but uncontrollable session");
        await running;
        Check(services.Input.Releases > 0, "input failure must release held keys during teardown");
    }

    static async Task RejectedAuth()
    {
        var services = new AgentServices();
        var socket = new TestSocket();
        socket.Text("""{"type":"auth","token":"invalid"}""");
        await new StreamSession(services, socket, "isolated-test").RunAsync(CancellationToken.None);
        Check(services.Input.Releases == 0, "rejected authentication must not release the owner's held input");
    }

    static async Task PausedInputQueue()
    {
        var (services, socket, running) = await Start();
        using var continueClick = new ManualResetEventSlim();
        var clickEntered = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        services.Input.BeforeClick = () =>
        {
            clickEntered.TrySetResult();
            if (!continueClick.Wait(TimeSpan.FromSeconds(3))) throw new Exception("test click not released");
        };
        socket.Text("""{"type":"click","x":0.5,"y":0.5}""");
        try
        {
            await clickEntered.Task.WaitAsync(TimeSpan.FromSeconds(3));
            socket.Text("""{"type":"down","x":0.5,"y":0.5}""");
            await Barrier(socket, 987);
            services.State.IsPaused = true;
            await Task.Delay(80);
            Check(services.Input.Releases == 0, "pause released input concurrently with an unfinished injection");
        }
        finally { continueClick.Set(); }
        await Until(() => services.Input.Releases > 0, "pause did not release input after the pending click finished");
        Check(services.Input.ButtonDowns == 0, "input queued before pause executed a new button-down afterwards");
        await Stop(socket, running);
    }
}

sealed class TestSocket : WebSocket
{
    readonly Channel<(byte[] Data, WebSocketMessageType Type, bool End)> incoming = Channel.CreateUnbounded<(byte[], WebSocketMessageType, bool)>();
    WebSocketState state = WebSocketState.Open;
    public ConcurrentQueue<string> Messages { get; } = new();
    public ConcurrentQueue<byte[]> Frames { get; } = new();
    public override WebSocketCloseStatus? CloseStatus => WebSocketCloseStatus.NormalClosure;
    public override string? CloseStatusDescription => "test";
    public override string? SubProtocol => null;
    public override WebSocketState State => state;
    public void Text(string value) => Fragment(Encoding.UTF8.GetBytes(value), true);
    public void Fragment(byte[] data, bool end) => incoming.Writer.TryWrite((data, WebSocketMessageType.Text, end));
    public void ReceiveClose() => incoming.Writer.TryWrite(([], WebSocketMessageType.Close, true));
    public bool Has(string type) => Messages.Any(m => m.Contains($"\"type\":\"{type}\""));
    public override void Abort() => state = WebSocketState.Aborted;
    public override void Dispose() => state = WebSocketState.Closed;
    public override Task CloseAsync(WebSocketCloseStatus closeStatus, string? description, CancellationToken ct)
    { state = WebSocketState.Closed; return Task.CompletedTask; }
    public override Task CloseOutputAsync(WebSocketCloseStatus closeStatus, string? description, CancellationToken ct)
        => CloseAsync(closeStatus, description, ct);
    public override async Task<WebSocketReceiveResult> ReceiveAsync(ArraySegment<byte> buffer, CancellationToken ct)
    {
        var next = await incoming.Reader.ReadAsync(ct);
        next.Data.CopyTo(buffer.AsSpan());
        if (next.Type == WebSocketMessageType.Close) state = WebSocketState.CloseReceived;
        return new WebSocketReceiveResult(next.Data.Length, next.Type, next.End);
    }
    public override Task SendAsync(ArraySegment<byte> buffer, WebSocketMessageType type, bool end, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        if (type == WebSocketMessageType.Binary) Frames.Enqueue(buffer.ToArray());
        else Messages.Enqueue(Encoding.UTF8.GetString(buffer));
        return Task.CompletedTask;
    }
}

public sealed class AgentServices
{
    public TestConfig Config { get; } = new();
    public TestSessions Sessions { get; } = new();
    public TestState State { get; } = new();
    public TestCapture Capture { get; } = new();
    public TestInput Input { get; } = new();
}
public sealed class TestConfig
{
    public int JpegQuality => 75;
    public int MaxFps => 30;
    public int IdleTimeoutMinutes => 20;
    public bool ShowRemoteCursor => true;
    public bool EmbedCursor => true;
}
public sealed class TestSessions { public bool ValidateAndTouch(string token) => token == "test"; }
public sealed class TestState
{
    public bool IsPaused { get; set; }
    public int ActiveCount => 1;
    public TestHandle Register(string remote) => new();
}
public sealed class TestHandle : IDisposable
{
    public CancellationToken Token => CancellationToken.None;
    public void Dispose() { }
}
public sealed class TestCapture
{
    Action<byte[]>? subscriber;
    public string Codec { get; set; } = "jpeg";
    public int SelectedIndex => 0;
    public (int, int) ScreenSize => (1920, 1080);
    public IEnumerable<(int Index, string Name, bool Primary)> Monitors => [(0, "MoOS", true)];
    public int KeyframeRequests;
    public void Emit(byte[] unit) => subscriber?.Invoke(unit);
    public IDisposable SubscribeH264(Action<byte[]> callback) { subscriber = callback; return new TestHandle(); }
    public void SessionArrived(Guid id) { }
    public void SessionGone(Guid id) { subscriber = null; }
    public void SessionCodec(Guid id, bool supported) { }
    public void SessionWatching(Guid id, bool watching) { }
    public void SessionQuality(Guid id, int quality, double scale, int width) { }
    public void SetFps(int fps) { }
    public void SelectMonitor(int monitor) { }
    public void RequestKeyframe() => Interlocked.Increment(ref KeyframeRequests);
    public (bool Available, bool Changed, byte[] Jpeg) Capture(int quality, double scale, bool cursor) => (true, true, [0xff, 0xd8, 0xff]);
}
public sealed class TestInput
{
    public ConcurrentQueue<string> Texts { get; } = new();
    public bool FailClicks;
    public int Releases;
    public int ButtonDowns;
    public Action? BeforeClick;
    public bool IsReady => true;
    public string BackendName => "isolated-test";
    public string LastError => "";
    public void ReleaseAll() => Interlocked.Increment(ref Releases);
    public void MouseMove(double x, double y) { }
    public void MouseMoveRelative(double x, double y) { }
    public void MouseButton(string button, bool down, double x, double y) { if (down) Interlocked.Increment(ref ButtonDowns); }
    public void MouseButtonCurrent(string button, bool down) { }
    public void ClickCurrent(string button) { }
    public void DoubleClickCurrent() { }
    public void Click(string button, double x, double y)
    {
        BeforeClick?.Invoke();
        if (FailClicks) throw new InvalidOperationException("injected backend failure");
    }
    public void DoubleClick(double x, double y) { }
    public void Scroll(double x, double y) { }
    public void KeyCode(string code, bool down) { }
    public void KeyTapCode(string code) { }
    public void KeyDown(string key) { }
    public void KeyUp(string key) { }
    public void KeyTap(string key) { }
    public void Combo(List<string> keys) { }
    public void TypeText(string value) => Texts.Enqueue(value);
}
static class ClipboardBridge { public static bool IsReady => true; }
static class Log
{
    public static ConcurrentQueue<string> Messages { get; } = new();
    public static void Info(string message) => Messages.Enqueue(message);
    public static void Warn(string message) { }
}

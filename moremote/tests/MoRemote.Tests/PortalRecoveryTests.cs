using System.Text.Json;
using System.Diagnostics;
using System.Net.Sockets;

namespace MoRemote;

internal static class PortalRecoveryTests
{
    public static async Task<int> Run()
    {
        int passed = 0;
        void Eq<T>(T expected, T actual, string name)
        {
            if (!EqualityComparer<T>.Default.Equals(expected, actual))
                throw new Exception($"{name}: expected {expected}, got {actual}");
            passed++;
        }

        var retry = new PortalRetryPolicy();
        foreach (int delay in new[] { 1000, 2000, 4000, 8000, 16000, 30000, 30000 })
            Eq(delay, retry.AfterExit(100, false, 0), "instant EOF still backs off");
        Eq(1000, retry.AfterExit(20_000, true, 4), "useful video restores a one-second recovery");
        Eq(1000, retry.AfterExit(100, false, 4), "a fresh failure starts at the short delay");
        Eq(2000, retry.AfterExit(100, false, 4), "repeated failures still grow after useful video");
        Eq(1000, retry.AfterExit(61_000, false, 0), "long idle helper preserves the existing reset");
        Eq(300_000, retry.AfterExit(20_000, true, 3), "declined sharing keeps its five-minute cooldown");
        Eq(300_000, retry.AfterExit(100, false, 3), "repeated refusal never accelerates");

        var progress = new PortalRunProgress();
        Eq(false, progress.DeliveredForFiveSeconds, "ready without pictures earns no reset");
        progress.NoteFrame(1000);
        Eq(false, progress.DeliveredForFiveSeconds, "one picture earns no reset");
        progress.NoteFrame(5999);
        Eq(false, progress.DeliveredForFiveSeconds, "less than five seconds of pictures earns no reset");
        progress.NoteFrame(6000);
        Eq(true, progress.DeliveredForFiveSeconds, "five seconds of delivery earns recovery");
        Eq(false, new PortalRunProgress().DeliveredForFiveSeconds, "a new helper has its own progress");

        // Real PortalBridge stdin/stdout/frame sockets, but an entirely private child recorder.
        // No DBus, screen picker, credentials, desktop commands or owner input socket are used.
        string dir = Path.Combine(Path.GetTempPath(), "mo-portal-test-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        try
        {
            using (var bridge = RecorderBridge(dir))
            {
                bridge.SetStreaming(true);
                bridge.SetCodec("h264");
                Eq(false, bridge.SetVideoSettings(52, .6, 1024, 30), "offline settings are remembered");
                bridge.SetFps(15);
                await File.WriteAllTextAsync(Path.Combine(dir, "start"), "go");
                var commands = Path.Combine(dir, "commands.jsonl");
                await Until(() => File.Exists(commands) && File.ReadAllLines(commands).Length >= 1 &&
                    !bridge.IsReady, "first private helper did not exit");
                Eq(false, bridge.SetVideoSettings(34, .45, 854, 15), "latest offline preset is remembered");
                int pictures = 0;
                bridge.H264Frame += _ => Interlocked.Increment(ref pictures);
                await Until(() => Volatile.Read(ref pictures) > 0, "restarted private helper delivered no frame");
                var firstCommands = new Dictionary<int, JsonElement>();
                foreach (var line in File.ReadAllLines(commands))
                {
                    using var doc = JsonDocument.Parse(line);
                    firstCommands.TryAdd(doc.RootElement.GetProperty("generation").GetInt32(), doc.RootElement.Clone());
                }
                foreach (var (generation, width, quality) in new[] { (1, 1024, 52), (2, 854, 34) })
                {
                    var message = firstCommands[generation];
                    Eq(width, message.GetProperty("width").GetInt32(), "first restart command carries agreed width");
                    Eq(quality, message.GetProperty("quality").GetInt32(), "restart carries agreed quality");
                    Eq(15, message.GetProperty("fps").GetInt32(), "restart carries the latest FPS");
                    Eq("h264", message.GetProperty("codec").GetString(), "restart restores codec before encoding");
                    Eq(true, message.GetProperty("streaming").GetBoolean(), "restart restores watching before encoding");
                }
            }
            File.Delete(Path.Combine(dir, "generation"));
            using (var bridge = RecorderBridge(dir, idle: true))
            {
                await Until(() => bridge.Generation >= 3 && bridge.WaitingForIdleViewer,
                    "idle failures did not reach the four-second recovery wait");
                var resumed = Stopwatch.StartNew();
                bridge.SetStreaming(true);
                await Until(() => bridge.Generation >= 4 && bridge.IsReady,
                    "new viewer did not wake the idle output-loss retry");
                Eq(true, resumed.Elapsed < TimeSpan.FromSeconds(2), "new viewer skips the accumulated idle wait");
            }
            File.Delete(Path.Combine(dir, "generation"));
            using (var bridge = RecorderBridge(dir, decline: true))
            {
                await Until(() => bridge.Generation == 1 && bridge.LastError == "private refusal" && !bridge.IsReady,
                    "private refusal was not observed");
                bridge.SetStreaming(true);
                await Task.Delay(250);
                Eq(false, bridge.WaitingForIdleViewer, "a refused grant cannot be woken by a viewer");
                Eq(1, bridge.Generation, "new viewer preserves the refused grant's cooldown");
            }
        }
        finally { Directory.Delete(dir, true); }
        Console.WriteLine($"PASS: {passed} portal recovery/preset assertions (private helper/socket)");
        return passed;
    }

    private static PortalBridge RecorderBridge(string dir, bool idle = false, bool decline = false) =>
        new(dir, socket =>
        {
            var command = new ProcessStartInfo(Environment.ProcessPath!);
            command.ArgumentList.Add(typeof(PortalRecoveryTests).Assembly.Location);
            command.ArgumentList.Add("--portal-recorder");
            if (idle) command.ArgumentList.Add("--idle");
            if (decline) command.ArgumentList.Add("--decline");
            command.ArgumentList.Add(socket);
            command.ArgumentList.Add(dir);
            return command;
        });

    public static async Task Record(string socketPath, string dir, bool idle, bool decline)
    {
        string counter = Path.Combine(dir, "generation");
        int generation = File.Exists(counter) ? int.Parse(await File.ReadAllTextAsync(counter)) + 1 : 1;
        await File.WriteAllTextAsync(counter, generation.ToString());
        await Until(() => File.Exists(Path.Combine(dir, "start")), "recorder did not start");
        using var connection = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.Unspecified);
        await connection.ConnectAsync(new UnixDomainSocketEndPoint(socketPath));
        void Emit(object message) => Console.WriteLine(JsonSerializer.Serialize(message));
        Emit(new { type = "ready", backend = "private-recorder", logical_width = 1536, logical_height = 864 });
        if (decline || idle && generation <= 3)
        {
            Emit(new { type = "error", error = decline ? "private refusal" : "private idle output loss", fatal = true });
            Console.Out.Flush();
            Environment.Exit(decline ? 3 : 4);
            return;
        }
        while (await Console.In.ReadLineAsync() is { } line)
        {
            using var doc = JsonDocument.Parse(line);
            var message = doc.RootElement;
            var recorded = message.EnumerateObject().ToDictionary(prop => prop.Name, prop => (object)prop.Value);
            recorded["generation"] = generation;
            await File.AppendAllTextAsync(Path.Combine(dir, "commands.jsonl"), JsonSerializer.Serialize(recorded) + "\n");
            if (message.GetProperty("type").GetString() != "video" || !message.TryGetProperty("width", out var width)) continue;
            if (generation == 1 && !idle)
            {
                Emit(new { type = "error", error = "private output loss", fatal = true });
                Console.Out.Flush();
                Environment.Exit(4);
                return;
            }
            Emit(new { type = "video", codec = "h264", width = width.GetInt32(), height = 480 });
            byte[] packet = [5, 0, 0, 0, 0, 0, 0, 1, 0x65];
            for (int i = 0; i < 10; i++)
            {
                await connection.SendAsync(packet, SocketFlags.None);
                await Task.Delay(20);
            }
        }
    }

    private static async Task Until(Func<bool> condition, string message)
    {
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        while (!condition())
        {
            if (deadline.IsCancellationRequested) throw new Exception(message);
            await Task.Delay(10);
        }
    }
}

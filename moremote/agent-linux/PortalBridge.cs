using System.Buffers.Binary;
using System.Diagnostics;
using System.Net.Sockets;
using System.Text.Json;

namespace MoRemote;

/// <summary>
/// Owns the Python portal helper, which holds a single XDG RemoteDesktop+ScreenCast session.
/// That one session gives us both halves of remote control:
///   - video: a PipeWire stream, encoded to JPEG by GStreamer and pushed over a unix socket
///   - input: absolute/relative pointer, buttons, scroll and keys via portal D-Bus calls
///
/// The helper is supervised: if it dies (portal revoked, compositor restart) we respawn it with
/// backoff, and callers transparently fall back (spectacle for video, ydotoold for input).
/// </summary>
public sealed class PortalBridge : IDisposable
{
    private readonly object _gate = new();
    private readonly string _socketPath;
    private Socket? _listener;
    private Process? _proc;
    private StreamWriter? _stdin;
    private volatile bool _ready;
    private volatile bool _disposed;
    private volatile string _lastError = "";

    private byte[]? _frame;
    private long _version;
    private long _readyTicks;
    private long _framesReceived;
    private int _generation;

    /// <summary>
    /// Bumped every time a new helper takes over. The helper starts from its own default encoder
    /// settings, so anything caching "what I last pushed" must notice the change and push again.
    /// </summary>
    public int Generation => Volatile.Read(ref _generation);

    public bool IsReady => _ready && !_disposed;
    public string LastError => _lastError;
    public int LogicalWidth { get; private set; }
    public int LogicalHeight { get; private set; }
    public int VideoWidth { get; private set; }
    public int VideoHeight { get; private set; }

    /// <summary>
    /// True only when the helper came up but its video pipeline never delivered a single frame,
    /// i.e. it is genuinely broken. A long gap between frames is NOT a stall: PipeWire is
    /// damage-driven, so a desktop that nobody is changing correctly produces nothing at all.
    /// </summary>
    public bool Stalled =>
        _ready && Interlocked.Read(ref _framesReceived) == 0 &&
        Environment.TickCount64 - Interlocked.Read(ref _readyTicks) > 5000;

    public PortalBridge()
    {
        var runtime = Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR") ?? "/tmp";
        _socketPath = Path.Combine(runtime, $"mo-remote-frames-{Environment.ProcessId}.sock");
        new Thread(Supervise) { IsBackground = true, Name = "portal-supervisor" }.Start();
    }

    /// <summary>Latest JPEG frame, or null. <paramref name="version"/> only advances on a new frame.</summary>
    public byte[]? Latest(ref long version)
    {
        lock (_gate)
        {
            if (_frame == null || version == _version) return null;
            version = _version;
            return _frame;
        }
    }

    public byte[]? Current()
    {
        lock (_gate) return _frame;
    }

    public bool Send(object message)
    {
        int generation = Volatile.Read(ref _generation);
        var w = _stdin;
        if (!_ready || w == null) return false;
        try
        {
            lock (w) w.WriteLine(JsonSerializer.Serialize(message));
            return true;
        }
        catch (Exception ex)
        {
            _lastError = ex.Message;
            // Only mark the bridge down if this failure belongs to the *current* helper. A write
            // that lost a race with a restart would otherwise flag a perfectly healthy new helper
            // as dead — and nothing would ever set _ready back to true.
            if (generation == Volatile.Read(ref _generation)) _ready = false;
            return false;
        }
    }

    // ---------------------------------------------------------------- supervision

    private const int ExitDenied = 3;   // the user declined the portal dialog

    private void Supervise()
    {
        int backoffMs = 1000;
        while (!_disposed)
        {
            var started = Environment.TickCount64;
            int exitCode = -1;
            try
            {
                exitCode = RunOnce();
            }
            catch (Exception ex)
            {
                _lastError = ex.Message;
                Log.Warn("Portal helper failed: " + ex.Message);
            }
            _ready = false;
            if (_disposed) return;

            // A helper that exits normally (stdout EOF) is still a failure, so the backoff has to
            // grow on *any* short-lived run — otherwise a helper that dies instantly is respawned
            // once a second forever. Only a run that actually stayed up earns a reset.
            bool ranWell = Environment.TickCount64 - started > 60_000;
            if (ranWell) backoffMs = 1000;

            if (exitCode == ExitDenied)
            {
                // Re-launching would just re-open the permission dialog in the user's face.
                backoffMs = Math.Max(backoffMs, 5 * 60_000);
                Log.Warn("Screen sharing was declined; retrying in 5 minutes. " +
                         "Input and video fall back to ydotool/spectacle until then.");
            }

            Thread.Sleep(backoffMs);
            if (!ranWell) backoffMs = Math.Min(backoffMs * 2, 30_000);
        }
    }

    private int RunOnce()
    {
        var helper = Path.Combine(AppContext.BaseDirectory, "mo-remote-portal.py");
        if (!File.Exists(helper)) throw new FileNotFoundException("portal helper missing", helper);

        try { File.Delete(_socketPath); } catch { /* stale socket from a crash */ }
        using var listener = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.Unspecified);
        listener.Bind(new UnixDomainSocketEndPoint(_socketPath));
        listener.Listen(1);
        _listener = listener;

        var psi = new ProcessStartInfo("python3")
        {
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        psi.ArgumentList.Add(helper);
        psi.ArgumentList.Add(_socketPath);
        psi.Environment["MOREMOTE_EMBED_CURSOR"] = AppConfig.Current.EmbedCursor ? "1" : "0";

        using var proc = Process.Start(psi) ?? throw new IOException("could not start python3");
        int generation = Interlocked.Increment(ref _generation);
        _proc = proc;
        _stdin = proc.StandardInput;
        _stdin.AutoFlush = true;

        // Dispose() may have run while we were starting up; it would have killed the *previous*
        // process, leaving this one orphaned with a live screen-capture grant.
        if (_disposed) { try { proc.Kill(true); } catch { } return -1; }

        // Drain stderr so a chatty traceback can never block the helper on a full pipe.
        new Thread(() =>
        {
            try
            {
                string? line;
                while ((line = proc.StandardError.ReadLine()) != null)
                    if (line.Length > 0) Log.Warn("portal helper: " + line);
            }
            catch { /* process gone */ }
        })
        { IsBackground = true }.Start();

        // If the frame socket breaks, the helper is useless to us — kill it so this run ends and
        // the supervisor starts a fresh one, instead of parking forever on ReadLine().
        var frames = new Thread(() =>
        {
            ReadFrames(listener);
            if (!_disposed && generation == Volatile.Read(ref _generation))
            {
                try { if (!proc.HasExited) proc.Kill(true); } catch { }
            }
        })
        { IsBackground = true, Name = "portal-frames" };
        frames.Start();

        // Helper events on stdout. Blocks until the helper exits.
        string? msg;
        while ((msg = proc.StandardOutput.ReadLine()) != null)
        {
            if (msg.Length == 0) continue;
            try { HandleEvent(msg); }
            catch (Exception ex) { Log.Warn($"Bad portal message '{msg}': {ex.Message}"); }
        }

        proc.WaitForExit(2000);
        _ready = false;
        try { listener.Close(); } catch { }
        int code = SafeExitCode(proc);
        if (!_disposed) Log.Warn($"Portal helper exited (code {code}); restarting.");
        return code;
    }

    private static int SafeExitCode(Process p)
    {
        try { return p.HasExited ? p.ExitCode : -1; } catch { return -1; }
    }

    private void HandleEvent(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        var type = root.TryGetProperty("type", out var t) ? t.GetString() : null;
        switch (type)
        {
            case "ready":
                LogicalWidth = GetInt(root, "logical_width", LogicalWidth);
                LogicalHeight = GetInt(root, "logical_height", LogicalHeight);
                Interlocked.Exchange(ref _framesReceived, 0);
                Interlocked.Exchange(ref _readyTicks, Environment.TickCount64);
                _ready = true;
                _lastError = "";
                Log.Info($"Portal ready: {root.GetProperty("backend").GetString()} " +
                         $"(desktop {LogicalWidth}x{LogicalHeight}).");
                break;
            case "video":
                VideoWidth = GetInt(root, "width", VideoWidth);
                VideoHeight = GetInt(root, "height", VideoHeight);
                LogicalWidth = GetInt(root, "logical_width", LogicalWidth);
                LogicalHeight = GetInt(root, "logical_height", LogicalHeight);
                // The helper reports what it ACTUALLY got running, not what it was asked for: an
                // encoder that exists can still refuse to open (NVENC wants VRAM it may not get),
                // in which case the helper falls down the list and lands on JPEG. Believing the
                // request rather than the report is how a client ends up decoding the wrong codec.
                if (root.TryGetProperty("codec", out var cv) && cv.ValueKind == JsonValueKind.String)
                {
                    var codec = cv.GetString() == "h264" ? "h264" : "jpeg";
                    if (codec != Codec)
                    {
                        Codec = codec;
                        lock (_gate) { _frame = null; }   // a JPEG left over from before is not an H.264 frame
                        Log.Info($"Video codec: {codec} ({(root.TryGetProperty("encoder", out var ev) ? ev.GetString() : "?")}).");
                    }
                }
                Log.Info($"Video stream: {VideoWidth}x{VideoHeight} " +
                         $"(source {GetInt(root, "source_width", 0)}x{GetInt(root, "source_height", 0)}).");
                break;
            case "error":
                _lastError = root.TryGetProperty("error", out var e) ? e.GetString() ?? "" : "";
                Log.Warn("Portal error: " + _lastError);
                break;
            case "warn":
                Log.Warn("Portal: " + (root.TryGetProperty("warn", out var w) ? w.GetString() : ""));
                break;
        }
    }

    private static int GetInt(JsonElement e, string name, int fallback) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetInt32() : fallback;

    /// <summary>What the helper's encoder is producing right now: "jpeg" or "h264".</summary>
    public string Codec { get; private set; } = "jpeg";

    /// <summary>
    /// Every H.264 access unit, in order, as it arrives. JPEG keeps the single-slot model below —
    /// a JPEG is a whole picture, so keeping only the newest is exactly right and a late one is
    /// worth nothing. H.264 is the opposite: a P-frame is a diff against its predecessor, so a
    /// frame that is skipped is not a frame that is missed, it is every frame after it corrupted
    /// until the next IDR. So H.264 is pushed, and every subscriber gets all of it.
    /// </summary>
    public event Action<byte[]>? H264Frame;

    private void ReadFrames(Socket listener)
    {
        try
        {
            using var conn = listener.Accept();
            var header = new byte[4];
            while (!_disposed)
            {
                if (!ReadExact(conn, header, 4)) break;
                int len = (int)BinaryPrimitives.ReadUInt32LittleEndian(header);
                if (len <= 0 || len > 32 * 1024 * 1024) break; // desync — drop the connection
                var buf = new byte[len];
                if (!ReadExact(conn, buf, len)) break;
                if (Codec == "h264")
                {
                    H264Frame?.Invoke(buf);
                }
                else
                {
                    lock (_gate)
                    {
                        _frame = buf;
                        _version++;
                    }
                }
                Interlocked.Increment(ref _framesReceived);
            }
        }
        catch (Exception ex)
        {
            if (!_disposed) Log.Warn("Frame socket closed: " + ex.Message);
        }
    }

    private static bool ReadExact(Socket s, byte[] buf, int count)
    {
        int got = 0;
        while (got < count)
        {
            int n = s.Receive(buf, got, count - got, SocketFlags.None);
            if (n <= 0) return false;
            got += n;
        }
        return true;
    }

    public void Dispose()
    {
        _disposed = true;
        _ready = false;
        try { _stdin?.Close(); } catch { }
        try { if (_proc is { HasExited: false }) _proc.Kill(true); } catch { }
        try { _listener?.Close(); } catch { }
        try { File.Delete(_socketPath); } catch { }
    }
}

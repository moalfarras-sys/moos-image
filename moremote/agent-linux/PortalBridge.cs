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
    private static int _bridgeIds;
    private readonly object _gate = new();
    private readonly string _socketPath;
    private readonly Func<string, ProcessStartInfo> _helperCommand;
    private readonly ManualResetEventSlim _stop = new(false);
    private readonly AutoResetEvent _viewerRetry = new(false);
    private bool _wakeIdleRetry;
    private readonly Thread _supervisor;
    private Socket? _listener;
    private Process? _proc;
    private StreamWriter? _stdin;
    private volatile bool _ready;
    private volatile bool _disposed;
    private int _disposeStarted;
    private volatile string _lastError = "";
    private LiveKeymap? _keymap;

    private byte[]? _frame;
    private long _version;
    private long _lastFrameTicks;
    private int _generation;
    private volatile bool _streaming;      // a viewer is connected and wants frames
    private int _streamingGeneration = -1; // which helper `_streaming` was pushed to
    private string _codec = "jpeg";        // what a fresh helper starts on
    private int _codecGeneration = -1;     // which helper `_codec` was pushed to
    private readonly record struct VideoSettings(int Quality, double Scale, int Width, int Fps);
    private VideoSettings? _videoSettings;
    private const int FrameStarvationMs = 5000;

    /// <summary>
    /// Bumped every time a new helper takes over. The helper starts from its own default encoder
    /// settings, so anything caching "what I last pushed" must notice the change and push again.
    /// </summary>
    public int Generation => Volatile.Read(ref _generation);

    public bool IsReady => _ready && !_disposed;
    internal bool WaitingForIdleViewer { get { lock (_gate) return _wakeIdleRetry; } }
    public string LastError => _lastError;
    public string BackendName { get; private set; } = "Session input initializing";
    public bool? SessionLocked { get; private set; }
    public int LogicalWidth { get; private set; }
    public int LogicalHeight { get; private set; }
    public int VideoWidth { get; private set; }
    public int VideoHeight { get; private set; }

    /// <summary>
    /// True when a viewer is waiting and the helper has delivered no frame for five seconds — both
    /// before the first frame and after a previously healthy pipeline goes quiet. The helper sets
    /// pipewiresrc keepalive-time=1000, so an unchanged desktop still repeats its last frame once a
    /// second; five missed keepalives are a dead source/encoder/appsink chain, not an idle desktop.
    /// The helper owns the matching fatal watchdog and exits to recreate the portal session; this
    /// property keeps the capture side from continuing to describe the stale frame as healthy while
    /// that recovery is being observed.
    /// </summary>
    public bool Stalled =>
        _ready && _streaming &&
        Environment.TickCount64 - Interlocked.Read(ref _lastFrameTicks) >= FrameStarvationMs;

    /// <summary>
    /// Somebody is watching. The helper comes up idle and holds no encode pipeline until this says
    /// otherwise — see the note on `streaming` in mo-remote-portal.py. Idempotent, and re-pushed
    /// whenever a fresh helper takes over, because a new helper starts idle no matter what the last
    /// one was doing.
    /// </summary>
    public void SetStreaming(bool on)
    {
        lock (_gate)
        {
            if (on == _streaming && _streamingGeneration == Generation) return;
            if (on && !_streaming && _wakeIdleRetry) _viewerRetry.Set();
            _streaming = on;
            _streamingGeneration = Generation;
            Interlocked.Exchange(ref _lastFrameTicks, Environment.TickCount64);
            if (!on) _frame = null;   // never hand a new viewer the last frame of the previous one
            Send(new { type = "video", streaming = on });
        }
    }

    /// <summary>
    /// Which codec the helper should encode with ("h264" or "jpeg"). Same shape as SetStreaming
    /// and for the same reason: a FRESH HELPER STARTS ON JPEG whatever the last one was doing.
    ///
    /// This is the bug that shape exists to prevent, and the codec did not have it. ScreenCapture
    /// only told the helper about a codec CHANGE, so after a helper crash — input injection hitting
    /// a dead D-Bus destination is enough — the new helper came up on jpeg while the agent still
    /// believed it had asked for h264. Nothing changed, so nothing was re-sent, and the session
    /// stayed on JPEG until the viewer disconnected: 346 KB whole-picture frames, the socket backed
    /// up, and the round trip measured on the cloud server went from 32 ms to 2.7 SECONDS. No error
    /// anywhere; the picture simply turned to treacle and stayed there.
    /// </summary>
    public void SetCodec(string codec)
    {
        lock (_gate)
        {
            if (codec == _codec && _codecGeneration == Generation) return;
            _codec = codec;
            _codecGeneration = Generation;
            Send(new { type = "video", codec });
        }
    }

    /// <summary>Remember the agreed preset even while the helper is down, and restore it before
    /// the next encoder starts. H.264 does not poll Capture(), so waiting for that loses it.</summary>
    public bool SetVideoSettings(int quality, double scale, int width, int fps)
    {
        lock (_gate)
        {
            _videoSettings = new(quality, scale, width, fps);
            return Send(new { type = "video", quality, scale, width, fps });
        }
    }

    public void SetFps(int fps)
    {
        lock (_gate)
        {
            if (_videoSettings is { } settings) _videoSettings = settings with { Fps = fps };
            Send(new { type = "video", fps });
        }
    }

    public PortalBridge(bool inputOnly = false) : this(Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR") ?? "/tmp",
        socketPath =>
        {
            var helper = Path.Combine(AppContext.BaseDirectory, "mo-remote-portal.py");
            if (!File.Exists(helper)) throw new FileNotFoundException("portal helper missing", helper);
            // A named app scope gives the portal the real MoOS app ID. A grant
            // for org.moos.remote must never become the empty-ID host wildcard.
            bool named = !inputOnly && string.IsNullOrEmpty(Environment.GetEnvironmentVariable("MOREMOTE_DATA_DIR"))
                && File.Exists("/usr/share/applications/org.moos.remote.desktop")
                && File.Exists("/usr/bin/systemd-run");
            var command = new ProcessStartInfo(named ? "systemd-run" : "python3");
            if (named)
            {
                command.ArgumentList.Add("--user");
                command.ArgumentList.Add("--scope");
                command.ArgumentList.Add("--quiet");
                command.ArgumentList.Add("--collect");
                command.ArgumentList.Add($"--unit=app-org.moos.remote-{Environment.ProcessId}.scope");
                command.ArgumentList.Add("--property=PartOf=mo-remote-personal.service");
                command.ArgumentList.Add("python3");
            }
            command.ArgumentList.Add(helper);
            command.ArgumentList.Add(socketPath);
            if (inputOnly) command.ArgumentList.Add("--input-only");
            else command.ArgumentList.Add("--capture-only");
            return command;
        }) { }

    // Private recorder tests use their own helper and socket; never the desktop portal.
    internal PortalBridge(string runtime, Func<string, ProcessStartInfo> helperCommand)
    {
        _helperCommand = helperCommand;
        _socketPath = Path.Combine(runtime, $"mo-r-{Environment.ProcessId}-{Interlocked.Increment(ref _bridgeIds)}.sock");
        _supervisor = new Thread(Supervise) { IsBackground = true, Name = "portal-supervisor" };
        _supervisor.Start();
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
        var retry = new PortalRetryPolicy();
        while (!_disposed)
        {
            var started = Environment.TickCount64;
            var progress = new PortalRunProgress();
            int exitCode = -1;
            try
            {
                exitCode = RunOnce(progress);
            }
            catch (Exception ex)
            {
                _lastError = ex.Message;
                Log.Warn("Portal helper failed: " + ex.Message);
            }
            _ready = false;
            if (_disposed) return;

            // HDMI loss can close useful streams every 20-60 s. Counting all of those as rapid
            // crashes accumulated a 30 s wait for a display that was back within one second.
            // Ready/PLAYING alone earns nothing: require actual frame delivery across five seconds.
            int delayMs = retry.AfterExit(Environment.TickCount64 - started,
                progress.DeliveredForFiveSeconds, exitCode);

            if (exitCode == ExitDenied)
            {
                // Re-launching would just re-open the permission dialog in the user's face.
                Log.Warn("Screen sharing was declined; retrying in 5 minutes. " +
                         "Input and video fall back to ydotool/spectacle until then.");
            }

            Log.Info($"Portal recovery: retry in {delayMs} ms " +
                     $"(sustained pictures: {progress.DeliveredForFiveSeconds}).");
            lock (_gate)
            {
                _viewerRetry.Reset();
                // Output loss while nobody watched is not permission refusal. A newly
                // authenticated viewer may bring that idle retry forward once; subsequent
                // failed watching runs still keep their backoff. Never wake an explicit refusal.
                _wakeIdleRetry = exitCode == 4 && !_streaming;
            }
            int wake = WaitHandle.WaitAny([_stop.WaitHandle, _viewerRetry], delayMs);
            lock (_gate) _wakeIdleRetry = false;
            if (wake == 0) return;
            if (wake == 1) Log.Info("Portal recovery: new viewer resumed an idle output-loss retry.");
        }
    }

    private int RunOnce(PortalRunProgress progress)
    {
        try { File.Delete(_socketPath); } catch { /* stale socket from a crash */ }
        using var listener = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.Unspecified);
        listener.Bind(new UnixDomainSocketEndPoint(_socketPath));
        listener.Listen(1);
        _listener = listener;

        var psi = _helperCommand(_socketPath);
        psi.UseShellExecute = false;
        psi.RedirectStandardInput = true;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.Environment["MOREMOTE_EMBED_CURSOR"] = AppConfig.Current.EmbedCursor ? "1" : "0";

        using var proc = Process.Start(psi) ?? throw new IOException("could not start portal helper");
        int generation = Interlocked.Increment(ref _generation);
        lock (_gate) { _keymap = null; _frame = null; }
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
            ReadFrames(listener, generation, progress);
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
        frames.Join(2000);
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
            case "input-availability":
                _ready = root.TryGetProperty("ready", out var available) && available.ValueKind == JsonValueKind.True;
                _lastError = root.TryGetProperty("error", out var availabilityError) ? availabilityError.GetString() ?? "" : "";
                break;
            case "session":
                SessionLocked = root.TryGetProperty("locked", out var locked) &&
                    locked.ValueKind is JsonValueKind.True or JsonValueKind.False ? locked.GetBoolean() : null;
                break;
            case "ready":
                BackendName = root.GetProperty("backend").GetString() ?? "Session input";
                LogicalWidth = GetInt(root, "logical_width", LogicalWidth);
                LogicalHeight = GetInt(root, "logical_height", LogicalHeight);
                Interlocked.Exchange(ref _lastFrameTicks, Environment.TickCount64);
                Log.Info($"Portal ready: {root.GetProperty("backend").GetString()} " +
                         $"(desktop {LogicalWidth}x{LogicalHeight}).");
                lock (_gate)
                {
                    _ready = true;
                    _lastError = "";
                    // Restore one complete snapshot before the helper starts encoding. Sending
                    // only streaming/codec built its default 1920 px pipeline until a later
                    // client message finally restored the phone's 1024 px preset.
                    _streamingGeneration = Generation;
                    _codecGeneration = Generation;
                    if (_videoSettings is { } settings)
                        Send(new { type = "video", streaming = _streaming, codec = _codec,
                            quality = settings.Quality, scale = settings.Scale,
                            width = settings.Width, fps = settings.Fps });
                    else
                        Send(new { type = "video", streaming = _streaming, codec = _codec });
                }
                break;
            case "layouts":
                {
                    int current = root.TryGetProperty("current", out var cur) && cur.ValueKind == JsonValueKind.Number
                        && cur.TryGetInt32(out var index) ? index : -1;
                    lock (_gate)
                    {
                        // The helper sends the compiled keymap only when it (re)built one; a group
                        // switch alone updates which group is active.
                        if (root.TryGetProperty("keymaps", out var keymaps))
                        {
                            root.TryGetProperty("compose", out var compose);
                            _keymap = LiveKeymap.Parse(keymaps, compose, current);
                            if (_keymap is null)
                                Log.Warn("Portal: no usable live keymap; typed text that needs one uses exact paste.");
                        }
                        else if (_keymap is not null) _keymap = _keymap.WithCurrent(current);
                    }
                    break;
                }
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
                // A fatal helper event is immediately followed by process exit. Mark it unavailable
                // before that exit is reaped so nobody can observe a known-dead pipeline as healthy.
                if (root.TryGetProperty("fatal", out var fatal) && fatal.ValueKind == JsonValueKind.True)
                    _ready = false;
                Log.Warn("Portal error: " + _lastError);
                break;
            case "warn":
                Log.Warn("Portal: " + (root.TryGetProperty("warn", out var w) ? w.GetString() : ""));
                break;
        }
    }

    private static int GetInt(JsonElement e, string name, int fallback) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetInt32() : fallback;

    /// <summary>
    /// The keymap KWin has loaded for this exact portal generation, compiled by the helper, plus the
    /// group KWin last reported active. Null until the helper reports one, or when it could not be
    /// reproduced — callers then use exact paste rather than guessing positions.
    /// </summary>
    public LiveKeymap? Keymap
    {
        get { lock (_gate) return _keymap; }
    }

    /// <summary>What the helper's encoder is producing right now: "jpeg" or "h264".</summary>
    public string Codec { get; private set; } = "jpeg";

    /// <summary>
    /// Every H.264 access unit, in order, as it arrives. JPEG keeps the single-slot model below —
    /// a JPEG is a whole picture, so keeping only the newest is exactly right and a late one is
    /// worth nothing. H.264 is the opposite: a P-frame is a diff against its predecessor, so a
    /// frame that is skipped is not a frame that is missed, it is every frame after it corrupted
    /// until the next IDR. So H.264 is pushed, and every subscriber gets all of it.
    /// </summary>
    public event Action<byte[], int>? H264Frame;

    private void ReadFrames(Socket listener, int generation, PortalRunProgress progress)
    {
        try
        {
            using var conn = listener.Accept();
            var header = new byte[4];
            while (!_disposed && generation == Generation)
            {
                if (!ReadExact(conn, header, 4)) break;
                int len = (int)BinaryPrimitives.ReadUInt32LittleEndian(header);
                if (len <= 0 || len > 32 * 1024 * 1024) break; // desync — drop the connection
                var buf = new byte[len];
                if (!ReadExact(conn, buf, len)) break;
                if (generation != Generation) break;
                if (Codec == "h264")
                {
                    H264Frame?.Invoke(buf, generation);
                }
                else
                {
                    lock (_gate)
                    {
                        _frame = buf;
                        _version++;
                    }
                }
                Interlocked.Exchange(ref _lastFrameTicks, Environment.TickCount64);
                progress.NoteFrame(Environment.TickCount64);
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
        if (Interlocked.Exchange(ref _disposeStarted, 1) != 0) return;
        _disposed = true;
        _ready = false;
        _stop.Set();
        try { _stdin?.Close(); } catch { }
        try { if (_proc is { HasExited: false }) _proc.Kill(true); } catch { }
        try { _listener?.Close(); } catch { }
        if (Thread.CurrentThread != _supervisor && _supervisor.Join(3000))
        {
            _stop.Dispose();
            _viewerRetry.Dispose();
        }
        try { File.Delete(_socketPath); } catch { }
    }
}

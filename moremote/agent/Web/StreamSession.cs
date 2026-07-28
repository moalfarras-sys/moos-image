using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

namespace MoRemote;

/// <summary>
/// One phone connection: authenticates in-band, then runs a send loop (JPEG frames) and
/// a receive loop (mouse/keyboard control) over a single WebSocket. Honors pause/stop.
/// </summary>
public sealed class StreamSession
{
    private readonly AgentServices _svc;
    private readonly WebSocket _socket;
    private readonly string _remote;
    private readonly SemaphoreSlim _sendLock = new(1, 1);

    private const int MaxMessageChars = 256 * 1024; // cap to stop a flooded control message

    // per-session, adjustable live by the controller
    private int _quality;
    private int _fps;
    private double _scale = 1.0;
    private DateTimeOffset _lastInput = DateTimeOffset.UtcNow;
    private bool _screenOk = true;
    private long _lastFrameSent;
    private bool _loggedFirstInput;
    private readonly InputSequenceGuard _sequenceGuard=new();
    private long _legacySequence;
    private bool _legacyLogged;

    // H.264, when the client says it can decode it. The id is what lets the capture know this
    // session is gone — a phone that closed must not keep the whole room on JPEG forever.
    private readonly Guid _id = Guid.NewGuid();
    private readonly System.Collections.Concurrent.ConcurrentQueue<byte[]> _encoded = new();

    /// <summary>
    /// Raised by the encoder the instant an access unit exists, waited on by the send loop.
    ///
    /// WHY A SIGNAL AND NOT A SLEEP, AND WHAT THE SLEEP WAS COSTING
    ///
    /// The send loop polls: it did its work and then slept `1000/fps` — 33ms at 30fps — before
    /// looking again. For JPEG that is correct, because JPEG frames are PULLED (Capture() asks the
    /// helper for the newest picture), so waking early only wastes CPU.
    ///
    /// H.264 is PUSHED. The helper encodes a frame and hands it to us through this subscription,
    /// asynchronously, at whatever moment the compositor happened to damage the screen. The send
    /// loop then sat on it for whatever was left of its 33ms tick: 0ms if the frame happened to
    /// land just before the loop woke, 33ms if it landed just after, 16ms on average — on EVERY
    /// FRAME, for the entire session, on top of encode, network and decode.
    ///
    /// 16ms of median added latency is not a rounding error on a remote desktop; it is half of the
    /// whole frame budget, spent waiting for a timer that had nothing to wait for. The frame is
    /// already encoded and already in memory. Waiting on this instead of on the clock sends it the
    /// moment it exists, and the timeout keeps the loop's other duties (idle timeout, pause status,
    /// codec change) ticking exactly as often as they did before.
    ///
    /// Bounded at 1 because it is an edge, not a counter: the drain below is a `while TryDequeue`,
    /// so one wake-up empties the whole queue however many frames arrived.
    /// </summary>
    private readonly SemaphoreSlim _frameReady = new(0, 1);

    /// <summary>
    /// Input waiting to be injected, in the order it arrived.
    ///
    /// SingleReader because ordering is not negotiable — a mouse-up that overtook its mouse-down
    /// leaves a button physically held on the desktop, and a Shift-up that overtook the character it
    /// was shifting types the wrong thing. One consumer, one FIFO, no reordering possible.
    ///
    /// 1024 is a "something is badly wrong" bound rather than a policy: a human generates input at
    /// tens per second and a mouse at a few hundred, so a second of the worst case does not reach a
    /// tenth of it. The enqueue site falls back to running inline when it is full, so the depth can
    /// never cost an event — only, in an impossible case, the benefit.
    /// </summary>
    private readonly System.Threading.Channels.Channel<(JsonElement Root, string Type)> _inputQueue =
        System.Threading.Channels.Channel.CreateBounded<(JsonElement, string)>(
            new System.Threading.Channels.BoundedChannelOptions(1024)
            {
                SingleReader = true,
                SingleWriter = true,
                FullMode = System.Threading.Channels.BoundedChannelFullMode.Wait,
            });
    private string _sentCodec = "";
    private bool _inputConfirmed;
    private int _moveLogCounter;
    private long _lastRejectReport;
    private string _lastRejectReason = "";
    private long _lastKeyframeRequest;

    public StreamSession(AgentServices svc, WebSocket socket, string remote)
    {
        _svc = svc;
        _socket = socket;
        _remote = remote;
        _quality = svc.Config.JpegQuality;
        _fps = svc.Config.MaxFps;
    }

    public async Task RunAsync(CancellationToken requestAborted)
    {
      try
      {
        // 1) Authenticate: first message must be {"type":"auth","token":"..."} within 10s.
        string? token = await ReadAuthToken(requestAborted);
        if (token == null || !_svc.Sessions.ValidateAndTouch(token))
        {
            await SendJson(new { type = "error", error = "unauthorized" }, CancellationToken.None);
            await CloseQuietly(WebSocketCloseStatus.PolicyViolation, "unauthorized");
            return;
        }

        // 2) Register the live session (this flips the on-screen banner).
        using var handle = _svc.State.Register(_remote);

        // A viewer exists — start the encoder. Deliberately AFTER the auth check above: the capture
        // pipeline is not free (on Linux it makes the compositor copy every frame), so an
        // unauthenticated socket must not be able to start it. SessionGone in the finally below is
        // the other half; between them the encoder runs exactly while somebody is watching.
        _svc.Capture.SessionArrived(_id);
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(requestAborted, handle.Token);
        var ct = linked.Token;

        // Every H.264 access unit for THIS session, in order. Per-session and not shared: two
        // phones draining one queue would each get half a stream, which decodes to nothing.
        //
        // The bound is a backstop, not a policy. If a phone falls this far behind (~3s at 30fps)
        // the backlog is worthless — it would arrive late and still be behind — so it is dropped
        // whole and a fresh IDR is requested, which is the one point where discarding H.264 is
        // right: not a hole in the middle of a stream, but a clean restart of it.
        using var h264 = _svc.Capture.SubscribeH264(au =>
        {
            _encoded.Enqueue(au);
            // 12, not 90. The cap is a LATENCY budget, not a memory one, and 90 frames at 30fps is
            // three entire seconds of the past waiting its turn to be drawn. Long before the cap was
            // reached the session was unusable: the picture lags the input by seconds, so every click
            // appears to do nothing, and the eventual recovery is a hard flush plus a keyframe — a
            // visible jump that reads as a reconnect. A viewer that cannot keep up wants the PRESENT,
            // late and once, not the last three seconds in order.
            //
            // 12 frames is ~0.4s at 30fps: past what a jittery link should hiccup over, well short of
            // what a person reads as lag. Dropping the whole queue rather than the oldest frame is
            // still correct and not negotiable — a P-frame is a diff against its predecessor, so a
            // hole corrupts everything after it until the keyframe this asks for.
            if (_encoded.Count > 12)
            {
                while (_encoded.TryDequeue(out _)) { }
                _svc.Capture.RequestKeyframe();
                Log.Warn("Viewer fell behind; dropped the H.264 backlog and asked for a keyframe.");
            }
            // Wake the send loop now rather than at its next tick. Release throws once the semaphore
            // is already at its bound, which simply means "the loop has not consumed the last signal
            // yet" — there is nothing to do about that and nothing wrong with it.
            try { _frameReady.Release(); } catch (SemaphoreFullException) { }
            catch (ObjectDisposedException) { }
        });

        var (sw, sh) = _svc.Capture.ScreenSize;
        await SendJson(new
        {
            type = "hello",
            screen = new { w = sw, h = sh },
            quality = _quality,
            fps = _fps,
            paused = _svc.State.IsPaused,
            cursor = _svc.Config.ShowRemoteCursor,
            monitors = _svc.Capture.Monitors.Select(m => new { index = m.Index, name = m.Name, primary = m.Primary }).ToArray(),
            monitor = _svc.Capture.SelectedIndex,
            input = new { ready = _svc.Input.IsReady, backend = _svc.Input.BackendName, error = _svc.Input.LastError },
            clipboard = new { ready = ClipboardBridge.IsReady },
        }, ct);

        var send = SendLoop(ct);
        var recv = ReceiveLoop(ct);
        // The third loop, and the reason the first two stay responsive: injecting input blocks
        // (a click is press-pause-release, Arabic borrows the clipboard through a subprocess), and
        // doing that on the socket reader made every ping queue behind it. See the enqueue site.
        var inject = InputLoop(ct);
        var finished = await Task.WhenAny(send, recv);

        linked.Cancel();
        _inputQueue.Writer.TryComplete();
        try { await Task.WhenAll(send, recv, inject); } catch { /* expected on teardown */ }

        if (handle.Token.IsCancellationRequested && !requestAborted.IsCancellationRequested)
            await SendJson(new { type = "stopped" }, CancellationToken.None);
        await CloseQuietly(WebSocketCloseStatus.NormalClosure, "bye");
        _ = finished;
      }
      finally { _svc.Capture.SessionGone(_id); _svc.Input.ReleaseAll(); _sendLock.Dispose(); }
    }

    // ---------------- send: frames + status ----------------

    private async Task SendLoop(CancellationToken ct)
    {
        bool lastPaused = !_svc.State.IsPaused; // force an initial status emit
        try
        {
            while (!ct.IsCancellationRequested && _socket.State == WebSocketState.Open)
            {
                if ((DateTimeOffset.UtcNow - _lastInput).TotalMinutes >= Math.Max(1, _svc.Config.IdleTimeoutMinutes))
                {
                    Log.Info($"Session idle-timeout from {_remote}.");
                    await SendJson(new { type = "idle" }, ct);
                    break;
                }

                bool paused = _svc.State.IsPaused;
                if (paused != lastPaused)
                {
                    // Pausing drops all further input, so a drag in flight would never get its
                    // mouse-up and the button would stay physically held down on the desktop.
                    if (paused) _svc.Input.ReleaseAll();
                    await SendJson(new { type = "status", paused, active = _svc.State.ActiveCount }, ct);
                    lastPaused = paused;
                }

                int fps = Math.Clamp(_fps, 1, 30);
                var frameStart = Environment.TickCount64;

                // The codec can change under a live session — the helper falls back to JPEG on its
                // own when NVENC will not open, and back up again when it will. The client cannot
                // infer that from the bytes (it would have to guess a container from a byte
                // stream), so it is told, every time it changes, before the first frame of the new
                // kind arrives.
                var codec = _svc.Capture.Codec;
                if (codec != _sentCodec)
                {
                    _sentCodec = codec;
                    while (_encoded.TryDequeue(out _)) { }   // whatever is queued is the old codec
                    await SendJson(new { type = "codec", codec }, ct);
                }

                if (!paused && _svc.Capture.Codec == "h264")
                {
                    // H.264 is a stream, not a series of pictures, and every trick the JPEG path
                    // below relies on is poison here.
                    //
                    //   - skipping an unchanged frame:  there are none; the encoder already spends
                    //     almost nothing on a still desktop, which is the entire point of it.
                    //   - dropping a frame when the client is slow:  a P-frame is a diff against
                    //     its predecessor, so a hole does not cost one frame, it corrupts every
                    //     frame after it until the next IDR.
                    //   - resending the last frame to refresh a client:  a decoder handed the same
                    //     access unit twice does not redraw, it desynchronises.
                    //
                    // So this drains, in order, and never decides. The dropping happens where it is
                    // safe — upstream of the encoder, in the helper's videorate.
                    if (!_screenOk) { _screenOk = true; await SendJson(new { type = "screen", available = true }, ct); }
                    while (_encoded.TryDequeue(out var au))
                    {
                        await SendBinary(au, ct);
                        _lastFrameSent = Environment.TickCount64;
                    }
                }
                else if (!paused)
                {
                    var frame = _svc.Capture.Capture(_quality, _scale, _svc.Config.ShowRemoteCursor);
                    if (!frame.Available)
                    {
                        // screen can't be captured (PC locked / secure desktop / display off)
                        if (_screenOk) { _screenOk = false; await SendJson(new { type = "screen", available = false }, ct); }
                    }
                    else
                    {
                        if (!_screenOk) { _screenOk = true; await SendJson(new { type = "screen", available = true }, ct); }
                        // Skip byte-identical frames (nothing moved) to save data + battery, but resend at
                        // least once a second as a keyframe so a re-focused/reconnected client is never blank.
                        bool keyframe = Environment.TickCount64 - _lastFrameSent > 1000;
                        if ((frame.Changed || keyframe) && frame.Jpeg != null)
                        {
                            await SendBinary(frame.Jpeg, ct);
                            _lastFrameSent = Environment.TickCount64;
                        }
                    }
                }

                int budget = 1000 / fps;
                int elapsed = (int)(Environment.TickCount64 - frameStart);
                int delay = Math.Max(paused ? 200 : 5, budget - elapsed);
                if (!paused && _svc.Capture.Codec == "h264")
                {
                    // Sleep until the encoder produces something OR the tick expires, whichever comes
                    // first. The timeout is what keeps the idle check, the pause check and the codec
                    // check running on exactly the cadence they always did on a still desktop; the
                    // signal is what stops a frame that already exists waiting for the clock.
                    await _frameReady.WaitAsync(delay, ct);
                }
                else await Task.Delay(delay, ct);
            }
        }
        catch (OperationCanceledException) { }
        catch (WebSocketException) { }
        catch (Exception ex) { Log.Warn("Send loop ended: " + ex.Message); }
    }

    // ---------------- receive: input control ----------------

    private async Task ReceiveLoop(CancellationToken ct)
    {
        var buffer = new byte[16 * 1024];
        var sb = new StringBuilder();
        try
        {
            while (!ct.IsCancellationRequested && _socket.State == WebSocketState.Open)
            {
                sb.Clear();
                WebSocketReceiveResult result;
                bool tooBig = false;
                do
                {
                    result = await _socket.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
                    if (result.MessageType == WebSocketMessageType.Close) return;
                    if (result.MessageType == WebSocketMessageType.Text && !tooBig)
                        sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                    if (sb.Length > MaxMessageChars) tooBig = true;
                } while (!result.EndOfMessage);

                if (tooBig) { Log.Warn("Dropped oversized control message."); continue; }
                if (sb.Length > 0) await HandleMessage(sb.ToString(), ct);
            }
        }
        catch (OperationCanceledException) { }
        catch (WebSocketException) { }
        catch (Exception ex) { Log.Warn("Receive loop ended: " + ex.Message); }
    }

    private async Task HandleMessage(string json, CancellationToken ct)
    {
        JsonDocument doc;
        try { doc = JsonDocument.Parse(json); } catch { return; }
        using (doc)
        {
            var root = doc.RootElement;
            if (!root.TryGetProperty("type", out var typeEl)) return;
            var type = typeEl.GetString() ?? "";

            // Settings + ping are always allowed; input is suppressed while paused.
            switch (type)
            {
                case "ping":
                    await SendJson(new { type = "pong", t = GetNum(root, "t") }, ct);
                    return;
                // "video" is what the PWA actually sends to declare its decoder, on connect and
                // again if the decoder gives up mid-session. It used to fall through to the input
                // switch, which has no case for it — so the declaration was silently discarded and
                // every phone, however capable, was served JPEG forever. "settings" carries the
                // same field, so both names route here.
                case "video":
                case "settings":
                    if (TryGetInt(root, "quality", out var q)) _quality = Math.Clamp(q, 10, 95);
                    if (TryGetInt(root, "fps", out var f)) { _fps = Math.Clamp(f, 1, 30); _svc.Capture.SetFps(_fps); }
                    // Declared HERE, once per settings message, and never from the send loop. One
                    // pipeline serves the whole room, so what this session wants is an opinion to be
                    // arbitrated (ScreenCapture.SessionQuality), not an instruction to be obeyed by
                    // whichever session polled last.
                    // The client tells us what it can decode; we never guess. WebCodecs needs a
                    // secure context, so a phone on the old http LAN address will say false here
                    // and correctly stay on JPEG.
                    if (root.TryGetProperty("h264", out var hv) &&
                        (hv.ValueKind == JsonValueKind.True || hv.ValueKind == JsonValueKind.False))
                    {
                        _svc.Capture.SessionCodec(_id, hv.GetBoolean());
                        if (hv.GetBoolean()) _svc.Capture.RequestKeyframe();
                    }
                    if (root.TryGetProperty("scale", out var sc) && sc.ValueKind == JsonValueKind.Number)
                        _scale = Math.Clamp(sc.GetDouble(), 0.3, 1.0);
                    _svc.Capture.SessionQuality(_id, _quality, _scale);
                    return;
                case "selectMonitor":
                    if (TryGetInt(root, "index", out var mon)) _svc.Capture.SelectMonitor(mon);
                    return;
                // The viewer's DECODER fell behind and threw away everything it was holding, so it
                // now has no reference frame and every P-frame we send it is noise. Only the client
                // knows that has happened — the agent's own backlog can be empty while the phone's
                // decode queue is seconds deep — so it has to be able to ask.
                //
                // Rate-limited here rather than trusted, because an IDR is many times the size of a
                // P-frame: a client that asked once per frame would answer its own congestion with
                // the single most expensive thing we can send it. One per second is enough to
                // recover a stream and far too few to sustain one.
                case "keyframe":
                    if (Environment.TickCount64 - _lastKeyframeRequest > 1000)
                    {
                        _lastKeyframeRequest = Environment.TickCount64;
                        _svc.Capture.RequestKeyframe();
                    }
                    return;
            }

            // The idle timer is stamped HERE, before the two early returns below, and that placement is
            // the fix rather than an accident.
            //
            // It used to be stamped after both of them. So a session the owner had paused, and a session
            // whose envelopes were being rejected, both looked completely idle to the timeout at :143 —
            // and were force-disconnected for inactivity while the viewer was clicking as hard as they
            // could. One feature killing another, and the resulting "idle timeout" is the least
            // informative possible explanation of what happened.
            //
            // Only input-typed messages reach this line, which is the point: `ping` is deliberately NOT
            // counted. ws.ts pings every 2s even in a throttled background tab, so counting those would
            // make IdleTimeoutMinutes dead code and let a phone forgotten in a pocket stream the owner's
            // desktop indefinitely.
            _lastInput = DateTimeOffset.UtcNow;

            if (_svc.State.IsPaused) return; // owner paused the session — ignore all input

            if (!ValidateEnvelope(root,type,out var reject))
            {
                // Report a rejection at most once every few seconds, and log it the same way.
                //
                // Every rejected message used to answer with a fresh inputState. The client turns that
                // into a toast and a React render, and a real mouse emits input far faster than a
                // finger — so one bad envelope field (a clock skew, a missing geometry) did not produce
                // one complaint, it produced a stream of them: the screen papered over with toasts, the
                // UI re-rendering continuously, and the log filling at the same rate. The cause is
                // never per-message anyway; it is a condition that lasts. Say so once.
                long nowTicks = Environment.TickCount64;
                if (nowTicks - _lastRejectReport > 3000 || reject != _lastRejectReason)
                {
                    _lastRejectReport = nowTicks;
                    _lastRejectReason = reject;
                    Log.Warn($"Rejected input '{type}' from {_remote}: {reject}.");
                    await SendJson(new { type="inputState", ready=_svc.Input.IsReady, error=reject },ct);
                }
                return;
            }

            // HAND THE INPUT OFF; DO NOT PERFORM IT HERE.
            //
            // WHAT THIS COSTS WHEN IT IS DONE INLINE, MEASURED ON LOOPBACK
            //
            // Injecting input is not instantaneous and never can be: a click has to be a press, a
            // pause, and a release, or applications do not see a click at all (InputInjector sleeps
            // 25ms between them); a double-click is 25+40+25; and typing anything the keysym path
            // cannot reach borrows the clipboard, which means spawning wl-copy and waiting for it.
            //
            // All of that used to run ON THIS THREAD, which is the one reading the socket. So while
            // an input was being injected, nothing else could be read — including the pings. Measured
            // against the live agent over loopback, where the network contributes 0.7ms, by firing an
            // input and then fifteen pings back to back and timing the pongs:
            //
            //     baseline            0.7 ms
            //     1 click            25.7 ms
            //     5 clicks          133.4 ms
            //     double-click       90.7 ms
            //     one Arabic word    43.2 ms
            //
            // exactly the sleep constants, plus the subprocess. The latency itself is bad enough, but
            // the second consequence is worse and entirely self-inflicted: RemoteScreen's automatic
            // quality ladder steps DOWN when RTT crosses 400ms, and it reads that RTT from these very
            // pongs. On a cellular link with a 200ms base, a handful of clicks and a word of Arabic
            // push it over the line — so the picture gets worse BECAUSE the user is using it, and
            // improves again when they stop. That is precisely the "it goes blurry when I actually do
            // something" complaint, and no amount of encoder tuning could have fixed it.
            //
            // So the socket reader now only parses and validates, and the work goes to a queue drained
            // by one consumer. Ordering is the whole reason it is ONE consumer and a FIFO: a mouse-up
            // that overtook its mouse-down would leave a button held on the desktop.
            //
            // Clone() is what makes the handoff safe — `root` belongs to a JsonDocument that is
            // disposed the moment this method returns, and a JsonElement read after that is undefined.
            // Clone detaches it onto its own buffer, which is documented as safe to store beyond the
            // document's lifetime.
            if (!_inputQueue.Writer.TryWrite((root.Clone(), type)))
            {
                // The queue is 1024 deep and human input does not fill it, so this is the "something
                // is very wrong" path. Run it inline rather than drop it: a dropped mouse-up is a
                // button stuck down on the desktop, which is far worse than a hitch.
                await ExecuteInput(root, type, ct);
            }
        }
    }

    /// <summary>
    /// Drains the input queue in order, off the socket-reading thread. Started with the session and
    /// cancelled with it; see the note at the enqueue site for why this exists.
    /// </summary>
    private async Task InputLoop(CancellationToken ct)
    {
        try
        {
            await foreach (var (root, type) in _inputQueue.Reader.ReadAllAsync(ct))
                await ExecuteInput(root, type, ct);
        }
        catch (OperationCanceledException) { }
        catch (Exception ex) { Log.Warn("Input loop ended: " + ex.Message); }
    }

    private async Task ExecuteInput(JsonElement root, string type, CancellationToken ct)
    {
        {
            if (!_loggedFirstInput)
            {
                _loggedFirstInput = true;
                Log.Info($"First control input '{type}' received from {_remote}.");
            }
            var input = _svc.Input;
            switch (type)
            {
                case "move":
                    if(++_moveLogCounter%30==1)Log.Info($"Input sample {_remote}: move x={GetNum(root,"x"):F3} y={GetNum(root,"y"):F3} mode={GetStr(root,"mode","legacy")}.");
                    input.MouseMove(GetNum(root, "x"), GetNum(root, "y"));
                    break;
                case "moveRelative":
                    if(++_moveLogCounter%30==1)Log.Info($"Input sample {_remote}: relative dx={GetNum(root,"dx"):F2} dy={GetNum(root,"dy"):F2}.");
                    input.MouseMoveRelative(GetNum(root,"dx"),GetNum(root,"dy"));
                    break;
                case "down":
                    input.MouseButton(GetStr(root, "button", "left"), true, GetNum(root, "x"), GetNum(root, "y"));
                    break;
                case "up":
                    input.MouseButton(GetStr(root, "button", "left"), false, GetNum(root, "x"), GetNum(root, "y"));
                    break;
                case "downCurrent": input.MouseButtonCurrent(GetStr(root,"button","left"),true); break;
                case "upCurrent": input.MouseButtonCurrent(GetStr(root,"button","left"),false); break;
                case "clickCurrent": input.ClickCurrent(GetStr(root,"button","left")); break;
                case "dblclickCurrent": input.DoubleClickCurrent(); break;
                case "click":
                    Log.Info($"Input sample {_remote}: click {GetStr(root,"button","left")} x={GetNum(root,"x"):F3} y={GetNum(root,"y"):F3}.");
                    input.Click(GetStr(root, "button", "left"), GetNum(root, "x"), GetNum(root, "y"));
                    break;
                case "dblclick":
                    input.DoubleClick(GetNum(root, "x"), GetNum(root, "y"));
                    break;
                case "scroll":
                    input.Scroll(GetNum(root, "dx"), GetNum(root, "dy"));
                    break;
                case "key":
                    {
                        // `code` is a PHYSICAL key position (a browser KeyboardEvent.code) and takes
                        // precedence over `key`, which is a character the viewer's own layout
                        // produced. A desktop browser sends both; preferring the position is what
                        // makes held keys, Ctrl-chords and the numeric keypad work at all, and it
                        // leaves the remote's keymap in charge of what the position MEANS.
                        //
                        // The phone sends only `key`, so its path below is untouched.
                        var code = GetStr(root, "code", "");
                        if (code.Length is > 0 and <= 32)
                        {
                            if (root.TryGetProperty("down", out var cd) && cd.ValueKind != JsonValueKind.Null)
                                input.KeyCode(code, cd.GetBoolean());
                            else input.KeyTapCode(code);
                            break;
                        }
                        var key = GetStr(root, "key", "");
                        if (key.Length == 0) break;
                        if (root.TryGetProperty("down", out var d) && d.ValueKind != JsonValueKind.Null)
                        {
                            if (d.GetBoolean()) input.KeyDown(key); else input.KeyUp(key);
                        }
                        else input.KeyTap(key);
                        break;
                    }
                case "combo":
                    if (root.TryGetProperty("keys", out var keysEl) && keysEl.ValueKind == JsonValueKind.Array)
                    {
                        var keys = keysEl.EnumerateArray()
                            .Select(k => k.GetString() ?? "")
                            .Where(k => k.Length > 0).Take(8).ToList();
                        if (keys.Count > 0) input.Combo(keys);
                    }
                    break;
                case "text":
                    {
                        var v = GetStr(root, "value", "");
                        if (v.Length > 4096) v = v[..4096];
                        Log.Info($"Input sample {_remote}: text length={v.Length}.");
                        input.TypeText(v);
                        break;
                    }
            }
            if(!_inputConfirmed){_inputConfirmed=true;await SendJson(new{type="inputState",ready=input.IsReady,backend=input.BackendName,error=input.LastError},ct);}
        }
    }

    private bool ValidateEnvelope(JsonElement root,string type,out string reason)
    {
        reason="invalid input envelope";
        long seq=0;bool legacy=!root.TryGetProperty("seq",out var seqEl)||!seqEl.TryGetInt64(out seq);
        if(legacy){seq=++_legacySequence;if(!_legacyLogged){_legacyLogged=true;Log.Warn($"Legacy cached controller detected from {_remote}; accepting authenticated normalized input until its PWA updates.");}}
        if(legacy)
        {
            bool absoluteLegacy=type is "move" or "down" or "up" or "click" or "dblclick";
            if(absoluteLegacy&&(!Finite(root,"x",0,1)||!Finite(root,"y",0,1))){reason="invalid legacy coordinates";return false;}
            if(type=="scroll"&&(!Finite(root,"dx",-100,100)||!Finite(root,"dy",-100,100))){reason="invalid legacy scroll";return false;}
            reason="";return true;
        }
        if(!root.TryGetProperty("ts",out var tsEl)||!tsEl.TryGetInt64(out var ts)){reason="missing timestamp";return false;}
        if(!_sequenceGuard.Accept(seq,ts,DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),out reason))return false;
        if(!root.TryGetProperty("display",out var display)||!display.TryGetInt32(out var displayId)||displayId!=_svc.Capture.SelectedIndex){reason="unknown display";return false;}
        // "desktop" is the real-mouse-and-keyboard viewer (a computer, not a phone). It has to be
        // listed HERE or nothing else in this file matters: every input message carries its mode and
        // an unlisted one is rejected by this line before any handler sees it. That is a silent
        // failure — the stream looks perfect and not one click lands — so a new client mode is a
        // two-file change by construction, and this is the second file.
        if(!root.TryGetProperty("mode",out var modeEl)||modeEl.ValueKind!=JsonValueKind.String||modeEl.GetString() is not ("trackpad" or "direct" or "touch" or "desktop")){reason="invalid input mode";return false;}
        if(!root.TryGetProperty("viewport",out var viewport)||!Positive(viewport,"w")||!Positive(viewport,"h")){reason="invalid viewport";return false;}
        bool absolute=type is "move" or "down" or "up" or "click" or "dblclick";
        if(absolute&&(!root.TryGetProperty("content",out var content)||!Positive(content,"width")||!Positive(content,"height")||!root.TryGetProperty("source",out var source)||!Positive(source,"w")||!Positive(source,"h"))){reason="invalid remote content geometry";return false;}
        if(absolute&&(!Finite(root,"x",0,1)||!Finite(root,"y",0,1))){reason="invalid normalized coordinates";return false;}
        if(type=="moveRelative"&&(!Finite(root,"dx",-1000,1000)||!Finite(root,"dy",-1000,1000))){reason="invalid relative movement";return false;}
        if(type=="scroll"&&(!Finite(root,"dx",-100,100)||!Finite(root,"dy",-100,100))){reason="invalid scroll";return false;}
        reason=""; return true;
    }
    private static bool Positive(JsonElement e,string name)=>e.TryGetProperty(name,out var v)&&v.ValueKind==JsonValueKind.Number&&v.TryGetDouble(out var n)&&double.IsFinite(n)&&n>0;
    private static bool Finite(JsonElement e,string name,double min,double max)=>e.TryGetProperty(name,out var v)&&v.ValueKind==JsonValueKind.Number&&v.TryGetDouble(out var n)&&double.IsFinite(n)&&n>=min&&n<=max;

    // ---------------- low-level send + auth ----------------

    private async Task<string?> ReadAuthToken(CancellationToken outer)
    {
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(outer);
        cts.CancelAfter(TimeSpan.FromSeconds(10));
        try
        {
            var buffer = new byte[1024];
            var sb = new StringBuilder();
            WebSocketReceiveResult result;
            do
            {
                result = await _socket.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
                if (result.MessageType != WebSocketMessageType.Text) return null;
                sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                if (sb.Length > 2048) return null; // the auth message must be tiny
            } while (!result.EndOfMessage);

            using var doc = JsonDocument.Parse(sb.ToString());
            var root = doc.RootElement;
            if (root.TryGetProperty("type", out var t) && t.GetString() == "auth" &&
                root.TryGetProperty("token", out var tok))
                return tok.GetString();
            return null;
        }
        catch { return null; }
    }

    /// <summary>
    /// Send one frame, bounded.
    ///
    /// This awaited SendAsync under _sendLock with no timeout at all, while SendJson right below bounds
    /// the identical operation at 3s. On a congested socket a ~300KB frame can sit in that await for as
    /// long as the kernel is willing to retransmit, and because it holds _sendLock the PONG queues
    /// behind it — so the client's stall watchdog and the RTT ladder both go blind at precisely the
    /// moment they are needed, and the measured RTT reports the send backlog rather than the network.
    /// A frame that cannot leave in 3 seconds is not worth sending: it is already older than the queue
    /// depth allows, and dropping it lets the pong through so the client can adapt.
    /// </summary>
    private async Task SendBinary(byte[] data, CancellationToken ct)
    {
        await _sendLock.WaitAsync(ct);
        try
        {
            using var bound = CancellationTokenSource.CreateLinkedTokenSource(ct);
            bound.CancelAfter(TimeSpan.FromSeconds(3));
            await _socket.SendAsync(new ArraySegment<byte>(data), WebSocketMessageType.Binary, true, bound.Token);
        }
        catch (OperationCanceledException) when (!ct.IsCancellationRequested)
        {
            // The frame timed out, not the session. Say so once per occurrence and carry on — the next
            // frame is newer anyway, and the keyframe request on the backlog drop repairs the reference.
            Log.Warn("Frame send exceeded 3s and was abandoned; the viewer's link is saturated.");
        }
        finally { _sendLock.Release(); }
    }

    private async Task SendJson(object payload, CancellationToken ct)
    {
        if (_socket.State != WebSocketState.Open) return;
        var bytes = JsonSerializer.SerializeToUtf8Bytes(payload);
        try
        {
            // Always bound the send so a frozen socket can't hang shutdown (CancellationToken.None callers).
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            cts.CancelAfter(TimeSpan.FromSeconds(3));
            await _sendLock.WaitAsync(cts.Token);
            try
            {
                if (_socket.State != WebSocketState.Open) return; // re-check inside the lock (TOCTOU)
                await _socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cts.Token);
            }
            finally { _sendLock.Release(); }
        }
        catch (Exception ex) { Log.Warn("SendJson failed: " + ex.Message); }
    }

    private async Task CloseQuietly(WebSocketCloseStatus status, string desc)
    {
        try
        {
            if (_socket.State == WebSocketState.Open || _socket.State == WebSocketState.CloseReceived)
            {
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(3));
                await _socket.CloseAsync(status, desc, cts.Token);
            }
        }
        catch { }
    }

    // ---------------- json helpers ----------------

    private static double GetNum(JsonElement e, string name) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetDouble() : 0;

    private static string GetStr(JsonElement e, string name, string def) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? (v.GetString() ?? def) : def;

    private static bool TryGetInt(JsonElement e, string name, out int val)
    {
        val = 0;
        if (e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number)
        {
            val = (int)Math.Round(v.GetDouble());
            return true;
        }
        return false;
    }
}

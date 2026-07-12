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
    private string _sentCodec = "";
    private bool _inputConfirmed;
    private int _moveLogCounter;

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
            if (_encoded.Count > 90)
            {
                while (_encoded.TryDequeue(out _)) { }
                _svc.Capture.RequestKeyframe();
                Log.Warn("Phone fell behind; dropped the H.264 backlog and asked for a keyframe.");
            }
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
        var finished = await Task.WhenAny(send, recv);

        linked.Cancel();
        try { await Task.WhenAll(send, recv); } catch { /* expected on teardown */ }

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
                await Task.Delay(delay, ct);
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
                case "settings":
                    if (TryGetInt(root, "quality", out var q)) _quality = Math.Clamp(q, 10, 95);
                    if (TryGetInt(root, "fps", out var f)) { _fps = Math.Clamp(f, 1, 30); _svc.Capture.SetFps(_fps); }
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
                    return;
                case "selectMonitor":
                    if (TryGetInt(root, "index", out var mon)) _svc.Capture.SelectMonitor(mon);
                    return;
            }

            if (_svc.State.IsPaused) return; // owner paused the session — ignore all input

            if (!ValidateEnvelope(root,type,out var reject))
            {
                Log.Warn($"Rejected input '{type}' from {_remote}: {reject}.");
                await SendJson(new { type="inputState", ready=_svc.Input.IsReady, error=reject },ct);
                return;
            }

            _lastInput = DateTimeOffset.UtcNow; // real input resets the idle timer
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
        if(!root.TryGetProperty("mode",out var modeEl)||modeEl.ValueKind!=JsonValueKind.String||modeEl.GetString() is not ("trackpad" or "direct" or "touch")){reason="invalid input mode";return false;}
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

    private async Task SendBinary(byte[] data, CancellationToken ct)
    {
        await _sendLock.WaitAsync(ct);
        try { await _socket.SendAsync(new ArraySegment<byte>(data), WebSocketMessageType.Binary, true, ct); }
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

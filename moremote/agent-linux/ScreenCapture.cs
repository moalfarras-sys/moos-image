using System.Collections.Concurrent;
using System.Diagnostics;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats.Jpeg;
using SixLabors.ImageSharp.Processing;

namespace MoRemote;

/// <summary>
/// Frames come from the PipeWire stream the portal helper encodes for us — Capture() just hands
/// back the newest one, so it costs nothing and never blocks the send loop. If the portal is
/// unavailable we degrade to spawning spectacle per frame, which works but is ~700ms a frame.
/// </summary>
public sealed class ScreenCapture : IDisposable
{
    public readonly record struct Bounds(int Left, int Top, int Width, int Height);
    public readonly record struct MonitorInfo(int Index, string Name, Bounds Bounds, bool Primary);
    public readonly record struct Frame(byte[]? Jpeg, bool Available, bool Changed);

    private readonly PortalBridge _portal;
    private long _version;               // last frame version handed out
    private int _quality = -1, _fps = -1;
    private double _scale = -1;
    private int _settingsGeneration = -1;   // which helper the values above were pushed to
    private long _lastSettingsPush;

    // spectacle fallback state
    private readonly string _shot = Path.Combine(Path.GetTempPath(), $"mo-remote-{Environment.ProcessId}.png");
    private byte[]? _lastFallback;
    private long _lastFallbackTicks;

    public ScreenCapture(PortalBridge portal) { _portal = portal; }

    private int Width => _portal.LogicalWidth > 0 ? _portal.LogicalWidth : 1920;
    private int Height => _portal.LogicalHeight > 0 ? _portal.LogicalHeight : 1080;

    public IReadOnlyList<MonitorInfo> Monitors =>
        new[] { new MonitorInfo(0, $"Desktop · {Width}×{Height}", new(0, 0, Width, Height), true) };
    public int SelectedIndex => 0;
    public Bounds SelectedBounds => new(0, 0, Width, Height);
    public Bounds InputBounds => new(0, 0, Width, Height);
    public (int w, int h) ScreenSize => (Width, Height);
    public void SelectMonitor(int index) { }

    /// <summary>
    /// Non-blocking. Pushes any changed encoder settings down to the helper, then returns the
    /// newest frame. Returning Changed=false makes the send loop skip, so a still desktop costs
    /// no bandwidth and a slow client simply drops frames instead of building a backlog.
    /// </summary>
    public Frame Capture(int quality, double scale, bool drawCursor)
    {
        if (_portal.IsReady && !_portal.Stalled)
        {
            // The ARBITRATED values, not this session's own — see SessionQuality. The parameters are
            // still honoured by the spectacle fallback below, which encodes per frame and so has no
            // shared pipeline to fight over.
            PushSettings(_wantQuality > 0 ? _wantQuality : quality,
                         _wantScale > 0 ? _wantScale : scale);
            var jpeg = _portal.Latest(ref _version);
            if (jpeg != null) return new(jpeg, true, true);
            var current = _portal.Current();
            return current != null
                ? new(current, true, false)          // nothing new since last poll
                : new(null, true, false);            // stream up, first frame not in yet
        }
        return CaptureFallback(quality, scale, drawCursor);
    }

    /// <summary>
    /// Push encoder settings, but only when they actually changed — a scale change costs the
    /// helper a full pipeline rebuild. A restarted helper comes back on its own defaults, so a
    /// generation change forces a re-push even if the values look unchanged.
    ///
    /// The values arriving here are now the room's ARBITRATED ones (SessionQuality), so two viewers
    /// on different presets agree before this is reached. The 500ms floor below is what it always
    /// claimed to be — a backstop against a single client flapping its own preset — rather than the
    /// only thing standing between two clients and two pipeline rebuilds per second.
    /// </summary>
    private void PushSettings(int quality, double scale)
    {
        bool sameHelper = _settingsGeneration == _portal.Generation;
        if (sameHelper && quality == _quality && Math.Abs(scale - _scale) < 0.001) return;
        if (sameHelper && Environment.TickCount64 - _lastSettingsPush < 500) return;

        if (!_portal.Send(new { type = "video", quality, scale, fps = _fps > 0 ? _fps : 30 })) return;
        _quality = quality;
        _scale = scale;
        _settingsGeneration = _portal.Generation;
        _lastSettingsPush = Environment.TickCount64;
    }

    /// <summary>Tell the encoder not to bother producing more than the client will consume.</summary>
    public void SetFps(int fps)
    {
        if (fps == _fps && _settingsGeneration == _portal.Generation) return;
        _fps = fps;
        _portal.Send(new { type = "video", fps });
    }

    // ---------------------------------------------------------------- codec

    /// <summary>What the helper is producing right now — reported by it, never assumed.</summary>
    public string Codec => _portal.Codec;

    /// <summary>All H.264 access units, in order. Returns null when the codec is JPEG.</summary>
    public IDisposable? SubscribeH264(Action<byte[]> onFrame)
    {
        _portal.H264Frame += onFrame;
        return new Unsubscriber(() => _portal.H264Frame -= onFrame);
    }

    /// <summary>A phone that just joined has no reference frame; without this it watches garbage
    /// until the next scheduled IDR.</summary>
    public void RequestKeyframe() => _portal.Send(new { type = "keyframe" });

    private readonly ConcurrentDictionary<Guid, bool> _sessionH264 = new();

    /// <summary>
    /// One pipeline feeds every phone, so the codec is a property of the ROOM, not of a session.
    /// H.264 is therefore only safe when every connected client can decode it: a client handed
    /// bytes it cannot decode does not degrade, it shows nothing. One old browser and everyone
    /// stays on JPEG — which is the honest trade, and the reason this is a vote and not a setting.
    /// </summary>
    /// <summary>
    /// A viewer connected. This is what starts the encoder — until it runs, the helper holds no
    /// pipeline and the compositor is copying nothing. Registered here rather than on the first
    /// codec vote because a JPEG-only client never sends one, and it would stream to a viewer we
    /// never counted (and, worse, never stop when that viewer left).
    /// </summary>
    public void SessionArrived(Guid id)
    {
        _sessionH264.TryAdd(id, false);   // assume no H.264 until the client says otherwise
        Reconcile();
    }

    public void SessionCodec(Guid id, bool canH264)
    {
        _sessionH264[id] = canH264;
        Reconcile();
    }

    // ---------------------------------------------------------------- quality arbitration

    private readonly ConcurrentDictionary<Guid, (int Quality, double Scale)> _sessionWants = new();
    private int _wantQuality = -1;
    private double _wantScale = -1;

    /// <summary>
    /// What one viewer is asking the ENCODER for. Like the codec, this is a property of the room:
    /// there is one pipeline, so there is one answer.
    ///
    /// THE BUG THIS REPLACES, because it destroyed the session rather than degrading it
    ///
    /// Capture() used to push whatever the session that happened to poll was asking for, and the
    /// comment above PushSettings said so plainly — "with two phones connected on different quality
    /// presets, the last one to poll wins. That is rate-limited here so they can't thrash the
    /// pipeline." Rate-limiting is not the same as arbitrating. With two viewers on different
    /// presets, both requests are permanently different from the last-pushed value, so BOTH always
    /// pass the idempotence check and the only thing left standing between them and the pipeline is
    /// the 500ms floor. The result, measured on the live server:
    ///
    ///   22:55:04  Control session END (active: 1)   -> h264 1920x1080, then 77s of silence
    ///   22:56:21  Control session START (active: 2) -> jpeg, 1920x1080, 1344x756, 1920x1080 ...
    ///
    /// two renegotiations per second, for as long as two viewers were connected. Every one of them
    /// rebuilds the GStreamer pipeline and starts a new stream, so the client never held a keyframe
    /// long enough to draw: a black or frozen picture, input that appeared to do nothing (it was
    /// arriving and being injected the whole time), and a session that felt like it kept dropping.
    ///
    /// WHY MINIMUM
    ///
    /// The most constrained viewer sets the pace, matching what Reconcile() already does for the
    /// codec (All(v => v)). It is also the only choice that cannot oscillate: min over a set only
    /// moves when a member's own request moves or the set changes, so a steady room is a steady
    /// pipeline. Sending 1080p to a phone that asked for half of it helps nobody — it pays full
    /// bandwidth for pixels that phone immediately scales away.
    /// </summary>
    public void SessionQuality(Guid id, int quality, double scale)
    {
        _sessionWants[id] = (quality, scale);
        RecomputeWants();
    }

    private void RecomputeWants()
    {
        if (_sessionWants.IsEmpty) return;   // keep the last agreed values; nobody is watching
        int q = int.MaxValue;
        double s = double.MaxValue;
        foreach (var (quality, scale) in _sessionWants.Values)
        {
            if (quality < q) q = quality;
            if (scale < s) s = scale;
        }
        _wantQuality = q;
        _wantScale = s;

        // Push from HERE, not only from Capture(), and this is not belt-and-braces — without it the
        // arbitration above is dead code for every H.264 session.
        //
        // The send loop has two branches. The JPEG branch polls Capture() every frame, which is where
        // PushSettings was called from. The H.264 branch drains the encoded queue and returns without
        // ever touching Capture() — correctly, because H.264 frames arrive by subscription rather than
        // by polling. The consequence was that on H.264 nothing ever reached the encoder: the quality
        // slider did nothing, the auto-quality ladder did nothing, and the resolution stayed at
        // whatever the pipeline was first built with. Two independent audits found this the same way.
        //
        // Settings are a property of the room and change rarely, so pushing them when they CHANGE is
        // both cheaper and more correct than pushing them 30 times a second and hoping the codec
        // branch that does it is the one running.
        PushSettings(_wantQuality, _wantScale);
    }

    public void SessionGone(Guid id)
    {
        _sessionH264.TryRemove(id, out _);
        _sessionWants.TryRemove(id, out _);
        RecomputeWants();
        Reconcile();
    }

    private void Reconcile()
    {
        // Streaming first: with no viewers left this tears the pipeline down, and the codec below
        // is then a note for the next one rather than a change to a running encoder.
        _portal.SetStreaming(!_sessionH264.IsEmpty);

        bool all = !_sessionH264.IsEmpty && _sessionH264.Values.All(v => v);
        // SetCodec owns the idempotence AND the re-push after a helper restart. Deciding here
        // whether anything changed is what left a restarted helper on JPEG for ever: from this
        // side nothing had changed, because from this side nothing had.
        _portal.SetCodec(all ? "h264" : "jpeg");
    }

    private sealed class Unsubscriber(Action dispose) : IDisposable
    {
        public void Dispose() => dispose();
    }

    // ---------------------------------------------------------------- fallback

    private Frame CaptureFallback(int quality, double scale, bool drawCursor)
    {
        // Rate-limit: spectacle costs ~700ms, so hammering it would just pin a core.
        if (Environment.TickCount64 - _lastFallbackTicks < 700 && _lastFallback != null)
            return new(_lastFallback, true, false);
        _lastFallbackTicks = Environment.TickCount64;
        try
        {
            var args = $"--background --nonotify --fullscreen {(drawCursor ? "--pointer" : "")} --output {Quote(_shot)}";
            using var p = Process.Start(new ProcessStartInfo("spectacle", args)
            { UseShellExecute = false, RedirectStandardError = true });
            if (p == null || !p.WaitForExit(5000) || p.ExitCode != 0 || !File.Exists(_shot))
                return new(null, false, false);
            using var image = Image.Load(_shot);
            scale = Math.Clamp(scale, .2, 1);
            if (scale < .995)
                image.Mutate(x => x.Resize(Math.Max(1, (int)(image.Width * scale)), Math.Max(1, (int)(image.Height * scale))));
            using var ms = new MemoryStream();
            image.Save(ms, new JpegEncoder { Quality = Math.Clamp(quality, 10, 95) });
            var bytes = ms.ToArray();
            bool changed = _lastFallback == null || !_lastFallback.AsSpan().SequenceEqual(bytes);
            _lastFallback = bytes;
            return new(bytes, true, changed);
        }
        catch (Exception ex)
        {
            Log.Warn("Fallback screen capture failed: " + ex.Message);
            return new(null, false, false);
        }
    }

    private static string Quote(string s) => "\"" + s.Replace("\"", "\\\"") + "\"";
    public void Dispose() { try { File.Delete(_shot); } catch { } }
}

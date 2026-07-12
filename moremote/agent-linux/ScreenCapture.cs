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
            PushSettings(quality, scale);
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
    /// Note the encoder is process-wide: with two phones connected on different quality presets,
    /// the last one to poll wins. That is rate-limited here so they can't thrash the pipeline.
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

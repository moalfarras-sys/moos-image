using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace MoRemote;

/// <summary>Result of a single backend grab.</summary>
internal enum GrabStatus { Updated, Unchanged, Lost }

/// <summary>A capture backend for one monitor (GDI BitBlt or DXGI Desktop Duplication).</summary>
internal interface ICaptureBackend : IDisposable
{
    string Name { get; }
    /// <summary>Fill <paramref name="frame"/> with the desktop for <paramref name="bounds"/> (no cursor).</summary>
    GrabStatus Grab(Rectangle bounds, out Bitmap? frame);
}

/// <summary>
/// Captures a chosen monitor, overlays the cursor, scales, and encodes JPEG. Prefers DXGI
/// Desktop Duplication (fast, GPU-composited, catches hardware-accelerated windows & games
/// that BitBlt misses) and falls back to GDI BitBlt automatically. Supports multi-monitor
/// selection. The lock screen / secure desktop still can't be captured — by OS design.
/// </summary>
public sealed class ScreenCapture : IDisposable
{
    public readonly record struct MonitorInfo(int Index, string Name, Rectangle Bounds, bool Primary);

    private readonly object _gate = new();
    private readonly ImageCodecInfo _jpegEncoder;

    private MonitorInfo[] _monitors;
    private int _selected;

    private ICaptureBackend? _backend;
    private bool _preferDxgi = true;   // flips off permanently once DXGI proves unavailable
    private Bitmap? _composed;         // frame + cursor (keeps backend bitmaps pristine)
    private Bitmap? _scaled;

    // change-detection state, so we can skip re-sending an identical frame (saves data + battery)
    private byte[]? _lastJpeg;
    private Point _lastCursor = new(-1, -1);
    private int _lastQuality = -1;
    private double _lastScale = -1;

    public ScreenCapture()
    {
        _jpegEncoder = ImageCodecInfo.GetImageEncoders().First(c => c.FormatID == ImageFormat.Jpeg.Guid);
        _monitors = EnumerateMonitors();
        _selected = Math.Max(0, Array.FindIndex(_monitors, m => m.Primary));
    }

    // ---------------- monitors ----------------

    public IReadOnlyList<MonitorInfo> Monitors { get { lock (_gate) return _monitors; } }

    public int SelectedIndex { get { lock (_gate) return _selected; } }

    /// <summary>The selected monitor's rectangle in virtual-desktop (physical) pixels.</summary>
    public Rectangle SelectedBounds
    {
        get { lock (_gate) return _selected < _monitors.Length ? _monitors[_selected].Bounds : new Rectangle(0, 0, 1, 1); }
    }

    public (int w, int h) ScreenSize { get { var b = SelectedBounds; return (b.Width, b.Height); } }

    public void SelectMonitor(int index)
    {
        lock (_gate)
        {
            _monitors = EnumerateMonitors(); // refresh (monitors may have been plugged/unplugged)
            if (index < 0 || index >= _monitors.Length || index == _selected) return;
            _selected = index;
            _backend?.Dispose();
            _backend = null;      // rebuilt for the new monitor on the next capture
            _composed?.Dispose(); _composed = null;
            _scaled?.Dispose(); _scaled = null;
            _lastJpeg = null;     // never resend the previous monitor's frame
            _lastCursor = new Point(-1, -1); _lastQuality = -1; _lastScale = -1;
            Log.Info($"Capture monitor -> #{index} ({_monitors[index].Name} {_monitors[index].Bounds.Width}x{_monitors[index].Bounds.Height}).");
        }
    }

    private static MonitorInfo[] EnumerateMonitors()
    {
        try
        {
            var all = Screen.AllScreens;
            var list = new MonitorInfo[all.Length];
            for (int i = 0; i < all.Length; i++)
            {
                var s = all[i];
                var label = (s.Primary ? "Primary" : $"Display {i + 1}") + $" · {s.Bounds.Width}×{s.Bounds.Height}";
                list[i] = new MonitorInfo(i, label, s.Bounds, s.Primary);
            }
            return list.Length > 0 ? list : Fallback();
        }
        catch { return Fallback(); }

        static MonitorInfo[] Fallback()
        {
            int w = GetSystemMetrics(SM_CXSCREEN), h = GetSystemMetrics(SM_CYSCREEN);
            return new[] { new MonitorInfo(0, $"Primary · {w}×{h}", new Rectangle(0, 0, w, h), true) };
        }
    }

    // ---------------- capture ----------------

    /// <summary>Result of a capture: a JPEG (or null when the screen is unavailable) plus whether it
    /// differs from the previous frame — so the caller can skip re-sending identical frames.</summary>
    public readonly record struct Frame(byte[]? Jpeg, bool Available, bool Changed);

    /// <param name="quality">JPEG quality 1..100.</param>
    /// <param name="scale">Output scale 0.2..1.0 (downscale for bandwidth).</param>
    /// <param name="drawCursor">Overlay the mouse cursor.</param>
    /// <summary>Capture the selected monitor. <see cref="Frame.Available"/> is false when the screen
    /// can't be captured (locked / secure desktop / display off); <see cref="Frame.Changed"/> is false
    /// when the frame is byte-identical to the previous one (nothing moved) so it need not be resent.</summary>
    public Frame Capture(int quality, double scale, bool drawCursor)
    {
        lock (_gate)
        {
            try
            {
                var bounds = _selected < _monitors.Length ? _monitors[_selected].Bounds : Screen.PrimaryScreen!.Bounds;
                if (bounds.Width <= 0 || bounds.Height <= 0) return new Frame(null, false, false);

                EnsureBackend(bounds);
                var status = _backend!.Grab(bounds, out var frame);

                if (status == GrabStatus.Lost)
                {
                    // Access lost (resolution change / desktop switch / DXGI hiccup): drop the backend so
                    // it's rebuilt next time, and serve this frame from a fresh GDI grab so we never stall.
                    Log.Info($"Capture backend '{_backend.Name}' lost — rebuilding.");
                    _backend.Dispose(); _backend = null;
                    using var gdi = new GdiBackend();
                    if (gdi.Grab(bounds, out frame) != GrabStatus.Updated || frame == null) return new Frame(null, false, false);
                    status = GrabStatus.Updated;
                }

                if (frame == null) return new Frame(null, false, false);

                // Decide whether anything actually changed since the last sent frame.
                scale = Math.Clamp(scale, 0.2, 1.0);
                var cursor = drawCursor ? Cursor.Position : Point.Empty;
                bool changed = status != GrabStatus.Unchanged      // screen content changed
                               || (drawCursor && cursor != _lastCursor) // cursor moved
                               || quality != _lastQuality || Math.Abs(scale - _lastScale) > 1e-6 // settings changed
                               || _lastJpeg == null;                // first frame
                if (!changed) return new Frame(_lastJpeg, true, false);

                Bitmap source = frame;
                if (drawCursor)
                {
                    EnsureComposed(bounds.Width, bounds.Height);
                    using (var g = Graphics.FromImage(_composed!))
                    {
                        g.DrawImageUnscaled(frame, 0, 0);
                        DrawCursor(g, bounds.Left, bounds.Top);
                    }
                    source = _composed!;
                }

                Bitmap output = source;
                if (scale < 0.999)
                {
                    int sw = Math.Max(2, (int)Math.Round(bounds.Width * scale));
                    int sh = Math.Max(2, (int)Math.Round(bounds.Height * scale));
                    if (_scaled == null || _scaled.Width != sw || _scaled.Height != sh)
                    {
                        _scaled?.Dispose();
                        _scaled = new Bitmap(sw, sh, PixelFormat.Format24bppRgb);
                    }
                    using var sg = Graphics.FromImage(_scaled);
                    sg.InterpolationMode = InterpolationMode.Bilinear;
                    sg.PixelOffsetMode = PixelOffsetMode.Half;
                    sg.DrawImage(source, 0, 0, sw, sh);
                    output = _scaled;
                }

                var bytes = Encode(output, quality);
                _lastJpeg = bytes; _lastCursor = cursor; _lastQuality = quality; _lastScale = scale;
                return new Frame(bytes, true, true);
            }
            catch (Exception ex)
            {
                // Locked desktop / UAC secure desktop / display off — signal "unavailable" to the client.
                Log.Warn("Capture failed: " + ex.Message);
                try { _backend?.Dispose(); } catch { }
                _backend = null;
                _composed?.Dispose(); _composed = null;
                _scaled?.Dispose(); _scaled = null;
                _lastJpeg = null;
                return new Frame(null, false, false);
            }
        }
    }

    private void EnsureBackend(Rectangle bounds)
    {
        if (_backend != null) return;
        if (_preferDxgi)
        {
            try
            {
                var dxgi = DxgiCapture.TryCreate(bounds);
                if (dxgi != null) { _backend = dxgi; Log.Info("Capture backend: DXGI Desktop Duplication."); return; }
            }
            catch (Exception ex) { Log.Warn("DXGI init failed, using GDI: " + ex.Message); }
            _preferDxgi = false; // don't keep retrying a backend this machine can't provide
        }
        _backend = new GdiBackend();
        Log.Info("Capture backend: GDI BitBlt.");
    }

    private void EnsureComposed(int w, int h)
    {
        if (_composed != null && _composed.Width == w && _composed.Height == h) return;
        _composed?.Dispose();
        _composed = new Bitmap(w, h, PixelFormat.Format24bppRgb);
    }

    private byte[] Encode(Bitmap bmp, int quality)
    {
        using var ps = new EncoderParameters(1);
        ps.Param[0] = new EncoderParameter(Encoder.Quality, (long)Math.Clamp(quality, 1, 100));
        using var ms = new MemoryStream();
        bmp.Save(ms, _jpegEncoder, ps);
        return ms.ToArray();
    }

    private void DrawCursor(Graphics g, int originX, int originY)
    {
        var ci = new CURSORINFO { cbSize = Marshal.SizeOf<CURSORINFO>() };
        if (!GetCursorInfo(ref ci) || ci.flags != CURSOR_SHOWING || ci.hCursor == IntPtr.Zero) return;

        int x = ci.ptScreenPos.x - originX;
        int y = ci.ptScreenPos.y - originY;
        if (GetIconInfo(ci.hCursor, out var ii))
        {
            x -= ii.xHotspot;
            y -= ii.yHotspot;
            if (ii.hbmColor != IntPtr.Zero) DeleteObject(ii.hbmColor);
            if (ii.hbmMask != IntPtr.Zero) DeleteObject(ii.hbmMask);
        }

        IntPtr hdc = g.GetHdc();
        try { DrawIconEx(hdc, x, y, ci.hCursor, 0, 0, 0, IntPtr.Zero, DI_NORMAL); }
        finally { g.ReleaseHdc(hdc); }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            _backend?.Dispose();
            _composed?.Dispose();
            _scaled?.Dispose();
        }
    }

    // ---------------- Win32 ----------------
    private const int SM_CXSCREEN = 0;
    private const int SM_CYSCREEN = 1;
    private const int CURSOR_SHOWING = 0x00000001;
    private const int DI_NORMAL = 0x0003;

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT { public int x; public int y; }

    [StructLayout(LayoutKind.Sequential)]
    private struct CURSORINFO
    {
        public int cbSize;
        public int flags;
        public IntPtr hCursor;
        public POINT ptScreenPos;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ICONINFO
    {
        public bool fIcon;
        public int xHotspot;
        public int yHotspot;
        public IntPtr hbmMask;
        public IntPtr hbmColor;
    }

    [DllImport("user32.dll")] private static extern int GetSystemMetrics(int nIndex);
    [DllImport("user32.dll")] private static extern bool GetCursorInfo(ref CURSORINFO pci);
    [DllImport("user32.dll")] private static extern bool GetIconInfo(IntPtr hIcon, out ICONINFO piconinfo);
    [DllImport("user32.dll")]
    private static extern bool DrawIconEx(IntPtr hdc, int x, int y, IntPtr hIcon,
        int w, int h, int step, IntPtr brush, int flags);
    [DllImport("gdi32.dll")] private static extern bool DeleteObject(IntPtr hObject);
}

/// <summary>GDI BitBlt capture of a monitor's rectangle. Reliable everywhere; the safe fallback.</summary>
internal sealed class GdiBackend : ICaptureBackend
{
    public string Name => "GDI";
    private Bitmap? _bmp;
    private Graphics? _g;
    private int _w, _h;

    public GrabStatus Grab(Rectangle bounds, out Bitmap? frame)
    {
        if (_bmp == null || _w != bounds.Width || _h != bounds.Height)
        {
            _g?.Dispose(); _bmp?.Dispose();
            _bmp = new Bitmap(bounds.Width, bounds.Height, PixelFormat.Format24bppRgb);
            _g = Graphics.FromImage(_bmp);
            _w = bounds.Width; _h = bounds.Height;
        }
        _g!.CopyFromScreen(bounds.Left, bounds.Top, 0, 0, new Size(bounds.Width, bounds.Height), CopyPixelOperation.SourceCopy);
        frame = _bmp;
        return GrabStatus.Updated;
    }

    public void Dispose() { _g?.Dispose(); _bmp?.Dispose(); }
}

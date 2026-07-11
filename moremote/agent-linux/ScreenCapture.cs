using System.Diagnostics;
using System.Text.Json;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats.Jpeg;
using SixLabors.ImageSharp.Processing;

namespace MoRemote;

public sealed class ScreenCapture : IDisposable
{
    public readonly record struct Bounds(int Left, int Top, int Width, int Height);
    public readonly record struct MonitorInfo(int Index, string Name, Bounds Bounds, bool Primary);
    public readonly record struct Frame(byte[]? Jpeg, bool Available, bool Changed);
    private byte[]? _last;
    private int _width = 1920, _height = 1080;
    private int _inputLeft, _inputTop, _inputWidth = 1920, _inputHeight = 1080;
    private bool _geometryResolved;
    private readonly string _shot = Path.Combine(Path.GetTempPath(), $"mo-remote-{Environment.ProcessId}.png");
    public IReadOnlyList<MonitorInfo> Monitors => new[] { new MonitorInfo(0, $"Desktop · {_width}×{_height}", new(0,0,_width,_height), true) };
    public int SelectedIndex => 0;
    public Bounds SelectedBounds => new(0, 0, _width, _height);
    public Bounds InputBounds => new(_inputLeft, _inputTop, _inputWidth, _inputHeight);
    public (int w, int h) ScreenSize => (_width, _height);
    public void SelectMonitor(int index) { }

    public ScreenCapture() { }

    private void UpdateInputGeometry()
    {
        if (_geometryResolved) return;

        // A globally enabled user unit can also be considered by system users
        // (for example SDDM), and Plasma may start services before the Wayland
        // socket is ready.  Starting a Qt Wayland client in either state makes
        // Qt abort, producing a user-visible DrKonqi notification.  Geometry is
        // optional, so only probe KScreen once the real compositor socket exists.
        var runtime = Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR");
        var display = Environment.GetEnvironmentVariable("WAYLAND_DISPLAY");
        if (string.IsNullOrWhiteSpace(runtime) || string.IsNullOrWhiteSpace(display)) return;
        var socket = Path.IsPathRooted(display) ? display : Path.Combine(runtime, display);
        if (!File.Exists(socket)) return;

        try
        {
            using var p = Process.Start(new ProcessStartInfo("kscreen-doctor", "-j")
            { UseShellExecute=false, RedirectStandardOutput=true, RedirectStandardError=true });
            if (p == null) return;
            var json = p.StandardOutput.ReadToEnd();
            if (!p.WaitForExit(3000)) { try { p.Kill(); } catch { } return; }
            if (p.ExitCode != 0 || string.IsNullOrWhiteSpace(json)) return;
            using var doc = JsonDocument.Parse(json);
            int minX=int.MaxValue,minY=int.MaxValue,maxX=int.MinValue,maxY=int.MinValue;
            foreach (var output in doc.RootElement.GetProperty("outputs").EnumerateArray())
            {
                if (!output.GetProperty("enabled").GetBoolean()) continue;
                var scale = output.GetProperty("scale").GetDouble();
                var modeId = output.GetProperty("currentModeId").GetString();
                var mode = output.GetProperty("modes").EnumerateArray()
                    .First(m => m.GetProperty("id").GetString() == modeId);
                var size = mode.GetProperty("size");
                var pos = output.GetProperty("pos");
                int x=pos.GetProperty("x").GetInt32(),y=pos.GetProperty("y").GetInt32();
                int w=(int)Math.Ceiling(size.GetProperty("width").GetInt32()/scale),h=(int)Math.Ceiling(size.GetProperty("height").GetInt32()/scale);
                minX=Math.Min(minX,x);minY=Math.Min(minY,y);maxX=Math.Max(maxX,x+w);maxY=Math.Max(maxY,y+h);
            }
            if (maxX>minX&&maxY>minY) { _inputLeft=minX;_inputTop=minY;_inputWidth=maxX-minX;_inputHeight=maxY-minY; _geometryResolved=true; Log.Info($"KDE logical input geometry: {_inputLeft},{_inputTop} {_inputWidth}x{_inputHeight}."); }
        }
        catch (Exception ex) { Log.Warn("Could not read KDE input geometry: " + ex.Message); }
    }

    public Frame Capture(int quality, double scale, bool drawCursor)
    {
        UpdateInputGeometry();
        try
        {
            var args = $"--background --nonotify --fullscreen {(drawCursor ? "--pointer" : "")} --output {Quote(_shot)}";
            using var p = Process.Start(new ProcessStartInfo("spectacle", args) { UseShellExecute=false, RedirectStandardError=true });
            if (p == null || !p.WaitForExit(5000) || p.ExitCode != 0 || !File.Exists(_shot)) return new(null, false, false);
            using var image = Image.Load(_shot);
            _width = image.Width; _height = image.Height;
            scale = Math.Clamp(scale, .2, 1);
            if (scale < .995) image.Mutate(x => x.Resize(Math.Max(1,(int)(_width*scale)), Math.Max(1,(int)(_height*scale))));
            using var ms = new MemoryStream();
            image.Save(ms, new JpegEncoder { Quality = Math.Clamp(quality, 10, 95) });
            var bytes = ms.ToArray();
            bool changed = _last == null || !_last.AsSpan().SequenceEqual(bytes);
            _last = bytes;
            return new(bytes, true, changed);
        }
        catch (Exception ex) { Log.Warn("Screen capture failed: " + ex.Message); return new(null, false, false); }
    }
    private static string Quote(string s) => "\"" + s.Replace("\"", "\\\"") + "\"";
    public void Dispose() { try { File.Delete(_shot); } catch { } }
}

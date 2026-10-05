using System.Diagnostics;
using System.Text.Json;

namespace MoRemote;

/// <summary>The fallback captures the whole desktop. Its coordinates come from KScreen's
/// logical workspace, including fractional scaling, never from the video pixels or a preset.</summary>
public static class KdeDesktopGeometry
{
    public static (int Width, int Height) Parse(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (!root.GetProperty("outputs").EnumerateArray().Any(o =>
            o.GetProperty("enabled").GetBoolean() && o.GetProperty("connected").GetBoolean()))
            return (0, 0);
        var size = root.GetProperty("screen").GetProperty("currentSize");
        int w = size.GetProperty("width").GetInt32(), h = size.GetProperty("height").GetInt32();
        return w is > 0 and <= 64000 && h is > 0 and <= 64000 ? (w, h) : (0, 0);
    }

    public static (int Width, int Height) Read()
    {
        try
        {
            using var process = Process.Start(new ProcessStartInfo("kscreen-doctor", "-j")
            { UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true });
            if (process is null) return (0, 0);
            var output = process.StandardOutput.ReadToEndAsync();
            var error = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(1500))
            {
                process.Kill(entireProcessTree: true);
                process.WaitForExit();
                return (0, 0);
            }
            // Drain both pipes before releasing the worker; errors are not screen geometry.
            Task.WaitAll(output, error);
            return process.ExitCode == 0 ? Parse(output.Result) : (0, 0);
        }
        catch (Exception) { return (0, 0); }
    }
}

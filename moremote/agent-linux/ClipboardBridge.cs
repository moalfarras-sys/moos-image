using System.Diagnostics;
using System.Text;
using System.Threading;

namespace MoRemote;

public sealed record ClipContent(string Kind, string? Text, byte[]? ImagePng);

public static class ClipboardBridge
{
    internal const int MaxClipboardBytes = 25_000_000;
    private static readonly TimeSpan CommandTimeout = TimeSpan.FromSeconds(3);

    public static bool IsReady =>
        File.Exists("/usr/bin/wl-copy") &&
        File.Exists("/usr/bin/wl-paste") &&
        !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("WAYLAND_DISPLAY"));

    public static ClipContent GetContent()
    {
        try
        {
            var types = Encoding.UTF8.GetString(RunRead("wl-paste", "--list-types"));
            if (types.Contains("image/png", StringComparison.Ordinal))
                return new("image", null, RunRead("wl-paste", "--type", "image/png"));

            var text = Encoding.UTF8.GetString(RunRead("wl-paste", "--no-newline"));
            return string.IsNullOrEmpty(text) ? new("empty", null, null) : new("text", text, null);
        }
        catch
        {
            return new("empty", null, null);
        }
    }

    public static string GetText() => GetContent().Text ?? "";

    // Payload always travels on stdin. Passing it as an argument corrupts quoting and Arabic.
    public static bool SetText(string text) =>
        Write("wl-copy", Encoding.UTF8.GetBytes(text));

    /// <summary>
    /// Publish user-requested clipboard text and do not acknowledge the HTTP request until the
    /// exact UTF-8 bytes can be read back from Wayland. `wl-copy` exits after forking its provider,
    /// before that provider necessarily owns a servable selection; an immediate remote Ctrl+V can
    /// otherwise paste the previous value or nothing. The explicit clipboard feature uses this
    /// before it sends Paste. InputInjector uses it only as a bounded compatibility path for text
    /// no installed keymap can represent; ordinary ASCII, Arabic and US-symbol typing stays on
    /// real key events and never spends the clipboard.
    /// </summary>
    public static bool SetTextConfirmed(string text)
    {
        var expected = Encoding.UTF8.GetBytes(text);
        if (expected.Length == 0) return SetText(text);
        return WriteAndConfirm(
            () => SetText(text),
            () => RunRead("wl-paste", "--no-newline"),
            expected);
    }

    public static bool SetImagePng(byte[] data) =>
        Write("wl-copy", data, "--type", "image/png");

    /// <summary>Image counterpart of SetTextConfirmed; used before sending Paste to the PC.</summary>
    public static bool SetImagePngConfirmed(byte[] data)
    {
        if (data.Length == 0) return false;
        return WriteAndConfirm(
            () => SetImagePng(data),
            () => RunRead("wl-paste", "--type", "image/png"),
            data);
    }

    internal static bool WriteAndConfirm(
        Func<bool> write, Func<byte[]> read, byte[] expected,
        int attempts = 12, int pollMs = 25)
    {
        if (attempts <= 0) throw new ArgumentOutOfRangeException(nameof(attempts));
        if (pollMs < 0) throw new ArgumentOutOfRangeException(nameof(pollMs));
        if (!write()) return false;
        for (var i = 0; i < attempts; i++)
        {
            if (read().AsSpan().SequenceEqual(expected)) return true;
            if (i + 1 < attempts && pollMs > 0) Thread.Sleep(pollMs);
        }
        Log.Warn("Clipboard provider did not serve the exact requested payload within the confirmation budget.");
        return false;
    }

    private static byte[] RunRead(string file, params string[] args) =>
        RunReadCommand(file, args, CommandTimeout, MaxClipboardBytes);

    private static bool Write(string file, byte[] data, params string[] args) =>
        WriteCommand(file, args, data, CommandTimeout);

    // Internal command seams let the behavioural tests prove timeout and output bounds with an
    // inert helper process. Production callers above still select fixed executables and argv.
    internal static byte[] RunReadCommand(
        string file, IReadOnlyList<string> args, TimeSpan timeout, int maxBytes) =>
        RunReadCommandAsync(file, args, timeout, maxBytes).GetAwaiter().GetResult();

    internal static bool WriteCommand(
        string file, IReadOnlyList<string> args, byte[] data, TimeSpan timeout) =>
        WriteCommandAsync(file, args, data, timeout).GetAwaiter().GetResult();

    private static Process Start(string file, IReadOnlyList<string> args, bool read, bool write)
    {
        var start = new ProcessStartInfo(file)
        {
            UseShellExecute = false,
            RedirectStandardOutput = read,
            RedirectStandardInput = write,
            RedirectStandardError = false,
        };
        foreach (var arg in args) start.ArgumentList.Add(arg);
        return Process.Start(start) ?? throw new IOException($"Could not start {file}");
    }

    private static async Task<byte[]> RunReadCommandAsync(
        string file, IReadOnlyList<string> args, TimeSpan timeout, int maxBytes)
    {
        if (maxBytes <= 0) throw new ArgumentOutOfRangeException(nameof(maxBytes));
        using var process = Start(file, args, read: true, write: false);
        using var deadline = new CancellationTokenSource(timeout);
        Task<byte[]>? read = null;
        try
        {
            read = ReadBoundedAsync(process.StandardOutput.BaseStream, maxBytes, deadline.Token);
            await process.WaitForExitAsync(deadline.Token);
            var data = await read;
            return process.ExitCode == 0 ? data : [];
        }
        catch (OperationCanceledException)
        {
            Kill(process);
            await Observe(read);
            return [];
        }
        catch (InvalidDataException)
        {
            Kill(process);
            await Observe(read);
            return [];
        }
    }

    private static async Task<bool> WriteCommandAsync(
        string file, IReadOnlyList<string> args, byte[] data, TimeSpan timeout)
    {
        using var process = Start(file, args, read: false, write: true);
        using var deadline = new CancellationTokenSource(timeout);
        try
        {
            await process.StandardInput.BaseStream.WriteAsync(data, deadline.Token);
            await process.StandardInput.BaseStream.FlushAsync(deadline.Token);
            process.StandardInput.Close();
            await process.WaitForExitAsync(deadline.Token);
            return process.ExitCode == 0;
        }
        catch (OperationCanceledException)
        {
            Kill(process);
            return false;
        }
        catch (IOException)
        {
            Kill(process);
            return false;
        }
    }

    private static async Task<byte[]> ReadBoundedAsync(Stream source, int maxBytes, CancellationToken stop)
    {
        using var output = new MemoryStream(Math.Min(maxBytes, 64 * 1024));
        var buffer = new byte[64 * 1024];
        while (true)
        {
            var read = await source.ReadAsync(buffer, stop);
            if (read == 0) return output.ToArray();
            if (output.Length + read > maxBytes)
                throw new InvalidDataException("Clipboard exceeds its size limit");
            await output.WriteAsync(buffer.AsMemory(0, read), stop);
        }
    }

    private static async Task Observe(Task? task)
    {
        if (task is null) return;
        try { await task; } catch { }
    }

    private static void Kill(Process process)
    {
        try
        {
            if (!process.HasExited) process.Kill(entireProcessTree: true);
            process.WaitForExit(1000);
        }
        catch
        {
            // The process may have exited between HasExited and Kill. Either way it cannot hold
            // the request open any longer, and clipboard failure remains a recoverable empty result.
        }
    }
}

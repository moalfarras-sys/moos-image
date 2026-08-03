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

    // SetTextConfirmed lived here, and it is deliberately gone.
    //
    // It existed for ONE caller: typing. Arabic used to be typed by borrowing this clipboard and
    // pasting it with Shift+Insert, and `wl-copy` returns as soon as it has forked the process
    // that will SERVE the selection — not when the compositor is handing that content to readers.
    // The paste therefore raced the copy; measured live on 2026-08-03, three Arabic words injected
    // that way produced " في مشكلة " with the first word simply gone. SetTextConfirmed read the
    // clipboard back until it served what was set, which fixed that race and left three others:
    // the application fetches the selection asynchronously (so a following keystroke could
    // overtake a word), a clipboard manager can rewrite it, and the whole mechanism spends the
    // user's own clipboard to type.
    //
    // Typing no longer touches the clipboard at all. It selects the keymap group that carries the
    // characters and presses the keys — see InputInjector.Deliver and AraKeymap. So the confirmed
    // write has no callers, and a read-back loop that exists for nobody is a trap for the next
    // person who assumes typing still comes through here.
    //
    // The clipboard feature the USER asked for — copy from the PC, paste to the PC, send an image
    // — is untouched below. It was never the problem; being used as a typing mechanism was.

    public static bool SetImagePng(byte[] data) =>
        Write("wl-copy", data, "--type", "image/png");

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

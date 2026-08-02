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
    /// Set the clipboard AND wait until it actually serves that text.
    ///
    /// PROVEN LIVE on the MoOS Cloud session, 2026-08-03: `wl-copy` returns as soon as it has
    /// forked the process that will SERVE the selection — not when the compositor is handing
    /// that content to readers. A Shift+Insert fired immediately after therefore pasted the
    /// PREVIOUS clipboard, or nothing at all. Injecting three Arabic words that way produced
    /// " في مشكلة " — the first word simply gone. The same three words with the read-back
    /// below produced "لسى في مشكلة ", intact, every time.
    ///
    /// This is the whole of "Arabic types scrambled and letters go missing": the paste raced
    /// the copy. Reading it back is the only honest confirmation that the offer is live —
    /// a fixed sleep is a guess that is either too short on a loaded box or wasted time on an
    /// idle one. Bounded so a clipboard manager that rewrites the selection can never hang
    /// typing: after the budget the paste proceeds anyway, which is exactly today's behaviour.
    /// </summary>
    public static bool SetTextConfirmed(string text)
    {
        if (!SetText(text)) return false;
        var want = text;
        for (int i = 0; i < ConfirmAttempts; i++)
        {
            var got = GetText();
            if (got == want) return true;
            Thread.Sleep(ConfirmPollMs);
        }
        Log.Warn("Clipboard did not confirm the typed text within the budget; pasting anyway.");
        return true;
    }

    private const int ConfirmAttempts = 12;
    private const int ConfirmPollMs = 25;

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

namespace MoRemote;

/// <summary>Only this helper's delivered pictures earn a short recovery after output loss.</summary>
internal sealed class PortalRunProgress
{
    private long _firstFrame = -1;
    private long _lastFrame = -1;

    public void NoteFrame(long now)
    {
        Interlocked.CompareExchange(ref _firstFrame, now, -1);
        Interlocked.Exchange(ref _lastFrame, now);
    }

    public bool DeliveredForFiveSeconds =>
        Interlocked.Read(ref _firstFrame) >= 0 &&
        Interlocked.Read(ref _lastFrame) - Interlocked.Read(ref _firstFrame) >= 5000;
}

/// <summary>
/// A display disappearing after useful video is a recovery, not an instant crash loop.
/// Keep exponential backoff for helpers that never settle, and the full refusal cooldown.
/// </summary>
internal sealed class PortalRetryPolicy
{
    private int _nextDelayMs = 1000;

    public int AfterExit(long runMs, bool deliveredForFiveSeconds, int exitCode)
    {
        bool usefulRun = runMs > 60_000 || deliveredForFiveSeconds;
        if (usefulRun) _nextDelayMs = 1000;
        if (exitCode == 3) _nextDelayMs = Math.Max(_nextDelayMs, 5 * 60_000);
        int delay = _nextDelayMs;
        if (!usefulRun) _nextDelayMs = Math.Min(_nextDelayMs * 2, 30_000);
        return delay;
    }
}

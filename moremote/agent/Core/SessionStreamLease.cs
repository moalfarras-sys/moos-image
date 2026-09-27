namespace MoRemote;

// Passive streaming never renews authentication. Cancellation also covers a silent upstream,
// a pending HTTP connection and a slow receiver, not just the next audio packet.
public sealed class SessionStreamLease : IAsyncDisposable
{
    private readonly Func<bool> _authorized;
    private readonly CancellationTokenSource _cancel;
    private readonly Task _watch;
    private int _revoked;

    public SessionStreamLease(Func<bool> authorized, CancellationToken aborted)
    {
        _authorized = authorized;
        _cancel = CancellationTokenSource.CreateLinkedTokenSource(aborted);
        _ = IsAuthorized;
        _watch = WatchAsync();
    }

    public CancellationToken Token => _cancel.Token;
    public bool Revoked => Volatile.Read(ref _revoked) != 0;
    public bool IsAuthorized
    {
        get
        {
            if (!_authorized())
            {
                Interlocked.Exchange(ref _revoked, 1);
                _cancel.Cancel();
            }
            return !Revoked;
        }
    }

    private async Task WatchAsync()
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(1));
        try
        {
            while (await timer.WaitForNextTickAsync(Token))
                if (!IsAuthorized) return;
        }
        catch (OperationCanceledException) when (Token.IsCancellationRequested) { }
    }

    public async Task CopyAsync(Stream source, Stream destination)
    {
        var buffer = new byte[16384];
        while (IsAuthorized)
        {
            int count = await source.ReadAsync(buffer, Token);
            if (count == 0 || !IsAuthorized) return;
            await destination.WriteAsync(buffer.AsMemory(0, count), Token);
        }
    }

    public async ValueTask DisposeAsync()
    {
        _cancel.Cancel();
        await _watch;
        _cancel.Dispose();
    }
}

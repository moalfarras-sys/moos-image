using System.Collections.Concurrent;

namespace MoRemote;

/// <summary>
/// Tracks live control connections so the owner always sees what's happening and can
/// kill or pause a session instantly. This is the anti-stealth guarantee: a connection
/// can't exist without flipping <see cref="IsActive"/>, which drives the on-screen banner.
/// </summary>
public sealed class SessionState
{
    private readonly ConcurrentDictionary<Guid, ControllerHandle> _controllers = new();
    private volatile bool _paused;

    /// <summary>Fires whenever the active-session count or paused state changes (UI thread-marshals itself).</summary>
    public event Action? Changed;

    public int ActiveCount => _controllers.Count;
    public bool IsActive => !_controllers.IsEmpty;
    public bool IsPaused => _paused;

    public IReadOnlyCollection<string> ActiveRemotes =>
        _controllers.Values.Select(c => c.Remote).ToArray();

    public ControllerHandle Register(string remote)
    {
        var h = new ControllerHandle(this, remote);
        _controllers[h.Id] = h;
        Log.Info($"Control session START from {remote} (active: {_controllers.Count}).");
        RaiseChanged();
        return h;
    }

    internal void Unregister(ControllerHandle h)
    {
        if (_controllers.TryRemove(h.Id, out _))
        {
            Log.Info($"Control session END from {h.Remote} (active: {_controllers.Count}).");
            RaiseChanged();
        }
    }

    /// <summary>Instant kill switch: disconnect every controller right now.</summary>
    public void StopAll()
    {
        if (_controllers.IsEmpty) return;
        Log.Warn("STOP pressed — disconnecting all control sessions.");
        foreach (var h in _controllers.Values) h.Cancel();
        // handles remove themselves as their socket loops unwind
    }

    public void SetPaused(bool paused)
    {
        if (_paused == paused) return;
        _paused = paused;
        Log.Info(paused ? "Session PAUSED (input + streaming halted)." : "Session RESUMED.");
        RaiseChanged();
    }

    public void TogglePaused() => SetPaused(!_paused);

    private void RaiseChanged()
    {
        try { Changed?.Invoke(); } catch (Exception ex) { Log.Error("SessionState.Changed handler threw.", ex); }
    }
}

/// <summary>One live controller connection. Disposing it ends the session.</summary>
public sealed class ControllerHandle : IDisposable
{
    private readonly SessionState _owner;
    private readonly CancellationTokenSource _cts = new();

    public Guid Id { get; } = Guid.NewGuid();
    public string Remote { get; }
    public CancellationToken Token => _cts.Token;

    internal ControllerHandle(SessionState owner, string remote)
    {
        _owner = owner;
        Remote = remote;
    }

    public void Cancel() { try { _cts.Cancel(); } catch { } }

    public void Dispose()
    {
        _owner.Unregister(this);
        _cts.Dispose();
    }
}

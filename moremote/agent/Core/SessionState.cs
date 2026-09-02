using System.Collections.Concurrent;

namespace MoRemote;

/// <summary>
/// Tracks live control connections so the owner always sees what's happening and can
/// kill or pause a session instantly. This is the anti-stealth guarantee: a connection
/// can't exist without flipping <see cref="IsActive"/>, which drives the on-screen banner.
/// </summary>
public sealed class SessionState : IDisposable
{
    private readonly ConcurrentDictionary<Guid, ControllerHandle> _controllers = new();
    private readonly object _presenceGate = new();
    private readonly string? _presenceDirectory;
    private string? _presencePath;
    private bool _disposed;
    private volatile bool _paused;

    public SessionState(string? presenceDirectory = null)
    {
        if (!OperatingSystem.IsLinux()) return;
        if (presenceDirectory is null)
        {
            // An explicitly isolated test/cloud instance must never overwrite
            // the signed-in desktop's one well-known presence signal.
            if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("MOREMOTE_DATA_DIR")))
                return;
            var runtime = Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR");
            if (string.IsNullOrEmpty(runtime) || !Path.IsPathFullyQualified(runtime)) return;
            presenceDirectory = Path.Combine(runtime, "mo-remote");
        }
        if (!Path.IsPathFullyQualified(presenceDirectory)) return;
        _presenceDirectory = presenceDirectory;
        PreparePresenceDirectory();
    }

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
        PublishPresence();
        try { Changed?.Invoke(); } catch (Exception ex) { Log.Error("SessionState.Changed handler threw.", ex); }
    }

    private void PreparePresenceDirectory()
    {
        if (_presenceDirectory is null) return;
        try
        {
            Directory.CreateDirectory(_presenceDirectory);
            if (OperatingSystem.IsLinux())
                File.SetUnixFileMode(_presenceDirectory,
                    UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            foreach (var pattern in new[] { "presence-active-*", "presence-paused-*", ".presence-*.tmp" })
                foreach (var stale in Directory.EnumerateFiles(_presenceDirectory, pattern))
                    File.Delete(stale);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            Log.Warn("Could not prepare the runtime presence directory: " + ex.Message);
        }
    }

    private void PublishPresence()
    {
        if (_presenceDirectory is null) return;
        lock (_presenceGate)
        {
            if (_disposed) return;
            var count = ActiveCount;
            var name = count == 0 ? null
                : $"presence-{(IsPaused ? "paused" : "active")}-{count}";
            var next = name is null ? null : Path.Combine(_presenceDirectory, name);
            if (next == _presencePath) return;
            var temporary = Path.Combine(_presenceDirectory,
                $".presence-{Environment.ProcessId}-{Guid.NewGuid():N}.tmp");
            try
            {
                if (_presencePath is not null) File.Delete(_presencePath);
                if (next is not null)
                {
                    File.WriteAllText(temporary, "1\n");
                    if (OperatingSystem.IsLinux())
                        File.SetUnixFileMode(temporary,
                            UnixFileMode.UserRead | UnixFileMode.UserWrite);
                    File.Move(temporary, next, true);
                }
                _presencePath = next;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                Log.Warn("Could not publish remote-session presence: " + ex.Message);
                try { File.Delete(temporary); } catch { }
            }
        }
    }

    public void Dispose()
    {
        lock (_presenceGate)
        {
            if (_disposed) return;
            _disposed = true;
            if (_presencePath is not null)
            {
                try { File.Delete(_presencePath); }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                { Log.Warn("Could not remove remote-session presence: " + ex.Message); }
                _presencePath = null;
            }
        }
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

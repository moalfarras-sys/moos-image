namespace MoRemote;

public enum H264EnqueueResult
{
    Queued,
    NeedKeyframe,
    DroppedWhileWaiting,
    Recovered,
}

/// <summary>
/// A bounded H.264 queue that never exposes a delta after it has discarded that
/// delta's reference history. Once the latency budget is exceeded, all access
/// units are ignored until an IDR arrives; that IDR becomes the sole new root.
/// </summary>
public sealed class H264RecoveryQueue
{
    private readonly object _sync = new();
    private readonly Queue<byte[]> _items = new();
    private readonly int _maxDepth;
    private bool _waitingForIdr;

    public H264RecoveryQueue(int maxDepth = 12)
    {
        if (maxDepth < 1) throw new ArgumentOutOfRangeException(nameof(maxDepth));
        _maxDepth = maxDepth;
    }

    public H264EnqueueResult Enqueue(byte[] accessUnit)
    {
        ArgumentNullException.ThrowIfNull(accessUnit);
        bool randomAccess = H264AccessUnit.IsRandomAccess(accessUnit);
        lock (_sync)
        {
            if (_waitingForIdr)
            {
                if (!randomAccess) return H264EnqueueResult.DroppedWhileWaiting;
                _items.Clear();
                _waitingForIdr = false;
                _items.Enqueue(accessUnit);
                return H264EnqueueResult.Recovered;
            }

            _items.Enqueue(accessUnit);
            if (_items.Count <= _maxDepth) return H264EnqueueResult.Queued;

            // The reference chain is gone. Keeping even one delta after this point would make the
            // client decode corruption until the next IDR, which is the black/frozen interval this
            // queue exists to remove.
            _items.Clear();
            if (randomAccess)
            {
                _items.Enqueue(accessUnit);
                return H264EnqueueResult.Recovered;
            }
            _waitingForIdr = true;
            return H264EnqueueResult.NeedKeyframe;
        }
    }

    public bool TryDequeue(out byte[] accessUnit)
    {
        lock (_sync)
        {
            if (_items.TryDequeue(out var value))
            {
                accessUnit = value;
                return true;
            }
            accessUnit = Array.Empty<byte>();
            return false;
        }
    }

    public void Clear()
    {
        lock (_sync)
        {
            _items.Clear();
            _waitingForIdr = false;
        }
    }

    public int Count { get { lock (_sync) return _items.Count; } }
    public bool WaitingForIdr { get { lock (_sync) return _waitingForIdr; } }
}

public static class H264AccessUnit
{
    /// <summary>True when an Annex-B access unit contains an IDR slice (NAL type 5).</summary>
    public static bool IsRandomAccess(ReadOnlySpan<byte> bytes)
    {
        for (int i = 0; i + 3 < bytes.Length; i++)
        {
            if (bytes[i] != 0 || bytes[i + 1] != 0) continue;
            int at = -1;
            if (bytes[i + 2] == 1) at = i + 3;
            else if (i + 4 < bytes.Length && bytes[i + 2] == 0 && bytes[i + 3] == 1) at = i + 4;
            if (at < 0 || at >= bytes.Length) continue;
            if ((bytes[at] & 0x1f) == 5) return true;
            i = at;
        }
        return false;
    }
}

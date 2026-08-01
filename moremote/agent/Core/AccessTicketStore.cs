using System.Collections.Concurrent;
using System.Security.Cryptography;

namespace MoRemote;

/// <summary>Short URL capabilities for elements/download agents that cannot send Authorization.</summary>
public sealed class AccessTicketStore
{
    private const int MaxTickets = 1024;
    private sealed record Entry(string Purpose, string Resource, DateTimeOffset Expires);
    private sealed class LeaseEntry
    {
        public required string Purpose { get; init; }
        public required string Resource { get; init; }
        public required DateTimeOffset Expires { get; init; }
        public int RemainingUses;
    }
    private readonly ConcurrentDictionary<string, Entry> _tickets = new();
    private readonly ConcurrentDictionary<string, LeaseEntry> _leases = new();
    private readonly ConcurrentQueue<string> _issueOrder = new();
    private readonly TimeProvider _clock;

    public AccessTicketStore(TimeProvider? clock = null) => _clock = clock ?? TimeProvider.System;

    public string Issue(string purpose, string resource = "", TimeSpan? lifetime = null)
    {
        // Bound both memory and work. The first implementation swept the whole dictionary on every
        // issue, making a burst of N authenticated requests O(N²). FIFO eviction is amortised O(1)
        // and old single-use capabilities are the right entries to sacrifice under pressure.
        EvictForCapacity();
        var token = NewToken();
        _tickets[token] = new Entry(purpose, resource,
            _clock.GetUtcNow() + (lifetime ?? TimeSpan.FromSeconds(45)));
        _issueOrder.Enqueue(token);
        return token;
    }

    /// <summary>A resource-bound capability for HTTP Range/retry requests.</summary>
    public string IssueLease(string purpose, string resource, int maxUses = 32,
        TimeSpan? lifetime = null)
    {
        if (maxUses is < 2 or > 64) throw new ArgumentOutOfRangeException(nameof(maxUses));
        EvictForCapacity();
        var token = NewToken();
        _leases[token] = new LeaseEntry {
            Purpose = purpose,
            Resource = resource,
            Expires = _clock.GetUtcNow() + (lifetime ?? TimeSpan.FromMinutes(5)),
            RemainingUses = maxUses,
        };
        _issueOrder.Enqueue(token);
        return token;
    }

    public bool Consume(string? token, string purpose, out string resource)
    {
        resource = "";
        if (string.IsNullOrEmpty(token) || !_tickets.TryRemove(token, out var entry)) return false;
        if (!SamePurpose(entry.Purpose, purpose) || entry.Expires < _clock.GetUtcNow()) return false;
        resource = entry.Resource;
        return true;
    }

    public bool UseLease(string? token, string purpose, out string resource)
    {
        resource = "";
        if (string.IsNullOrEmpty(token) || !_leases.TryGetValue(token, out var entry)) return false;
        if (!SamePurpose(entry.Purpose, purpose) || entry.Expires < _clock.GetUtcNow())
        {
            _leases.TryRemove(token, out _);
            return false;
        }
        var remaining = Interlocked.Decrement(ref entry.RemainingUses);
        if (remaining < 0) return false;
        if (remaining == 0) _leases.TryRemove(token, out _);
        resource = entry.Resource;
        return true;
    }

    private void EvictForCapacity()
    {
        while (_tickets.Count + _leases.Count >= MaxTickets && _issueOrder.TryDequeue(out var oldest))
        {
            _tickets.TryRemove(oldest, out _);
            _leases.TryRemove(oldest, out _);
        }
    }

    private static string NewToken() => Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
        .TrimEnd('=').Replace('+', '-').Replace('/', '_');

    private static bool SamePurpose(string expected, string actual)
        => CryptographicOperations.FixedTimeEquals(
            System.Text.Encoding.UTF8.GetBytes(expected),
            System.Text.Encoding.UTF8.GetBytes(actual));

    internal int Count => _tickets.Count + _leases.Count;
}

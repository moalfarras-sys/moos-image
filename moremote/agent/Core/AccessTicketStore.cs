using System.Collections.Concurrent;
using System.Security.Cryptography;

namespace MoRemote;

/// <summary>Single-use URL capabilities for elements that cannot send an Authorization header.</summary>
public sealed class AccessTicketStore
{
    private const int MaxTickets = 1024;
    private sealed record Entry(string Purpose, string Resource, DateTimeOffset Expires);
    private readonly ConcurrentDictionary<string, Entry> _tickets = new();
    private readonly ConcurrentQueue<string> _issueOrder = new();
    private readonly TimeProvider _clock;

    public AccessTicketStore(TimeProvider? clock = null) => _clock = clock ?? TimeProvider.System;

    public string Issue(string purpose, string resource = "", TimeSpan? lifetime = null)
    {
        // Bound both memory and work. The first implementation swept the whole dictionary on every
        // issue, making a burst of N authenticated requests O(N²). FIFO eviction is amortised O(1)
        // and old single-use capabilities are the right entries to sacrifice under pressure.
        while (_tickets.Count >= MaxTickets && _issueOrder.TryDequeue(out var oldest))
            _tickets.TryRemove(oldest, out _);
        var token = Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
            .TrimEnd('=').Replace('+', '-').Replace('/', '_');
        _tickets[token] = new Entry(purpose, resource,
            _clock.GetUtcNow() + (lifetime ?? TimeSpan.FromSeconds(45)));
        _issueOrder.Enqueue(token);
        return token;
    }

    public bool Consume(string? token, string purpose, out string resource)
    {
        resource = "";
        if (string.IsNullOrEmpty(token) || !_tickets.TryRemove(token, out var entry)) return false;
        if (!CryptographicOperations.FixedTimeEquals(
                System.Text.Encoding.UTF8.GetBytes(entry.Purpose),
                System.Text.Encoding.UTF8.GetBytes(purpose))
            || entry.Expires < _clock.GetUtcNow()) return false;
        resource = entry.Resource;
        return true;
    }

    internal int Count => _tickets.Count;
}

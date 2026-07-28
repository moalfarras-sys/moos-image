namespace MoRemote;

/// <summary>
/// Rejects replayed and out-of-order input. Sequence only — deliberately NOT wall-clock freshness.
///
/// THE CLOCK CHECK THAT USED TO BE HERE, AND WHY IT IS GONE
///
///     if (Math.Abs(nowMs - timestampMs) > 30000) { error = "stale timestamp"; return false; }
///
/// That compared the SERVER's clock to the browser's Date.now() with nothing anywhere on the wire
/// negotiating the two. A phone or laptop whose clock is more than thirty seconds out — which is
/// ordinary after a flat battery, a plane, a VM resume, or simply no working NTP — had EVERY input
/// message rejected. Not degraded: every one, permanently, with reconnecting landing in exactly the
/// same state, because the skew is a property of the device and not of the session. The user's
/// experience of that is a remote desktop that streams video perfectly and ignores every touch, which
/// is a report this project has already received.
///
/// And it bought nothing. `seq` travels on the wire in plain sight, so anyone able to replay a message
/// is equally able to stamp a fresh timestamp on it; the monotonic sequence below is what actually
/// makes a replay fail. A check that cannot stop an attacker and can lock out a legitimate user is not
/// a security control, it is a liability with a security-sounding name.
///
/// Do not "fix" this by deriving freshness from the ping/pong instead: ws.ts sends performance.now(),
/// a monotonic clock with an arbitrary per-page origin that the server only echoes back. There is no
/// server epoch on the wire to compare anything to.
/// </summary>
public sealed class InputSequenceGuard
{
    private long _last;
    public bool Accept(long sequence,long timestampMs,long nowMs,out string error)
    {
        if(sequence<=_last){error="duplicate or out-of-order sequence";return false;}
        _last=sequence;error="";return true;
    }
}

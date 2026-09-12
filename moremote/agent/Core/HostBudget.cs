using System.Text.Json;

namespace MoRemote;

/// <summary>
/// What THIS MACHINE can afford to encode, as MoOS already decided it.
///
/// WHY THE AGENT ASKS INSTEAD OF GUESSING
///
/// `moos-visual-tier` is MoOS's single authority on "what is this machine". It probes the GPU
/// class, cores, memory and display once, picks a motion tier, and publishes a budget alongside
/// it — file indexing, update concurrency, the Mo AI route, and `remote_encode`, described in its
/// own source as "Mo PC Remote software-encode ceiling: a host with no GPU encodes H.264 on the
/// CPU, so cap resolution x fps to keep interacting with the desktop from starving the encoder."
///
/// That value had no reader. On the maintainer's 2-core Oracle A1 the recorded state says
///
///     "budget": { ..., "remote_encode": "1280x720@30" }
///
/// while the live agent log says `Video stream: 1920x1080` and the portal helper sits at ~15% of
/// one core of two, continuously, for a desktop nobody is changing. The OS had computed the right
/// answer and Remote was not listening. This is the listener.
///
/// WHAT IT IS NOT: a cap on what the viewer may ask for. It is advertised to the controller in
/// `hello` and bounds the AUTOMATIC choice only; a person who deliberately selects Sharp or Ultra
/// still gets it, and is told what the host's own estimate was. A ceiling that silently overrode
/// an explicit choice would be a dead control, which this repository does not ship.
/// </summary>
public static class HostBudget
{
    /// <summary>The parsed ceiling, or null when this machine has published no opinion.</summary>
    public readonly record struct Encode(int Width, int Height, int Fps);

    private static readonly object Gate = new();
    private static Encode? _cached;
    private static DateTime _cachedStamp;
    private static long _checkedTicks = -1;

    /// <summary>
    /// How long a read is trusted before the file's timestamp is checked again. The state is
    /// rewritten only when the machine's hardware signature changes (moos-visual-tier is
    /// idempotent and keyed on that), so this is about picking up a change within a session
    /// without stat()ing on the path of every settings message.
    /// </summary>
    private const int RecheckMs = 30_000;

    private static string StatePath()
    {
        // Matches moos-visual-tier's own state_path(): $XDG_STATE_HOME, else ~/.local/state.
        var stateHome = Environment.GetEnvironmentVariable("MOREMOTE_TIER_STATE")
            ?? Environment.GetEnvironmentVariable("XDG_STATE_HOME");
        if (!string.IsNullOrEmpty(stateHome) && stateHome.EndsWith(".json", StringComparison.Ordinal))
            return stateHome;   // MOREMOTE_TIER_STATE may name the file directly, for tests
        if (string.IsNullOrEmpty(stateHome))
            stateHome = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                                     ".local", "state");
        return Path.Combine(stateHome, "moos-visual-tier.json");
    }

    /// <summary>
    /// The host's advisory encode ceiling, or null.
    ///
    /// Every failure is a null, never an exception and never a log line per call: a machine
    /// without moos-visual-tier (a Windows host, a container, a fresh install before the
    /// post-desktop timer has run) simply has no opinion, and "no opinion" must not be louder or
    /// more expensive than an answer.
    /// </summary>
    public static Encode? RemoteEncode()
    {
        lock (Gate)
        {
            var now = Environment.TickCount64;
            if (_checkedTicks >= 0 && now - _checkedTicks < RecheckMs) return _cached;
            _checkedTicks = now;
            try
            {
                var path = StatePath();
                var info = new FileInfo(path);
                if (!info.Exists) { _cached = null; return null; }
                if (_cached is not null && info.LastWriteTimeUtc == _cachedStamp) return _cached;
                _cachedStamp = info.LastWriteTimeUtc;
                using var doc = JsonDocument.Parse(File.ReadAllBytes(path));
                if (!doc.RootElement.TryGetProperty("budget", out var budget) ||
                    !budget.TryGetProperty("remote_encode", out var value) ||
                    value.ValueKind != JsonValueKind.String)
                {
                    _cached = null;
                    return null;
                }
                _cached = Parse(value.GetString());
                if (_cached is { } e)
                    Log.Info($"Host encode ceiling from moos-visual-tier: {e.Width}x{e.Height}@{e.Fps}.");
                return _cached;
            }
            catch (Exception ex)
            {
                Log.Warn("Could not read the host encode budget: " + ex.Message);
                _cached = null;
                return null;
            }
        }
    }

    /// <summary>"1280x720@30" -> (1280, 720, 30). Anything else is no opinion.</summary>
    public static Encode? Parse(string? text)
    {
        if (string.IsNullOrWhiteSpace(text)) return null;
        var at = text.IndexOf('@');
        if (at <= 0 || at == text.Length - 1) return null;
        var by = text.IndexOf('x', StringComparison.OrdinalIgnoreCase);
        if (by <= 0 || by > at) return null;
        if (!int.TryParse(text.AsSpan(0, by), out var w) ||
            !int.TryParse(text.AsSpan(by + 1, at - by - 1), out var h) ||
            !int.TryParse(text.AsSpan(at + 1), out var fps)) return null;
        // A ceiling outside these bounds is a corrupt or hostile state file, not a policy.
        if (w is < 320 or > 7680 || h is < 240 or > 4320 || fps is < 5 or > 240) return null;
        return new Encode(w, h, fps);
    }
}

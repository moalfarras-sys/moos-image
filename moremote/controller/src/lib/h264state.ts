/**
 * Whether this browser has already proven it cannot hold the H.264 stream.
 *
 * WHY THIS IS A MODULE AND NOT A REF IN THE COMPONENT
 *
 * There are TWO places that offer H.264 to the agent, and they have to agree:
 *
 *   * ws.ts, on every `onopen`, declares what this browser can decode;
 *   * RemoteScreen, after a decode failure, backs off and re-offers it.
 *
 * The retry path was bounded to three attempts. The CONNECT path was not bounded at all — it
 * asked `canDecodeH264()`, which only answers "is WebCodecs available in principle", and knows
 * nothing about the three failures that just happened. So every reconnect re-declared H.264 from
 * scratch and the room started the whole cycle again. Read off the live cloud server, with the
 * three-strikes rule working exactly as designed inside one page load and then being handed a
 * clean slate by the socket:
 *
 *     08:58:46 jpeg -> 08:59:01 h264   15s   (retry n=0)
 *     08:59:15 jpeg -> 08:59:45 h264   30s   (retry n=1)
 *     09:00:00 jpeg -> 09:01:00 h264   60s   (retry n=2)
 *                                   -> stops, budget spent   <- correct
 *     13:39:30 session END
 *     13:39:31 session START -> h264 IMMEDIATELY               <- the hole
 *
 * Every codec change is a full GStreamer teardown and rebuild on the server, which the person
 * watching experiences as the screen cutting out. Sessions on this machine end and reconnect
 * every one to two minutes, so an unbounded connect path means the cut-out never stops.
 *
 * sessionStorage is the right scope: per tab, cleared when the tab closes. A genuinely transient
 * failure costs one tab, and a new tab is always allowed to try again from scratch. It is also
 * why this is not localStorage — a browser that fails once must not be condemned for ever.
 *
 * This does NOT claim to fix H.264 decoding. It stops the damage: a browser that has proven three
 * times that it cannot hold the stream settles on a picture that works.
 */

const KEY = "h264Failures";

/** How many times H.264 has failed to decode in this tab. */
export function h264Failures(): number {
  try {
    return Number(sessionStorage.getItem(KEY)) || 0;
  } catch {
    return 0; // private mode / storage disabled — behave exactly as before.
  }
}

/**
 * Three, and the reasoning is the backoff it gates: 15s, then 30s, then 60s. By the third failure
 * the browser has been given a minute and a half to recover from whatever was transient, so a
 * fourth attempt is not evidence-gathering, it is just another teardown.
 */
export const H264_MAX_FAILURES = 3;

/** Record a decode failure and return the new count. */
export function noteH264Failure(): number {
  const next = h264Failures() + 1;
  try {
    sessionStorage.setItem(KEY, String(next));
  } catch {
    /* private mode — the in-memory retry bound in RemoteScreen still applies */
  }
  return next;
}

/**
 * Has this tab given up on H.264? Consulted by BOTH the connect-time declaration and the retry
 * timer, which is the whole point: one fact, two readers, no way for a reconnect to out-vote it.
 */
export function h264GivenUp(): boolean {
  return h264Failures() >= H264_MAX_FAILURES;
}

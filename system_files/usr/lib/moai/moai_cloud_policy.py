"""Mo AI cloud-only, zero-price inference policy shared by every edition.

A provider's marketing free tier cannot prove that an arbitrary account will
not be billed. The initial supported route therefore uses OpenRouter's explicit
free model IDs AND a zero maximum price. Other providers require an equally
verifiable no-charge boundary before entering the catalogue.
"""
import re
import json
import os
from pathlib import Path
import threading
import time
import urllib.request

BASE = 'https://openrouter.ai/api/v1'
DEFAULT_MODEL = 'openrouter/free'
ERROR = ('Mo AI يعمل بالسحابة فقط. اختر مزوّداً ونموذجاً مسموحاً في الإعدادات؛ '
         'المدفوع يحتاج اختياراً صريحاً ولا يوجد بديل محلي. | Cloud inference only; '
         'choose an allowed provider/model. Paid models require explicit selection; no local fallback.')


def free_model(model):
    return isinstance(model, str) and (model == DEFAULT_MODEL or bool(
        re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+:free', model)))


def selected_cost_policy():
    """Only the explicit Settings provider selection enables billed requests."""
    path = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'moai-agent/state.json'
    try:
        state = json.loads(path.read_text())
        return 'paid' if state.get('provider') == 'openrouter-paid' else 'free'
    except (OSError, ValueError, TypeError):
        return 'free'


def valid_model(model):
    return isinstance(model, str) and bool(re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._/:-]+', model))


def validate(base, model, wire='openai', allow_paid=False):
    if (str(base).rstrip('/') != BASE or wire != 'openai'
            or not (free_model(model) or allow_paid and valid_model(model))):
        raise ValueError(ERROR)


def request_body(body, model, allow_paid=False):
    """Discard caller routing/plugins so paid web/audio tools cannot bypass policy."""
    if not (free_model(model) or allow_paid and valid_model(model)):
        raise ValueError(ERROR)
    allowed = {'messages', 'stream', 'stream_options', 'temperature', 'top_p',
               'max_tokens', 'max_completion_tokens', 'stop', 'seed',
               'frequency_penalty', 'presence_penalty', 'response_format',
               'tools', 'tool_choice', 'parallel_tool_calls', 'reasoning'}
    out = {k: v for k, v in body.items() if k in allowed}
    out['model'] = model
    out['provider'] = {'allow_fallbacks': True}
    if free_model(model):
        out['provider']['max_price'] = {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0}
    # Model fallback is never supplied: a free selection cannot escalate to paid.
    return out


def visible_models(items):
    """Only explicit free variants whose catalogue pricing is entirely zero."""
    result = []
    for item in items:
        if not isinstance(item, dict) or not free_model(item.get('id')):
            continue
        pricing = item.get('pricing')
        if not isinstance(pricing, dict) or not pricing:
            continue
        try:
            if any(float(v) != 0 for v in pricing.values()):
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        result.append(item)
    return result


_catalogue_lock = threading.Lock()
_catalogue = (0, [])

# ── Measured preference for the automatic free route ───────────────────────────
# 2026-09-11, through the real moai-gateway with this zero-price policy active, one
# sample each (docs/MOOS_COMPLETION_PLAN.md, section 1). The previous ranking chose
# the LARGEST free reasoning model, nvidia/nemotron-3-ultra-550b-a55b:free, which
# took 36.7 s and 13.1 s for one-line answers. Measured instead:
#   dots-studio/dots-3-note-preview:free    tool call correct 2.7 s, Arabic 5.1 s
#   nex-agi/nex-n2.5-pro:free               Arabic 2.4 s; asked to confirm instead of calling
#   nvidia/nemotron-3-super-120b-a12b:free  tool call correct 3.0 s, Arabic 9.4 s
# This only ORDERS candidates the live catalogue already proves free. A withdrawn or
# priced id drops out and the next candidate answers; nothing here can admit a model.
MEASURED_PREFERENCE = {
    'chat': ('nex-agi/nex-n2.5-pro:free', 'dots-studio/dots-3-note-preview:free',
             'nvidia/nemotron-3-super-120b-a12b:free'),
    'tools': ('dots-studio/dots-3-note-preview:free', 'nvidia/nemotron-3-super-120b-a12b:free',
              'nex-agi/nex-n2.5-pro:free'),
}

# Upstream answers that mean "not this free model right now". Authentication and
# request errors are not the model's fault and never cool a model down.
RETRIABLE_STATUS = frozenset({403, 404, 408, 429, 500, 502, 503, 504})
_cooldown_lock = threading.Lock()
_cooldown = {}


def note_upstream_failure(model, status):
    """Skip a free model the provider refused: hours if withdrawn, minutes if busy."""
    if not isinstance(model, str) or status not in RETRIABLE_STATUS:
        return
    seconds = 6 * 3600 if status in (403, 404) else 600
    with _cooldown_lock:
        _cooldown[model] = time.monotonic() + seconds


def _free_catalogue():
    global _catalogue
    with _catalogue_lock:
        if time.monotonic() - _catalogue[0] > 300 or not _catalogue[1]:
            try:
                req = urllib.request.Request(BASE + '/models', headers={'User-Agent': 'MoAI/1'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read(4 * 1024 * 1024))
                _catalogue = (time.monotonic(), visible_models(data['data']))
            except Exception as exc:
                raise ValueError('Cannot verify the free model catalogue. Retry; no paid fallback was used.') from exc
        return list(_catalogue[1])


def automatic_candidates(require_tools=False, limit=3):
    """Ordered verified-free candidates for the automatic route.

    Measured preference first; models without a measurement follow in the
    previous capability heuristic (tools, reasoning, size, context). A model the
    provider recently refused is skipped unless it is the only one left, so the
    route degrades to a slower answer rather than to no answer. Refreshes
    availability every five minutes and fails closed if it cannot be verified.
    """
    candidates = [item for item in _free_catalogue() if item['id'].endswith(':free')
                  and (not require_tools or 'tools' in item.get('supported_parameters', []))]
    if not candidates:
        raise ValueError('No verified free model supports this request. No paid fallback was used.')
    now = time.monotonic()
    with _cooldown_lock:
        cooled = {model for model, until in _cooldown.items() if until > now}
    available = [item for item in candidates if item['id'] not in cooled] or candidates
    preference = MEASURED_PREFERENCE['tools' if require_tools else 'chat']

    def heuristic(item):
        parameters = item.get('supported_parameters', [])
        sizes = re.findall(r'(\d+(?:\.\d+)?)b(?:[^a-z]|$)', item['id'].lower())
        return ('tools' in parameters, 'reasoning' in parameters,
                max([float(size) for size in sizes] or [0]),
                int(item.get('context_length') or 0), item['id'])

    measured = sorted((item for item in available if item['id'] in preference),
                      key=lambda item: preference.index(item['id']))
    unmeasured = sorted((item for item in available if item['id'] not in preference),
                        key=heuristic, reverse=True)
    return [item['id'] for item in measured + unmeasured][:max(1, int(limit))]


def automatic_model(require_tools=False):
    """The single best verified-free model; never substitutes a billed one."""
    return automatic_candidates(require_tools, limit=1)[0]

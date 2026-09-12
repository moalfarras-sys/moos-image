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
# OpenCode Zen, a billed provider the owner can pick in Settings. Only the families Zen
# serves on /chat/completions (the one wire Mo AI speaks) are routable, per
# opencode.ai/docs/zen on 2026-09-12: DeepSeek, MiniMax, GLM, Kimi, Big Pickle, MiMo, Ling
# and Nemotron. GPT, Grok and Muse use /responses, Claude and Qwen /messages, Gemini its
# own path; listing those would offer choices that can only fail.
ZEN_BASE = 'https://opencode.ai/zen/v1'
ZEN_CHAT_MODEL = re.compile(r'(?:deepseek|minimax|glm|kimi|mimo|ling|nemotron)-[a-z0-9][a-z0-9.-]*|big-pickle')
# Every billed provider; each is reachable only after the owner selects it in Settings.
PAID_PROVIDERS = {'openrouter-paid': BASE, 'opencode-zen': ZEN_BASE}
ERROR = ('Mo AI يعمل بالسحابة فقط. اختر مزوّداً ونموذجاً مسموحاً في الإعدادات؛ '
         'المدفوع يحتاج اختياراً صريحاً ولا يوجد بديل محلي. | Cloud inference only; '
         'choose an allowed provider/model. Paid models require explicit selection; no local fallback.')


def free_model(model):
    return isinstance(model, str) and (model == DEFAULT_MODEL or bool(
        re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+:free', model)))


def selected_provider():
    """The provider the owner selected in Settings; '' when none was chosen."""
    path = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'moai-agent/state.json'
    try:
        provider = json.loads(path.read_text()).get('provider')
    except (OSError, ValueError, TypeError, AttributeError):
        return ''
    return provider if isinstance(provider, str) else ''


def selected_cost_policy():
    """Only the explicit Settings provider selection enables billed requests."""
    return 'paid' if selected_provider() in PAID_PROVIDERS else 'free'


def valid_model(model):
    return isinstance(model, str) and bool(re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._/:-]+', model))


def zen_model(model):
    return isinstance(model, str) and bool(ZEN_CHAT_MODEL.fullmatch(model))


def paid_model(model, provider=None):
    """A billed model the SELECTED paid provider can actually serve."""
    provider = selected_provider() if provider is None else provider
    if provider == 'openrouter-paid':
        return valid_model(model)
    if provider == 'opencode-zen':
        return zen_model(model)
    return False


def validate_selection(provider, model):
    """Check a Settings choice before it is saved; saving it IS the explicit selection."""
    if provider in ('openrouter-free', 'openrouter-paid') and free_model(model):
        return
    if provider == 'openrouter-paid' and valid_model(model):
        return
    if provider == 'opencode-zen' and zen_model(model):
        return
    raise ValueError(ERROR)


def _zen_route(base, model, allow_paid):
    # Zen is never free here and never a fallback: it takes the owner's explicit
    # selection in Settings AND a documented chat-completions model.
    return (str(base).rstrip('/') == ZEN_BASE and allow_paid
            and selected_provider() == 'opencode-zen' and zen_model(model))


def validate(base, model, wire='openai', allow_paid=False):
    if wire != 'openai':
        raise ValueError(ERROR)
    if str(base).rstrip('/') == BASE and (free_model(model) or allow_paid and valid_model(model)):
        return
    if _zen_route(base, model, allow_paid):
        return
    raise ValueError(ERROR)


def request_body(body, model, allow_paid=False, base=BASE):
    """Discard caller routing/plugins so paid web/audio tools cannot bypass policy."""
    zen = str(base).rstrip('/') == ZEN_BASE
    if zen and not _zen_route(base, model, allow_paid):
        raise ValueError(ERROR)
    if not zen and not (free_model(model) or allow_paid and valid_model(model)):
        raise ValueError(ERROR)
    allowed = {'messages', 'stream', 'stream_options', 'temperature', 'top_p',
               'max_tokens', 'max_completion_tokens', 'stop', 'seed',
               'frequency_penalty', 'presence_penalty', 'response_format',
               'tools', 'tool_choice', 'parallel_tool_calls', 'reasoning'}
    out = {k: v for k, v in body.items() if k in allowed}
    out['model'] = model
    if zen:
        # OpenRouter's routing object and reasoning extension mean nothing to Zen.
        out.pop('reasoning', None)
        return out
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
    # Re-measured 2026-09-12 through the gateway (Arabic answer, set_volume tool call):
    #   nex-n2.5-pro        1.9 s / 1.1 s   correct Arabic, correct call
    #   nemotron-3-super    2.3 s / 1.0 s   correct Arabic, correct call
    #   nex-n2.5-mini       0.9 s / 0.7 s   correct Arabic, correct call
    #   ling-3.0-flash-vl   1.9 s / 1.4 s   correct Arabic, correct call, reads images
    # Dropped: dots-3-note-preview mixed English into Arabic answers; nemotron-3.5-lightning
    # printed its reasoning as the answer; inkling models answered 403; gemma-4 and laguna 429.
    'chat': ('nex-agi/nex-n2.5-pro:free', 'nvidia/nemotron-3-super-120b-a12b:free',
             'nex-agi/nex-n2.5-mini:free', 'inclusionai/ling-3.0-flash-vl:free'),
    'tools': ('nex-agi/nex-n2.5-pro:free', 'nex-agi/nex-n2.5-mini:free',
              'nvidia/nemotron-3-super-120b-a12b:free', 'inclusionai/ling-3.0-flash-vl:free'),
}

# The free models Mo AI offers by name, in the order the picker shows them, each with the
# plain-language reason to pick it. Same measurements as above; anything else stays reachable
# under "all free models". Update both lists together after re-measuring.
CURATED_FREE = (
    ('nex-agi/nex-n2.5-pro:free', 'Nex Pro', 'قوي وسريع — الأفضل لمعظم الأسئلة', 'Strong and fast — best for most questions'),
    ('nex-agi/nex-n2.5-mini:free', 'Nex Mini', 'الأسرع — ردود فورية', 'Fastest — instant replies'),
    ('nvidia/nemotron-3-super-120b-a12b:free', 'Nemotron Super', 'تفكير أعمق للمسائل الصعبة', 'Deeper reasoning for hard problems'),
    ('inclusionai/ling-3.0-flash-vl:free', 'Ling Flash Vision', 'يفهم الصور', 'Understands images'),
    ('cohere/north-mini-code:free', 'North Code', 'مخصص للبرمجة', 'Built for code'),
    ('nvidia/nemotron-3-ultra-550b-a55b:free', 'Nemotron Ultra', 'الأعمق — أبطأ بكثير', 'Deepest — much slower'),
)

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
            except Exception:
                # The provider's official free router remains usable when the
                # optional catalogue endpoint is unavailable. Keep a previously
                # verified catalogue if one exists; otherwise let the caller use
                # that router directly. The request still carries a zero-price
                # ceiling, so this cannot cross into a billed model.
                pass
        return list(_catalogue[1])


def automatic_candidates(require_tools=False, limit=3):
    """Ordered zero-price candidates with the provider router as final fallback.

    Measured preference first; models without a measurement follow in the
    capability heuristic (tools, reasoning, size, context). A model the provider
    recently refused is skipped unless it is the only one left. The official
    ``openrouter/free`` capability router is always the last attempt, including
    when catalogue refresh fails, so catalogue availability is never a chat
    dependency. Every attempt is independently pinned to a zero price.
    """
    candidates = [item for item in _free_catalogue() if item['id'].endswith(':free')
                  and (not require_tools or 'tools' in item.get('supported_parameters', []))]
    if not candidates:
        return [DEFAULT_MODEL]
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
    chosen = [item['id'] for item in measured + unmeasured][:max(1, int(limit))]
    if DEFAULT_MODEL not in chosen:
        chosen.append(DEFAULT_MODEL)
    return chosen


def automatic_model(require_tools=False):
    """The single best verified-free model; never substitutes a billed one."""
    return automatic_candidates(require_tools, limit=1)[0]

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

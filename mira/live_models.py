"""Lightweight Live model metadata shared by settings and the voice executor.

Reading saved model choices must not initialize the Live audio/SDK/NumPy path
on the GUI thread. The actual voice operation imports live_voice when needed.
"""

# The voice executor has its own model; typed-chat choices never select it.
DEFAULT_LIVE_MODEL = 'gemini-3.1-flash-live-preview'
# Reviewed against Google's pricing/deprecation tables on 2026-11-14:
# https://ai.google.dev/gemini-api/docs/pricing
# https://ai.google.dev/gemini-api/docs/deprecations#live-api-models
# free_tier means the provider offers one, subject to the owner's project and
# quota. It does not establish this account's billing state or switch a model.
LIVE_MODEL_CHOICES = (
    {'id': DEFAULT_LIVE_MODEL, 'label': 'Gemini 3.1 Flash Live Preview', 'free_tier': True},
    {'id': 'gemini-2.5-flash-native-audio-preview-12-2025',
     'label': 'Gemini 2.5 Flash Native Audio Preview', 'free_tier': True},
)

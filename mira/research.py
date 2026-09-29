"""Mira's research tool: think carefully and, when it helps, search the web — with sources.

The voice model is fast but answers from memory. For anything current (news, prices, results,
opening hours, weather elsewhere, facts it is unsure of) or anything that needs real reasoning,
the voice and text brains call `research`: a Gemini model with Google Search grounding and thinking
answers, and the answer comes back with the sites it used. Measured free tier (2026-09-29 pricing
page): grounding on 2.5 Flash is free up to 1,500 requests per day.
"""
import json
from pathlib import Path
from urllib.parse import urlparse

GEMINI_CONFIG = Path.home() / '.config/mo-dot/gemini.json'
MODELS = ('gemini-2.5-flash', 'gemini-flash-lite-latest')


def _client():
    from google import genai
    from google.genai import types
    config = json.loads(GEMINI_CONFIG.read_text())
    return genai.Client(api_key=config['api_key'], http_options=types.HttpOptions(timeout=45000)), config


def _sources(response, limit=4):
    out = []
    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks or []
    except (AttributeError, IndexError, TypeError):
        return out
    for chunk in chunks:
        web = getattr(chunk, 'web', None)
        if not web:
            continue
        title = (getattr(web, 'title', '') or '').strip()
        uri = getattr(web, 'uri', '') or ''
        name = title or urlparse(uri).netloc
        if name and name not in [s['title'] for s in out]:
            out.append({'title': name[:80]})   # the URL is a long search redirect: useful to nobody
        if len(out) >= limit:
            break
    return out


def research(question: str, lang: str = 'ar', web: bool = True) -> dict:
    """Answer `question` with careful thought and, if `web`, live Google results. Never raises."""
    question = (question or '').strip()[:1200]
    if not question:
        return {'status': 'error', 'error': 'empty_question', 'summary': 'لا يوجد سؤال للبحث'}
    try:
        from google.genai import types
        client, config = _client()
    except Exception as exc:
        return {'status': 'error', 'error': type(exc).__name__, 'summary': 'إعداد Gemini غير متاح'}
    instruction = (
        'أنت باحثة دقيقة تساعد ميرا. فكّر بعناية، واعتمد على نتائج البحث الحديثة عند الحاجة. '
        'أجب بالعربية بثلاث إلى خمس جمل قصيرة تُقرأ بصوت عالٍ: بلا Markdown ولا قوائم ولا روابط. '
        'اذكر الأرقام والتواريخ بدقة، وقل بوضوح إن لم تجد معلومة موثوقة.' if lang != 'en' else
        'You are a careful researcher helping Mira. Think it through and use fresh search results when needed. '
        'Answer in 3–5 short sentences meant to be spoken: no Markdown, lists or links. Give numbers and dates '
        'precisely, and say plainly if nothing reliable was found.')
    tools = [types.Tool(google_search=types.GoogleSearch())] if web else None
    last = None
    for model in [config.get('research_model')] + list(MODELS):
        if not model:
            continue
        try:
            response = client.models.generate_content(
                model=model, contents=question,
                config=types.GenerateContentConfig(system_instruction=instruction, tools=tools, temperature=0.3))
            text = (response.text or '').strip()
            if not text:
                continue
            sources = _sources(response)
            return {'status': 'ok', 'answer': text[:1400], 'sources': sources, 'model': model, 'searched': bool(sources),
                    'summary': ('بحثت في الإنترنت · ' + ' · '.join(s['title'] for s in sources[:3])) if sources
                               else 'فكّرت في السؤال (بلا بحث)'}
        except Exception as exc:   # next model; only the class name is reported
            last = exc
    return {'status': 'error', 'error': type(last).__name__ if last else 'empty', 'summary': 'تعذّر البحث الآن'}

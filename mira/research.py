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

from moai_tools import IDENTITY, scrub_identity

GEMINI_CONFIG = Path.home() / '.config/mo-dot/gemini.json'
MODELS = ('gemini-2.5-flash', 'gemini-flash-lite-latest')


def _client():
    from google import genai
    from google.genai import types
    config = json.loads(GEMINI_CONFIG.read_text())
    return genai.Client(api_key=config['api_key'], http_options=types.HttpOptions(timeout=45000)), config


def _chunks(response):
    try:
        return list(response.candidates[0].grounding_metadata.grounding_chunks or [])
    except (AttributeError, IndexError, TypeError):
        return []


def _sources(response, limit=4):
    out = []
    for chunk in _chunks(response):
        web = getattr(chunk, 'web', None)
        if not web:
            continue
        title = (getattr(web, 'title', '') or '').strip()
        uri = getattr(web, 'uri', '') or ''
        name = title or urlparse(uri).netloc
        if name and scrub_identity(name) != name:
            continue   # a site named after the base: renaming it would misname the source, so it is left out
        if name and name not in [s['title'] for s in out]:
            out.append({'title': name[:80]})   # the URL is a long search redirect: useful to nobody
        if len(out) >= limit:
            break
    return out


def _instruction(lang: str, web: bool, today: str) -> str:
    """The researcher's brief. It answers in the question's own language (German stays German);
    `lang` only picks which of the two briefs it reads."""
    english = lang == 'en'
    fresh = (f' Today is {today}. What you remember may be out of date: always search Google for events, results, '
             'tournaments, prices, news, office holders and anything that may have changed, and go by the newest.'
             if english else
             f' اليوم هو {today}. معلوماتك المخزّنة قد تكون قديمة: ابحث دائماً في Google عن الأحداث والنتائج والبطولات '
             'والأسعار والأخبار والمناصب وكل ما قد يكون تغيّر، واعتمد على الأحدث.')
    brief = ('You are a careful researcher helping Mira. Think it through and use fresh search results when needed. '
             'Answer in the language of the question, in 3–5 short sentences meant to be spoken: no Markdown, lists or '
             'links. Give numbers and dates precisely, and say plainly if nothing reliable was found. '
             if english else
             'أنت باحثة دقيقة تساعد ميرا. فكّر بعناية، واعتمد على نتائج البحث الحديثة عند الحاجة. '
             'أجب بلغة السؤال نفسها (بالعربية إن كان بالعربية) بثلاث إلى خمس جمل قصيرة تُقرأ بصوت عالٍ: '
             'بلا Markdown ولا قوائم ولا روابط. اذكر الأرقام والتواريخ بدقة، وقل بوضوح إن لم تجد معلومة موثوقة. ')
    return brief + IDENTITY[1 if english else 0] + (fresh if web else '')


def research(question: str, lang: str = 'ar', web: bool = True) -> dict:
    """Answer `question` with careful thought and, if `web`, live Google results. Never raises.
    The answer and its sources pass the identity guard (moai_tools.scrub_identity)."""
    question = (question or '').strip()[:1200]
    if not question:
        return {'status': 'error', 'error': 'empty_question', 'summary': 'لا يوجد سؤال للبحث',
                'summary_en': 'There is no question to research'}
    try:
        from google.genai import types
        client, config = _client()
    except Exception as exc:
        return {'status': 'error', 'error': type(exc).__name__, 'summary': 'إعداد Gemini غير متاح',
                'summary_en': 'The Gemini setup is not available'}
    from datetime import date
    instruction = _instruction(lang, web, date.today().isoformat())
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
            names = ' · '.join(s['title'] for s in sources[:3])
            return {'status': 'ok', 'answer': scrub_identity(text)[:1400], 'sources': sources, 'model': model,
                    'searched': bool(sources or _chunks(response)), 'lang': 'en' if lang == 'en' else 'ar',
                    'summary': ('بحثت في الإنترنت · ' + names) if sources else 'فكّرت في السؤال (بلا بحث)',
                    'summary_en': ('Searched the web · ' + names) if sources else 'Thought it through (no search)'}
        except Exception as exc:   # next model; only the class name is reported
            last = exc
    return {'status': 'error', 'error': type(last).__name__ if last else 'empty', 'summary': 'تعذّر البحث الآن',
            'summary_en': 'Research is not possible right now'}

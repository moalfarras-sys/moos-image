"""The Brain page: which minds Mira thinks with, which model each uses, and where the words go.

Two brains answer typed chat, in this order: Gemini with the owner's own key (also Mira's voice),
then Mo AI's free cloud brain through moai-gateway. The page shows both as they really are — the
key state, the typed-chat model, Mo AI's provider and its measured model list — lets the owner pick
the model each one uses (QSettings 'text_model' / 'cloud_model', read by brain.TextBrain), tests
either for real, and says which brain answered the last typed question. Mo AI's permission tier is
shown read-only with the way to System Settings. Nothing here changes the system: a model pick is
Mira's own preference, a test sends one probe, and measuring is Mo AI's own read-and-rank run.

Which brain answers now follows brain.TextBrain's own rule, derived in one place (`_derived`): Gemini
whenever gemini.json holds a key, unless the latest proof (the page's test, the controller's
Save-and-test, or a real answer) says the key is rejected or missing. Any other failure keeps Gemini
first, with its reason shown as a warning.
"""
import re
import time
import urllib.parse

from PySide6.QtCore import QTimer, QUrl, Slot
from PySide6.QtGui import QDesktopServices

import brain
import moai_agent
import moai_tools
import moos_routes

from pages.base import Page, TEST_MODE

KEY_HELP_URL = 'https://aistudio.google.com/apikey'
SETTINGS_ROUTE = 'moos://settings/assistant'
GROUP_ORDER = ('auto', 'measured', 'curated', 'all', 'paid')
TIERS = ('read', 'project', 'system', 'full')
MEASURE_POLL_MS = 2000

STRINGS = {
    'br_sub': ('من يفكّر لميرا، بأي نموذج، وإلى أين تذهب كلماتك',
               'Who thinks for Mira, with which model, and where your words go'),
    'br_refresh': ('تحديث', 'Refresh'),
    # the route
    'br_route_now': ('الكتابة تُجاب الآن عبر', 'Typed chat is answered by'),
    'br_route_gemini': ('عقل Gemini بمفتاحك', 'Gemini with your key'),
    'br_route_cloud': ('عقل Mo AI السحابي المجاني', "Mo AI's free cloud brain"),
    'br_route_router': ('الأوامر المحلية', 'Local commands'),
    'br_route_moai': ('وكيل Mo AI', 'The Mo AI agent'),
    'br_route_none': ('لا أحد', 'Nobody'),
    'br_chain': ('إن تعذّر عقلٌ يجيب الذي يليه، وتقول ميرا من أجاب',
                 'If one brain cannot answer the next one does, and Mira says which'),
    'br_voice': ('الصوت على Echo', 'Voice on Echo'),
    'br_voice_needs_key': ('يحتاج مفتاح Gemini', 'Needs a Gemini key'),
    'br_last': ('آخر إجابة مكتوبة', 'Last typed answer'),
    'br_last_none': ('لم تُجب ميرا على سؤال مكتوب منذ فتحتها', 'Mira has not answered a typed question since she started'),
    'br_last_stopped': ('أوقفتَها', 'You stopped it'),
    'br_last_failed': ('لم تكتمل', 'Did not finish'),
    'br_last_refused': ('رُفض النموذج المختار فأجاب اختيار Mo AI', "Your pick was refused, so Mo AI's setting answered"),
    'br_seconds': ('ث', 's'),
    'br_no_model': ('—', '—'),
    # Gemini key
    'br_key_title': ('مفتاح Gemini', 'Gemini key'),
    'br_key_sub': ('صوت ميرا وأدواتها وأسرع إجابة مكتوبة. مجاني من Google AI Studio.',
                   "Mira's voice, her tools and the fastest typed answers. Free from Google AI Studio."),
    'br_key_stored': ('يُحفظ على هذا الكمبيوتر فقط (0600) ولا يُعرض أبداً',
                      'Kept on this computer only (0600) and never shown'),
    'br_key_test': ('جرّب المفتاح', 'Test the key'),
    'br_key_get': ('احصل على مفتاح مجاني', 'Get a free key'),
    'br_testing': ('أجرّب…', 'Testing…'),
    'br_works': ('يعمل', 'Works'),
    'br_failed': ('لم ينجح', 'Failed'),
    'br_key_works': ('المفتاح يعمل', 'The key works'),
    'br_key_rejected': ('المفتاح مرفوض', 'Key rejected'),
    'br_key_failed_last': ('لم ينجح المفتاح في آخر اختبار له', 'The key did not pass its last test'),
    'br_gemini_reason': ('تعذّر Gemini: {reason}', 'Gemini could not answer: {reason}'),
    'br_test_ok': ('أجاب {model} خلال {ms}', '{model} answered in {ms}'),
    # typed model
    'br_model_title': ('نموذج الكتابة', 'Typed-chat model'),
    'br_model_sub': ('نموذج Gemini الذي يجيب ما تكتبه. إن نفدت حصته يجيب التالي.',
                     'The Gemini model that answers what you type. If its quota runs out the next one answers.'),
    'br_model_lite': ('Flash-Lite', 'Flash-Lite'),
    'br_model_lite_note': ('الأسرع · 0.7 ث مقيسة هنا · الافتراضي', 'Fastest · 0.7 s measured here · default'),
    'br_model_25': ('2.5 Flash', '2.5 Flash'),
    'br_model_25_note': ('أقوى قليلاً · 0.9 ث مقيسة هنا', 'A little stronger · 0.9 s measured here'),
    'br_model_latest': ('\u200fFlash (الأحدث)', 'Flash (latest)'),
    'br_model_latest_note': ('الأحدث لكنه بطيء (12 ث) وحصته تنفد بسرعة', 'Newest, but slow (12 s) and its quota runs out fast'),
    'br_model_from_config': ('مأخوذ من gemini.json · اختر هنا ليصبح اختيارك', 'Taken from gemini.json · pick here to make it yours'),
    'br_model_needs_key': ('يعمل بعد حفظ مفتاح Gemini', 'Takes effect once a Gemini key is saved'),
    'br_default': ('الافتراضي', 'Default'),
    'br_chosen': ('المختار', 'Chosen'),
    'br_model_saved': ('ستجيب الكتابة الآن عبر {model}', 'Typed chat now answers with {model}'),
    'br_model_not_saved': ('تعذّر حفظ اختيارك', 'Your choice could not be saved'),
    # Mo AI cloud
    'br_cloud_title': ('عقل Mo AI السحابي', "Mo AI's cloud brain"),
    'br_cloud_sub': ('يجيب بلا مفتاح Gemini، ويحلّ محلّه إن تعذّر. أدوات ميرا نفسها تعمل عليه.',
                     "Answers when there is no Gemini key, and stands in when Gemini fails. Mira's own tools work on it."),
    'br_provider': ('المزوّد', 'Provider'),
    'br_key_saved': ('المفتاح محفوظ', 'Key saved'),
    'br_key_missing': ('لا مفتاح', 'No key'),
    'br_provider_settings': ('المزوّد والمفتاح', 'Provider and key'),
    'br_test_connection': ('اختبر الاتصال', 'Test connection'),
    'br_best': ('الأفضل قياساً على هذا الكمبيوتر', 'Best measured on this computer'),
    'br_best_none': ('لم يُقَس أي نموذج هنا بعد', 'No model has been measured here yet'),
    'br_age_today': ('اليوم', 'today'),
    'br_age_yesterday': ('أمس', 'yesterday'),
    'br_age_two': ('قبل يومين', '2 days ago'),
    'br_age_few': ('قبل {days} أيام', '{days} days ago'),          # 3–10 (Arabic plural)
    'br_age_many': ('قبل {days} يوماً', '{days} days ago'),        # 11 and more
    'br_best_gone': ('لم يعد في قائمة المزوّد', 'no longer in the provider\'s list'),
    'br_use_it': ('استخدمه', 'Use it'),
    'br_best_short': ('الأفضل هنا', 'Best here'),
    'br_measure': ('قِس من جديد', 'Measure again'),
    'br_measuring': ('أقيس {done} من {total}…', 'Measuring {done} of {total}…'),
    'br_uses': ('طريق ميرا المجاني يستخدم', "Mira's free route uses"),
    'br_follow': ('اتبع إعداد Mo AI', "Follow Mo AI's setting"),
    'br_follow_note': ('النموذج المختار في إعدادات Mo AI: {model}', 'The model chosen in Mo AI settings: {model}'),
    'br_moai_setting': ('إعداد Mo AI', "Mo AI's setting"),
    'br_group_auto': ('تلقائي', 'Automatic'),
    'br_group_measured': ('مقيس هنا', 'Measured here'),
    'br_group_curated': ('مختار مسبقاً', 'Curated'),
    'br_group_all': ('كل النماذج المجانية', 'All free models'),
    'br_group_paid': ('مدفوع باختيارك', 'Paid by your choice'),
    'br_show_all': ('اعرض كل النماذج المجانية ({count})', 'Show all free models ({count})'),
    'br_hide_all': ('أخفِ القائمة الكاملة', 'Hide the full list'),
    'br_paid': ('مدفوع', 'Paid'),
    'br_vision': ('يرى الصور', 'Sees images'),
    'br_paid_confirm': ('النموذج {model} يُحاسَب على مفتاحك لدى {provider}. أتستخدمه لطريق ميرا السحابي؟',
                        '{model} is billed to your key with {provider}. Use it for Mira\'s cloud route?'),
    'br_paid_yes': ('نعم، استخدمه', 'Yes, use it'),
    'br_cancel': ('إلغاء', 'Cancel'),
    'br_pick_gone': ('اختيارك {model} لم يعد في القائمة؛ سيجيب إعداد Mo AI حتى تختار غيره',
                     "Your pick {model} is no longer listed; Mo AI's setting answers until you pick another"),
    'br_cloud_saved': ('طريق ميرا المجاني يستخدم الآن {model}', "Mira's free route now uses {model}"),
    'br_cloud_follow_saved': ('طريق ميرا المجاني يتبع إعداد Mo AI', "Mira's free route follows Mo AI's setting"),
    'br_models_loading': ('أقرأ قائمة النماذج من المزوّد…', "Reading the provider's model list…"),
    'br_models_failed': ('تعذّر قراءة قائمة النماذج', 'The model list could not be read'),
    'br_not_listed': ('القائمة لم تُقرأ بعد', 'The list has not been read yet'),
    'br_unreachable': ('لا يستجيب Mo AI الآن', 'Mo AI is not answering right now'),
    # permissions
    'br_perm_title': ('صلاحيات وكيل Mo AI', "The Mo AI agent's permissions"),
    'br_perm_sub': ('الوكيل الذي تستطيع ميرا أن تكلّفه بمهمة، ووكيل الهاتف', 'The agent Mira can hand a task to, and the phone agent'),
    'br_tier_read': ('معطّل — بلا تحكّم', 'Disabled — no control'),
    'br_tier_read_note': ('يردّ ويحلّل داخل عزل فقط', 'Replies inside a sandbox only'),
    'br_tier_project': ('تعديل المشروع', 'Edit project'),
    'br_tier_project_note': ('يقرأ ويعدّل ويختبر داخل مجلد المشروع المعزول', 'Reads, edits and tests inside the sandboxed project'),
    'br_tier_system': ('تحكّم بالنظام — بموافقة', 'System control — ask first'),
    'br_tier_system_note': ('يتحكّم بالجهاز، ويعرض كل أمر لتوافق عليه أولاً', 'Controls the device, showing every command for your approval first'),
    'br_tier_full': ('كامل — بلا سؤال', 'Full — no confirmation'),
    'br_tier_full_note': ('ينفّذ على جهازك فوراً بلا موافقة. الأقوى والأخطر', 'Runs on your device at once without approval. Most powerful, highest risk'),
    'br_tier_custom': ('صلاحيات مخصّصة', 'Custom permissions'),
    'br_tier_custom_note': ('الإعداد لا يطابق أي مستوى؛ اختر مستوى من الإعدادات', 'Matches no tier; pick one in Settings'),
    'br_web_on': ('الإنترنت: مسموح', 'Internet: allowed'),
    'br_web_off': ('الإنترنت: ممنوع', 'Internet: off'),
    'br_exec_on': ('الطرفية: نعم', 'Terminal: yes'),
    'br_exec_off': ('الطرفية: لا', 'Terminal: no'),
    'br_host_on': ('يصل إلى الجهاز', 'Reaches the device'),
    'br_host_off': ('معزول', 'Sandboxed'),
    'br_approvals_on': ('يسأل قبل التنفيذ', 'Asks before acting'),
    'br_approvals_off': ('لا يسأل', 'Does not ask'),
    'br_mira_rule': ('أدوات ميرا نفسها لا تتبع هذا المستوى: القراءة والتحكّم الفوري يعملان مباشرة، وكل تغيير في النظام ينتظر موافقتك على بطاقة.',
                     "Mira's own tools do not follow this tier: reads and instant controls run at once, and every system change waits for your approval on a card."),
    'br_perm_open': ('غيّرها في إعدادات النظام', 'Change in System Settings'),
    # privacy
    'br_privacy_title': ('الخصوصية', 'Privacy'),
    'br_privacy_sub': ('إلى أين تذهب كلماتك', 'Where your words go'),
    'br_priv_gemini': ('مع مفتاح Gemini: ما تكتبه وما تقوله لميرا، ونتائج أدواتها، تذهب إلى Google بمفتاحك أنت. البحث يمرّ عبر بحث Google.',
                       'With a Gemini key: what you type and say to Mira, and her tool results, go to Google under your own key. Research goes through Google Search.'),
    'br_priv_cloud': ('الطريق المجاني: الكتابة ونتائج الأدوات تذهب إلى {provider} على {host}، وإلى النموذج الذي يوجّهها إليه.',
                      'The free route: typed turns and tool results go to {provider} at {host}, and to the model it routes them to.'),
    # tools.system_instruction puts mira_memory.load() and profile_text() into every prompt, and
    # tools.conversation_turns adds the recent messages: say so (test_page_brain pins both halves).
    'br_priv_local': ('ذاكرة ميرا وملفك محفوظان على هذا الكمبيوتر فقط، لكنهما مع آخر المحادثة يُرسلان مع كل سؤال '
                      'إلى العقل الذي يجيب. الأوامر المحلية والتذكيرات تعمل هنا.',
                      "Mira's memory and your profile are stored only on this computer, but they and your recent "
                      'conversation go with each question to whichever brain answers. Local commands and reminders run here.'),
    'br_priv_keys': ('المفاتيح لا تُعرض ولا تُرسل إلا إلى خدمتها.', 'Keys are never shown and go only to their own service.'),
    # reasons (Gemini) — the page's words for brain.REASONS
    'br_reason_quota': ('انتهت الحصة الآن', 'the quota is used up right now'),
    'br_reason_auth': ('المفتاح مرفوض', 'the key was rejected'),
    'br_reason_network': ('لا اتصال', 'no connection'),
    'br_reason_timeout': ('تأخر الرد', 'it took too long'),
    'br_reason_server': ('الخوادم تواجه مشكلة', 'the servers are failing'),
    'br_reason_config': ('لا يوجد مفتاح محفوظ', 'no key is saved'),
    'br_reason_empty': ('لم يصل رد', 'no answer came back'),
    'br_reason_request': ('رُفض الطلب', 'the request was refused'),
    'br_reason_unknown': ('غير متاح', 'unavailable'),
    'br_route_failed': ('تعذّر فتح الإعدادات', 'Settings could not be opened'),
}

TEXT_MODEL_WORDS = {
    'gemini-flash-lite-latest': ('br_model_lite', 'br_model_lite_note'),
    'gemini-2.5-flash': ('br_model_25', 'br_model_25_note'),
    'gemini-flash-latest': ('br_model_latest', 'br_model_latest_note'),
}


def _pair(text):
    """Mo AI's services answer 'عربي | English'; keep both halves (either may be missing)."""
    parts = [part.strip() for part in str(text or '').split(' | ', 1)]
    return (parts[0], parts[1] if len(parts) > 1 else parts[0])


def _provider_names(name, fallback):
    """'OpenRouter (مجاني فقط | free only)' → ('OpenRouter (مجاني فقط)', 'OpenRouter (free only)')."""
    name = str(name or '').strip()
    match = re.fullmatch(r'(.*?)\s*\((.*?)\s*\|\s*(.*?)\)', name)
    if match:
        return f'{match[1]} ({match[2]})', f'{match[1]} ({match[3]})'
    return (name or fallback, name or fallback)


def _short(model_id):
    """'nvidia/nemotron-3-super-120b-a12b:free' → 'nemotron-3-super-120b-a12b' (for a sentence)."""
    tail = str(model_id or '').split('/')[-1]
    return tail[:-5] if tail.endswith(':free') else tail


IDLE_TEST = {'state': 'idle', 'model': '', 'ms': 0, 'reason': ''}
UNKNOWN_HEALTH = {'state': 'unknown', 'reason': '', 'source': ''}
# A Gemini failure that makes every typed question fall through to Mo AI's cloud brain. Any other
# failure (quota, network, a slow or failing server) is Gemini still asked first, with a warning.
HARD_REASONS = ('auth', 'config')


class BrainPage(Page):
    def __init__(self, host, parent=None):
        super().__init__(host, parent)
        self._rows = {}                    # bare model id → row, from the last /models read
        self._key_seen = ''                # the controller's Save-and-test state last handled
        self._shown = True                 # False once the owner left the page: polling stops
        # One poll at a time, however many reads report a run in progress (a restart coalesces).
        self._poll = QTimer(self)
        self._poll.setSingleShot(True)
        self._poll.setInterval(MEASURE_POLL_MS)
        self._poll.timeout.connect(self._poll_measure)
        brain.add_answer_listener(self._answer_arrived)

    # ── state ───────────────────────────────────────────────────────
    def update(self, **fields):
        """Every change also refreshes what is derived from it: which brain answers now, the key's
        state and the warning, from one rule (brain.TextBrain asks Gemini first whenever a key is
        saved; only a rejected or missing key sends every question on to Mo AI)."""
        fields.update(self._derived({**self._state, **fields}))
        super().update(**fields)

    @staticmethod
    def _derived(state):
        has_key = state.get('has_key')
        health = state.get('gemini_health') or UNKNOWN_HEALTH
        testing = state.get('saving') is True or (state.get('gemini_test') or {}).get('state') == 'testing'
        failed = health.get('state') == 'failed'
        hard = failed and health.get('reason') in HARD_REASONS
        if has_key is None:
            return {'key_status': 'unknown', 'route_now': '', 'gemini_warning': ''}
        if not has_key:
            return {'key_status': 'missing', 'route_now': 'moai-cloud', 'gemini_warning': ''}
        status = ('testing' if testing else 'ok' if health.get('state') == 'ok' else 'failed' if failed else 'set')
        warning = ''
        if failed and not hard:
            # A save's own test does not say why; the page's test (run right after) does.
            warning = 'save' if health.get('source') == 'save' and health.get('reason') == 'unknown' \
                else (health.get('reason') or 'unknown')
        return {'key_status': status, 'route_now': 'moai-cloud' if hard else 'gemini', 'gemini_warning': warning}

    def initial(self):
        prefs = brain.preferences()
        text_model = prefs.get('text_model') or brain.DEFAULT_TEXT_MODEL
        state = {
            'loading': False,
            'text_model': text_model,
            'text_model_source': 'mira' if prefs.get('text_model') else 'default',
            'text_models': self._text_models(),
            'voice_model': '',
            'has_key': None,
            'saving': False,
            'gemini_health': dict(UNKNOWN_HEALTH),
            'gemini_test': dict(IDLE_TEST),
            'cloud': {'state': 'loading', 'provider': '', 'name_ar': '', 'name_en': '', 'host': '', 'has_key': False,
                      'model': '', 'free': True, 'wire': 'openai', 'base': ''},
            'models_state': 'idle', 'models_error_ar': '', 'models_error_en': '',
            'groups': [], 'all_count': 0,
            'moai_default': '',
            'cloud_model': prefs.get('cloud_model') or '',
            'pick_missing': False,
            'paid_pending': '', 'paid_pending_label': '',
            'measure': {'state': 'idle', 'measuring': False, 'done': 0, 'total': 0, 'best': '', 'best_label': '',
                        'age_days': 0, 'best_available': False, 'error_ar': '', 'error_en': ''},
            'cloud_test': {'state': 'idle', 'model': '', 'reply': '', 'error_ar': '', 'error_en': '', 'ms': 0},
            'last': self._last(brain.last_answer()),
            'permissions': {'state': 'loading', 'tier': '', 'web': False, 'exec': False, 'host_control': False,
                            'approvals': False, 'sandbox': '', 'workspace': '', 'project': ''},
        }
        state.update(self._derived(state))
        return state

    @staticmethod
    def _text_models():
        out = []
        for model_id in brain.TEXT_MODEL_IDS:
            name, note = TEXT_MODEL_WORDS.get(model_id, ('', ''))
            out.append({'id': model_id, 'name_key': name, 'note_key': note,
                        'default': model_id == brain.DEFAULT_TEXT_MODEL})
        return out

    @staticmethod
    def _last(summary):
        if not isinstance(summary, dict) or not summary.get('route'):
            return {}
        at = summary.get('at')
        return {'route': summary.get('route'), 'model': summary.get('model') or '',
                'status': summary.get('status') or '', 'ms': int(summary.get('elapsed_ms') or 0),
                'reason': summary.get('fallback_reason') or '',
                'refused': summary.get('model_refused') or '', 'tools': int(summary.get('tools') or 0),
                'time': time.strftime('%H:%M', time.localtime(at)) if isinstance(at, (int, float)) else ''}

    # ── reading ─────────────────────────────────────────────────────
    def activated(self):
        self._shown = True
        super().activated()

    @Slot()
    def pageHidden(self):
        """The owner left the page (its QML went away): no more polling until he comes back."""
        self._shown = False
        self._poll.stop()

    @Slot()
    def refresh(self):
        prefs = brain.preferences()
        self.update(loading=True, models_state='loading', cloud_model=prefs.get('cloud_model') or '',
                    last=self._last(brain.last_answer()))
        self.run('gemini', brain.gemini_settings)
        self.run('config', moai_agent.get, '/api/config')
        self.run('models', moai_tools.get, '/models', 40)
        self.run('measure', moai_tools.get, '/measure')

    def on_gemini(self, tag, result):
        result = result if isinstance(result, dict) else {}
        picked = brain.preferences().get('text_model')
        configured = result.get('text_model') or ''
        if picked:
            model, source = picked, 'mira'
        elif configured:
            model, source = configured, 'config'
        else:
            model, source = brain.DEFAULT_TEXT_MODEL, 'default'
        self.update(has_key=bool(result.get('has_key')), voice_model=result.get('voice_model') or '',
                    text_model=model, text_model_source=source)

    def on_config(self, tag, result):
        if not isinstance(result, dict) or result.get('error'):
            reason = (result or {}).get('error', '') if isinstance(result, dict) else ''
            self.update(loading=False,
                        cloud={**self._state['cloud'], 'state': 'error', 'error': reason},
                        permissions={**self._state['permissions'], 'state': 'error'})
            return
        cloud = result.get('cloud') if isinstance(result.get('cloud'), dict) else {}
        provider_id = str(cloud.get('provider') or '')
        entry = next((p for p in (result.get('providers') or []) if isinstance(p, dict) and p.get('id') == provider_id), {})
        base = str(cloud.get('base') or entry.get('base') or '')
        name_ar, name_en = _provider_names(entry.get('name'), provider_id or urllib.parse.urlparse(base).hostname or '')
        api = str(entry.get('api') or '').lower()
        self.update(loading=False, cloud={
            'state': 'ok', 'provider': provider_id, 'name_ar': name_ar, 'name_en': name_en,
            'host': urllib.parse.urlparse(base).hostname or '', 'base': base,
            'has_key': cloud.get('has_key') is True, 'model': str(cloud.get('model') or ''),
            'free': entry.get('free') is not False, 'wire': 'anthropic' if api.startswith('anthropic') else 'openai'})
        permissions = result.get('permissions') if isinstance(result.get('permissions'), dict) else {}
        tier = str(permissions.get('tier') or '')
        self.update(permissions={
            'state': 'ok', 'tier': tier if tier in TIERS else ('custom' if tier else ''),
            'web': permissions.get('web') is True, 'exec': permissions.get('exec') is True,
            'host_control': permissions.get('host_control') is True, 'approvals': permissions.get('approvals') is True,
            'sandbox': str(permissions.get('sandbox') or ''), 'workspace': str(permissions.get('workspace') or ''),
            'project': str(permissions.get('project') or '')})

    def on_models(self, tag, result):
        if not isinstance(result, dict) or result.get('error'):
            reason = str(result.get('error') or '') if isinstance(result, dict) else 'shape'
            if reason == 'moai_control_unreachable':
                ar, en = STRINGS['br_unreachable']
            else:
                ar, en = (f'{text} ({reason})' for text in STRINGS['br_models_failed'])
            self.update(models_state='error', models_error_ar=ar, models_error_en=en)
            return
        groups = {key: [] for key in GROUP_ORDER}
        rows = {}
        for item in result.get('cloud') or []:
            if not isinstance(item, dict):
                continue
            full = str(item.get('id') or '')
            bare = full[6:] if full.startswith('cloud:') else full
            if not bare or bare in rows:
                continue
            group = item.get('group') if item.get('group') in GROUP_ORDER else 'all'
            label = str(item.get('label') or bare)
            row = {'id': bare, 'group': group,
                   'label_ar': str(item.get('label_ar') or (label if label != bare else _short(bare))),
                   'label_en': str(item.get('label_en') or (label if label != bare else _short(bare))),
                   'note_ar': str(item.get('note_ar') or ''), 'note_en': str(item.get('note_en') or ''),
                   'full_id': bare, 'paid': group == 'paid', 'serving': item.get('serving') is True,
                   'vision': 'image' in (item.get('input') or [])}
            rows[bare] = row
            groups[group].append(row)
        self._rows = rows
        default = str(result.get('default') or '')
        default = default[6:] if default.startswith('cloud:') else default
        error_ar, error_en = _pair(result.get('cloud_error')) if result.get('cloud_error') else ('', '')
        picked = self._state.get('cloud_model') or ''
        self.update(models_state='ok' if rows else 'error',
                    models_error_ar=error_ar or (STRINGS['br_models_failed'][0] if not rows else ''),
                    models_error_en=error_en or (STRINGS['br_models_failed'][1] if not rows else ''),
                    groups=[{'key': key, 'rows': groups[key]} for key in GROUP_ORDER if groups[key]],
                    all_count=len(groups['all']), moai_default=default,
                    pick_missing=bool(picked) and picked not in rows)
        self._update_best()

    def on_measure(self, tag, result):
        if not isinstance(result, dict) or (result.get('error') and 'measuring' not in result):
            error = str(result.get('error') or '') if isinstance(result, dict) else 'shape'
            ar, en = STRINGS['br_unreachable'] if error == 'moai_control_unreachable' else _pair(error)
            self.update(measure={**self._state['measure'], 'state': 'error', 'measuring': False,
                                 'error_ar': ar, 'error_en': en})
            return
        was_measuring = self._state['measure'].get('measuring')
        measuring = result.get('measuring') is True
        ar, en = _pair(result.get('error')) if result.get('error') else ('', '')
        best = str(result.get('best') or '')
        # moai-control keeps the last run's error beside the best it measured before: both are shown.
        self.update(measure={'state': 'error' if ar else 'ok', 'measuring': measuring,
                             'done': int(result.get('done') or 0), 'total': int(result.get('total') or 0),
                             'best': best, 'best_label': str(result.get('bestLabel') or _short(best)),
                             'age_days': result.get('ageDays') or 0, 'best_available': best in self._rows,
                             'error_ar': ar, 'error_en': en})
        if measuring and self._shown and not TEST_MODE:
            self._poll.start()
        else:
            self._poll.stop()
        if was_measuring and not measuring and not TEST_MODE:
            # The ranking changed: the picker's groups and notes did too.
            self.run('models', moai_tools.get, '/models', 40)

    def _poll_measure(self):
        if self._shown:
            self.run('measure:poll', moai_tools.get, '/measure')

    def _update_best(self):
        measure = self._state['measure']
        if measure.get('best'):
            self.update(measure={**measure, 'best_available': measure['best'] in self._rows})

    # ── the answer that just finished (from the brain thread) ────────
    def _answer_arrived(self, summary):
        self._done.emit('answer', summary)

    def on_answer(self, tag, summary):
        summary = summary if isinstance(summary, dict) else {}
        fields = {'last': self._last(summary)}
        reason = summary.get('fallback_reason')
        if reason == 'config':
            fields['has_key'] = False          # the brain found no usable key in gemini.json
        elif reason in brain.REASONS:
            fields['gemini_health'] = {'state': 'failed', 'reason': reason, 'source': 'answer'}
        elif summary.get('route') == 'gemini' and summary.get('status') != 'cancelled':
            fields['gemini_health'] = {'state': 'ok', 'reason': '', 'source': 'answer'}
        self.update(**fields)

    # ── the key (saved by the controller's Save-and-test) ───────────
    @Slot(str, str)
    def keyChecked(self, state, reason):
        """The controller's `brainKey` moved (the QML passes it on): 'testing' after a save, then 'ok' or
        'failed'; 'set' / 'missing' only answer while the page has not read gemini.json yet. A failed
        save does not say why, so the page's own classified test runs next."""
        state, reason = str(state or ''), str(reason or '')
        if state == self._key_seen:
            return
        self._key_seen = state
        if state == 'testing':
            self.update(has_key=True, saving=True, gemini_health=dict(UNKNOWN_HEALTH), gemini_test=dict(IDLE_TEST))
        elif state == 'ok':
            # A test shown from before this save was about the previous key.
            self.update(has_key=True, saving=False, gemini_test=dict(IDLE_TEST),
                        gemini_health={'state': 'ok', 'reason': '', 'source': 'save'})
        elif state == 'failed':
            known = reason if reason in brain.REASONS else ''
            self.update(has_key=True, saving=False, gemini_test=dict(IDLE_TEST),
                        gemini_health={'state': 'failed', 'reason': known or 'unknown', 'source': 'save'})
            if not known and not TEST_MODE:
                self.testGemini()
        elif state in ('set', 'missing') and self._state.get('has_key') is None:
            self.update(has_key=state == 'set')

    # ── choosing ────────────────────────────────────────────────────
    @Slot(str)
    def setTextModel(self, model_id):
        try:
            brain.set_text_model(model_id)
        except (ValueError, RuntimeError):
            self.host.toast.emit('error', self.text('br_model_not_saved'))
            return
        name_key = TEXT_MODEL_WORDS.get(model_id, ('', ''))[0]
        self.update(text_model=model_id, text_model_source='mira', gemini_test=dict(IDLE_TEST))
        self.host.toast.emit('ok', self.text('br_model_saved').format(model=self.text(name_key) if name_key else model_id))

    @Slot(str)
    def setCloudModel(self, model_id):
        model_id = str(model_id or '').strip()
        if model_id and model_id not in self._rows:
            self.host.toast.emit('error', self.text('br_not_listed'))
            return
        row = self._rows.get(model_id)
        if row is not None and row['paid'] and model_id != self._state.get('cloud_model'):
            # Billed to the owner's key: one explicit yes on the page first.
            self.update(paid_pending=model_id, paid_pending_label=row['label_en' if self.lang == 'en' else 'label_ar'])
            return
        self._save_cloud_model(model_id)

    @Slot()
    def confirmPaidModel(self):
        model_id = self._state.get('paid_pending') or ''
        if model_id and model_id in self._rows:
            self._save_cloud_model(model_id)
        self.update(paid_pending='', paid_pending_label='')

    @Slot()
    def cancelPaidModel(self):
        self.update(paid_pending='', paid_pending_label='')

    def _save_cloud_model(self, model_id):
        try:
            saved = brain.set_cloud_model(model_id)
        except ValueError:
            self.host.toast.emit('error', self.text('br_not_listed'))
            return
        except RuntimeError:
            self.host.toast.emit('error', self.text('br_model_not_saved'))
            return
        self.update(cloud_model=saved, pick_missing=False, paid_pending='', paid_pending_label='',
                    cloud_test={'state': 'idle', 'model': '', 'reply': '', 'error_ar': '', 'error_en': '', 'ms': 0})
        if saved:
            row = self._rows.get(saved) or {}
            label = row.get('label_en' if self.lang == 'en' else 'label_ar') or _short(saved)
            self.host.toast.emit('ok', self.text('br_cloud_saved').format(model=label))
        else:
            self.host.toast.emit('ok', self.text('br_cloud_follow_saved'))

    # ── testing and measuring ───────────────────────────────────────
    @Slot()
    def testGemini(self):
        if self._state['gemini_test'].get('state') == 'testing':
            return
        model = self._state.get('text_model') or brain.DEFAULT_TEXT_MODEL
        self.update(gemini_test={'state': 'testing', 'model': model, 'ms': 0, 'reason': ''})
        self.run('gtest', brain.probe_gemini, model)

    def on_gtest(self, tag, result):
        result = result if isinstance(result, dict) else {'status': 'error', 'error': 'shape'}
        ok = result.get('status') == 'ok'
        reason = '' if ok else (result.get('reason') if result.get('reason') in brain.REASONS else 'unknown')
        fields = {'gemini_test': {'state': 'ok' if ok else 'failed', 'model': result.get('model') or '',
                                  'ms': int(result.get('elapsed_ms') or 0), 'reason': reason},
                  # The latest proof wins: this test, a save's test or an answer, whichever came last.
                  'gemini_health': {'state': 'ok' if ok else 'failed', 'reason': reason, 'source': 'test'}}
        if reason == 'config':
            fields['has_key'] = False
        self.update(**fields)

    @Slot()
    def testCloud(self):
        cloud = self._state['cloud']
        if self._state['cloud_test'].get('state') == 'testing':
            return
        if cloud.get('state') != 'ok' or not cloud.get('base'):
            self.host.toast.emit('error', self.text('br_unreachable'))
            return
        # The model Mira's free route really asks for: her own pick while it is still listed, else what
        # moai-gateway uses when no model is sent (moai-control's default, which /models reports).
        picked = self._state.get('cloud_model') if not self._state.get('pick_missing') else ''
        model = picked or self._state.get('moai_default') or cloud.get('model') or ''
        # moai-control's /test contract: base, model and wire only. The saved key stays in Mo AI's own
        # credential store; this page never reads or sends one.
        body = {'cloud_base': cloud['base'], 'cloud_model': model, 'cloud_wire': cloud.get('wire') or 'openai'}
        self.update(cloud_test={'state': 'testing', 'model': model, 'reply': '', 'error_ar': '', 'error_en': '', 'ms': 0})
        self.run('ctest', self._timed, moai_tools.post, '/test', body, 60)

    @staticmethod
    def _timed(fn, *args):
        started = time.monotonic()
        result = fn(*args)
        return {'result': result, 'ms': int((time.monotonic() - started) * 1000)}

    def on_ctest(self, tag, result):
        ms = int(result.get('ms') or 0) if isinstance(result, dict) else 0
        reply = result.get('result') if isinstance(result, dict) and 'result' in result else result
        model = self._state['cloud_test'].get('model') or ''
        if isinstance(reply, dict) and reply.get('ok') is True:
            self.update(cloud_test={'state': 'ok', 'model': str(reply.get('model') or model), 'ms': ms,
                                    'reply': str(reply.get('reply') or '')[:120], 'error_ar': '', 'error_en': ''})
            return
        error = reply.get('error') if isinstance(reply, dict) else ''
        if error == 'moai_control_unreachable':
            ar, en = STRINGS['br_unreachable']
        else:
            ar, en = _pair(error or 'unknown')
        self.update(cloud_test={'state': 'failed', 'model': model, 'ms': ms, 'reply': '', 'error_ar': ar, 'error_en': en})

    @Slot()
    def measureNow(self):
        if self._state['measure'].get('measuring'):
            return
        self.update(measure={**self._state['measure'], 'measuring': True, 'done': 0, 'total': 0,
                             'error_ar': '', 'error_en': ''})
        self.run('measure:start', moai_tools.post, '/measure', {}, 30)

    # ── elsewhere ───────────────────────────────────────────────────
    def _open(self, route):
        result = moos_routes.open_route(route)
        if result.get('status') != 'ok':
            self.host.toast.emit('error', self.text('br_route_failed'))

    @Slot()
    def openProviderSettings(self):
        self._open(SETTINGS_ROUTE)

    @Slot()
    def openPermissionSettings(self):
        self._open(SETTINGS_ROUTE)

    @Slot()
    def openKeyHelp(self):
        QDesktopServices.openUrl(QUrl(KEY_HELP_URL))

    # ── review renders (MIRA_TEST_MODE) ─────────────────────────────
    def review(self):
        """Visibly-sample state: the shapes the real services return, with sample values."""
        rows = [
            {'id': 'openrouter/free', 'group': 'auto', 'label_ar': 'تلقائي — أفضل نموذج مجاني متاح',
             'label_en': 'Automatic — best free model available', 'note_ar': 'الآن: Sample Super',
             'note_en': 'Right now: Sample Super', 'serving': True, 'paid': False, 'vision': False},
            {'id': 'sample/super-120b:free', 'group': 'measured', 'label_ar': 'Sample Super', 'label_en': 'Sample Super',
             'note_ar': '1.9 ث للردّ · 6.8 ث للتنفيذ — مقيس هنا', 'note_en': '1.9s to answer · 6.8s to act — measured here',
             'serving': False, 'paid': False, 'vision': False},
            {'id': 'sample/flash-vl:free', 'group': 'measured', 'label_ar': 'Sample Flash VL', 'label_en': 'Sample Flash VL',
             'note_ar': '1.4 ث للردّ · 1.5 ث للتنفيذ — مقيس هنا', 'note_en': '1.4s to answer · 1.5s to act — measured here',
             'serving': False, 'paid': False, 'vision': True},
            {'id': 'sample/north-code:free', 'group': 'curated', 'label_ar': 'Sample Code', 'label_en': 'Sample Code',
             'note_ar': 'مخصص للبرمجة', 'note_en': 'Built for code', 'serving': False, 'paid': False, 'vision': False},
            {'id': 'sample/gemma-31b-it:free', 'group': 'all', 'label_ar': 'gemma-31b-it', 'label_en': 'gemma-31b-it',
             'note_ar': '', 'note_en': '', 'serving': False, 'paid': False, 'vision': False},
            {'id': 'sample/inkling:free', 'group': 'all', 'label_ar': 'inkling', 'label_en': 'inkling',
             'note_ar': 'المزوّد رفض الطلب — HTTP 403', 'note_en': 'The provider refused it — HTTP 403',
             'serving': False, 'paid': False, 'vision': False},
        ]
        for row in rows:
            row['full_id'] = row['id']
        self._rows = {row['id']: row for row in rows}
        groups = [{'key': key, 'rows': [r for r in rows if r['group'] == key]} for key in GROUP_ORDER
                  if any(r['group'] == key for r in rows)]
        self.update(
            loading=False, has_key=True, voice_model='gemini-live-sample', text_model='gemini-flash-lite-latest',
            text_model_source='mira', saving=False,
            gemini_test={'state': 'ok', 'model': 'gemini-flash-lite-latest', 'ms': 720, 'reason': ''},
            gemini_health={'state': 'ok', 'reason': '', 'source': 'test'},
            cloud={'state': 'ok', 'provider': 'openrouter-free', 'name_ar': 'OpenRouter (مجاني فقط)',
                   'name_en': 'OpenRouter (free only)', 'host': 'openrouter.ai', 'base': 'https://openrouter.ai/api/v1',
                   'has_key': True, 'model': 'openrouter/free', 'free': True, 'wire': 'openai'},
            models_state='ok', models_error_ar='', models_error_en='', groups=groups, all_count=2,
            moai_default='openrouter/free', cloud_model='sample/super-120b:free', pick_missing=False,
            measure={'state': 'ok', 'measuring': False, 'done': 0, 'total': 0, 'best': 'sample/flash-vl:free',
                     'best_label': 'Sample Flash VL', 'age_days': 11.2, 'best_available': True, 'error_ar': '', 'error_en': ''},
            cloud_test={'state': 'ok', 'model': 'sample/super-120b:free', 'reply': 'OK (sample)', 'ms': 1900,
                        'error_ar': '', 'error_en': ''},
            last={'route': 'gemini', 'model': 'gemini-flash-lite-latest', 'status': 'ok', 'ms': 1420, 'reason': '',
                  'refused': '', 'tools': 1, 'time': '14:05'},
            permissions={'state': 'ok', 'tier': 'system', 'web': False, 'exec': True, 'host_control': True,
                         'approvals': True, 'sandbox': 'off', 'workspace': 'rw', 'project': ''})


PAGE = BrainPage

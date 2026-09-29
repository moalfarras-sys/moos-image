"""Small, deterministic Arabic-first command dock. One explicit fixed action per request."""
import json
import re
from home_link import entities, control, control_all_lights, summary
from mira_memory import load
from moai_link import execute
from weather_link import current as current_weather

COLORS = {
    'بنفسجي': 'purple', 'موف': 'purple', 'purple': 'purple',
    'وردي': 'pink', 'زهري': 'pink', 'pink': 'pink',
    'ازرق': 'blue', 'blue': 'blue', 'اخضر': 'green', 'green': 'green',
    'اصفر': 'yellow', 'yellow': 'yellow', 'برتقالي': 'orange', 'orange': 'orange',
    'احمر': 'red', 'red': 'red',
}
PC_WORDS = ('كمبيوتر', 'الحاسوب', 'الجهاز', 'مووس', 'mo ai', 'moos', 'pc', 'computer')
ON_WORDS = ('شغل', 'شغلي', 'شغّل', 'شغّلي', 'افتح', 'افتحي', 'ولع', 'ولعي', 'تشغيل', 'turn on', 'switch on')
OFF_WORDS = ('طفي', 'طفّي', 'اطفي', 'اطفئي', 'سكر', 'سكّري', 'إطفاء', 'اقفل', 'turn off', 'switch off')


def normalize(text):
    text = text.lower().translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    return re.sub(r'[\u064b-\u065f]', '', text).replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ى', 'ي').strip()


def _target(message, listed, english=False):
    aliases = load().get('aliases', {})
    aliases.update({'المكتب': 'light.fernseher_buro', 'بيرو': 'light.fernseher_buro', 'برو': 'light.fernseher_buro'})
    candidates = []
    for item in listed:
        names = [normalize(item['name'].strip()), normalize(item['entity_id'].split('.', 1)[1].replace('_', ' '))]
        names += [normalize(a) for a, e in aliases.items() if e == item['entity_id']]
        if any(name and name in message for name in names):
            candidates.append(item)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # One longer explicit name may contain another short device name.
        ranked = sorted(candidates, key=lambda x: len(normalize(x['name'].strip())), reverse=True)
        if len(normalize(ranked[0]['name'].strip())) > len(normalize(ranked[1]['name'].strip())):
            return ranked[0]
        raise ValueError('Several devices match; name one exactly' if english else 'وجدت أكثر من جهاز بهذا الاسم؛ حدّد الجهاز بدقة')
    return None


def _system_summary(result, english=False):
    if result.get('status') != 'ok':
        return 'Could not check this computer' if english else 'تعذّر فحص الكمبيوتر'
    try:
        data = json.loads(result.get('output') or '{}')
        if not isinstance(data, dict):
            raise ValueError('invalid status')
        parts = []
        if isinstance(data.get('volume'), (int, float)):
            parts.append(('Volume ' if english else 'الصوت ') + str(data['volume']) + '%')
        if isinstance(data.get('brightness'), (int, float)):
            parts.append(('Display ' if english else 'سطوع الشاشة ') + str(data['brightness']) + '%')
        for key, label in (('wifi', 'Wi-Fi'), ('bluetooth', 'Bluetooth')):
            if isinstance(data.get(key), bool):
                parts.append(label + ((' connected' if data[key] else ' off') if english else (' متصل' if data[key] else ' متوقف')))
        if parts:
            return ('Computer checked · ' if english else 'فحصت الكمبيوتر · ') + ' · '.join(parts)
    except (TypeError, ValueError):
        pass
    return 'Computer checked' if english else 'فحصت الكمبيوتر'


def _installed_app(message, english=False):
    catalog = execute('list_installed_apps', {})
    if catalog.get('status') != 'ok':
        raise ValueError('Cannot read installed applications' if english else 'تعذّرت قراءة التطبيقات المثبتة')
    apps = {}
    for line in str(catalog.get('output') or '').splitlines():
        fields = line.split('\t')
        if len(fields) >= 2 and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+', fields[0]):
            apps[fields[0]] = fields[1]
    aliases = {
        'com.google.Chrome': ('كروم', 'chrome', 'جوجل كروم', 'غوغل كروم'),
        'com.visualstudio.code': ('فجوال ستوديو كود', 'فيجوال ستوديو كود', 'vs code', 'vscode'),
        'com.valvesoftware.Steam': ('ستيم', 'steam'),
        'com.usebottles.bottles': ('بوتلز', 'bottles'),
        'io.github.kolunmi.Bazaar': ('بازار', 'bazaar'),
    }
    matches = []
    for app_id, display in apps.items():
        names = (app_id, display, *aliases.get(app_id, ()))
        if any(normalize(name) in message for name in names if len(name) >= 4):
            matches.append(app_id)
    if len(matches) == 1:
        return matches[0], apps[matches[0]]
    if len(matches) > 1:
        raise ValueError('Name one installed application' if english else 'حدّد تطبيقاً واحداً فقط')
    raise ValueError('Application not installed or name not found' if english else 'لم أجد هذا التطبيق بين البرامج المثبتة')


def dispatch(text, city=None):
    if not isinstance(text, str) or not text.strip() or len(text) > 6000:
        raise ValueError('اكتب أمراً قصيراً وواضحاً')
    message = normalize(text)
    english = bool(re.search(r'[A-Za-z]', text)) and not bool(re.search(r'[\u0600-\u06ff]', text))
    if any(word in message for word in ('طقس','الجو','weather')):
        match = re.search(r'(?:\bفي\b|\bin\b)\s+([^؟?!]+)',message)
        if match:
            city=match.group(1).strip(' .,،')
        elif not city:
            raise ValueError('اذكر المدينة بعد «في» لمعرفة طقسها' if not english else 'Name a city after “in”')
        result=current_weather(city)
        description=(f"الطقس في {result['city']}: {result['condition_ar']}، "
                     f"{result['temperature_c']}°C · {result['source']}")
        return {'kind':'weather','result':result,'message':description}
    if ('حاله المنزل' in message or 'حالة المنزل' in text or
            'حاله الاضواء' in message or 'حالة الأضواء' in text or
            ('كم' in message and any(word in message for word in ('ضو','اضاء','مصباح','لمب')))):
        result=summary()
        description=(f"الأضواء المتاحة {result['lights_available']} من {result['lights_total']}، "
                     f"والمضاءة {result['lights_on']}؛ الأجهزة المتاحة {result['devices_available']}.")
        return {'kind':'home','result':result,'message':description}
    pc = any(word in message for word in PC_WORDS)
    light = any(word in message for word in ('ضو', 'اضاء', 'اضوا', 'لمب', 'مصباح', 'اناره', 'tuya', 'hue', 'فيليبس', 'philips', 'light', 'lamp'))
    home = light or any(word in message for word in ('تلفزيون', 'television', 'tv'))
    all_lights = light and bool(re.search(r'\b(?:كل|كلها|جميع|جميعها|الكل|all|every)\b', message))
    if all_lights:
        if any(word in message for word in OFF_WORDS):
            action = 'turn_off'
        elif any(word in message for word in ON_WORDS):
            action = 'turn_on'
        else:
            raise ValueError('قل تشغيل أو إطفاء كل الإضاءة' if not english else 'Say turn all lights on or off')
        result = control_all_lights(action)
        verb = ('شغّلت' if action == 'turn_on' else 'أطفأت') if not english else ('Turned on' if action == 'turn_on' else 'Turned off')
        count = str(result['confirmed']) + '/' + str(result['total'])
        message = (verb + ' ' + count + ' من الأضواء؛ البقية غير متاحة أو لم تؤكد التنفيذ') if result['status'] != 'ok' and not english else (verb + ' ' + count + ' lights; the rest are unavailable or unverified') if result['status'] != 'ok' else (verb + ' كل الأضواء المتاحة (' + count + ')') if not english else (verb + ' all lights (' + count + ')')
        return {'kind':'home','result':result,'message':message}
    if pc and not home:
        if any(word in message for word in ('حاله', 'حال', 'وضع', 'افحص', 'افحصي', 'status', 'check')):
            result = execute('get_system_status', {})
            return {'kind': 'computer', 'result': result, 'message': _system_summary(result, english)}
        if any(word in message for word in ('ذاكره', 'رام', 'memory')):
            result = execute('memory_status', {})
            return {'kind': 'computer', 'result': result, 'message': ('Computer memory checked' if english else 'قرأت ذاكرة الكمبيوتر') if result.get('status') == 'ok' else ('Could not read memory' if english else 'تعذّرت قراءة الذاكرة')}
        if any(word in message for word in ('الغاء كتم', 'ازل الكتم', 'شغل الصوت', 'unmute')):
            result = execute('set_mute', {'value': 'unmute'})
            return {'kind': 'computer', 'result': result, 'message': 'أعدت صوت الكمبيوتر' if result.get('status') == 'ok' else 'تعذّرت إعادة الصوت'}
        if any(word in message for word in ('اكتم', 'كتم', 'mute')):
            result = execute('set_mute', {'value': 'mute'})
            return {'kind': 'computer', 'result': result, 'message': 'كتمت صوت الكمبيوتر' if result.get('status') == 'ok' else 'تعذّر كتم الصوت'}
        if any(word in message for word in ('سطوع', 'brightness')):
            numbers = re.findall(r'\d+', message)
            if len(numbers) != 1 or not 5 <= int(numbers[0]) <= 100:
                raise ValueError('Set screen brightness between 5 and 100' if english else 'حدّد سطوع الشاشة من 5 إلى 100')
            result = execute('set_brightness', {'value': numbers[0]})
            return {'kind': 'computer', 'result': result, 'message': 'غيّرت سطوع الشاشة' if result.get('status') == 'ok' else 'لم يتغير سطوع الشاشة'}
        if any(word in message for word in ('النوافذ', 'windows', 'overview')) and any(word in message for word in ('اعرض', 'وريني', 'show', 'open')):
            result = execute('show_windows', {'view': 'overview'})
            return {'kind': 'computer', 'result': result, 'message': 'عرضت نوافذ الكمبيوتر' if result.get('status') == 'ok' else 'تعذّر عرض النوافذ'}
        if any(word in message for word in ('صوت', 'volume')):
            numbers = re.findall(r'\d+', message)
            if len(numbers) != 1 or not 0 <= int(numbers[0]) <= 100:
                raise ValueError('Set computer volume between 0 and 100' if english else 'حدّد مستوى صوت الكمبيوتر من 0 إلى 100')
            result = execute('set_volume', {'value': numbers[0]})
            return {'kind': 'computer', 'result': result, 'message': ('Computer volume changed' if english else 'أرسلت تغيير صوت الكمبيوتر') if result.get('status') == 'ok' else ('Computer volume did not change' if english else 'لم يتغير صوت الكمبيوتر')}
        if any(word in message for word in ('افتح', 'افتحي', 'شغل', 'شغلي', 'open', 'launch')):
            app_id, display = _installed_app(message, english)
            result = execute('open_app', {'app_id': app_id})
            return {'kind': 'computer', 'result': result, 'message': (('Opened ' if english else 'فتحت ')+display) if result.get('status') == 'ok' else ('Could not open '+display if english else 'تعذّر فتح '+display)}
    try:
        listed = entities()
    except RuntimeError:
        if home: raise
        return None
    item = _target(message, listed, english)
    if not item:
        if home:
            raise ValueError('Which device do you mean? Open Home to see names.' if english else 'أي ضوء أو جهاز تقصد؟ افتح «البيت» لرؤية الأسماء')
        return None
    if item['state'] in ('unavailable', 'unknown'):
        raise ValueError('That device is unavailable now' if english else 'هذا الجهاز غير متاح الآن')
    color = next((value for word, value in COLORS.items() if word in message), None)
    if color and any(word in message for word in ('لون', 'خلي', 'خلّي', 'يصير', 'حولي', 'غيري', 'غيّر', 'color', 'make', 'change', 'set')):
        action = 'color'; kwargs = {'color': color}
    elif any(word in message for word in OFF_WORDS):
        action = 'turn_off'; kwargs = {}
    elif any(word in message for word in ON_WORDS):
        action = 'turn_on'; kwargs = {}
    elif any(word in message for word in ('سطوع', 'إضاءة', 'اضاء', 'brightness')):
        numbers = re.findall(r'\d+', message)
        if len(numbers) != 1 or not 0 <= int(numbers[0]) <= 100:
            raise ValueError('Set brightness between 0 and 100' if english else 'حدّد سطوعاً من 0 إلى 100')
        action = 'brightness'; kwargs = {'value': int(numbers[0])}
    else:
        raise ValueError('Name a clear action: on, off, color or brightness' if english else 'عرفت الجهاز؛ اكتب تشغيل أو إطفاء أو لوناً أو سطوعاً واضحاً')
    result = control(item['entity_id'], action, **kwargs)
    message = (('Action verified' if english else 'تأكدت من التنفيذ') if result['status'] == 'ok' else ('Action sent but not verified' if english else 'أرسلت الأمر ولم أتأكد من تغيّر الجهاز')) + ' · ' + item['name'].strip()
    return {'kind': 'home', 'result': result, 'message': message}

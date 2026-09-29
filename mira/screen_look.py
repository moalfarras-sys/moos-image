"""Let Mira look at the screen — only when the owner has allowed it and asks.

The owner turns this on in Settings ("let Mira see the screen when I ask"). When a request needs it,
one full-screen capture is taken with Spectacle (KDE's own screenshot tool, allowed by KWin),
reduced to 1600 px, described by Gemini with the owner's question, and deleted at once. Nothing is
kept and nothing is captured in the background. A notification says each time that Mira looked.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

SETTING = 'screen_look'
MAX_WIDTH = 1600
VISION_MODELS = ('gemini-flash-lite-latest', 'gemini-2.5-flash')
GEMINI_CONFIG = Path.home() / '.config/mo-dot/gemini.json'


def allowed() -> bool:
    """The owner's switch in Mira's settings (off unless turned on)."""
    try:
        from PySide6.QtCore import QSettings
        return bool(QSettings('MoOS', 'Mira').value(SETTING, False, type=bool))
    except Exception:
        return False


def capture(path: Path, timeout: float = 12.0) -> Path:
    """One full-screen capture through Spectacle in background mode (no window, no sound)."""
    result = subprocess.run(['spectacle', '--background', '--nonotify', '--fullscreen', '--output', str(path)],
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    if result.returncode != 0 or not path.exists() or path.stat().st_size == 0:
        raise RuntimeError('تعذّر التقاط الشاشة')
    return path


def shrink(path: Path) -> bytes:
    """JPEG at most MAX_WIDTH wide: enough to read a window, less to send."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage
    image = QImage(str(path))
    if image.isNull():
        raise RuntimeError('صورة الشاشة غير صالحة')
    if image.width() > MAX_WIDTH:
        image = image.scaledToWidth(MAX_WIDTH, Qt.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, 'JPEG', 80)
    buffer.close()
    return bytes(data)


def describe(jpeg: bytes, question: str, lang: str = 'ar') -> str:
    from google import genai
    from google.genai import types
    config = json.loads(GEMINI_CONFIG.read_text())
    client = genai.Client(api_key=config['api_key'], http_options=types.HttpOptions(timeout=40000))
    prompt = ('صف ما على شاشة المالك بإيجاز ودقة بالعربية، ثم أجب عن سؤاله إن وُجد. لا تقرأ كلمات مرور أو أرقاماً سرية، '
              'واذكر فقط ما يظهر فعلاً. اكتب نصاً عادياً يُقرأ بصوت عالٍ: جمل قصيرة بلا رموز ولا قوائم ولا Markdown. سؤال المالك: '
              if lang != 'en' else
              "Briefly and accurately describe the owner's screen, then answer their question if any. Never read out passwords "
              'or secret numbers; mention only what is visible. Plain text meant to be spoken: short sentences, no symbols, '
              'lists or Markdown. The question: ') + (question or '')
    last = None
    for model in [config.get('vision_model')] + list(VISION_MODELS):
        if not model:
            continue
        try:
            response = client.models.generate_content(
                model=model, contents=[types.Part.from_bytes(data=jpeg, mime_type='image/jpeg'), prompt])
            text = (response.text or '').strip()
            if text:
                return text[:1500]
        except Exception as exc:  # next model; the reason is reported by class only
            last = exc
    raise RuntimeError('تعذّر وصف الشاشة: ' + (type(last).__name__ if last else 'empty'))


def notify() -> None:
    try:
        subprocess.Popen(['notify-send', '-a', 'Mira', '--hint=string:desktop-entry:org.moos.moai', 'ميرا نظرت إلى الشاشة', 'التُقطت صورة واحدة للشاشة بطلبك ثم حُذفت.'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def look(question: str = '', lang: str = 'ar') -> dict:
    """The whole round trip; the capture file never outlives this call."""
    if not allowed():
        return {'status': 'unsupported', 'error': 'not_allowed',
                'summary': 'رؤية الشاشة غير مفعّلة · فعّلها من إعدادات ميرا إن أردت'}
    folder = Path(tempfile.mkdtemp(prefix='mira-look-', dir=os.environ.get('XDG_RUNTIME_DIR') or None))
    path = folder / 'screen.png'
    try:
        capture(path)
        jpeg = shrink(path)
    finally:
        path.unlink(missing_ok=True)
        folder.rmdir()
    notify()
    text = describe(jpeg, question, lang)
    return {'status': 'ok', 'description': text, 'summary': 'نظرت إلى الشاشة بطلبك'}

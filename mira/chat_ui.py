"""The conversation's own interface: chat history (threads), search, new chat, and Mira's formatted replies.

`ChatHistory` is one QObject the controller exposes to QML as `mira.chatHistory`. It reads and changes
only Mira's local conversation files (`mira_memory`); it never reaches the machine, the Echo or a model.
Opening or starting a chat changes what the model is fed next (only the open chat), so it asks the
controller to reload the visible conversation (`host.reload_chat()`), and it refuses while Mira is
mid-turn so a reply can never land in a chat the owner did not ask it in (an approved job that is
still running writes its result into the chat it was approved in: the controller keeps that chat).

`render_markdown` turns one of Mira's replies into safe rich text for a TextEdit: Markdown without
raw HTML, every paragraph given its own direction (Arabic right-to-left, English, code and URLs
left-to-right), links only where the window can open them, and remote images never fetched.
`reply_pieces` cuts a reply at its fenced code blocks so each block is its own rounded card with
its own Copy (the delegate draws them; the words between are rendered by `render_markdown`).
"""
import os
import re
import unicodedata
from datetime import datetime, timedelta
from functools import lru_cache
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

from PySide6.QtCore import Property, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (QColor, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, QTextFormat,
                           QTextLength, QTextTable, QTextTableFormat)

from models import DictListModel
from pages.base import Page

TEST_MODE = os.environ.get('MIRA_TEST_MODE') == '1'

STRINGS = {
    'ch_title': ('المحادثات', 'Chats'),
    'ch_history': ('سجل المحادثات · Ctrl+H', 'Chat history · Ctrl+H'),
    'ch_new': ('محادثة جديدة', 'New chat'),
    'ch_new_tip': ('محادثة جديدة · Ctrl+N — من السؤال التالي لا تُرسَل المحادثة السابقة للنموذج',
                   'New chat · Ctrl+N — from the next question on, the earlier chat is not sent to the model'),
    'ch_started': ('بدأت محادثة جديدة', 'Started a new chat'),
    'ch_busy': ('انتظر حتى تنهي ميرا ردّها', 'Wait until Mira finishes her reply'),
    'ch_search': ('ابحث في المحادثات', 'Search chats'),
    'ch_search_clear': ('مسح البحث', 'Clear search'),
    'ch_all': ('الكل', 'All'),
    'ch_archived': ('المؤرشفة', 'Archived'),
    'ch_pinned': ('المثبّتة', 'Pinned'),
    'ch_today': ('اليوم', 'Today'),
    'ch_yesterday': ('أمس', 'Yesterday'),
    'ch_week': ('آخر 7 أيام', 'Previous 7 days'),
    'ch_older': ('أقدم', 'Older'),
    'ch_results': ('نتائج البحث', 'Search results'),
    'ch_untitled': ('محادثة جديدة', 'New chat'),
    'ch_unnamed': ('محادثة بلا عنوان', 'Untitled chat'),
    'ch_open_now': ('مفتوحة الآن', 'Open now'),
    'ch_rename': ('إعادة تسمية', 'Rename'),
    'ch_rename_hint': ('اسم المحادثة · Enter للحفظ', 'Chat name · Enter to save'),
    'ch_pin': ('تثبيت في الأعلى', 'Pin to top'),
    'ch_unpin': ('إلغاء التثبيت', 'Unpin'),
    'ch_archive': ('أرشفة', 'Archive'),
    'ch_unarchive': ('إرجاع من الأرشيف', 'Unarchive'),
    'ch_archived_done': ('نُقلت المحادثة إلى الأرشيف', 'Chat archived'),
    'ch_empty': ('لا محادثات بعد', 'No chats yet'),
    'ch_empty_body': ('كل محادثة تبدؤها مع ميرا تُحفظ هنا على جهازك فقط.',
                      'Every chat you start with Mira is kept here, on this computer only.'),
    'ch_empty_archived': ('لا محادثات مؤرشفة', 'No archived chats'),
    'ch_no_results': ('لا نتائج لهذا البحث', 'Nothing matches this search'),
    'ch_loading': ('أقرأ المحادثات…', 'Reading chats…'),
    'ch_failed': ('تعذّر حفظ التغيير على المحادثة', 'Could not save the change to the chat'),
    'ch_read_failed': ('تعذّرت قراءة سجل المحادثات', 'Could not read the chat history'),
    'ch_missing': ('هذه المحادثة لم تعد موجودة', 'This chat no longer exists'),
    'ch_name_invalid': ('اسم المحادثة حتى 80 حرفاً', 'A chat name is up to 80 characters'),
    'ch_copy': ('نسخ النص', 'Copy text'),
    'ch_copy_code': ('نسخ', 'Copy'),
    'ch_copy_code_tip': ('نسخ هذا الكود فقط', 'Copy only this code'),
    'ch_code': ('كود', 'Code'),
    'ch_regenerate': ('إجابة جديدة', 'Regenerate'),
    'ch_regenerate_tip': ('اطلب من ميرا إجابة جديدة على السؤال نفسه', 'Ask Mira for a fresh answer to the same question'),
    'ch_retry': ('حاول مجدداً', 'Try again'),
    'ch_retry_tip': ('اسأل ميرا السؤال نفسه مرة أخرى', 'Ask Mira the same question again'),
    'ch_opens': ('يفتح', 'Opens'),
    'ch_send_tip': ('إرسال · Enter  —  سطر جديد · Shift+Enter', 'Send · Enter  —  new line · Shift+Enter'),
    'ch_too_long': ('الرسالة أطول من 6000 حرف', 'The message is over 6000 characters'),
    'ch_too_long_file': ('الملف المرفق يجعل الرسالة أطول من 6000 حرف', 'The attached file makes the message over 6000 characters'),
    'ch_close': ('إغلاق السجل', 'Close history'),
    'ch_latest': ('إلى آخر الرسائل', 'Jump to the latest'),
}

# Names QML reaches on the controller with a bracket lookup (mira["name"]) until the controller
# exposes them; test_chat_ui proves every such lookup is listed here and, once present, is a property.
CONTROLLER_HOOKS = ('chatHistory',)

# What the window may open: https to any host; plain http only to this computer or the home network.
# The address is parsed, never prefix-tested (http://192.168.evil.com and http://127.0.0.1@evil.example
# start like a home address and are not one). Any other link is shown as plain text.
LOCAL_HOSTS = ('127.0.0.1', 'localhost')
HOME_NETWORK = ip_network('192.168.0.0/16')

_WEEKDAYS = (('الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد'),
             ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'))
_MONTHS = (('كانون الثاني', 'شباط', 'آذار', 'نيسان', 'أيار', 'حزيران', 'تموز', 'آب', 'أيلول',
            'تشرين الأول', 'تشرين الثاني', 'كانون الأول'),
           ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
            'October', 'November', 'December'))


# ── Mira's replies as safe rich text ──────────────────────────────────
LINK = QColor('#35D8F4')
INK = QColor('#F4F1FF')
CODE_INK = QColor('#DCE6FF')
CODE_BLOCK = QColor('#0B0F26')
CODE_INLINE = QColor('#262B55')
CODE_FONT = 'JetBrains Mono'
# Arabic in code (a comment) falls back to the window's Arabic face, never to a monospace one that
# gives every Arabic letter a whole cell.
CODE_FAMILIES = [CODE_FONT, 'IBM Plex Sans Arabic', 'monospace']
CODE_LINE = QTextFormat.UserProperty + 1           # marks the lines of a code card


def openable(url):
    """True when the window may open `url`: https to any host, http only to this computer or 192.168.x.x.

    Never an address with a user name or password in it (`http://127.0.0.1@evil.example` goes to
    evil.example), and never one with spaces, control characters or backslashes.
    """
    url = str(url or '')
    if (not url.startswith(('https://', 'http://')) or len(url) > 2048 or '\\' in url
            or any(ch.isspace() or unicodedata.category(ch) in ('Cc', 'Cf') for ch in url)):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname or ''
        parts.port                                     # a malformed port raises
    except ValueError:
        return False
    if not host or '@' in parts.netloc:
        return False
    if parts.scheme == 'https':
        return True
    if host in LOCAL_HOSTS:
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return address.version == 4 and address in HOME_NETWORK


def link_label(url):
    """Where a link really goes, for its tooltip: host (as ASCII, so a look-alike name shows) and path."""
    if not openable(url):
        return ''
    parts = urlsplit(str(url))
    host = parts.hostname or ''
    try:
        host = host.encode('idna').decode('ascii')
    except UnicodeError:
        pass
    port = f':{parts.port}' if parts.port else ''
    shown = ('' if parts.scheme == 'https' else 'http://') + host + port + parts.path.rstrip('/')
    return shown if len(shown) <= 64 else shown[:63] + '…'


def _strong(text):
    """(first strong direction, Arabic letters, Latin letters) of a paragraph."""
    first, arabic, latin = None, 0, 0
    for ch in text:
        kind = unicodedata.bidirectional(ch)
        if kind in ('R', 'AL'):
            arabic += 1
            first = first or 'rtl'
        elif kind == 'L':
            latin += 1
            first = first or 'ltr'
    return first, arabic, latin


def paragraph_rtl(text):
    """Right-to-left when the paragraph starts Arabic, or when Arabic is at least 40% of its letters."""
    first, arabic, latin = _strong(text)
    return first == 'rtl' or (first is not None and arabic >= 0.4 * (arabic + latin))


def _is_code(block):
    fmt = block.blockFormat()
    if fmt.hasProperty(QTextFormat.BlockCodeFence) or fmt.nonBreakableLines():
        return True
    it, fixed, any_text = block.begin(), True, False
    while not it.atEnd():
        fragment = it.fragment()
        if fragment.text().strip():
            any_text = True
            fixed = fixed and fragment.charFormat().fontFixedPitch()
        it += 1
    return any_text and fixed and not block.textList()


def _cell_selection(table, row, column):
    cell = table.cellAt(row, column)
    cursor = cell.firstCursorPosition()
    cursor.setPosition(cell.lastCursorPosition().position(), QTextCursor.KeepAnchor)
    return cursor


def _reverse_columns(table):
    """Put a table's first column on the right. Qt Quick lays every table out left to right whatever
    its direction, so a right-to-left table is drawn by reversing its columns' contents."""
    columns = table.columns()
    for row in range(table.rows()):
        pieces = [_cell_selection(table, row, column).selection() for column in range(columns)]
        for column in range(columns):
            cursor = _cell_selection(table, row, column)
            cursor.removeSelectedText()
            cursor.insertFragment(pieces[columns - 1 - column])


def _fragments(block):
    it = block.begin()
    while not it.atEnd():
        yield it.fragment()
        it += 1


@lru_cache(maxsize=512)
def render_markdown(text):
    """One reply as HTML for a TextEdit (Markdown, no raw HTML, a direction on every paragraph)."""
    doc = QTextDocument()
    doc.setMarkdown(str(text or ''), QTextDocument.MarkdownFeatures(
        QTextDocument.MarkdownDialectGitHub | QTextDocument.MarkdownNoHTML))
    cursor = QTextCursor(doc)

    # Images are never fetched: each becomes its address as text (a link when it may be opened).
    images = []
    block = doc.begin()
    while block.isValid():
        for fragment in _fragments(block):
            fmt = fragment.charFormat()
            if fmt.isImageFormat():
                images.append((fragment.position(), fragment.length(), fmt.toImageFormat().name()))
        block = block.next()
    for position, length, name in reversed(images):
        cursor.setPosition(position)
        cursor.setPosition(position + length, QTextCursor.KeepAnchor)
        plain = QTextCharFormat()
        if openable(name):
            plain.setAnchor(True)
            plain.setAnchorHref(name)
        cursor.insertText(name or '[image]', plain)

    # A code block becomes one padded card (a one-cell table): its lines stay left-to-right and wrap.
    runs, block = [], doc.begin()
    while block.isValid():
        if _is_code(block) and not block.textList():
            if runs and runs[-1][1] == block.position() - 1:
                runs[-1][1] = block.position() + block.length() - 1
                runs[-1][2].append(block.text())
            else:
                runs.append([block.position(), block.position() + block.length() - 1, [block.text()]])
        block = block.next()
    for start, end, lines in reversed(runs):
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        card = QTextTableFormat()
        card.setBorder(0)
        card.setCellPadding(9)
        card.setCellSpacing(0)
        card.setBackground(CODE_BLOCK)
        card.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        card.setTopMargin(4)
        card.setBottomMargin(4)
        table = cursor.insertTable(1, 1, card)
        inside = table.cellAt(0, 0).firstCursorPosition()
        line = QTextBlockFormat()
        line.setLayoutDirection(Qt.LeftToRight)
        line.setAlignment(Qt.AlignLeft | Qt.AlignAbsolute)
        line.setProperty(CODE_LINE, True)
        mono = QTextCharFormat()
        mono.setFontFamilies(CODE_FAMILIES)
        mono.setForeground(CODE_INK)
        mono.setProperty(QTextFormat.FontPixelSize, 13)
        inside.setBlockFormat(line)
        for i, text in enumerate(lines):
            if i:
                inside.insertBlock(line, mono)
            inside.insertText(text, mono)
        before = doc.findBlock(table.firstPosition() - 1)     # the emptied paragraph the card was put after
        if before.isValid() and not before.text() and before.previous().isValid():
            joiner = QTextCursor(doc)
            joiner.setPosition(before.position())
            joiner.deletePreviousChar()                         # merge it away: no blank line above the card

    # A Markdown table whose header reads Arabic runs right to left: first column on the right, and
    # every cell aligned to the right (the reading side). Code cards (borderless) are not tables here.
    rtl_spans = []
    for frame in doc.rootFrame().childFrames():
        if isinstance(frame, QTextTable) and frame.format().border() > 0:
            header = ' '.join(frame.cellAt(0, column).firstCursorPosition().block().text()
                              for column in range(frame.columns()))
            if paragraph_rtl(header):
                _reverse_columns(frame)
                rtl_spans.append((frame.firstPosition(), frame.lastPosition()))

    # Lists read in one direction: the direction of all their items together.
    list_rtl = {}
    block = doc.begin()
    while block.isValid():
        lst = block.textList()
        if lst is not None and lst.item(0).position() not in list_rtl:
            list_rtl[lst.item(0).position()] = paragraph_rtl(' '.join(lst.item(i).text() for i in range(lst.count())))
        block = block.next()

    marks = []                      # LTR blocks that would read as RTL on their own (code opening in Arabic)
    block = doc.begin()
    while block.isValid():
        if block.blockFormat().boolProperty(CODE_LINE):     # a code card's line: already set
            if _strong(block.text())[0] == 'rtl':
                marks.append(block.position())
            block = block.next()
            continue
        code = _is_code(block)
        lst = block.textList()
        rtl = False if code else list_rtl.get(lst.item(0).position()) if lst is not None else paragraph_rtl(block.text())
        if not rtl and _strong(block.text())[0] == 'rtl':
            marks.append(block.position())
        fmt = block.blockFormat()
        in_rtl_table = any(first <= block.position() <= last for first, last in rtl_spans)
        fmt.setLayoutDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
        fmt.setAlignment((Qt.AlignRight if rtl or in_rtl_table else Qt.AlignLeft) | Qt.AlignAbsolute)
        if rtl and fmt.leftMargin() > fmt.rightMargin():       # a quote's indent belongs on the leading side
            left, right = fmt.leftMargin(), fmt.rightMargin()
            fmt.setLeftMargin(right)
            fmt.setRightMargin(left)
        if code:
            fmt.setNonBreakableLines(False)                    # long lines wrap inside the bubble
            fmt.setBackground(CODE_BLOCK)
            fmt.setLeftMargin(0)
            fmt.setRightMargin(0)
        cursor.setPosition(block.position())
        cursor.setBlockFormat(fmt)
        level = fmt.headingLevel()
        for fragment in list(_fragments(block)):
            char = fragment.charFormat()
            change = QTextCharFormat()
            changed = False
            if char.isAnchor():
                href = char.anchorHref()
                if openable(href):
                    change.setForeground(LINK)
                    change.setFontUnderline(True)
                else:                                          # the window could not open it: plain text
                    change.setAnchor(False)
                    change.setAnchorHref('')
                    change.setForeground(INK)
                    change.setFontUnderline(False)
                changed = True
            if code or char.fontFixedPitch():
                change.setFontFamilies(CODE_FAMILIES)
                change.setForeground(CODE_INK)
                if not code:
                    change.setBackground(CODE_INLINE)
                changed = True
            if level:
                change.setProperty(QTextFormat.FontSizeAdjustment, 1 if level <= 2 else 0)
                changed = True
            if changed:
                cursor.setPosition(fragment.position())
                cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(change)
        block = block.next()

    # Tables: hairline borders, room in the cells; an Arabic one sits on the right of the bubble.
    for frame in doc.rootFrame().childFrames():
        if isinstance(frame, QTextTable) and frame.format().border() > 0:
            fmt = frame.format()
            fmt.setBorder(1)
            fmt.setBorderBrush(QColor('#3A3F6B'))
            fmt.setBorderCollapse(True)
            fmt.setCellPadding(6)
            rtl = any(first == frame.firstPosition() for first, last in rtl_spans)
            fmt.setAlignment(Qt.AlignRight if rtl else Qt.AlignLeft)
            frame.setFormat(fmt)

    first, last = doc.begin(), doc.lastBlock()   # the bubble gives the padding, not the first/last paragraph
    for block, edge in ((first, 'top'), (last, 'bottom')):
        if block.isValid() and not block.textList():
            fmt = block.blockFormat()
            (fmt.setTopMargin if edge == 'top' else fmt.setBottomMargin)(0)
            cursor.setPosition(block.position())
            cursor.setBlockFormat(fmt)

    # The HTML writer names only right-to-left paragraphs; a left-to-right one whose first letter is
    # Arabic gets a left-to-right mark so it is not read back as right-to-left.
    for position in reversed(marks):
        cursor.setPosition(position)
        cursor.insertText('\u200e')
    return re.sub(r'<body style="[^"]*">', '<body>', doc.toHtml(), count=1)


def _local_line(row):
    """A Mira line the model never wrote: a fired reminder, or the window's own answer to a waiting card.

    The controller marks them with a `tool`; lines stored before it did are recognised by their words.
    """
    import i18n
    text = str(row.get('text') or '').strip()
    return bool(row.get('tool')) or text.startswith('⏰') or text in {
        line for key in ('act_cancelled_say', 'act_choose') for line in i18n.STRINGS.get(key, ())}


def _tail(rows):
    """(the owner's last question, the rows after it) — or ('', []) when that turn may not be asked again.

    After the question only Mira's plain replies (a fresh answer may be asked for) or only errors (the
    question may be tried again) may follow. An action, a result, a reminder, a card's answer, or
    words and errors mixed: the turn is left as it is, so a turn that acted is never run twice.
    """
    rows = list(rows)
    i = len(rows) - 1
    while i >= 0 and ((rows[i].get('role') == 'mira' and not _local_line(rows[i])) or rows[i].get('role') == 'error'):
        i -= 1
    tail = rows[i + 1:]
    if not tail or i < 0 or rows[i].get('role') != 'user' or len({row.get('role') for row in tail}) > 1:
        return '', []
    return str(rows[i].get('text') or ''), tail


FENCE = re.compile(r'(`{3,}|~{3,})[ \t]*([^\s`~]*)[^`]*')


def _fence_closes(line, fence):
    stripped = line.strip()
    return len(stripped) >= len(fence) and set(stripped) == {fence[0]}


@lru_cache(maxsize=512)
def split_reply(text):
    """A reply as ('text', markdown, '') and ('code', code, language) pieces, in order.

    Only a fence at the very start of a line is cut out: one indented under a list step stays in
    its text (cutting it would restart the list's numbering) and is drawn by render_markdown.
    An unclosed fence runs to the end, as Markdown reads it.
    """
    pieces, words, code, fence, lang = [], [], None, '', ''
    for line in str(text or '').split('\n'):
        if code is None:
            match = FENCE.fullmatch(line.rstrip())
            if match and not line.startswith((' ', '\t')):
                if '\n'.join(words).strip():
                    pieces.append(('text', '\n'.join(words).strip('\n'), ''))
                words, code, fence, lang = [], [], match.group(1), match.group(2)[:24]
            else:
                words.append(line)
        elif _fence_closes(line, fence):
            pieces.append(('code', '\n'.join(code).rstrip(), lang))
            code = None
        else:
            code.append(line)
    if code is not None:
        pieces.append(('code', '\n'.join(code).rstrip(), lang))
    elif '\n'.join(words).strip():
        pieces.append(('text', '\n'.join(words).strip('\n'), ''))
    return tuple(piece for piece in pieces if piece[1].strip())


@lru_cache(maxsize=256)
def code_html(code):
    """One code block as rich text: every line left to right (even one that opens in Arabic), in the
    code face with an Arabic fallback, never wrapped in the Markdown machinery."""
    doc = QTextDocument()
    cursor = QTextCursor(doc)
    line = QTextBlockFormat()
    line.setLayoutDirection(Qt.LeftToRight)
    line.setAlignment(Qt.AlignLeft | Qt.AlignAbsolute)
    mono = QTextCharFormat()
    mono.setFontFamilies(CODE_FAMILIES)
    mono.setForeground(CODE_INK)
    mono.setProperty(QTextFormat.FontPixelSize, 13)
    cursor.setBlockFormat(line)
    for i, text in enumerate(str(code or '').split('\n')):
        if i:
            cursor.insertBlock(line, mono)
        cursor.insertText(('\u200e' if _strong(text)[0] == 'rtl' else '') + text, mono)
    return re.sub(r'<body style="[^"]*">', '<body>', doc.toHtml(), count=1)


def reply_pieces(text):
    """What the delegate draws for one reply: [{'kind': 'text', 'html'} | {'kind': 'code', 'html', 'code', 'lang'}]."""
    out = []
    for kind, body, lang in split_reply(text):
        if kind == 'code':
            out.append({'kind': 'code', 'html': code_html(body), 'code': body, 'lang': lang})
        else:
            out.append({'kind': 'text', 'html': render_markdown(body), 'code': '', 'lang': ''})
    return out or [{'kind': 'text', 'html': render_markdown(text), 'code': '', 'lang': ''}]


def regenerable(rows):
    """The question whose answer may be asked for again (a plain reply, or only an error), or ''."""
    return _tail(rows)[0]


def retry_after_error(rows):
    """True when the turn to ask again ended only in an error (the button says «Try again»)."""
    question, tail = _tail(rows)
    return bool(question) and tail[-1].get('role') == 'error'


# ── dates as the owner reads them ─────────────────────────────────────
def _local(stamp):
    try:
        value = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    return value.astimezone() if value.tzinfo else value


def day_label(day, lang, today=None):
    """'Today', 'Yesterday', or «الاثنين 28 أيلول» for a local ISO date (YYYY-MM-DD)."""
    try:
        date = datetime.strptime(str(day)[:10], '%Y-%m-%d').date()
    except ValueError:
        return ''
    i = 1 if lang == 'en' else 0
    today = today or datetime.now().date()
    if date == today:
        return STRINGS['ch_today'][i]
    if date == today - timedelta(days=1):
        return STRINGS['ch_yesterday'][i]
    label = f'{_WEEKDAYS[i][date.weekday()]} {date.day} {_MONTHS[i][date.month - 1]}'
    return label if date.year == today.year else f'{label} {date.year}'


def when_label(stamp, lang, now=None):
    """A chat's last activity: 14:05 today, Yesterday, a weekday this week, else a date."""
    moment = _local(stamp)
    if moment is None:
        return ''
    i = 1 if lang == 'en' else 0
    now = now or datetime.now().astimezone()
    days = (now.date() - moment.date()).days
    if days <= 0:
        return moment.strftime('%H:%M')
    if days == 1:
        return STRINGS['ch_yesterday'][i]
    if days < 7:
        return _WEEKDAYS[i][moment.weekday()]
    label = f'{moment.day} {_MONTHS[i][moment.month - 1]}'
    return label if moment.year == now.year else f'{label} {moment.year}'


def group_key(row, now=None):
    if row.get('pinned'):
        return 'ch_pinned'
    moment = _local(row.get('updated'))
    if moment is None:
        return 'ch_older'
    now = now or datetime.now().astimezone()
    days = (now.date() - moment.date()).days
    return 'ch_today' if days <= 0 else 'ch_yesterday' if days == 1 else 'ch_week' if days < 7 else 'ch_older'


# ── the history object QML talks to ───────────────────────────────────
class ChatHistory(Page):
    """Mira's chats for the conversation panel: list, search, open, new, rename, pin, archive."""
    ROLES = ['tid', 'title', 'when', 'preview', 'pinned', 'archived', 'current', 'header', 'count', 'named']

    def __init__(self, host, parent=None):
        super().__init__(host, parent)
        self.threads = DictListModel(self.ROLES, key='tid')
        self._seq = 0
        chat = getattr(host, 'chat', None)
        if chat is not None:
            for signal in (chat.rowsInserted, chat.rowsRemoved, chat.modelReset, chat.dataChanged):
                signal.connect(self._chat_changed)
        busy = getattr(host, 'busyChanged', None)
        if busy is not None:
            busy.connect(self._chat_changed)
        lang = getattr(host, 'langChanged', None)
        if lang is not None:
            lang.connect(self._relabel)
        self._chat_changed()
        if TEST_MODE:
            self.review()
        else:
            QTimer.singleShot(0, self, self.refresh)     # the open chat's name for the panel header

    def initial(self):
        return {'threads': [], 'count': 0, 'current': '', 'currentTitle': '', 'query': '', 'archived': False,
                'loading': False, 'error': '', 'canRegenerate': False, 'retry': False}

    threadModel = Property(QObject, lambda self: self.threads, constant=True)

    # ── reading ──────────────────────────────────────────────────────
    @Slot()
    def refresh(self):
        """Read the chat list again (search results while a search is typed)."""
        if TEST_MODE:
            return
        import mira_memory
        self._seq += 1
        query, archived = self._state['query'], self._state['archived']
        self.update(loading=True)
        if query:
            self.run(f'threads:{self._seq}', mira_memory.search_threads, query)
        else:
            self.run(f'threads:{self._seq}', self._read_list, archived)

    @staticmethod
    def _read_list(archived):
        import mira_memory
        rows = mira_memory.list_threads(include_archived=archived)
        return [row for row in rows if row['archived']] if archived else rows

    def on_threads(self, tag, result):
        if tag != f'threads:{self._seq}':
            return                                   # an older read; a newer one is on its way
        if isinstance(result, dict):                 # the worker's error shape
            self.update(loading=False, error=self.text('ch_read_failed'))
            return
        self._show(result)

    def _show(self, rows):
        searching = bool(self._state['query'])
        now = datetime.now().astimezone()
        shown, previous = [], None
        current, current_title = '', ''
        for row in rows:
            key = 'ch_results' if searching else 'ch_archived' if self._state['archived'] else group_key(row, now)
            title = row.get('title') or self.text('ch_untitled' if not row.get('count') else 'ch_unnamed')
            if row.get('current'):
                current, current_title = row['id'], title if row.get('count') or row.get('named') else ''
            when = when_label(row.get('updated'), self.lang, now)
            if key == 'ch_yesterday':                 # the group already says the day: show the time
                moment = _local(row.get('updated'))
                when = moment.strftime('%H:%M') if moment else when
            shown.append({'tid': row['id'], 'title': title, 'when': when,
                          'preview': row.get('snippet') or row.get('preview') or '', 'pinned': bool(row.get('pinned')),
                          'archived': bool(row.get('archived')), 'current': bool(row.get('current')),
                          'header': self.text(key) if key != previous else '', 'count': int(row.get('count') or 0),
                          'named': bool(row.get('named'))})
            previous = key
        self.threads.set_rows(shown)
        fields = {'threads': shown, 'count': len(shown), 'loading': False, 'error': ''}
        if current or not (searching or self._state['archived']):   # a filtered list may not hold the open chat
            fields.update(current=current, currentTitle=current_title)
        self.update(**fields)

    @Slot(str)
    def search(self, query):
        query = ' '.join(str(query or '').split())[:120]
        if query == self._state['query']:
            return
        self.update(query=query)
        self.refresh()

    @Slot(bool)
    def showArchived(self, archived):
        if bool(archived) != self._state['archived']:
            self.update(archived=bool(archived), query='')
            self.refresh()

    # ── changing ─────────────────────────────────────────────────────
    def _mid_turn(self):
        if getattr(self.host, 'busy', False):
            self.host.toast.emit('pending', self.text('ch_busy'))
            return True
        return False

    def _reload(self):
        reload_chat = getattr(self.host, 'reload_chat', None)
        if reload_chat is not None:
            reload_chat()

    @Slot()
    def newChat(self):
        """Start a fresh chat: the view empties and the model stops receiving the earlier turns."""
        if self._mid_turn():
            return
        import mira_memory
        try:
            tid = mira_memory.new_thread()
        except OSError:
            self.host.toast.emit('error', self.text('ch_failed'))
            return
        self.update(current=tid, currentTitle='')
        self._reload()
        self.host.toast.emit('info', self.text('ch_started'))
        self.refresh()

    @Slot(str)
    def openThread(self, tid):
        if tid == self._state['current'] and tid:
            return
        if self._mid_turn():
            return
        import mira_memory
        try:
            mira_memory.open_thread(tid)
        except mira_memory.ThreadNotFound:
            self.host.toast.emit('error', self.text('ch_missing'))
            self.refresh()
            return
        except OSError:
            self.host.toast.emit('error', self.text('ch_failed'))
            return
        row = next((r for r in self.threads.rows() if r['tid'] == tid), {})
        self.update(current=tid, currentTitle=row.get('title', '') if row.get('count') or row.get('named') else '')
        self._reload()
        self.refresh()

    @Slot(str, str)
    def renameThread(self, tid, title):
        import mira_memory
        self._change(mira_memory.rename_thread, tid, title)

    @Slot(str, bool)
    def pinThread(self, tid, pinned):
        import mira_memory
        self._change(mira_memory.pin_thread, tid, bool(pinned))

    @Slot(str, bool)
    def archiveThread(self, tid, archived):
        """Archive (or bring back) a chat. Archiving the open chat starts a new one in its place."""
        import mira_memory
        if archived and tid == self._state['current'] and self._mid_turn():
            return
        if not self._change(mira_memory.archive_thread, tid, bool(archived)):
            return
        if archived:
            self.host.toast.emit('ok', self.text('ch_archived_done'))
            if tid == self._state['current'] or tid == mira_memory.current_thread():
                try:
                    mira_memory.new_thread()
                except OSError:
                    pass
                self._reload()
                self.refresh()

    def _change(self, fn, tid, value):
        import mira_memory
        try:
            fn(tid, value)
        except mira_memory.ThreadNotFound:
            self.host.toast.emit('error', self.text('ch_missing'))
            self.refresh()
            return False
        except ValueError:
            self.host.toast.emit('error', self.text('ch_name_invalid'))
            return False
        except OSError:
            self.host.toast.emit('error', self.text('ch_failed'))
            return False
        self.refresh()
        return True

    @Slot()
    def regenerate(self):
        """Ask the last question again for a fresh answer (the controller runs it; see its regenerate)."""
        if not self._state['canRegenerate'] or self._mid_turn():
            return
        regenerate = getattr(self.host, 'regenerate', None)
        if regenerate is not None:
            regenerate()

    # ── for the delegates ────────────────────────────────────────────
    @Slot(str, result=str)
    def render(self, text):
        return render_markdown(text)

    @Slot(str, result='QVariantList')
    def pieces(self, text):
        return reply_pieces(text)

    @Slot(str, str, result=str)
    def dayLabel(self, day, lang):
        """A day separator's words; `lang` is passed so the label follows a language switch."""
        return day_label(day, lang or self.lang)

    @Slot(str, result=bool)
    def openable(self, url):
        return openable(url)

    @Slot(str, result=str)
    def linkLabel(self, url):
        return link_label(url)

    def _chat_changed(self, *args):
        chat = getattr(self.host, 'chat', None)
        rows = chat.rows() if chat is not None else []
        fields = {}
        can = bool(regenerable(rows)) and not getattr(self.host, 'busy', False)
        if can != self._state['canRegenerate']:
            fields['canRegenerate'] = can
        retry = can and retry_after_error(rows)
        if retry != self._state['retry']:
            fields['retry'] = retry
        if not self._state['currentTitle']:        # a new chat is named by its first question
            first = next((row.get('text', '') for row in rows if row.get('role') == 'user'), '')
            if first:
                import mira_memory
                fields['currentTitle'] = mira_memory.auto_title(first)
        if fields:
            self.update(**fields)

    def _relabel(self):
        if TEST_MODE:
            self.review()
        else:
            self.refresh()

    # ── review renders (MIRA_TEST_MODE only) ─────────────────────────
    def review(self):
        now = datetime.now().astimezone()
        ar = self.lang != 'en'
        sample = [
            ('r1', 'خطة مشروع MoOS · المرحلة القادمة' if ar else 'MoOS project plan · next milestone', now - timedelta(days=3),
             'أول خطوة: دمج أدوات Mo AI في ميرا…' if ar else 'First step: bring the Mo AI tools into Mira…', True, 18),
            ('r2', 'كم ضوء مضاء الآن؟' if ar else 'How many lights are on?', now - timedelta(minutes=4),
             'تمام، صار ضو المكتب بنفسجي ✨' if ar else 'Done, the office light is purple now ✨', False, 6),
            ('r3', 'ثبّتي لي VLC' if ar else 'Install VLC for me', now - timedelta(hours=5),
             'جهّزت التثبيت وينتظر موافقتك.' if ar else 'The install is ready and waits for your approval.', False, 4),
            ('r4', 'ذكّريني بموعد الطبيب' if ar else 'Remind me about the doctor', now - timedelta(days=1, hours=2),
             'سأذكّرك الخميس الساعة 9:30.' if ar else "I'll remind you on Thursday at 9:30.", False, 3),
            ('r5', 'ليش الصوت ما عم يطلع؟' if ar else 'Why is there no sound?', now - timedelta(days=12),
             'أعدت تشغيل خدمة الصوت وتحققت منها.' if ar else 'I restarted the sound service and checked it.', False, 9),
        ]
        rows = [{'id': tid, 'title': title, 'updated': when.isoformat(), 'preview': preview, 'pinned': pinned,
                 'archived': False, 'current': tid == 'r2', 'count': count, 'named': tid == 'r1'}
                for tid, title, when, preview, pinned, count in sample]
        self._show(rows)

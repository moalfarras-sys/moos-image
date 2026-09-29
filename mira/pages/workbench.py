"""The Workbench: give Mira projects.

The backend is Mo AI's agent workspace (moai-agent-api, 127.0.0.1:8077): registered projects, a
file tree with a read-only preview, Git status and diff, tracked tasks the project agent runs, the
owner's own terminal and the agent's sessions. MoOS's coding agents (OpenCode, Claude Code, Codex)
open through moos-open's fixed routes; whether each is installed comes from moai-control's /quick.

What this page promises:
- A file is read, and a diff computed, only on the owner's click (the agent service audits both).
- The terminal is the owner's: only what he types into its field is written to it. The model never
  reaches it; a terminal the agent opened for its own sandboxed command is shown read-only.
- A task starts, pauses, resumes or stops only on the owner's click. The agent then works inside
  the permission tier shown at the top, which changes only in the assistant settings.
- Installing a coding agent is a system change: an approval card when MoOS declares a tool for it,
  otherwise a plain explanation — nothing runs.
- Every state shown is the backend's own answer; a failure says why.
"""
import codecs
import re
import time
from datetime import datetime

from PySide6.QtCore import Property, QTimer, QUrl, Signal, Slot

import moai_agent
import moai_tools
import moos_routes
from pages import base
from pages.base import Page

STRINGS = {
    'wb_sub': ('أعطِ ميرا مشاريعك: الملفات وGit والمهام وطرفيتك ووكلاء البرمجة. تقرأ فوراً، وتنفّذ بموافقتك',
               'Give Mira your projects: files, Git, tasks, your terminal and coding agents. She reads at once and acts with your approval'),
    'wb_agent': ('وكيل المشاريع', 'Project agent'),
    'wb_ready': ('جاهز للعمل', 'Ready to work'),
    'wb_setup': ('يحتاج إعداداً', 'Needs setup'),
    'wb_offline': ('لا يستجيب', 'Not answering'),
    'wb_checking': ('أتحقّق…', 'Checking…'),
    'wb_reason_ready': ('العقل السحابي متصل، والمهام تعمل عبره بالصلاحيات التي اخترتها',
                        'The cloud brain is connected; tasks run through it with the permissions you chose'),
    'wb_reason_offline': ('خدمة وكيل المشاريع لا تستجيب الآن. تعود الملفات والمهام والطرفية حين تعود',
                          'The project agent service is not answering. Files, tasks and the terminal return when it does'),
    'wb_reason_gateway': ('بوابة العقل لا تعمل، فلن تبدأ المهام. شغّلها من إعدادات المساعد',
                          'The brain gateway is not running, so tasks cannot start. Turn it on in the assistant settings'),
    'wb_reason_key': ('لم يُربط عقل سحابي بعد. أضف مزوّداً ومفتاحه من إعدادات المساعد',
                      'No cloud brain is connected yet. Add a provider and its key in the assistant settings'),
    'wb_refresh': ('أعد القراءة', 'Read again'),
    'wb_permissions': ('الصلاحيات والعقل', 'Permissions & brain'),
    'wb_tier_read': ('قراءة فقط', 'Read only'),
    'wb_tier_project': ('تعديل المشاريع', 'Project edits'),
    'wb_tier_system': ('النظام بموافقتك', 'System, with approval'),
    'wb_tier_full': ('تحكّم كامل', 'Full control'),
    'wb_tier_custom': ('صلاحيات مخصّصة', 'Custom permissions'),
    'wb_web_on': ('الويب مفعّل', 'Web on'),
    'wb_web_off': ('الويب مطفأ', 'Web off'),
    'wb_brain_on': ('العقل متصل', 'Brain connected'),
    'wb_brain_off': ('بلا عقل سحابي', 'No cloud brain'),
    'wb_approvals': ('بانتظار موافقتك', 'awaiting your approval'),
    'wb_projects': ('المشاريع', 'Projects'),
    'wb_all_projects': ('كل المشاريع', 'All projects'),
    'wb_hide_projects': ('إخفاء القائمة', 'Hide the list'),
    'wb_add_project': ('إضافة مشروع', 'Add project'),
    'wb_pick_folder': ('اختر مجلد المشروع', 'Choose the project folder'),
    'wb_show_archived': ('عرض المؤرشفة', 'Show archived'),
    'wb_no_projects': ('لا مشاريع بعد. أضف مجلداً من مجلدك الشخصي لتقرأه ميرا وتعمل عليه',
                       'No projects yet. Add a folder from your home so Mira can read it and work on it'),
    'wb_pin': ('تثبيت', 'Pin'),
    'wb_unpin': ('إلغاء التثبيت', 'Unpin'),
    'wb_archive': ('أرشفة', 'Archive'),
    'wb_unarchive': ('إعادة من الأرشيف', 'Restore'),
    'wb_pinned': ('مثبّت', 'Pinned'),
    'wb_archived': ('مؤرشف', 'Archived'),
    'wb_ask': ('اسأل ميرا عنه', 'Ask Mira about it'),
    'wb_ask_review': ('اطلب مراجعة', 'Ask for a review'),
    'wb_project_added': ('أُضيف المشروع', 'Project added'),
    'wb_project_saved': ('حُفظ المشروع', 'Project saved'),
    'wb_tab_files': ('الملفات', 'Files'),
    'wb_tab_git': ('التغييرات', 'Changes'),
    'wb_tab_tasks': ('المهام', 'Tasks'),
    'wb_tab_terminal': ('الطرفية', 'Terminal'),
    'wb_tab_agents': ('وكلاء البرمجة', 'Coding agents'),
    'wb_tab_sessions': ('الجلسات', 'Sessions'),
    'wb_pick_project': ('اختر مشروعاً أو أضف واحداً أولاً', 'Choose a project, or add one, first'),
    'wb_up': ('للأعلى', 'Up'),
    'wb_root': ('جذر المشروع', 'Project root'),
    'wb_empty_dir': ('المجلد فارغ', 'This folder is empty'),
    'wb_truncated': ('يظهر أول 500 عنصر فقط', 'Showing the first 500 entries'),
    'wb_preview_hint': ('اختر ملفاً لتقرأه هنا. لا يُقرأ ملف إلا بنقرتك',
                        'Choose a file to read it here. A file is read only when you click it'),
    'wb_preview_cut': ('يظهر أول 150٬000 حرف', 'Showing the first 150,000 characters'),
    'wb_close': ('إغلاق', 'Close'),
    'wb_git_clean': ('لا تغييرات. شجرة العمل نظيفة', 'No changes. The working tree is clean'),
    'wb_git_not_repo': ('هذا المشروع ليس مستودع Git', 'This project is not a Git repository'),
    'wb_show_diff': ('كل الفروقات', 'Whole diff'),
    'wb_diff_hint': ('انقر ملفاً لترى فروقاته. لا تُحسب الفروقات إلا بنقرتك',
                     'Click a file to see its diff. A diff is computed only when you click'),
    'wb_diff_all': ('كل المشروع', 'The whole project'),
    'wb_staged': ('مُجهّز للإيداع', 'Staged'),
    'wb_unstaged': ('غير مُجهّز', 'Not staged'),
    'wb_no_diff': ('لا فروقات نصية', 'No text differences'),
    'wb_diff_cut': ('يظهر أول 3000 سطر', 'Showing the first 3,000 lines'),
    'wb_change_one': ('تغيير واحد', '1 change'),
    'wb_change_two': ('تغييران', '2 changes'),
    'wb_changes_few': ('{n} تغييرات', '{n} changes'),
    'wb_changes_many': ('{n} تغييراً', '{n} changes'),
    'wb_changes_hundreds': ('{n} تغيير', '{n} changes'),
    'wb_new_file_note': ('ملف جديد لم يتتبّعه Git بعد، فلا فروقات له. تستطيع قراءته كاملاً',
                         'A new file Git does not track yet, so it has no diff. You can read it whole'),
    'wb_read_file': ('اقرأ الملف', 'Read the file'),
    'wb_gone_note': ('حُذف هذا الملف من مجلد المشروع. يظهر حذفه ضمن فروقات المشروع كله',
                     'This file was deleted from the project folder. Its removal shows in the whole project diff'),
    'wb_refresh_files': ('أعد قراءة المجلد', 'Read the folder again'),
    'wb_new_task': ('مهمة جديدة', 'New task'),
    'wb_task_title': ('ماذا تريد أن تنجزه ميرا؟', 'What should Mira get done?'),
    'wb_task_desc': ('التفاصيل: الهدف، الحدود، وكيف تعرف أنها انتهت (اختياري)',
                     'Details: the goal, the limits, how to tell it is done (optional)'),
    'wb_task_steps': ('الخطوات، سطر لكل خطوة (اختياري)', 'Steps, one per line (optional)'),
    'wb_create': ('أنشئ المهمة', 'Create task'),
    'wb_task_where': ('ستعمل في', 'Works in'),
    'wb_no_project_scope': ('بلا مشروع', 'no project'),
    'wb_no_tasks': ('لا مهام بعد. صِف ما تريده، ثم اضغط «ابدأ» حين تكون جاهزاً',
                    'No tasks yet. Describe what you want, then press Start when you are ready'),
    'wb_scope_project': ('هذا المشروع', 'This project'),
    'wb_scope_all': ('كل المشاريع', 'All projects'),
    'wb_start': ('ابدأ', 'Start'),
    'wb_pause': ('إيقاف مؤقت', 'Pause'),
    'wb_resume': ('تابع', 'Resume'),
    'wb_cancel': ('ألغِ', 'Cancel'),
    'wb_retry': ('أعد المحاولة', 'Retry'),
    'wb_st_pending': ('بانتظار البدء', 'Waiting to start'),
    'wb_st_running': ('تعمل الآن', 'Running'),
    'wb_st_paused': ('متوقفة مؤقتاً', 'Paused'),
    'wb_st_failed': ('فشلت', 'Failed'),
    'wb_st_completed': ('اكتملت', 'Completed'),
    'wb_st_cancelled': ('أُلغيت', 'Cancelled'),
    'wb_steps': ('الخطوات', 'Steps'),
    'wb_tools': ('الأدوات', 'Tools'),
    'wb_result': ('النتيجة', 'Result'),
    'wb_error': ('الخطأ', 'Error'),
    'wb_show_work': ('اعرض عملها', 'Show its work'),
    'wb_task_needs_title': ('اكتب عنوان المهمة أولاً', 'Write the task title first'),
    'wb_task_created': ('أُنشئت المهمة. اضغط «ابدأ» حين تريد', 'Task created. Press Start when you want'),
    'wb_now_running': ('المهمة تعمل الآن', 'The task is running'),
    'wb_now_paused': ('توقفت المهمة مؤقتاً', 'The task is paused'),
    'wb_now_cancelled': ('أُلغيت المهمة', 'The task was cancelled'),
    'wb_term_title': ('طرفيتك', 'Your terminal'),
    'wb_term_note': ('أنت وحدك تكتب هنا؛ لا ميرا ولا النموذج يكتبان في طرفيتك. تعمل باسمك، بلا صلاحيات مدير',
                     'Only you type here; neither Mira nor the model writes to your terminal. It runs as you, without administrator rights'),
    'wb_term_new': ('طرفية جديدة', 'New terminal'),
    'wb_term_input': ('اكتب أمراً ثم Enter', 'Type a command, then Enter'),
    'wb_term_interrupt': ('أوقف الأمر (Ctrl+C)', 'Stop command (Ctrl+C)'),
    'wb_term_stop': ('إغلاق الطرفية', 'Close terminal'),
    'wb_term_show_all': ('عرض الكل', 'Show all'),
    'wb_term_show_fewer': ('عرض الأحدث فقط', 'Show the latest only'),
    'wb_term_read_only': ('للقراءة فقط', 'read only'),
    'wb_term_ended': ('انتهت', 'ended'),
    'wb_term_none': ('لا طرفية مفتوحة. افتح واحدة في مجلد المشروع', 'No terminal is open. Open one in the project folder'),
    'wb_term_exited': ('انتهت الطرفية', 'The terminal has ended'),
    'wb_term_agent': ('نفّذها وكيل المشاريع في صندوق معزول، وهي للقراءة فقط',
                      'The project agent ran this in an isolated sandbox; it is read only'),
    'wb_term_waiting': ('بانتظار المخرجات…', 'Waiting for output…'),
    'wb_agents_note': ('وكلاء برمجة يعملون في طرفية باسمك، بلا صلاحيات مدير',
                       'Coding agents run in a terminal as you, without administrator rights'),
    'wb_run': ('تشغيل', 'Run'),
    'wb_install': ('تثبيت', 'Install'),
    'wb_installed': ('مثبّت', 'Installed'),
    'wb_not_installed': ('غير مثبّت', 'Not installed'),
    'wb_unknown': ('غير معروف', 'Unknown'),
    'wb_engine': ('محرّك', 'Engine'),
    'wb_open_code': ('مساحة البرمجة', 'Code workspace'),
    'wb_open_code_sub': ('طرفية البرمجة بالوكيل الافتراضي', 'The coding terminal with the default agent'),
    'wb_agent_opening': ('يفتح في طرفية:', 'Opening in a terminal:'),
    'wb_agents_where_home': ('تُفتح في مجلد Projects لديك، أو في مجلدك الشخصي إن لم يوجد، وليس في المشروع المختار بعد',
                             'They open in your Projects folder, or your home folder if there is none, not yet in the chosen project'),
    'wb_agents_where_project': ('تُفتح في مجلد المشروع:', 'They open in the project folder:'),
    'wb_install_how': ('هذه النسخة من MoOS لا تتيح تثبيته من ميرا بعد. من طرفيتك:',
                       'This MoOS version cannot install it from Mira yet. From your terminal:'),
    'wb_install_asked': ('بانتظار موافقتك على التثبيت في بطاقة الموافقة', 'Waiting for your approval on the approval card'),
    'wb_install_not_yet': ('لم يُثبَّت بعد. إن وافقت ولم يظهر، فافتح بطاقة الموافقة لترى ما حدث',
                           'Not installed yet. If you approved and it did not appear, open the approval card to see what happened'),
    'wb_install_failed': ('لم يكتمل التثبيت. تفاصيل الخطأ في بطاقة الموافقة', 'The install did not finish. The error is on the approval card'),
    'wb_install_cancelled': ('لم يُثبَّت: أُلغي الطلب أو انتهت مهلته', 'Not installed: the request was cancelled or expired'),
    'wb_agent_now_installed': ('ثُبِّت وجاهز للتشغيل:', 'Installed and ready to run:'),
    'wb_agent_opencode': ('يعمل على عقل MoOS السحابي المجاني، بلا حساب', "Runs on MoOS's free cloud brain, no account needed"),
    'wb_agent_claude': ('وكيل Anthropic البرمجي، يحتاج حساب Anthropic', "Anthropic's coding agent; needs an Anthropic account"),
    'wb_agent_codex': ('وكيل OpenAI البرمجي، يحتاج حساب OpenAI', "OpenAI's coding agent; needs an OpenAI account"),
    'wb_agent_hermes': ('المحرّك الذي يشغّل مهام وكيل المشاريع وجلساته', "The engine behind the project agent's tasks and sessions"),
    'wb_sessions_note': ('محادثات وكيل المشاريع ومهامه، مع كل أداة استخدمها. للقراءة فقط',
                         "The project agent's conversations and task runs, with every tool it used. Read only"),
    'wb_no_sessions': ('لا جلسات بعد', 'No sessions yet'),
    'wb_back': ('رجوع', 'Back'),
    'wb_no_messages': ('الجلسة فارغة', 'This session is empty'),
    'wb_you': ('أنت', 'You'),
    'wb_agent_role': ('الوكيل', 'Agent'),
    'wb_tool_running': ('تعمل', 'running'),
    'wb_tool_success': ('نجحت', 'succeeded'),
    'wb_tool_error': ('فشلت', 'failed'),
    'wb_tool_pending': ('بانتظار موافقتك', 'waiting for you'),
    'wb_err_prefix': ('تعذّر: ', 'Failed: '),
    'wb_err_unreachable': ('خدمة وكيل المشاريع لا تستجيب', 'The project agent service is not answering'),
    'wb_err_home': ('يجب أن يكون المشروع داخل مجلدك الشخصي', 'The project must be inside your home folder'),
    'wb_err_missing': ('المجلد غير موجود', 'The folder does not exist'),
    'wb_err_binary': ('ملف ثنائي، لا يُعرض نصاً', 'A binary file; it is not shown as text'),
    'wb_err_large': ('الملف أكبر من حد المعاينة (1 MiB)', 'The file is larger than the preview limit (1 MiB)'),
    'wb_err_encoding': ('الملف ليس نصاً بترميز UTF-8', 'The file is not UTF-8 text'),
    'wb_err_running': ('المهمة تعمل بالفعل', 'The task is already running'),
    'wb_err_not_live': ('لا تعمل هذه المهمة الآن', 'This task is not running now'),
    'wb_err_term_gone': ('الطرفية لم تعد موجودة', 'The terminal no longer exists'),
    'wb_err_engine': ('محرّك الوكيل غير مثبّت', 'The agent engine is not installed'),
    'wb_err_route': ('هذا المسار غير مسموح لميرا', 'Mira is not allowed to open this route'),
    'wb_err_agent_input': ('هذه طرفية الوكيل، ولا يُكتب فيها', "This is the agent's terminal; it takes no input"),
    'wb_err_entry_gone': ('هذا الملف أو المجلد لم يعد موجوداً. أعد القراءة', 'This file or folder no longer exists. Read again'),
    'wb_err_escapes': ('هذا المسار يقود إلى خارج مجلد المشروع، فلا يُفتح', 'This path leads outside the project folder, so it is not opened'),
    'wb_err_not_dir': ('هذا ليس مجلداً', 'This is not a folder'),
    'wb_err_not_file': ('هذا ليس ملفاً يُقرأ', 'This is not a file that can be read'),
    'wb_err_list': ('تعذّرت قراءة محتوى هذا المجلد', 'This folder could not be listed'),
    'wb_err_project_gone': ('هذا المشروع لم يعد مسجّلاً. أعد القراءة واختر مشروعاً', 'This project is no longer registered. Read again and choose one'),
    'wb_err_task_title': ('عنوان المهمة غير صالح: سطر واحد حتى 160 حرفاً', 'The task title is not valid: one line, up to 160 characters'),
    'wb_err_task_long': ('تفاصيل المهمة أطول من 8000 حرف', 'The task details are longer than 8,000 characters'),
    'wb_err_task_folder': ('مجلد مشروع هذه المهمة لم يعد موجوداً', "This task's project folder no longer exists"),
    'wb_err_term_input': ('لم يُرسل هذا إلى الطرفية: النص فارغ أو أطول من 64 KiB', 'Not sent to the terminal: the text is empty or longer than 64 KiB'),
    'wb_err_term_write': ('لم يصل ما كتبته إلى الطرفية', 'What you typed did not reach the terminal'),
}

TABS = ('files', 'git', 'tasks', 'terminal', 'agents', 'sessions')
TIERS = ('read', 'project', 'system', 'full')
TASK_ACTIONS = {
    'pending': ('start',),
    'running': ('pause', 'cancel'),
    'paused': ('resume', 'cancel'),
    'failed': ('start',),
    'cancelled': ('start',),
    'completed': (),
}
TASK_TONES = {'pending': 'info', 'running': 'info', 'paused': 'warn', 'failed': 'error',
              'completed': 'ok', 'cancelled': 'off'}
AGENTS = (('opencode', 'OpenCode'), ('claude', 'Claude Code'), ('codex', 'Codex'), ('hermes', 'Hermes'))
# The Mo AI tool that installs each agent (the first one the installed image declares is used).
INSTALL_TOOLS = {'opencode': ('install_opencode',), 'claude': ('install_claude_code', 'install_claude'),
                 'codex': ('install_codex',), 'hermes': ('install_hermes',)}
AGENT_TERMINAL = 'Mo AI: '          # the agent's own sandboxed command runs (moai_runtime)
AGENT_TERMS_SHOWN = 4               # the agent's newest command terminals shown before "Show all"
MAX_TERM = 60_000
MAX_PREVIEW = 150_000
MAX_DIFF_LINES = 3000
MAX_TRANSCRIPT = 200
TASK_POLL_MS = 2000
TERM_POLL_MS = 300
INSTALL_POLL_MS = 5000
# How long an install note may say "waiting": the card's own life (controller.CONFIRM_TTL, 180 s)
# plus the executor's default job limit (controller.JOB_LIMIT_S default, 30 min). Kept here because a
# page never imports the controller.
INSTALL_WATCH_S = 180 + 30 * 60
UUID = re.compile(r'[0-9a-f-]{36}')
PROJECT_ID = re.compile(r'[0-9a-f]{20}')
_ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]')
_CONTROL = re.compile(r'[\x00-\x07\x0b-\x1f\x7f]')
_QUOTED = r'"(?:[^"\\]|\\.)*"'
_RENAME = re.compile(rf'({_QUOTED}|.+?) -> ({_QUOTED}|.+)')
LRM = '‎'                      # a rename label reads left to right even when both names are Arabic


def agent_get(route, query=None):
    """GET from the agent service with a query dict. (The shared helper `get(path, **query)` cannot
    carry the service's own `path` query parameter: it collides with its first argument.)"""
    return moai_agent.request('GET', route, query=query or None)


# The agent service's own short reasons → the owner's words (anything else is shown as it came).
ERRORS = {
    'agent_unreachable': 'wb_err_unreachable',
    'project must be inside the real home directory': 'wb_err_home',
    'project path does not exist': 'wb_err_missing',
    'project does not exist': 'wb_err_project_gone',
    'unknown task project': 'wb_err_project_gone',
    'unknown terminal project': 'wb_err_project_gone',
    'project entry does not exist': 'wb_err_entry_gone',
    'project path escapes its root': 'wb_err_escapes',
    'project entry is not a directory': 'wb_err_not_dir',
    'project entry is not a file': 'wb_err_not_file',
    'binary project files are not previewed': 'wb_err_binary',
    'project file is larger than the 1 MiB preview limit': 'wb_err_large',
    'project file is not UTF-8 text': 'wb_err_encoding',
    'project is not a Git worktree': 'wb_git_not_repo',
    'invalid task title': 'wb_err_task_title',
    'task description is too long': 'wb_err_task_long',
    'task project no longer exists': 'wb_err_task_folder',
    'task is already running': 'wb_err_running',
    'task has no live agent process': 'wb_err_not_live',
    'terminal has exited': 'wb_term_exited',
    'terminal does not exist': 'wb_err_term_gone',
    'invalid terminal input': 'wb_err_term_input',
    'terminal input failed': 'wb_err_term_write',
    'OpenClaw is not installed': 'wb_err_engine',
    'route_not_allowed': 'wb_err_route',
}
# Reasons that carry a detail after a fixed start ("could not list project directory: [Errno 13] …").
ERROR_PREFIXES = (('could not list project directory', 'wb_err_list'),)


def git_path(text):
    """One path as `git status` prints it → the real name. Git wraps a name with a space, a quote or
    a control character in C quotes, and (core.quotePath) writes every non-ASCII byte as octal:
    `"\\331\\205\\331\\204\\331\\201.txt"` is «ملف.txt». Raw UTF-8 inside the quotes also decodes."""
    text = str(text or '')
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            return codecs.escape_decode(text[1:-1].encode('utf-8'))[0].decode('utf-8', 'replace')
        except ValueError:
            return text[1:-1]
    return text


def git_rows(status):
    """`git status --short` → [{code, path, oldPath, label, kind, staged}]. kind: new | modified |
    added | deleted | renamed | copied | conflict | other. For a rename or copy `path` is the new name
    (the one that exists) and `oldPath` the old one; `label` is what the row shows."""
    rows = []
    for line in str(status or '').splitlines():
        if len(line) < 4 or line.startswith('…'):
            continue
        code, rest = line[:2], line[3:]
        flat = code.strip() or '?'
        conflict = 'U' in code or code in ('AA', 'DD')
        kind = ('new' if code == '??' else 'conflict' if conflict else 'deleted' if 'D' in code
                else 'renamed' if 'R' in code else 'copied' if 'C' in code else 'added' if 'A' in code
                else 'modified' if 'M' in code else 'other')
        old = ''
        pair = _RENAME.fullmatch(rest) if kind in ('renamed', 'copied') else None
        if pair:
            old, path = git_path(pair.group(1)), git_path(pair.group(2))
        else:
            path = git_path(rest)
        rows.append({'code': flat, 'path': path, 'oldPath': old,
                     'label': f'{LRM}{old} → {path}' if old else path, 'kind': kind,
                     'staged': code[0] not in (' ', '?')})
    return rows


def changes_text(count, lang='ar'):
    """'1 change' / 'تغيير واحد', with the Arabic dual and the noun forms that follow a number."""
    index = 1 if lang == 'en' else 0
    if count == 1:
        key = 'wb_change_one'
    elif count == 2:
        key = 'wb_change_two'
    elif 3 <= count % 100 <= 10:
        key = 'wb_changes_few'
    elif 11 <= count % 100 <= 99:
        key = 'wb_changes_many'
    else:                           # 100, 101, 102, 200 …: the noun follows as a singular
        key = 'wb_changes_hundreds'
    return STRINGS[key][index].format(n=count)


def clean_terminal(text):
    """PTY output → plain text: no escape sequences, no carriage returns, backspaces applied."""
    text = _ANSI.sub('', str(text or '')).replace('\r\n', '\n').replace('\r', '')
    if '\b' in text:
        out = []
        for ch in text:
            if ch == '\b':
                if out and out[-1] != '\n':
                    out.pop()
            else:
                out.append(ch)
        text = ''.join(out)
    return _CONTROL.sub('', text)


def diff_lines(result, lang='ar'):
    """The agent's {staged, unstaged} diff → coloured lines [{t, k}] (k: head | meta | hunk | add | del | ctx)."""
    out = []
    labels = {'staged': STRINGS['wb_staged'], 'unstaged': STRINGS['wb_unstaged']}
    index = 1 if lang == 'en' else 0
    for section in ('unstaged', 'staged'):
        text = str(result.get(section) or '')
        if not text.strip():
            continue
        out.append({'t': labels[section][index], 'k': 'head'})
        for line in text.splitlines():
            if line.startswith(('diff --git', 'index ', '+++', '---', 'new file', 'deleted file', 'similarity',
                                'rename ', 'old mode', 'new mode', 'Binary files')):
                kind = 'meta'
            elif line.startswith('@@'):
                kind = 'hunk'
            elif line.startswith('+'):
                kind = 'add'
            elif line.startswith('-'):
                kind = 'del'
            else:
                kind = 'ctx'
            out.append({'t': line[:400], 'k': kind})
    return out


def when(ts):
    """Epoch seconds (or milliseconds) or an ISO timestamp → 'HH:MM' today, else 'DD/MM HH:MM';
    '' for anything else. It never raises: it runs inside answers on the Qt thread."""
    moment = None
    try:
        if isinstance(ts, (int, float)) and not isinstance(ts, bool) and ts > 0:
            moment = datetime.fromtimestamp(ts / 1000 if ts > 1e11 else ts)
        elif isinstance(ts, str) and ts:
            moment = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone()
    except (ValueError, OSError, OverflowError):
        return ''
    if moment is None:
        return ''
    if moment.date() == datetime.now(moment.tzinfo).date():
        return moment.strftime('%H:%M')
    return moment.strftime('%d/%m %H:%M')


def transcript_row(row):
    """One /api/session entry (the agent runtime's or OpenClaw's) → a row QML draws."""
    if not isinstance(row, dict):
        return None
    role = str(row.get('role') or '')
    text = str(row.get('text') or '')
    status = str(row.get('status') or '')
    stamp = when(row.get('ts'))
    if role == 'tool':
        first, _, rest = text.partition('\n')
        name = first.lstrip('⚙✓✕ ').strip()
        if name.endswith(': waiting for owner approval'):
            name, status = name[:-len(': waiting for owner approval')], 'pending'
        if first.startswith('✕'):
            status = 'error'
        elif first.startswith('✓'):
            status = 'success'
        return {'role': 'tool', 'tool': name[:80] or 'tool', 'body': rest.strip()[:4000],
                'status': status if status in ('running', 'success', 'error', 'pending') else 'running', 'when': stamp}
    if role not in ('user', 'assistant') or not text.strip():
        return None
    return {'role': role, 'text': text.strip()[:6000], 'status': status, 'when': stamp}


def transcript_rows(result):
    """A session's entries → rows, one per tool call: a call's later state (running → waiting for
    the owner → done) replaces its earlier line instead of adding another."""
    rows = []
    for row in (transcript_row(item) for item in result):
        if row is None:
            continue
        last = rows[-1] if rows else None
        if (row['role'] == 'tool' and last and last['role'] == 'tool' and last['tool'] == row['tool']
                and last['status'] in ('running', 'pending')):
            rows[-1] = row
        else:
            rows.append(row)
    return rows[-MAX_TRANSCRIPT:]


def _int(value, default=0):
    """A number the backend sent, or `default` when it sent something else."""
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def visible_terminals(terms, show_all=False, keep='', seen=()):
    """What the Terminal tab lists → (rows, how many were left out). The service never forgets a
    terminal, and every sandboxed command the agent runs adds one. Shown: every running terminal of
    the owner's, his ended ones from this session (`seen`), the agent's newest AGENT_TERMS_SHOWN and
    the one on screen (`keep`); the rest wait behind "Show all". Owner first, running first, newest first."""
    ordered = sorted(terms, key=lambda t: (t['agent'], not t['running'], -t.get('created', 0)))
    if show_all:
        return ordered, 0
    shown, agents = [], 0
    for term in ordered:
        if term['agent']:
            if agents < AGENT_TERMS_SHOWN or term['id'] == keep:
                shown.append(term)
                agents += 1
        elif term['running'] or term['id'] in seen or term['id'] == keep:
            shown.append(term)
    return shown, len(ordered) - len(shown)


def task_row(task, projects):
    status = str(task.get('status') or 'pending')
    steps = [{'id': s.get('id'), 'title': str(s.get('title') or ''), 'status': str(s.get('status') or 'pending'),
              'error': str(s.get('error') or '')[:600], 'result': str(s.get('result') or '')[:600]}
             for s in (task.get('steps') or []) if isinstance(s, dict)]
    tools = []
    for item in task.get('tools') or []:
        name = item.get('name') if isinstance(item, dict) else item
        if isinstance(name, str) and name and name not in tools:
            tools.append(name)
    project = projects.get(task.get('project') or '', {})
    return {'id': str(task.get('id') or ''), 'title': str(task.get('title') or ''),
            'description': str(task.get('description') or '')[:2000], 'status': status,
            'tone': TASK_TONES.get(status, 'info'), 'actions': list(TASK_ACTIONS.get(status, ())),
            'steps': steps, 'tools': tools[:24], 'error': str(task.get('error') or '')[:2000],
            'result': str(task.get('result') or '')[:8000], 'project': str(task.get('project') or ''),
            'projectName': str(project.get('name') or ''), 'updated': _int(task.get('updated'))}


# The lists QML draws have their own properties and change signals: a terminal poll or a task
# poll must not hand every ListView a new model (it would jump to the top and lose focus).
LISTS = ('projects', 'entries', 'gitRows', 'diff', 'tasks', 'terminals', 'agents', 'sessions', 'transcript')


def _list(key, signal):
    return Property('QVariantList', lambda self: self._state[key], notify=signal)


class WorkbenchPage(Page):
    projectsChanged = Signal()
    entriesChanged = Signal()
    gitRowsChanged = Signal()
    diffChanged = Signal()
    tasksChanged = Signal()
    terminalsChanged = Signal()
    agentsChanged = Signal()
    sessionsChanged = Signal()
    transcriptChanged = Signal()
    taskCreated = Signal()          # the service accepted a new task: QML clears the form (never before)
    _names = frozenset()            # the Mo AI tools the installed image declares (read on the Qt thread)
    projects = _list('projects', projectsChanged)
    entries = _list('entries', entriesChanged)
    gitRows = _list('gitRows', gitRowsChanged)
    diff = _list('diff', diffChanged)
    tasks = _list('tasks', tasksChanged)
    terminals = _list('terminals', terminalsChanged)
    agents = _list('agents', agentsChanged)
    sessions = _list('sessions', sessionsChanged)
    transcript = _list('transcript', transcriptChanged)

    def update(self, **fields):
        """Merge what changed; nothing is emitted when a poll brings back the same answer."""
        changed = {k: v for k, v in fields.items() if k not in self._state or self._state[k] != v}
        if not changed:
            return
        self._state = {**self._state, **changed}
        self.changed.emit()
        for key in changed:
            if key in LISTS:
                getattr(self, key + 'Changed').emit()

    def __init__(self, host, parent=None):
        super().__init__(host, parent)
        self._shown = False
        self._inflight = set()      # read families with a request on the way
        self._seq = {}              # read family → number of its newest request (older answers are dropped)
        self._select_after = ''
        self._term_offset = 0
        self._term_raw = ''
        self._terms_all = []        # every terminal the service lists; `terminals` is what is shown
        self._terms_seen = set()    # the owner's terminals seen running or opened in this session
        self._install_watch = {}    # agent key → {'tool', 'deadline'}: an install card is out
        self._task_timer = QTimer(self, interval=TASK_POLL_MS, timeout=self._poll_tasks)
        self._term_timer = QTimer(self, interval=TERM_POLL_MS, timeout=self._poll_terminal)
        self._agent_timer = QTimer(self, interval=INSTALL_POLL_MS, timeout=self._poll_agents)
        # The controller's word that an approved (or refused, or expired) action ended, when it has one.
        finished = getattr(host, 'actionFinished', None)
        if finished is not None and hasattr(finished, 'connect'):
            finished.connect(self._on_action_finished)

    def initial(self):
        return {
            'loading': False,
            'ready': 'unknown', 'readyReason': '', 'tier': '', 'web': False, 'brain': False, 'gateway': False,
            'provider': '', 'approvals': 0,
            'projects': [], 'projectsError': '', 'showArchived': False, 'projectsOpen': False,
            'project': '', 'projectName': '', 'projectPath': '', 'projectPinned': False, 'projectArchived': False,
            'tab': 'files',
            'dirPath': '', 'dirParent': '', 'entries': [], 'truncated': False, 'filesLoading': False, 'filesError': '',
            'previewPath': '', 'previewSize': 0, 'previewText': '', 'previewCut': False, 'previewLoading': False,
            'previewError': '',
            'gitRows': [], 'gitCountText': '', 'gitLoaded': False, 'gitLoading': False, 'gitError': '',
            'gitNotRepo': False,
            'diffShown': False, 'diffPath': '', 'diffLabel': '', 'diffNote': '', 'diff': [], 'diffCut': False,
            'diffLoading': False, 'diffError': '',
            'tasks': [], 'tasksLoading': False, 'tasksError': '', 'tasksScope': 'project', 'running': 0,
            'creating': False, 'taskBusy': '',
            'terminals': [], 'termsHidden': 0, 'showAllTerms': False,
            'terminal': '', 'termTitle': '', 'termCwd': '', 'termOutput': '', 'termRunning': False,
            'termAgent': False, 'termExit': -1, 'termError': '', 'termStarting': False,
            'agents': [self._agent(key, name, None) for key, name in AGENTS], 'agentNote': '', 'agentNoteKey': '',
            'agentsInProject': self._project_routes(),
            'sessions': [], 'sessionsLoading': False, 'sessionsError': '',
            'session': '', 'sessionLabel': '', 'transcript': [], 'transcriptLoading': False, 'transcriptError': '',
        }

    # ── helpers ─────────────────────────────────────────────────────
    def _reason(self, result):
        error = str(result.get('error') if isinstance(result, dict) else 'shape')
        key = ERRORS.get(error) or next((k for prefix, k in ERROR_PREFIXES if error.startswith(prefix)), None)
        return self.text(key) if key else self.text('wb_err_prefix') + (error or 'shape')[:200]

    @staticmethod
    def _failed(result):
        return not isinstance(result, (dict, list)) or (isinstance(result, dict) and bool(result.get('error')))

    @staticmethod
    def _error(result):
        return str(result.get('error') or '') if isinstance(result, dict) else ''

    def _read(self, family, fn, *args, detail='', guard=False, **kwargs):
        """A read whose newest answer wins: tag `family:seq:detail`; an older answer is dropped.
        With `guard`, nothing is asked while the family still has a request on the way (polls)."""
        if guard and family in self._inflight:
            return False
        seq = self._seq[family] = self._seq.get(family, 0) + 1
        self._inflight.add(family)
        self.run(f'{family}:{seq}:{detail}', fn, *args, **kwargs)
        return True

    def _cancel(self, family):
        """Forget the answer still on the way (the owner closed what it was for)."""
        self._seq[family] = self._seq.get(family, 0) + 1
        self._inflight.discard(family)

    def _deliver(self, tag, result):
        family, _, rest = tag.partition(':')
        if family in self._seq:             # a read: only its newest answer counts
            seq = rest.split(':', 1)[0]
            if not seq.isdigit() or int(seq) != self._seq[family]:
                return
            self._inflight.discard(family)
        super()._deliver(tag, result)

    @staticmethod
    def _detail(tag):
        return tag.split(':', 2)[2] if tag.count(':') >= 2 else ''

    def _project(self, pid):
        return next((p for p in self._state['projects'] if p['id'] == pid), None)

    def _agent(self, key, name, installed):
        tool = next((t for t in INSTALL_TOOLS.get(key, ()) if t in self._names), '')
        return {'key': key, 'name': name, 'installed': installed is True, 'known': installed is not None,
                'canRun': moos_routes.allowed('moos://dev/' + key), 'tool': tool,
                'install': 'tool' if tool else 'none', 'engine': key == 'hermes'}

    @staticmethod
    def _project_routes():
        """Whether moos-open can start a coding agent inside a chosen project (moos://dev/<agent>/<id>)."""
        return moos_routes.allowed('moos://dev/code/' + '0' * 20)

    def _sync_timers(self):
        live = self._shown and not base.TEST_MODE
        if live and self._state['running'] > 0:
            if not self._task_timer.isActive():
                self._task_timer.start()
        else:
            self._task_timer.stop()
        if live and self._state['tab'] == 'terminal' and self._state['terminal'] and self._state['termRunning']:
            if not self._term_timer.isActive():
                self._term_timer.start()
        else:
            self._term_timer.stop()
        if live and self._install_watch:
            if not self._agent_timer.isActive():
                self._agent_timer.start()
        else:
            self._agent_timer.stop()

    # ── reading ─────────────────────────────────────────────────────
    @Slot()
    def refresh(self):
        """Read everything again: status, projects (and, for the project on screen, its open folder
        and its Git status), tasks, terminals and sessions. A previewed file and a computed diff are
        never read again by themselves: both are audited reads, made only on the owner's click."""
        # moai_tools caches the schemas without a lock: read them here, on the Qt thread, never on a worker
        self._names = set(moai_tools.names())
        self.update(loading=True, agentsInProject=self._project_routes())
        self._read('status', self._read_status, guard=True)
        self._load_projects(reread=True)
        self.loadTasks()
        self._read('terms', agent_get, '/api/terminals', guard=True)
        self._read('sessions', agent_get, '/api/sessions', guard=True)

    def _load_projects(self, reread=False):
        self._read('projects', agent_get, '/api/projects', {'archived': '1'} if self._state['showArchived'] else None,
                   detail='reread' if reread else '')

    @staticmethod
    def _read_status():
        return {'status': agent_get('/api/status'), 'config': agent_get('/api/config'),
                'approvals': agent_get('/api/approvals'), 'quick': moai_tools.get('/quick')}

    def on_status(self, tag, result):
        status, config = result.get('status'), result.get('config')
        quick, approvals = result.get('quick'), result.get('approvals')
        agents = quick.get('agents') if isinstance(quick, dict) and isinstance(quick.get('agents'), dict) else {}
        self._apply_agents(agents)
        if self._failed(status):
            self.update(loading=False, ready='offline', readyReason='wb_reason_offline', approvals=0)
            return
        config = config if isinstance(config, dict) and not config.get('error') else {}
        perms, cloud = config.get('permissions') or {}, config.get('cloud') or {}
        brains = quick.get('brains') if isinstance(quick, dict) and isinstance(quick.get('brains'), dict) else None
        gateway = bool(brains.get('gateway')) if brains is not None else bool((status.get('services') or {}).get('moai'))
        brain = bool(brains.get('cloud')) if brains is not None else bool(cloud.get('has_key'))
        tier = perms.get('tier') or ''
        provider = next((p.get('name') for p in config.get('providers') or []
                         if isinstance(p, dict) and p.get('id') == cloud.get('provider')), '') or cloud.get('provider') or ''
        ready, reason = (('setup', 'wb_reason_gateway') if not gateway else ('setup', 'wb_reason_key') if not brain
                         else ('ready', 'wb_reason_ready'))
        self.update(loading=False, ready=ready, readyReason=reason, gateway=gateway, brain=brain,
                    tier=tier if tier in TIERS else ('custom' if tier else ''), web=bool(perms.get('web')),
                    provider=str(provider).split(' (')[0][:40],
                    approvals=len(approvals) if isinstance(approvals, list) else 0)

    def on_projects(self, tag, result):
        if self._failed(result) or not isinstance(result, list):
            self.update(projectsError=self._reason(result if isinstance(result, dict) else {}))
            return
        projects = [{'id': str(p.get('id') or ''), 'name': str(p.get('name') or ''), 'path': str(p.get('path') or ''),
                     'pinned': bool(p.get('pinned')), 'archived': bool(p.get('archived'))}
                    for p in result if isinstance(p, dict) and PROJECT_ID.fullmatch(str(p.get('id') or ''))]
        self.update(projects=projects, projectsError='')
        current = self._state['project']
        wanted = self._select_after or current
        self._select_after = ''
        chosen = next((p for p in projects if p['id'] == wanted), None)
        if chosen is None and projects:
            chosen = projects[0]
        if chosen is None:
            self._set_project(None)
        elif chosen['id'] != current:
            self._set_project(chosen)
        else:   # the same project: its flags may have changed, and on a refresh its folder and Git too
            self.update(projectName=chosen['name'], projectPath=chosen['path'],
                        projectPinned=chosen['pinned'], projectArchived=chosen['archived'])
            if self._detail(tag) == 'reread':
                self.openDir(self._state['dirPath'])
                self.refreshGit()

    def _set_project(self, project):
        for family in ('files', 'preview', 'git', 'diff'):    # nothing of the previous project may land here
            self._cancel(family)
        if project is None:
            self.update(project='', projectName='', projectPath='', projectPinned=False, projectArchived=False,
                        dirPath='', dirParent='', entries=[], truncated=False, filesError='', previewPath='',
                        previewText='', previewError='', gitRows=[], gitCountText='', gitLoaded=False, gitError='',
                        gitNotRepo=False, diffShown=False, diffNote='', diff=[], diffError='')
            return
        self.update(project=project['id'], projectName=project['name'], projectPath=project['path'],
                    projectPinned=project['pinned'], projectArchived=project['archived'],
                    dirPath='', dirParent='', entries=[], truncated=False, filesError='',
                    previewPath='', previewText='', previewSize=0, previewCut=False, previewError='',
                    gitRows=[], gitCountText='', gitLoaded=False, gitError='', gitNotRepo=False,
                    diffShown=False, diffPath='', diffLabel='', diffNote='', diff=[], diffError='')
        self.openDir('')
        self.refreshGit()
        if self._state['tasksScope'] == 'project':
            self._load_tasks()

    # ── projects ────────────────────────────────────────────────────
    @Slot(str)
    def selectProject(self, pid):
        project = self._project(pid)
        if project is None:
            return
        if pid != self._state['project']:
            self._set_project(project)
        self.update(projectsOpen=False)     # the switcher folds back once a project is chosen

    @Slot(bool)
    def setProjectsOpen(self, shown):
        self.update(projectsOpen=bool(shown))

    @Slot(str)
    def addProject(self, folder):
        """The owner picked a folder in the dialog (a file:// URL or a path). His explicit add also
        brings back a folder he archived earlier: the service would otherwise keep it hidden."""
        text = str(folder or '').strip()
        path = QUrl(text).toLocalFile() if text.startswith('file:') else text
        if not path:
            return
        self.run('upsert:add', moai_agent.post, '/api/project/upsert', {'path': path, 'archived': False})

    @Slot(str, bool)
    def pinProject(self, pid, pinned):
        project = self._project(pid)
        if project is not None:
            self.run('upsert:pin', moai_agent.post, '/api/project/upsert',
                     {'id': pid, 'path': project['path'], 'pinned': bool(pinned)})

    @Slot(str, bool)
    def archiveProject(self, pid, archived):
        project = self._project(pid)
        if project is not None:
            self.run('upsert:archive', moai_agent.post, '/api/project/upsert',
                     {'id': pid, 'path': project['path'], 'archived': bool(archived)})

    def on_upsert(self, tag, result):
        if self._failed(result) or not result.get('ok'):
            self.host.toast.emit('error', self._reason(result if isinstance(result, dict) else {}))
            return
        kind = tag.split(':', 1)[1]
        # an archived project leaves the list (unless archived ones are shown): the next one is chosen
        if not (result.get('archived') and not self._state['showArchived']):
            self._select_after = str(result.get('id') or '')
        if kind == 'add':
            self.update(projectsOpen=False)
        self.host.toast.emit('ok', self.text('wb_project_added' if kind == 'add' else 'wb_project_saved')
                             + ' · ' + str(result.get('name') or ''))
        self._load_projects()

    @Slot(bool)
    def setShowArchived(self, show):
        self.update(showArchived=bool(show))
        self._load_projects()

    @Slot()
    def askAboutProject(self):
        name, path = self._state['projectName'], self._state['projectPath']
        if not name:
            return
        if self.lang == 'en':
            text = f'Inspect my registered project "{name}" ({path}): tell me what it is, its state and what it needs next.'
        else:
            text = f'افحصي مشروعي المسجّل «{name}» ({path}): ما هو، وما حالته، وما الذي يحتاجه الآن؟'
        self.host.prefill.emit(text)

    @Slot()
    def askReview(self):
        name = self._state['projectName']
        if not name:
            return
        if self.lang == 'en':
            text = f'Review the uncommitted Git changes in my project "{name}" and tell me if anything looks wrong.'
        else:
            text = f'راجعي تغييرات Git غير المودعة في مشروعي «{name}» وأخبريني إن كان فيها خطأ.'
        self.host.prefill.emit(text)

    # ── files ───────────────────────────────────────────────────────
    @Slot(str)
    def openDir(self, path):
        pid = self._state['project']
        if not pid:
            return
        path = str(path or '')
        self.update(filesLoading=True, filesError='')
        self._read('files', agent_get, '/api/project/files', {'project': pid, 'path': path}, detail=path)

    @Slot()
    def goUp(self):
        if self._state['dirPath']:
            self.openDir(self._state['dirParent'])

    def on_files(self, tag, result):
        if self._failed(result) or not isinstance(result, dict):
            if self._error(result) == 'project entry does not exist' and self._detail(tag):
                self.openDir('')        # the open folder is gone (renamed or deleted): back to the root
                return
            self.update(filesLoading=False, filesError=self._reason(result if isinstance(result, dict) else {}))
            return
        entries = [{'name': str(e.get('name') or ''), 'path': str(e.get('path') or ''),
                    'dir': e.get('type') == 'directory', 'size': _int(e.get('size'))}
                   for e in result.get('entries') or [] if isinstance(e, dict)]
        self.update(filesLoading=False, filesError='', entries=entries, dirPath=str(result.get('path') or ''),
                    dirParent=str(result.get('parent') or ''), truncated=bool(result.get('truncated')))

    @Slot(str)
    def previewFile(self, path):
        """Read one file for the owner (his click; the agent service audits the read)."""
        pid = self._state['project']
        if not pid or not path:
            return
        self.update(previewPath=path, previewText='', previewSize=0, previewCut=False, previewLoading=True,
                    previewError='')
        self._read('preview', agent_get, '/api/project/file', {'project': pid, 'path': path})

    def on_preview(self, tag, result):
        if self._failed(result) or not isinstance(result, dict):
            self.update(previewLoading=False, previewError=self._reason(result if isinstance(result, dict) else {}))
            return
        content = str(result.get('content') or '')
        self.update(previewLoading=False, previewText=content[:MAX_PREVIEW], previewCut=len(content) > MAX_PREVIEW,
                    previewSize=_int(result.get('size')))

    @Slot()
    def closePreview(self):
        self._cancel('preview')
        self.update(previewPath='', previewText='', previewSize=0, previewCut=False, previewLoading=False,
                    previewError='')

    # ── git ─────────────────────────────────────────────────────────
    @Slot()
    def refreshGit(self):
        """Git status is not an audited read: it is asked again whenever the owner could expect it."""
        pid = self._state['project']
        if not pid:
            return
        self.update(gitLoading=True, gitError='')
        self._read('git', agent_get, '/api/project/git-status', {'project': pid})

    def on_git(self, tag, result):
        if self._failed(result) or not isinstance(result, dict):
            not_repo = isinstance(result, dict) and result.get('error') == 'project is not a Git worktree'
            self.update(gitLoading=False, gitLoaded=True, gitRows=[], gitCountText='', gitNotRepo=not_repo,
                        gitError='' if not_repo else self._reason(result if isinstance(result, dict) else {}))
            return
        rows = git_rows(result.get('status'))[:1000]
        self.update(gitLoading=False, gitLoaded=True, gitNotRepo=False, gitError='', gitRows=rows,
                    gitCountText=changes_text(len(rows), self.lang) if rows else '')

    @Slot(str)
    def openChange(self, path):
        """The owner clicked one row of the Changes list. A new (untracked) file has no diff: it is
        offered for reading instead. A deleted file no longer exists on disk: if the service cannot diff
        it by name, the page says so and offers the whole project's diff."""
        row = next((r for r in self._state['gitRows'] if r['path'] == path), None)
        if row is None or not self._state['project']:
            return
        if row['kind'] == 'new':
            self._cancel('diff')
            self.update(diffShown=True, diffPath=row['path'], diffLabel=row['label'], diffNote='new', diff=[],
                        diffCut=False, diffLoading=False, diffError='')
            return
        self._diff(row['path'], row['label'], row['kind'])

    @Slot(str)
    def showDiff(self, path):
        """Compute the diff for one path ('' = the whole project) — only on the owner's click."""
        self._diff(str(path or ''), str(path or ''), '')

    def _diff(self, path, label, kind):
        pid = self._state['project']
        if not pid:
            return
        self.update(diffShown=True, diffPath=path, diffLabel=label, diffNote='', diff=[], diffCut=False,
                    diffLoading=True, diffError='')
        self._read('diff', agent_get, '/api/project/git-diff', {'project': pid, 'path': path}, detail=kind)

    def on_diff(self, tag, result):
        if self._failed(result) or not isinstance(result, dict):
            if self._detail(tag) == 'deleted' and self._error(result) == 'project entry does not exist':
                self.update(diffLoading=False, diffError='', diffNote='gone')
                return
            self.update(diffLoading=False, diffError=self._reason(result if isinstance(result, dict) else {}))
            return
        lines = diff_lines(result, self.lang)
        self.update(diffLoading=False, diff=lines[:MAX_DIFF_LINES], diffCut=len(lines) > MAX_DIFF_LINES)

    @Slot()
    def closeDiff(self):
        self._cancel('diff')
        self.update(diffShown=False, diffPath='', diffLabel='', diffNote='', diff=[], diffCut=False,
                    diffLoading=False, diffError='')

    @Slot(str)
    def previewChange(self, path):
        """Read a changed (new) file in the Files tab, with its folder open beside it — his click."""
        if not path or not self._state['project']:
            return
        folder = path.rpartition('/')[0]
        self.setTab('files')
        if folder != self._state['dirPath']:
            self.openDir(folder)
        self.previewFile(path)

    # ── tasks ───────────────────────────────────────────────────────
    @Slot()
    def loadTasks(self):
        self._load_tasks()

    def _load_tasks(self, quiet=False, poll=False):
        """Read the tasks in scope; a poll never overtakes a read already on the way."""
        scope = self._state['project'] if self._state['tasksScope'] == 'project' else ''
        if not quiet:
            self.update(tasksLoading=True)
        self._read('tasks', agent_get, '/api/tasks', {'project': scope} if scope else None, guard=poll)

    @Slot(str)
    def setTasksScope(self, scope):
        if scope in ('project', 'all') and scope != self._state['tasksScope']:
            self.update(tasksScope=scope, tasks=[])
            self._load_tasks()

    def on_tasks(self, tag, result):
        if self._failed(result) or not isinstance(result, list):
            self.update(tasksLoading=False, tasksError=self._reason(result if isinstance(result, dict) else {}))
            self._sync_timers()
            return
        projects = {p['id']: p for p in self._state['projects']}
        tasks = [task_row(t, projects) for t in result if isinstance(t, dict) and UUID.fullmatch(str(t.get('id') or ''))]
        running = sum(1 for t in tasks if t['status'] == 'running')
        self.update(tasksLoading=False, tasksError='', tasks=tasks, running=running)
        self._sync_timers()

    def _poll_tasks(self):
        self._load_tasks(quiet=True, poll=True)
        self._read('approvals', agent_get, '/api/approvals', guard=True)

    def on_approvals(self, tag, result):
        if isinstance(result, list):
            self.update(approvals=len(result))

    @Slot(str, str, str)
    def createTask(self, title, description, steps):
        title = ' '.join(str(title or '').split())
        if not title:
            self.host.toast.emit('error', self.text('wb_task_needs_title'))
            return
        body = {'title': title[:160], 'description': str(description or '').strip()[:8000]}
        lines = [' '.join(line.split())[:300] for line in str(steps or '').splitlines() if line.strip()]
        if lines:
            body['steps'] = lines[:100]
        if self._state['project']:
            body['project'] = self._state['project']
        self.update(creating=True)
        self.run('created:task', moai_agent.post, '/api/task/create', body)

    def on_created(self, tag, result):
        self.update(creating=False)
        if self._failed(result) or not result.get('ok'):
            # the owner's words stay in the form: only taskCreated clears it
            self.host.toast.emit('error', self._reason(result if isinstance(result, dict) else {}))
            return
        self.taskCreated.emit()
        self.host.toast.emit('ok', self.text('wb_task_created'))
        self._load_tasks()

    @Slot(str, str)
    def taskAction(self, task_id, action):
        task = next((t for t in self._state['tasks'] if t['id'] == task_id), None)
        if task is None or action not in task['actions'] or self._state['taskBusy']:
            return
        self.update(taskBusy=task_id)
        self.run(f'taskact:{task_id}', moai_agent.post, '/api/task/action', {'id': task_id, 'action': action})

    def on_taskact(self, tag, result):
        self.update(taskBusy='')
        if self._failed(result) or not result.get('ok'):
            self.host.toast.emit('error', self._reason(result if isinstance(result, dict) else {}))
        else:
            status = result.get('status')
            key = {'running': 'wb_now_running', 'paused': 'wb_now_paused', 'cancelled': 'wb_now_cancelled'}.get(status)
            if key:
                self.host.toast.emit('ok' if status != 'running' else 'pending', self.text(key))
        self._load_tasks(quiet=True)

    @Slot(str)
    def askAboutTask(self, task_id):
        task = next((t for t in self._state['tasks'] if t['id'] == task_id), None)
        if task is None:
            return
        where = task['projectName'] or self._state['projectName']
        state = self.text('wb_st_' + task['status']) if ('wb_st_' + task['status']) in STRINGS else task['status']
        if self.lang == 'en':
            text = f'Help me with the task "{task["title"]}"' + (f' in my project "{where}"' if where else '') + f' — it is {state.lower()}.'
            if task['error']:
                text += f' Its error: {task["error"][:300]}'
        else:
            text = f'ساعديني في المهمة «{task["title"]}»' + (f' في مشروعي «{where}»' if where else '') + f'، حالتها: {state}.'
            if task['error']:
                text += f' خطؤها: {task["error"][:300]}'
        self.host.prefill.emit(text)

    @Slot(str)
    def showTaskWork(self, task_id):
        task = next((t for t in self._state['tasks'] if t['id'] == task_id), None)
        if task is None:
            return
        self.setTab('sessions')
        self._open_session('moai-task-' + task_id, task['title'])

    # ── the owner's terminal ────────────────────────────────────────
    def _publish_terms(self):
        shown, hidden = visible_terminals(self._terms_all, self._state['showAllTerms'], self._state['terminal'],
                                          self._terms_seen)
        self.update(terminals=shown, termsHidden=hidden)

    def _mark_term(self, term_id, running):
        self._terms_all = [dict(t, running=running) if t['id'] == term_id else t for t in self._terms_all]
        self._publish_terms()

    @Slot(bool)
    def setShowAllTerms(self, show):
        self.update(showAllTerms=bool(show))
        self._publish_terms()

    def on_terms(self, tag, result):
        if self._failed(result) or not isinstance(result, list):
            self.update(termError=self._reason(result if isinstance(result, dict) else {}))
            return
        terms = [{'id': str(t.get('id')), 'title': str(t.get('title') or '')[:80], 'cwd': str(t.get('cwd') or ''),
                  'running': bool(t.get('running')), 'agent': str(t.get('title') or '').startswith(AGENT_TERMINAL),
                  'exit': t.get('exit_code') if isinstance(t.get('exit_code'), int) else -1,
                  'created': _int(t.get('created'))}
                 for t in result if isinstance(t, dict) and UUID.fullmatch(str(t.get('id') or ''))]
        self._terms_all = terms
        self._terms_seen |= {t['id'] for t in terms if t['running'] and not t['agent']}
        self.update(termError='')
        current = next((t for t in terms if t['id'] == self._state['terminal']), None)
        if current is None:
            first = next((t for t in sorted(terms, key=lambda t: -t['created'])
                          if not t['agent'] and t['running']), None)
            if first is not None:
                self._publish_terms()
                self.selectTerminal(first['id'])
                return
            if self._state['terminal']:
                self.update(terminal='', termOutput='', termRunning=False)
        else:
            self.update(termRunning=current['running'])
        self._publish_terms()
        self._sync_timers()

    @Slot()
    def newTerminal(self):
        body = {'project': self._state['project']} if self._state['project'] else {}
        self.update(termStarting=True, termError='')
        self.run('termstart:new', moai_agent.post, '/api/terminal/start', body)

    def on_termstart(self, tag, result):
        self.update(termStarting=False)
        if self._failed(result) or not result.get('ok') or not UUID.fullmatch(str(result.get('id') or '')):
            self.update(termError=self._reason(result if isinstance(result, dict) else {}))
            return
        term = {'id': result['id'], 'title': str(result.get('title') or '')[:80], 'cwd': str(result.get('cwd') or ''),
                'running': bool(result.get('running', True)), 'agent': False, 'exit': -1,
                'created': _int(result.get('created'), int(time.time()))}
        self._terms_all = [term] + [t for t in self._terms_all if t['id'] != term['id']]
        self._terms_seen.add(term['id'])
        self._publish_terms()
        self.selectTerminal(term['id'])

    @Slot(str)
    def selectTerminal(self, term_id):
        term = next((t for t in self._terms_all if t['id'] == term_id), None)
        if term is None:
            return
        self._term_offset, self._term_raw = 0, ''
        self._cancel('termout')
        self.update(terminal=term_id, termTitle=term['title'], termCwd=term['cwd'], termAgent=term['agent'],
                    termRunning=term['running'], termExit=term['exit'], termOutput='', termError='')
        self._publish_terms()           # the terminal on screen is always listed
        self._poll_terminal()
        self._sync_timers()

    @Slot()
    def clearTerminalView(self):
        """Ctrl+L in his field: the view starts empty from here. Only the page's copy is cleared;
        nothing is written to the terminal."""
        self._term_raw = ''
        self.update(termOutput='')

    def _poll_terminal(self):
        term_id = self._state['terminal']
        if term_id:
            self._read('termout', agent_get, '/api/terminal/output', {'id': term_id, 'offset': str(self._term_offset)},
                       detail=term_id, guard=True)

    def on_termout(self, tag, result):
        term_id = self._detail(tag)
        if term_id != self._state['terminal']:
            return
        if self._failed(result) or not isinstance(result, dict):
            self.update(termRunning=False, termError=self._reason(result if isinstance(result, dict) else {}))
            self._sync_timers()
            return
        chunk = str(result.get('output') or '')
        self._term_offset = _int(result.get('offset'), self._term_offset)
        running = bool(result.get('running'))
        fields = {}
        if chunk:
            self._term_raw = (self._term_raw + chunk)[-MAX_TERM * 2:]
            fields['termOutput'] = clean_terminal(self._term_raw)[-MAX_TERM:]
        if running != self._state['termRunning']:
            fields['termRunning'] = running
            fields['termExit'] = result.get('exit_code') if isinstance(result.get('exit_code'), int) else -1
        if fields:
            self.update(**fields)
        if 'termRunning' in fields:
            self._mark_term(term_id, running)
        self._sync_timers()

    @Slot(str)
    def sendTerminal(self, text):
        """What the owner typed, plus Enter. Never called by the model: only the page's own field reaches it."""
        self._write_terminal(str(text or '') + '\n')

    @Slot()
    def interruptTerminal(self):
        self._write_terminal('\x03')

    def _write_terminal(self, data):
        term_id = self._state['terminal']
        if not term_id or not self._state['termRunning']:
            return
        if self._state['termAgent']:
            self.update(termError=self.text('wb_err_agent_input'))
            return
        self.run(f'termwrite:{term_id}', moai_agent.post, '/api/terminal/write', {'id': term_id, 'input': data})

    def on_termwrite(self, tag, result):
        if self._failed(result) or not result.get('ok'):
            self.update(termError=self._reason(result if isinstance(result, dict) else {}))
        else:
            self.update(termError='')
            self._poll_terminal()

    @Slot()
    def stopTerminal(self):
        term_id = self._state['terminal']
        if term_id and not self._state['termAgent']:
            self.run(f'termstop:{term_id}', moai_agent.post, '/api/terminal/stop', {'id': term_id})

    def on_termstop(self, tag, result):
        if self._failed(result) or not result.get('ok'):
            self.update(termError=self._reason(result if isinstance(result, dict) else {}))
            return
        term_id = tag.split(':', 1)[1]
        self._mark_term(term_id, False)
        if term_id == self._state['terminal']:
            self._poll_terminal()       # the last output and the exit code
        self._read('terms', agent_get, '/api/terminals', guard=True)

    # ── coding agents ───────────────────────────────────────────────
    @Slot(str)
    def openAgent(self, key):
        """Run a coding agent in a terminal: in the chosen project when moos-open can take it there
        (moos://dev/<agent>/<project id>), otherwise where moai-code starts by itself."""
        route = 'moos://dev/code' if key == 'code' else 'moos://dev/' + str(key)
        pid = self._state['project']
        in_project = bool(pid) and moos_routes.allowed(route + '/' + pid)
        result = moos_routes.open_route(route + '/' + pid if in_project else route)
        if result.get('status') == 'ok':
            name = dict(AGENTS).get(key) or self.text('wb_open_code')
            where = ' · ' + self._state['projectName'] if in_project and self._state['projectName'] else ''
            self.host.toast.emit('info', self.text('wb_agent_opening') + ' ' + name + where)
        else:
            self.host.toast.emit('error', self._reason(result))

    @Slot(str)
    def installAgent(self, key):
        """An approval card (the executor's own tool) when the image declares one; otherwise the
        command for his own terminal. Nothing is installed from here without his approval."""
        agent = next((a for a in self._state['agents'] if a['key'] == key), None)
        if agent is None or agent['installed']:
            return
        if agent['install'] != 'tool':
            self.update(agentNote=self.text('wb_install_how') + ' moai-do install-' + key, agentNoteKey=key)
            return
        # what approving will really do, from the schemas (download size, a sign-in, a changed setting …)
        detail = moai_tools.consequence(agent['tool'], self.lang) or (
            f'{agent["name"]}: installs into your home folder (~/.local) as you, with no administrator rights.'
            if self.lang == 'en' else f'{agent["name"]}: يُثبَّت في مجلدك (~/.local) باسمك، بلا صلاحيات مدير.')
        card = self.host.request_confirmation({'kind': 'moai', 'name': agent['tool'], 'args': {},
                                               'detail': detail, 'origin': 'workbench'})
        if not card:
            self.host.toast.emit('error', self.text('wb_err_prefix') + agent['tool'])
            return
        self._install_watch[key] = {'tool': agent['tool'], 'deadline': time.monotonic() + INSTALL_WATCH_S}
        self.update(agentNote=self.text('wb_install_asked'), agentNoteKey=key)
        self._sync_timers()

    def _apply_agents(self, installed):
        """moai-control's word on which agents are installed → the cards; a watched install that now
        reads as installed ends its note (the only proof the install happened)."""
        self.update(agents=[self._agent(key, name, installed.get(key) if key in installed else None)
                            for key, name in AGENTS])
        for key in [k for k in self._install_watch if installed.get(k) is True]:
            del self._install_watch[key]
            if self._state['agentNoteKey'] == key:
                self.update(agentNote='', agentNoteKey='')
            self.host.toast.emit('ok', self.text('wb_agent_now_installed') + ' ' + dict(AGENTS).get(key, key))
        self._sync_timers()

    def _poll_agents(self):
        """While an install card is out and the page is shown: is the agent there yet?"""
        now = time.monotonic()
        for key, watch in list(self._install_watch.items()):
            if now >= watch['deadline']:
                self._end_watch(key, 'wb_install_not_yet')
        if self._install_watch:
            self._read('agentcheck', moai_tools.get, '/quick', guard=True)
        self._sync_timers()

    def on_agentcheck(self, tag, result):
        agents = result.get('agents') if isinstance(result, dict) else None
        if isinstance(agents, dict):            # moai-control silent: keep waiting, claim nothing
            self._apply_agents(agents)

    def _end_watch(self, key, note):
        self._install_watch.pop(key, None)
        if self._state['agentNoteKey'] == key:
            self.update(agentNote=self.text(note))
        self._sync_timers()

    def _on_action_finished(self, name, outcome):
        """The controller's word that an approved action ended ('ok' | 'error') or that its card was
        refused or expired ('cancelled' | 'expired'). Only an install this page asked for is followed."""
        key = next((k for k, w in self._install_watch.items() if w['tool'] == name), None)
        if key is None:
            return
        if outcome == 'ok':
            self._read('agentcheck', moai_tools.get, '/quick')     # the proof is /quick, not the job
        elif outcome == 'error':
            self._end_watch(key, 'wb_install_failed')
        elif outcome in ('cancelled', 'expired'):
            self._end_watch(key, 'wb_install_cancelled')

    # ── agent sessions (read only) ──────────────────────────────────
    def on_sessions(self, tag, result):
        if self._failed(result) or not isinstance(result, list):
            self.update(sessionsLoading=False, sessionsError=self._reason(result if isinstance(result, dict) else {}))
            return
        rows = [{'id': str(s.get('id') or ''), 'key': str(s.get('key') or ''), 'label': str(s.get('label') or '')[:140],
                 'pinned': bool(s.get('pinned')), 'task': str(s.get('key') or '').startswith('moai-task-'),
                 'updated': _int(s.get('updated')), 'when': when(_int(s.get('updated')))}
                for s in result if isinstance(s, dict) and s.get('id')]
        self.update(sessionsLoading=False, sessionsError='', sessions=rows[:80])

    @Slot(str)
    def openSession(self, session_id):
        row = next((s for s in self._state['sessions'] if s['id'] == session_id), None)
        self._open_session(session_id, row['label'] if row else '')

    def _open_session(self, session_id, label):
        self.update(session=session_id, sessionLabel=label, transcript=[], transcriptLoading=True, transcriptError='')
        self._read('transcript', agent_get, '/api/session', {'id': session_id})

    def on_transcript(self, tag, result):
        if self._failed(result) or not isinstance(result, list):
            self.update(transcriptLoading=False, transcriptError=self._reason(result if isinstance(result, dict) else {}))
            return
        self.update(transcriptLoading=False, transcriptError='', transcript=transcript_rows(result))

    @Slot()
    def closeSession(self):
        self._cancel('transcript')
        self.update(session='', sessionLabel='', transcript=[], transcriptLoading=False, transcriptError='')
        self._read('sessions', agent_get, '/api/sessions', guard=True)

    # ── navigation, visibility, settings ────────────────────────────
    @Slot(str)
    def setTab(self, tab):
        """Choosing a destination shows it as it is now: its list is read again (never a file or a diff)."""
        if tab not in TABS:
            return
        self.update(tab=tab)
        if base.TEST_MODE:
            return
        if tab == 'terminal':
            self._read('terms', agent_get, '/api/terminals', guard=True)
            if self._state['terminal']:
                self._poll_terminal()
        elif tab == 'sessions' and not self._state['session']:
            self.update(sessionsLoading=not self._state['sessions'])
            self._read('sessions', agent_get, '/api/sessions', guard=True)
        elif tab == 'git' and self._state['project'] and not self._state['gitLoading']:
            self.refreshGit()
        elif tab == 'files' and self._state['project'] and not self._state['filesLoading']:
            self.openDir(self._state['dirPath'])
        self._sync_timers()

    @Slot(bool)
    def setShown(self, shown):
        """The page is on screen or not (its view went away, the window was hidden or minimised):
        polling runs only while it is."""
        self._shown = bool(shown)
        self._sync_timers()

    @Slot()
    def changePermissions(self):
        result = moos_routes.open_route('moos://settings/assistant')
        if result.get('status') != 'ok':
            self.host.toast.emit('error', self._reason(result))

    # ── review renders (MIRA_TEST_MODE only) ────────────────────────
    def review(self):
        import os
        now = int(time.time())
        projects = [
            {'id': 'ea6e19fda493e98f82e2', 'name': 'MoOS', 'path': '/var/home/moos/moos-image', 'pinned': True, 'archived': False},
            {'id': '0b5c7d2e41f9a8c3d6e1', 'name': 'Mira', 'path': '/var/home/moos/moos-wt/mira-v4/mira', 'pinned': False, 'archived': False},
            {'id': '7f3a9c1e5b2d8f4a6c0e', 'name': 'موقع المتجر', 'path': '/var/home/moos/Projects/store-site', 'pinned': False, 'archived': False},
        ]
        by_id = {p['id']: p for p in projects}
        tasks = [
            task_row({'id': '3f2b8c1a-9d4e-4f6a-8b2c-1e5d7a9c3b40', 'title': 'أضف اختبارات لصفحة الورشة',
                      'description': 'غطِّ قراءة المشاريع والمهام والطرفية، وشغّل الاختبارات قبل أن تنتهي.',
                      'project': projects[0]['id'], 'status': 'running', 'updated': now - 40,
                      'steps': [{'id': 1, 'title': 'اقرأ pages/workbench.py', 'status': 'completed'},
                                {'id': 2, 'title': 'اكتب test_page_workbench.py', 'status': 'running'},
                                {'id': 3, 'title': 'شغّل الاختبارات وأرفق النتيجة', 'status': 'pending'}],
                      'tools': [{'name': 'files'}, {'name': 'read_file'}, {'name': 'git_diff'}]}, by_id),
            task_row({'id': '8a1d4e7b-2c5f-4a9e-b3d6-7f0c2e8a5b19', 'title': 'نظّف ملفات البناء المؤقتة',
                      'project': projects[0]['id'], 'status': 'completed', 'updated': now - 3600,
                      'result': 'حُذفت 5 ملفات .log من جذر المشروع، و git status نظيف.',
                      'tools': [{'name': 'git_status'}, {'name': 'run_command'}]}, by_id),
            task_row({'id': 'c4e9a2f1-6b3d-4e8a-9c5f-2d7b1a0e4f63', 'title': 'حدّث قسم التثبيت في README',
                      'project': projects[0]['id'], 'status': 'failed', 'updated': now - 7200,
                      'error': 'Verification incomplete; inspect the session and continue.'}, by_id),
        ]
        entries = [{'name': n, 'path': n, 'dir': True, 'size': 0}
                   for n in ('.github', 'artwork', 'build_files', 'docs', 'mira', 'system_files', 'tests')]
        entries += [{'name': n, 'path': n, 'dir': False, 'size': s}
                    for n, s in (('AGENTS.md', 31840), ('Containerfile', 9120), ('README.md', 6404), ('justfile', 4210))]
        readme = ('# MoOS\n\nMoOS is a complete operating system: KDE Plasma 6 on an immutable, signed base,\n'
                  'with Mira as its assistant.\n\n## Build\n\n```sh\njust build        # the generic x86 image\n'
                  'just build-nvidia # with the NVIDIA driver\n```\n\n## Editions\n\n- moos\n- moos-nvidia\n'
                  '- moos-cloud\n- moos-arm\n')
        diff = diff_lines({'unstaged': 'diff --git a/mira/README.md b/mira/README.md\nindex 3c1e2f0..9ab4d71 100644\n'
                                       '--- a/mira/README.md\n+++ b/mira/README.md\n@@ -12,6 +12,8 @@ Mira is the owner\'s assistant\n'
                                       ' - `controller.py` — the only object QML talks to\n'
                                       '-- `qml/Mira/*` — the design system\n'
                                       '+- `pages/*.py` — one QObject per destination\n'
                                       '+- `qml/Mira/*Page.qml` — the pages, rooted in PageFrame\n'
                                       ' - `i18n.py` — Arabic and English interface text\n'}, self.lang)
        terminal = ('moai:~/moos-image$ git log --oneline -3\n7e3de8f6 Give Mira a labelled navigation and a page architecture\n'
                    '0619c75d Record the Echo asset path and PR #177 in the notes\n'
                    '7a75f48a Reach the Echo without an inbound port\nmoai:~/moos-image$ just check\n'
                    'python3 tests/verify_user_experience.py\nuser-experience gate: 214 checks passed\nmoai:~/moos-image$ ')
        transcript = transcript_rows((
            {'role': 'user', 'text': 'افحص مشروع MoOS وأخبرني بحالة Git.', 'ts': now - 900},
            {'role': 'tool', 'text': 'git_status', 'status': 'running', 'ts': now - 890},
            {'role': 'tool', 'text': 'git_status\n{"status": " M mira/README.md\\n?? mira/pages/workbench.py"}', 'status': 'success', 'ts': now - 889},
            {'role': 'tool', 'text': 'run_command: waiting for owner approval', 'status': 'pending', 'ts': now - 880},
            {'role': 'tool', 'text': 'run_command\n{"exit_code": 0, "output": "5 passed"}', 'status': 'success', 'ts': now - 875},
            {'role': 'tool', 'text': 'write_file: waiting for owner approval', 'status': 'pending', 'ts': now - 872},
            {'role': 'assistant', 'text': 'في المشروع ملفان تغيّرا: README معدّل، وصفحة جديدة لم تُضف بعد إلى Git.', 'ts': now - 870}))
        sessions = [{'id': 'a3a3342e-88bb-4c97-aecd-487a99787f28', 'key': 'mira-desktop-owner', 'pinned': True,
                     'label': 'افحص مشروع MoOS وأخبرني بحالة Git', 'task': False, 'updated': now - 870, 'when': when(now - 870)},
                    {'id': '5b7e8fa1-3f4f-4d39-b884-671cf206ad9c', 'key': 'moai-task-3f2b8c1a-9d4e-4f6a-8b2c-1e5d7a9c3b40',
                     'pinned': False, 'label': 'أضف اختبارات لصفحة الورشة', 'task': True, 'updated': now - 40, 'when': when(now - 40)}]
        tab = os.environ.get('MIRA_WORKBENCH_TAB', 'tasks')
        rows = git_rows(' M mira/README.md\n M mira/controller.py\n?? mira/pages/workbench.py\n'
                        '?? "docs/\\331\\205\\331\\204\\330\\247\\330\\255\\330\\270\\330\\247\\330\\252.md"\n'
                        'R  "docs/old notes.md" -> docs/NOTES.md\nA  docs/WORKBENCH.md\n D build/old.log')
        owner = '1d2c3b4a-5e6f-4a7b-8c9d-0e1f2a3b4c5d'
        self._terms_all = ([{'id': owner, 'title': 'MoOS', 'cwd': projects[0]['path'], 'running': True, 'agent': False,
                             'exit': -1, 'created': now - 600}]
                           + [{'id': f'9e8d7c6b-5a4f-4e3d-2c1b-0a9f8e7d6c{n:02d}', 'title': 'Mo AI: ' + command,
                               'cwd': projects[0]['path'], 'running': False, 'agent': True, 'exit': 0, 'created': now - 60 * n}
                              for n, command in enumerate(('pytest -q', 'git status', 'just check', 'ls docs', 'rg TODO',
                                                           'python3 -m unittest', 'git diff --stat'), 1)])
        self._terms_seen = {owner}
        note = os.environ.get('MIRA_WORKBENCH_DIFFNOTE', '')
        diff_row = next((r for r in rows if r['kind'] == ('new' if note == 'new' else 'deleted' if note == 'gone'
                                                         else 'modified')), rows[0])
        self.update(
            ready='ready', readyReason='wb_reason_ready', tier='project', web=True, brain=True, gateway=True,
            provider='OpenRouter', approvals=1, projects=projects, project=projects[0]['id'],
            projectName='MoOS', projectPath=projects[0]['path'], projectPinned=True,
            projectsOpen=bool(os.environ.get('MIRA_WORKBENCH_PROJECTS')),
            tab=tab if tab in TABS else 'tasks',
            entries=entries, dirPath='', dirParent='', previewPath='README.md', previewText=readme, previewSize=6404,
            gitRows=rows, gitCountText=changes_text(len(rows), self.lang),
            gitLoaded=True, diffShown=True, diffPath=diff_row['path'], diffLabel=diff_row['label'],
            diffNote=note if note in ('new', 'gone') else '', diff=[] if note in ('new', 'gone') else diff,
            tasks=tasks, running=1,
            terminal=owner, termTitle='MoOS', termCwd=projects[0]['path'], termOutput=terminal, termRunning=True,
            agents=[{'key': 'opencode', 'name': 'OpenCode', 'installed': True, 'known': True, 'canRun': True, 'tool': '', 'install': 'none', 'engine': False},
                    {'key': 'claude', 'name': 'Claude Code', 'installed': False, 'known': True, 'canRun': True, 'tool': 'install_claude_code', 'install': 'tool', 'engine': False},
                    {'key': 'codex', 'name': 'Codex', 'installed': True, 'known': True, 'canRun': True, 'tool': '', 'install': 'none', 'engine': False},
                    {'key': 'hermes', 'name': 'Hermes', 'installed': True, 'known': True, 'canRun': False, 'tool': '', 'install': 'none', 'engine': True}],
            agentNote=self.text('wb_install_asked') if os.environ.get('MIRA_WORKBENCH_NOTE') else '',
            agentNoteKey='claude' if os.environ.get('MIRA_WORKBENCH_NOTE') else '',
            sessions=sessions,
            session=sessions[0]['id'] if os.environ.get('MIRA_WORKBENCH_SESSION') else '',
            sessionLabel=sessions[0]['label'], transcript=transcript)
        self._publish_terms()

PAGE = WorkbenchPage

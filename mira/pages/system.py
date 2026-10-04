"""The System page: this MoOS, its updates, its daily check, the self-check, the device plan and every
repair — Mo AI's device centre as one of Mira's destinations.

Where each part comes from (all through Mo AI's own services, never a shell of Mira's):
  - the hero        `os_state` (moos-inspect: booted / staged / kept-for-rollback deployments), the
                    daily report's update facts (nightly update, its last result, app updates) and,
                    when this image declares it, `check_system_update` (the Updater's own resolver:
                    is a newer signed version published?);
  - the daily check `moai-control GET /health` (moos-health's latest report); "Check now" is
                    `POST /health/scan`, then /health is read every 3 s until a newer report appears;
  - the self-check  `GET /diagnose` (moos-selfcheck --quiet and its safe repair menu);
  - the device plan `GET /scan` → device_plan (GPU, driver, gaps, firmware, advice) and the live kernel;
  - repairs, tools  the Mo AI tools themselves (`moai_tools.execute`), and the playbooks
                    (`list_skills` → `read_skill`).

Reads run at once and show their real output under the tile that asked. Anything that changes the
system goes to the owner as a card (host.request_confirmation) with a plain account of what will
happen; the page never confirms for him. When the controller forwards the card's progress
(`action_update`), the tile shows the job's real end. The page does not depend on that for its own
health: a card it heard nothing about is released when the card's own time runs out, and the tile
says honestly that no word came back.

The page claims only what a service established: "up to date" needs the executor's check or a nightly
run with a known time (systemd reports Result=success for a unit that never ran), "signed official"
needs the update resolver to have accepted the origin, and a probe that could not answer is shown as
unknown, never as zero. Words the owner reads are keys translated in QML, so a language switch
re-renders everything; the backends' raw codes are translated there too.

What the owner reads is cleaned for the identity contract: a kernel is a number (no `.fc` tag) and a
base distribution's name never reaches the screen from a backend's text.
"""
import re
import time
from datetime import datetime, timezone

from PySide6.QtCore import QTimer, Slot

import moai_tools
import moos_routes
from pages.base import TEST_MODE, Page

STRINGS = {
    # page
    'sy_title': ('نظام MoOS', 'MoOS system'),
    'sy_sub': ('الإصدار والتحديثات والفحص اليومي والإصلاح — أي تغيير ينتظر موافقتك',
               'Version, updates, the daily check and repairs — every change waits for your approval'),
    'sy_reread': ('اقرأ الحالة من جديد', 'Read everything again'),
    'sy_today': ('اليوم', 'today'),
    'sy_yesterday': ('أمس', 'yesterday'),
    'sy_sample': ('بيانات عيّنة', 'Sample data'),
    # hero
    'sy_runs': ('يعمل هذا الكمبيوتر على', 'This computer runs'),
    'sy_reading': ('أقرأ النسخة…', 'Reading the version…'),
    'sy_unknown_version': ('تعذّرت قراءة النسخة', 'Could not read the version'),
    'sy_signed_official': ('MoOS رسمي موقّع', 'Signed official MoOS'),
    'sy_signed_origin': ('مصدر موقّع', 'Signed origin'),
    'sy_not_official': ('ليس مصدر MoOS رسمياً موقّعاً', 'Not a signed official MoOS origin'),
    'sy_unsigned': ('مصدر غير موقّع', 'Unsigned origin'),
    'sy_origin_tip': ('«رسمي» يعني أن محرك تحديث MoOS قبل هذا المصدر عند آخر بحث عن تحديث',
                      '“Official” means the MoOS update resolver accepted this origin at the last update check'),
    'sy_ed_moos': ('نسخة MoOS العامة', 'MoOS standard edition'),
    'sy_ed_moos-nvidia': ('نسخة MoOS لبطاقات NVIDIA', 'MoOS NVIDIA edition'),
    'sy_ed_moos-cloud': ('نسخة MoOS السحابية', 'MoOS Cloud edition'),
    'sy_ed_moos-arm': ('نسخة MoOS لمعالجات ARM', 'MoOS ARM edition'),
    'sy_kernel': ('النواة', 'Kernel'),
    'sy_kept': ('محفوظ للرجوع', 'Kept for rollback'),
    'sy_no_kept': ('لا نسخة محفوظة للرجوع', 'No earlier version kept'),
    'sy_state_staged': ('تحديث جاهز — أعد التشغيل لتطبيقه', 'Update ready — restart to apply'),
    'sy_state_current': ('محدَّث حسب الفحص الليلي', 'Up to date as of the nightly check'),
    'sy_state_none': ('لا تحديث بانتظار إعادة التشغيل', 'No update waiting for a restart'),
    'sy_state_unknown': ('حالة التحديث غير معروفة بعد', 'Update state not known yet'),
    # what check_system_update answered (MOOS_UPDATE state=…)
    'sy_upd_available': ('نسخة أحدث متاحة: {v}', 'Newer version {v} available'),
    'sy_upd_replace-staged': ('إصدار تصحيحي أحدث {v} سيحلّ محلّ التحديث الجاهز',
                              'A newer corrective release {v} will replace the staged update'),
    'sy_upd_current': ('على أحدث نسخة موقّعة', 'On the latest signed version'),
    'sy_upd_staged': ('تحديث جاهز — أعد التشغيل لتطبيقه', 'Update ready — restart to apply'),
    'sy_upd_blocked-downgrade': ('النسخة المنشورة ليست أحدث من نسختك؛ لا شيء لتثبيته',
                                 'The published version is not newer than yours; nothing to install'),
    'sy_upd_busy': ('يُجهَّز تحديث الآن — ابحث ثانيةً بعد دقائق', 'An update is being prepared now — check again in a few minutes'),
    'sy_upd_unsigned': ('لا يمكن التحقق من التحديثات: ليس مصدر MoOS رسمياً موقّعاً',
                        'Updates cannot be verified: not a signed official MoOS origin'),
    'sy_upd_unknown': ('تعذّر البحث عن تحديث', 'Could not check for updates'),
    'sy_check_done': ('اكتمل البحث عن تحديث', 'Update check complete'),
    'sy_ready_after': ('جاهز بعد إعادة التشغيل', 'Ready after restart'),
    'sy_updates_label': ('تحديث النظام', 'System update'),
    'sy_nightly': ('التحديث الليلي', 'Nightly update'),
    'sy_nightly_on': ('يعمل', 'On'),
    'sy_nightly_off': ('متوقف', 'Off'),
    'sy_last_ok': ('آخر مرة نجح', 'last run succeeded'),
    'sy_last_failed': ('آخر مرة لم ينجح', 'last run failed'),
    'sy_no_failure': ('لم يُسجَّل فشل', 'no failure recorded'),
    'sy_app_updates': ('تحديثات التطبيقات', 'App updates'),
    'sy_app_updates_none': ('لا شيء بالانتظار', 'none waiting'),
    'sy_update': ('حدّث MoOS', 'Update MoOS'),
    'sy_check_updates': ('ابحث عن تحديث', 'Check for updates'),
    'sy_restart': ('أعد التشغيل للتطبيق', 'Restart to apply'),
    'sy_rollback': ('ارجع للنسخة السابقة', 'Roll back'),
    'sy_recovery': ('الاسترداد', 'Recovery'),
    'sy_whats_new': ('ما الجديد', "What's new"),
    'sy_open_updater': ('افتح المحدِّث', 'Open the Updater'),
    'sy_checking': ('أقرأ حالة التحديث…', 'Reading the update state…'),
    'sy_check_staged': ('تحديث جاهز: أعد التشغيل لتطبيقه.', 'An update is ready: restart to apply it.'),
    'sy_check_none': ('لا تحديث بانتظار إعادة التشغيل. يبحث MoOS عن نسخة موقّعة أحدث كل ليلة وحده؛ «حدّث MoOS» يبحث الآن ولا ينزّل شيئاً إن لم توجد نسخة أحدث.',
                      'No update is waiting for a restart. MoOS looks for a newer signed version every night by itself; '
                      '“Update MoOS” looks now and downloads nothing if there is none.'),
    'sy_restart_where': ('فتحت إعدادات MoOS ← التحديث: أعد التشغيل من هناك.',
                         'Opened MoOS Settings → Update: restart from there.'),
    'sy_opened': ('فُتح', 'Opened'),
    'sy_open_failed': ('تعذّر الفتح', 'Could not open it'),
    # the systemd result of the last nightly run, in words
    'sy_res_exit-code': ('انتهى بخطأ', 'ended with an error'),
    'sy_res_signal': ('أُوقف قبل أن ينتهي', 'was stopped before it finished'),
    'sy_res_core-dump': ('انهار', 'crashed'),
    'sy_res_timeout': ('تجاوز الوقت المسموح', 'timed out'),
    'sy_res_watchdog': ('توقف عن الاستجابة', 'stopped responding'),
    'sy_res_start-limit-hit': ('فشل مرات كثيرة متتالية', 'failed too many times in a row'),
    'sy_res_resources': ('لم تتوفر له الموارد', 'lacked the resources to start'),
    'sy_res_oom-kill': ('نفدت الذاكرة', 'ran out of memory'),
    # backend codes, in words
    'sy_err_moai_control_unreachable': ('خدمة النظام في Mo AI لا تجيب', "Mo AI's system service is not answering"),
    'sy_err_busy': ('عملية أخرى ما زالت تعمل', 'another operation is still running'),
    'sy_err_shape': ('ردّ لم يُفهم', 'an answer that could not be read'),
    'sy_err_route_not_allowed': ('مسار غير مسموح', 'a route that is not allowed'),
    'sy_err_unknown': ('أداة غير معروفة للخدمة', 'a tool the service does not know'),
    'sy_err_http': ('ردّت الخدمة بخطأ', 'the service answered with an error'),
    'sy_err_exit': ('رمز الخروج', 'exit code'),
    # health
    'sy_health': ('الفحص اليومي', 'Daily check'),
    'sy_last_check': ('آخر فحص', 'Last check'),
    'sy_never_checked': ('لم يُجرَ فحص بعد', 'No check has run yet'),
    'sy_check_now': ('افحص الآن', 'Check now'),
    'sy_scanning': ('أفحص الآن…', 'Checking now…'),
    'sy_seconds': ('ث', 's'),
    'sy_scan_done': ('انتهى الفحص', 'The check finished'),
    'sy_scan_slow': ('ما زال الفحص يعمل — قد يأخذ بضع دقائق؛ ستظهر نتيجته هنا حين ينتهي.',
                     'The check is still running — it can take a few minutes; its result will appear here when it finishes.'),
    'sy_scan_gave_up': ('لم ينتهِ الفحص بعد 15 دقيقة؛ اقرأ الحالة من جديد لاحقاً.',
                        'The check has not finished after 15 minutes; read everything again later.'),
    'sy_scan_no_report': ('انتهى الفحص دون تقرير جديد', 'The check ended without a new report'),
    'sy_scan_failed': ('تعذّر بدء الفحص', 'Could not start the check'),
    'sy_all_fine': ('كل شيء بخير', 'Everything looks fine'),
    'sy_attention': ('يحتاج انتباهك', 'Needs your attention'),
    'sy_incomplete': ('جزء من الفحص لم يكتمل', 'Part of the check could not complete'),
    'sy_no_report': ('لا يوجد فحص يومي بعد — افحص الآن', 'No daily check yet — run one now'),
    'sy_health_error': ('تعذّر قراءة الفحص اليومي', 'Could not read the daily check'),
    'sy_important': ('مهم', 'Important'),
    'sy_warnings': ('تحذيرات', 'Warnings'),
    'sy_notes': ('ملاحظات', 'Notes'),
    'sy_nothing': ('لا شيء يحتاج انتباهك.', 'Nothing needs your attention.'),
    'sy_security': ('الأمان', 'Security'),
    'sy_selinux': ('حماية SELinux', 'SELinux protection'),
    'sy_firewall': ('الجدار الناري', 'Firewall'),
    'sy_enforcing': ('مفعّلة', 'Enforcing'),
    'sy_permissive': ('تسجّل ولا تمنع', 'Permissive — logs, does not block'),
    'sy_se_disabled': ('معطّلة', 'Disabled'),
    'sy_fw_running': ('يعمل', 'Running'),
    'sy_fw_off': ('متوقف', 'Not running'),
    'sy_unknown': ('غير معروف', 'Unknown'),
    'sy_ports': ('منافذ مفتوحة للشبكة', 'Ports open to the network'),
    'sy_unrecognised': ('غير معروفة', 'unrecognised'),
    'sy_sev_important': ('مهم', 'Important'),
    'sy_sev_warning': ('تحذير', 'Warning'),
    'sy_sev_info': ('ملاحظة', 'Note'),
    'sy_fix': ('أصلحه', 'Fix it'),
    'sy_open': ('افتح', 'Open'),
    'sy_opens_page': ('يفتح صفحة MoOS التي تعالج هذا', 'Opens the MoOS page that handles this'),
    'sy_route_asks': ('يفتح إجراء MoOS؛ يسألك MoOS قبل أي تغيير', 'Opens a MoOS action; MoOS asks you before any change'),
    'sy_ask': ('اسأل ميرا', 'Ask Mira'),
    'sy_asked': ('كتبت السؤال في خانة الكتابة — أرسله متى شئت', 'The question is in the composer — send it when you like'),
    # self-check
    'sy_diag': ('الفحص الذاتي', 'Self-check'),
    'sy_diag_sub': ('يتأكد أن كل جزء من MoOS في مكانه ويعمل', 'Confirms every part of MoOS is in place and working'),
    'sy_diag_run': ('افحص مجدداً', 'Run again'),
    'sy_diag_running': ('أجري الفحص الذاتي…', 'Running the self-check…'),
    'sy_diag_ok': ('نجحت كل الفحوص', 'Every check passed'),
    'sy_diag_passed': ('ناجحة', 'Passed'),
    'sy_diag_broken': ('مشاكل', 'Problems'),
    'sy_diag_error': ('تعذّر إجراء الفحص الذاتي', 'Could not run the self-check'),
    'sy_diag_idle': ('لم يُجرَ الفحص الذاتي بعد', 'The self-check has not run yet'),
    'sy_diag_tools': ('فحوص وإصلاحات', 'Checks and repairs'),
    # device plan
    'sy_device': ('الأجهزة والتعريفات', 'Devices and drivers'),
    'sy_device_ready': ('جاهز', 'Ready'),
    'sy_device_attention': ('يحتاج انتباهاً', 'Attention'),
    'sy_device_action': ('يحتاج إجراءً', 'Action needed'),
    'sy_device_pending': ('ما زالت خطة الأجهزة قيد التحضير — اقرأ الحالة من جديد بعد دقيقة.',
                          'The device plan is still being prepared — read again in a minute.'),
    'sy_device_error': ('تعذّر قراءة خطة الأجهزة', 'Could not read the device plan'),
    'sy_graphics': ('الرسوميات', 'Graphics'),
    'sy_firmware': ('تحديثات البرامج الثابتة', 'Firmware updates'),
    'sy_firmware_none': ('لا تحديثات برامج ثابتة بالانتظار', 'No firmware updates waiting'),
    'sy_firmware_found': ('تحديث متاح · لا يمكن التراجع عنه', 'available · cannot be undone'),
    'sy_firmware_install': ('ثبّت تحديثات البرامج الثابتة…', 'Install firmware updates…'),
    'sy_advice': ('ملاحظات ونصائح', 'Problems and advice'),
    # repairs and tools
    'sy_tools': ('الإصلاح والأدوات', 'Repairs and tools'),
    'sy_tools_sub': ('الفحوص تعمل فوراً؛ الإصلاحات تسألك أولاً', 'Checks run at once; repairs ask you first'),
    'sy_badge_asks': ('يسألك أولاً', 'asks first'),
    'sy_badge_password': ('كلمة المرور', 'password'),
    'sy_running': ('يعمل الآن…', 'Running…'),
    'sy_running_already': ('هذه الأداة تعمل الآن؛ انتظر نتيجتها', 'This tool is running now; wait for its result'),
    'sy_waiting': ('ينتظر موافقتك على البطاقة', 'Waiting for your approval on the card'),
    'sy_done': ('تم', 'Done'),
    'sy_failed': ('تعذّر', 'Failed'),
    'sy_cancelled': ('أُلغي؛ لم يُنفَّذ شيء', 'Cancelled; nothing ran'),
    'sy_expired': ('انتهت مهلة الموافقة؛ لم يُنفَّذ شيء', 'Approval timed out; nothing ran'),
    'sy_card_gone': ('انتهى انتظار البطاقة دون خبر هنا — إن وافقت فتابِعها على البطاقة، وإلا فلم يُنفَّذ شيء',
                     'The card’s wait ended with no word here — if you approved it, follow it on the card; otherwise nothing ran'),
    'sy_still_running': ('ما زال يعمل في الخلفية؛ ستخبرك ميرا حين ينتهي', 'Still running in the background; Mira tells you when it ends'),
    'sy_result': ('النتيجة', 'Result'),
    'sy_hide': ('أخفِ النتيجة', 'Hide the result'),
    'sy_ask_failed': ('تعذّر وضع البطاقة أمامك', 'Could not put the card in front of you'),
    'sy_not_available': ('هذه الأداة غير موجودة في هذه النسخة من MoOS', 'This tool is not part of this MoOS version'),
    # playbooks
    'sy_skills': ('أدلة الإصلاح', 'Troubleshooting playbooks'),
    'sy_skills_sub': ('ما تتبعه ميرا خطوة خطوة على هذا النظام', 'What Mira follows step by step on this system'),
    'sy_skills_none': ('لا توجد أدلة إصلاح في هذه النسخة', 'No playbooks ship with this version'),
    'sy_skill_reading': ('أقرأ الدليل…', 'Reading the playbook…'),
    'sy_skill_walk': ('اتبعيه معي يا ميرا', 'Walk me through it'),
    'sy_skill_lead': ('تتبع ميرا هذا الدليل معك خطوة خطوة: تقرأ حالة جهازك أولاً، وكل إصلاح فيه يسألك قبل أن يبدأ.',
                      'Mira follows this playbook with you step by step: she reads your computer’s state first, and '
                      'every repair in it asks you before it starts.'),
    'sy_use_when': ('متى تستخدمه', 'When to use it'),
    'sy_skill_steps': ('اعرض الخطوات التي تتبعها ميرا', 'Show the steps Mira follows'),
    'sy_skill_hide': ('أخفِ الخطوات', 'Hide the steps'),
    'sy_close': ('أغلق', 'Close'),
    # tool titles (tiles, cards)
    'sy_t_list_failed_units': ('الخدمات المتعطّلة', 'Failed services'),
    'sy_t_check_drivers': ('فحص التعريفات', 'Check drivers'),
    'sy_t_inspect_boot': ('فحص الإقلاع', 'Boot check'),
    'sy_t_net_doctor': ('طبيب الشبكة', 'Network doctor'),
    'sy_t_gpu_report': ('تقرير كرت الشاشة', 'Graphics report'),
    'sy_t_fix_audio': ('إصلاح الصوت', 'Repair sound'),
    'sy_t_optimize_system': ('تنظيف وتحرير مساحة', 'Clean up and free space'),
    'sy_t_system_rollback': ('الرجوع للنسخة السابقة', 'Roll back MoOS'),
    'sy_t_system_update': ('تحديث MoOS', 'Update MoOS'),
    'sy_t_device_report': ('تقرير الجهاز', 'Device report'),
    'sy_t_support_bundle': ('حزمة الدعم', 'Support bundle'),
    'sy_t_update_firmware': ('تحديث البرامج الثابتة', 'Update firmware'),
    'sy_t_install_nvidia': ('تعريف NVIDIA الرسمي', 'NVIDIA driver'),
    'sy_t_update_apps': ('تحديث التطبيقات', 'Update apps'),
    'sy_t_check_system_update': ('البحث عن تحديث', 'Check for updates'),
    'sy_t_restart_computer': ('إعادة التشغيل', 'Restart'),
    'sy_t_setup_gaming': ('تجهيز الألعاب', 'Set up gaming'),
    'sy_t_setup_windows': ('تجهيز برامج ويندوز', 'Set up Windows programs'),
    'sy_t_setup_waydroid': ('تجهيز تطبيقات أندرويد', 'Set up Android apps'),
    'sy_t_remote_anywhere': ('التحكم عن بُعد من أي مكان', 'Remote control from anywhere'),
    # tool one-liners (tiles)
    'sy_d_list_failed_units': ('خدمات النظام والجلسة التي فشلت', 'System and session services that failed'),
    'sy_d_check_drivers': ('حالة كرت الشاشة والبرامج الثابتة', 'Graphics and firmware status'),
    'sy_d_inspect_boot': ('حالة الإقلاع وآخر الأخطاء', 'Boot state and recent errors'),
    'sy_d_net_doctor': ('فحوص ping وDNS وTailscale حيّة', 'Live ping, DNS and Tailscale tests'),
    'sy_d_gpu_report': ('الذاكرة والتعريف والبرامج التي تستخدمه', 'Memory, driver and what uses it'),
    'sy_d_fix_audio': ('يعيد تشغيل خدمات الصوت', 'Restarts the sound services'),
    'sy_d_optimize_system': ('بيئات تطبيقات وصور حاويات غير مستخدمة، وسجلات أقدم من 7 أيام',
                             'Unused app runtimes and container images, logs older than 7 days'),
    'sy_d_system_rollback': ('يُطبَّق عند إعادة التشغيل', 'Applies on restart'),
    'sy_d_system_update': ('نسخة موقّعة، تُطبَّق عند إعادة التشغيل', 'Signed image, applies on restart'),
    'sy_d_device_report': ('النسخة والتحديثات والموارد والملاحظات', 'Version, updates, resources, findings'),
    'sy_d_support_bundle': ('تقرير منقّح تشاركه لطلب المساعدة', 'A redacted report to share for help'),
    'sy_d_update_firmware': ('من صانعي الأجهزة · لا يمكن التراجع', 'From the device makers · cannot be undone'),
    'sy_d_install_nvidia': ('ينتقل إلى نسخة MoOS NVIDIA الموقّعة', 'Moves to the signed MoOS NVIDIA edition'),
    'sy_d_update_apps': ('كل التطبيقات المثبّتة', 'Every installed app'),
    # what a card says will happen (request_confirmation 'detail')
    'sy_cd_system_update': ('يبحث عن أحدث نسخة MoOS موقّعة، ويتحقق من توقيعها وينزّلها ويجهّزها. لا يتغيّر شيء الآن: '
                            'تُطبَّق عند إعادة التشغيل التالية، وتبقى النسخة الحالية {version} محفوظة للرجوع. يطلب كلمة المرور.',
                            'Looks for the newest signed MoOS version, verifies its signature, downloads and prepares it. '
                            'Nothing changes now: it applies on the next restart, and the current version {version} stays '
                            'kept for rollback. Asks for your password.'),
    'sy_cd_system_rollback': ('يجعل النسخة المحفوظة {version} هي التي تُقلع في المرة القادمة. تُطبَّق عند إعادة التشغيل، '
                              'وتبقى النسخة الحالية محفوظة لتعود إليها. يطلب كلمة المرور.',
                              'Makes the kept version {version} the one that starts next time. Applies on the next restart; '
                              'the current version stays kept so you can come back. Asks for your password.'),
    'sy_cd_update_firmware': ('يثبّت تحديثات البرامج الثابتة من صانعي الأجهزة (fwupd). {found} يثبّت التحديث ما يعرضه صانعو '
                              'الأجهزة لحظة تشغيله، وقد يختلف عن هذه القائمة. لا يمكن التراجع عن تحديث البرامج الثابتة. '
                              'أبقِ الكمبيوتر موصولاً بالكهرباء؛ بعض الأجهزة تتحدّث أثناء إعادة التشغيل. يطلب كلمة المرور.',
                              'Installs firmware updates from the device makers (fwupd). {found} The update installs whatever '
                              'the device makers offer when it runs, which can differ from this list. A firmware update cannot '
                              'be undone. Keep the computer plugged in; some devices update during a restart. Asks for your password.'),
    'sy_cd_firmware_found': ('وجد فحص الأجهزة عند {time} ({count}): {list}.', 'The device check at {time} found {count}: {list}.'),
    'sy_cd_firmware_more': ('و{n} غيرها', 'and {n} more'),
    'sy_cd_firmware_any': ('لم يسرد فحص الأجهزة أي جهاز.', 'The device check listed no devices.'),
    'sy_cd_install_nvidia': ('ينقل هذا الكمبيوتر إلى نسخة MoOS NVIDIA الموقّعة مع تعريف NVIDIA الرسمي. تُطبَّق عند إعادة '
                             'التشغيل، وتبقى النسخة الحالية محفوظة للرجوع. يطلب كلمة المرور.',
                             'Moves this computer to the signed MoOS NVIDIA edition with the official NVIDIA driver. Applies '
                             'on the next restart; the current version stays kept for rollback. Asks for your password.'),
    'sy_cd_fix_audio': ('يعيد تشغيل خدمات الصوت (PipeWire). ينقطع الصوت لحظة، وقد تحتاج لإعادة فتح تطبيق كان يشغّل صوتاً.',
                        'Restarts the sound services (PipeWire). Sound drops for a moment; an app that was playing may '
                        'need reopening.'),
    'sy_cd_optimize_system': ('يحذف بيئات التطبيقات غير المستخدمة وصور الحاويات غير المستخدمة، ويقلّص سجلات النظام الأقدم '
                              'من 7 أيام لتحرير مساحة. لا يلمس ملفاتك ولا صورك ولا تطبيقاتك المثبّتة. تقليص سجلات النظام '
                              'يطلب كلمة المرور.',
                              'Removes unused app runtimes and unused container images, and trims system logs older than '
                              '7 days to free space. Your files, photos and installed apps are not touched. Trimming the '
                              'system logs asks for your password.'),
    'sy_cd_update_apps': ('يحدّث كل التطبيقات المثبّتة من المتجر.', 'Updates every installed app from the store.'),
    'sy_cd_restart_computer': ('يعيد تشغيل الكمبيوتر الآن لتطبيق التحديث الجاهز. احفظ عملك أولاً.',
                               'Restarts the computer now to apply the ready update. Save your work first.'),
    'sy_cd_generic': ('{title} — لا يبدأ قبل موافقتك.', '{title} — nothing starts before you approve.'),
    'sy_this_version': ('الحالية', 'in use now'),
    # what "Ask Mira" puts in the composer
    'sy_q_finding': ('ميرا، فحص MoOS اليومي وجد: «{title}»{detail}. اشرحي لي ماذا يعني وساعديني أصلحه خطوة خطوة.',
                     'Mira, MoOS’s daily check found: “{title}”{detail}. Explain what it means and help me fix it step by step.'),
    'sy_q_device': ('ميرا، خطة الأجهزة في MoOS تقول: «{title}»{detail}. ماذا يعني هذا وكيف نصلحه؟',
                    'Mira, MoOS’s device plan says: “{title}”{detail}. What does it mean and how do we fix it?'),
    'sy_q_issue': ('ميرا، الفحص الذاتي لـ MoOS وجد مشكلة: «{title}». اشرحيها لي وساعديني أصلحها.',
                   'Mira, MoOS’s self-check found a problem: “{title}”. Explain it and help me fix it.'),
    'sy_q_skill': ('ميرا، اتبعي معي دليل «{title}» خطوة خطوة.', 'Mira, walk me through the “{title}” playbook step by step.'),
    # playbook titles (the shipped front matter's title_ar / title_en)
    'sy_sk_app-wont-start': ('تطبيق لا يعمل أو يُغلق فوراً', 'An app does not start, or closes at once'),
    'sy_sk_bluetooth-device': ('توصيل جهاز بلوتوث أو إصلاحه', 'Connect or repair a Bluetooth device'),
    'sy_sk_boot-problems': ('إقلاع بطيء أو أخطاء عند التشغيل', 'Slow startup, or errors while starting'),
    'sy_sk_disk-full': ('القرص ممتلئ أو المساحة تنفد', 'The disk is full, or space is running out'),
    'sy_sk_failed-service': ('خدمة في النظام تعطّلت', 'A system service has failed'),
    'sy_sk_gaming-and-windows-apps': ('الألعاب وبرامج ويندوز وتطبيقات أندرويد', 'Games, Windows programs and Android apps'),
    'sy_sk_graphics-and-nvidia': ('مشاكل الرسوميات وبطاقات NVIDIA', 'Graphics problems and NVIDIA cards'),
    'sy_sk_install-an-app': ('تثبيت تطبيق من Mo Store أو من ملف منزَّل', 'Install an app, from Mo Store or a downloaded file'),
    'sy_sk_no-internet': ('لا يوجد إنترنت، أو الاتصال غير مستقر', 'No internet, or an unstable connection'),
    'sy_sk_no-sound': ('لا يوجد صوت، أو الصوت يخرج من جهاز خاطئ', 'No sound, or sound from the wrong device'),
    'sy_sk_oracle-cloud-workstation': ('حاسوب سحابي عبر Mo PC Remote: بطيء أو صورته غير واضحة',
                                       'A cloud computer through Mo PC Remote: slow, or an unclear picture'),
    'sy_sk_slow-system': ('الجهاز بطيء أو يتجمّد', 'The computer is slow or freezes'),
    'sy_sk_update-and-rollback': ('تحديث MoOS، أو الرجوع بعد تحديث سيّئ', 'Update MoOS, or go back after a bad update'),
}

# moai-do verbs (the old moos://do/<verb> routes and /diagnose's fix ids) → Mo AI tools.
DO_VERBS = {
    'diagnose-services': 'list_failed_units', 'check-drivers': 'check_drivers', 'inspect-boot': 'inspect_boot',
    'net-doctor': 'net_doctor', 'gpu-report': 'gpu_report', 'fix-audio': 'fix_audio', 'optimize': 'optimize_system',
    'rollback': 'system_rollback', 'update': 'system_update', 'update-apps': 'update_apps',
    'install-nvidia': 'install_nvidia', 'update-firmware': 'update_firmware', 'device-report': 'device_report',
    'support-bundle': 'support_bundle', 'setup-gaming': 'setup_gaming', 'setup-windows': 'setup_windows',
    'setup-waydroid': 'setup_waydroid', 'remote-anywhere': 'remote_anywhere',
}
REPAIRS = ('fix_audio', 'optimize_system', 'check_drivers', 'gpu_report', 'net_doctor', 'inspect_boot',
           'device_report', 'support_bundle', 'update_firmware', 'install_nvidia')
GLYPHS = {
    'list_failed_units': 'alert', 'check_drivers': 'chip', 'inspect_boot': 'power', 'net_doctor': 'wifi',
    'gpu_report': 'grid', 'fix_audio': 'volume', 'optimize_system': 'bolt', 'system_rollback': 'clock',
    'system_update': 'download', 'device_report': 'monitor', 'support_bundle': 'package',
    'update_firmware': 'memory', 'install_nvidia': 'rocket', 'update_apps': 'apps',
}
CHECK_TOOL = 'check_system_update'          # used when a MoOS image declares it
RESTART_TOOL = 'restart_computer'           # used when a MoOS image declares it
# The only tools a tile or chip of this page may name (runTool). Anything else is not this page's.
PAGE_TOOLS = frozenset(REPAIRS) | frozenset(DO_VERBS.values()) | {CHECK_TOOL, RESTART_TOOL}
# A change that ends by changing what boots or what is installed: its end is read back.
READ_BACK = ('system_update', 'system_rollback', 'install_nvidia', 'update_firmware', 'update_apps')
# moai-do escalates inside these (optimize: `run_priv journalctl --vacuum-time`). This image's schema
# declares optimize_system privileged_confirm; the set is kept for installed schemas that still say
# user_confirm, so the tile never hides the password prompt the owner will see.
ALSO_PASSWORD = frozenset({'optimize_system'})
UPDATE_STATES = ('current', 'available', 'replace-staged', 'staged', 'blocked-downgrade', 'busy', 'unsigned', 'unknown')
ROUTES = {
    'recovery': 'moos://settings/recovery', 'whats_new': 'moos://settings/whats-new',
    'update': 'moos://settings/update', 'updater': 'moos://app/updater',
}
INCOMPLETE = 'check-incomplete-'
SCAN_POLL_MS = 3000
SCAN_LIMIT_S = 90                 # after this, "still running — it can take a few minutes"
SCAN_GIVE_UP_S = 900              # moai-control's own limit for one moos-health run
DIAG_FRESH_S = 600
BADGE_EVERY_MS = 20 * 60 * 1000
OUTPUT_LIMIT = 12000
CARD_TTL_S = 180                  # the controller's CONFIRM_TTL, used only if a card carries no expiry
CARD_GRACE_S = 5                  # after a card's expiry, how long the controller's word may take
FIRMWARE_LISTED = 10              # devices named on the card before "and N more"
SKILL_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,60}')

# The page keeps only the release tag (with its architecture) for an older moai_tools; the base's
# names live in ONE place, moai_tools (clean_identity, built on scrub_identity).
_FC_TAG = re.compile(r'\.fc\d{2,3}(?:\.(?:x86_64|aarch64|noarch|i686))?(?![\w])')
_UPDATE_LINE = re.compile(r'^MOOS_UPDATE\s+state=(\S+)(.*)$', re.M)
_ARABIC = re.compile(r'[؀-ۿ]')
_LATIN = re.compile(r'[A-Za-z]')


def clean(text):
    """Backend text as the owner may read it: kernels as numbers, no base distribution's name."""
    shared = getattr(moai_tools, 'clean_identity', None)
    if callable(shared):
        return shared(text)
    return moai_tools.scrub_identity(_FC_TAG.sub('', '' if text is None else str(text)))


def kernel(value):
    return clean(value).split('.fc')[0].strip()


def halves(text):
    """Mo AI's services write "عربي | English"; both halves, cleaned (one language twice when unsplit)."""
    text = clean(text).strip()
    if ' | ' in text:
        ar, en = text.split(' | ', 1)
        return ar.strip(), en.strip()
    return text, text


def owner_lines(text):
    """moai-do's bilingual output → (arabic lines, english lines), without the machine line.

    A line is "✓ عربي | English", or one language on its own line (the next line carries the other).
    A leading mark (✓ ⚠ ✗ ⬆ ■ …) belongs to both halves; an Arabic half that stops at its label
    ("الحالي | Current: MoOS 44.1") borrows the English half's value after the colon."""
    ar_lines, en_lines = [], []
    for raw in clean(text).splitlines():
        line = raw.strip()
        if not line or line.startswith('MOOS_UPDATE'):
            continue
        mark = re.match(r'^([^\w\s]+)\s+', line)
        prefix = mark.group(1) + ' ' if mark else ''
        body = line[mark.end():] if mark else line
        if ' | ' in body:
            ar, en = (part.strip() for part in body.split(' | ', 1))
            if ':' in en and ':' not in ar and not re.search(r'\d', ar):
                ar = ar + ':' + en.split(':', 1)[1]
            ar_lines.append(prefix + ar)
            en_lines.append(prefix + en)
        elif _ARABIC.search(body) and not _LATIN.search(re.sub(r'MoOS|NVIDIA|ARM', '', body)):
            ar_lines.append(line)
        elif _ARABIC.search(body):
            ar_lines.append(line)
            en_lines.append(line)
        else:
            en_lines.append(line)
    return '\n'.join(ar_lines), '\n'.join(en_lines)


def parse_update_check(output):
    """check_system_update's last line `MOOS_UPDATE state=… edition=… current=… latest=… staged=…`."""
    found = _UPDATE_LINE.findall(str(output or ''))
    if not found:
        return {}
    state, rest = found[-1]
    fields = {key: ('' if value == '-' else clean(value)) for key, value in re.findall(r'(\w+)=(\S+)', rest)}
    return {'state': state if state in UPDATE_STATES else 'unknown', 'latest': fields.get('latest', ''),
            'staged': fields.get('staged', ''), 'current': fields.get('current', ''), 'edition': fields.get('edition', '')}


def edition(image):
    """An image reference → its repository name (moos, moos-nvidia, …): no registry, tag or digest."""
    name = str(image or '').strip().rsplit('/', 1)[-1]
    return clean(re.split(r'[@:]', name, maxsplit=1)[0]).strip() if name else ''


def parse_os(output):
    """os_state's lines → {'booted'|'staged'|'kept': {version, signed, edition, digest}} (first of each)."""
    roles = {'booted': 'booted', 'staged': 'staged', 'kept for rollback': 'kept'}
    found = {}
    for line in str(output or '').splitlines():
        match = re.match(r'\s*(booted|staged|kept for rollback):\s*(.*)$', line)
        if not match or roles[match.group(1)] in found:
            continue
        parts = [p.strip() for p in match.group(2).split('·')]
        version = re.sub(r'^version\s+', '', parts[0]) if parts else ''
        image = parts[2] if len(parts) > 2 else ''
        image = '' if image == 'unknown image' else image
        found[roles[match.group(1)]] = {
            'version': '' if version == '?' else clean(version),
            'signed': len(parts) > 1 and parts[1].startswith('signed'),
            'edition': edition(image),
            'digest': image.split('@sha256:', 1)[1][:12] if '@sha256:' in image else '',
        }
    return found


def when(stamp, now=None):
    """An ISO time → {'day': today|yesterday|date, 'date': 'YYYY-MM-DD', 'time': 'HH:MM'} in local time."""
    try:
        moment = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return {}
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone()
    today = (now or datetime.now().astimezone()).date()
    days = (today - local.date()).days
    return {'day': 'today' if days == 0 else 'yesterday' if days == 1 else 'date',
            'date': local.strftime('%Y-%m-%d'), 'time': local.strftime('%H:%M')}


def gpu_name(raw):
    """lspci's line → "NVIDIA GeForce RTX 2080 SUPER" (every GPU, joined)."""
    names = []
    for line in str(raw or '').splitlines():
        line = line.strip()
        if not line or line == 'unavailable':
            continue
        body = line.split(']: ', 1)[1] if ']: ' in line else line
        body = re.sub(r'\s*\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]', '', body)
        body = re.sub(r'\s*\(rev [^)]*\)', '', body).strip()
        vendor = ('NVIDIA' if 'NVIDIA' in body.upper() else 'AMD' if re.search(r'\bAMD\b|\bATI\b|Advanced Micro', body)
                  else 'Intel' if 'INTEL' in body.upper() else '')
        model = re.search(r'\[([^\]]+)\]\s*$', body)
        if model:                      # the marketing name lspci puts last, in brackets
            names.append(f'{vendor} {model.group(1)}'.strip())
        else:
            names.append(re.sub(r'\s+(Corporation|Inc\.?|Co\.)\b', '', body).strip())
    return clean(' + '.join(names))


def _reason(summary):
    """The controller's card line "Failed Update MoOS (exit 1)" → "exit 1" (its reason only)."""
    match = re.search(r'\(([^()]{1,80})\)\s*$', str(summary or ''))
    return clean(match.group(1)) if match else ''


class SystemPage(Page):
    def __init__(self, host, parent=None):
        self._inflight = set()
        self._cards = {}                      # confirmation card id → {'name', 'expires' (epoch seconds)}
        self._diag_at = 0.0
        self._scan = {'active': False, 'generated': '', 'started': 0.0}
        self._generated = ''                  # generated_at of the report on screen
        self._checking = False                # "Check for updates" (no executor check) waits for its reads
        self._kernel_live = False             # /scan's live kernel outranks the daily report's copy
        self._clock = time.monotonic
        self._wall = time.time                # the cards' clock (pending.py stamps them with time.time)
        super().__init__(host, parent)
        self._poll = QTimer(self, interval=SCAN_POLL_MS, timeout=self._poll_health)
        self._expiry = QTimer(self, interval=1000, timeout=self._expire_cards)
        self._badge_timer = QTimer(self, interval=BADGE_EVERY_MS, timeout=self._read_health)
        if not TEST_MODE:
            # The rail's badge is useful before the page is ever opened: read the daily report soon
            # after start, then again every 20 minutes (a file read; the check itself is daily).
            QTimer.singleShot(4000, self._read_health)
            self._badge_timer.start()

    # ── state ───────────────────────────────────────────────────────
    def initial(self):
        names = moai_tools.names()
        return {
            'loading': False, 'checking': False, 'sample': False,
            'booted': {}, 'staged': {}, 'kept': {}, 'kernel': '', 'os_state': 'idle',
            'update': {'known': False, 'staged': False, 'staged_version': '', 'nightly': None,
                       'last_result': '', 'last_run': {}, 'app_updates': 0, 'check': {}},
            'note_key': '', 'note_tone': 'info',
            'health': {'state': 'unknown', 'important': 0, 'warning': 0, 'info': 0, 'incomplete': 0,
                       'checked': {}, 'error': ''},
            'scan': {'running': False, 'elapsed': 0, 'key': '', 'error': '', 'tone': 'info'},
            'findings': [],
            'security': self._security(None, []),
            'diag': {'state': 'idle', 'healthy': False, 'ok': 0, 'fail': 0, 'issues': [], 'fixes': [], 'error': ''},
            'device': {'state': 'idle', 'verdict': '', 'gpu': '', 'driver_ar': '', 'driver_en': '',
                       'driver_ok': False, 'problems': [], 'firmware': [], 'nvidia_active': False,
                       'nvidia_offer': False, 'error': '', 'checked': ''},
            'tiles': self._tiles(names, nvidia_offer=False),
            'outputs': {},
            'skills': [], 'skills_state': 'idle', 'skill': {'id': '', 'state': '', 'text': '', 'error': ''},
            'can_check': CHECK_TOOL in names, 'can_restart': RESTART_TOOL in names,
            'badge': '',
        }

    @staticmethod
    def _tile(name):
        category = (moai_tools.meta(name) or {}).get('category', '')
        return {'name': name, 'icon': GLYPHS.get(name, 'wrench'), 'category': category,
                'password': category == 'privileged_confirm' or name in ALSO_PASSWORD}

    def _tiles(self, names, nvidia_offer):
        return [self._tile(n) for n in REPAIRS if n in names and (n != 'install_nvidia' or nvidia_offer)]

    def _set_output(self, name, **fields):
        """One tool's state and output. `origin` says where the owner asked (hero, tools, diag,
        finding:<id>, device:<id>): the result is shown there, under what he pressed. `key` is a word
        of this page (translated in QML); `summary` is a backend's reason, shown as it came."""
        outputs = dict(self._state.get('outputs') or {})
        previous = outputs.get(name) or {}
        entry = {'state': '', 'text': '', 'text_ar': '', 'text_en': '', 'summary': '', 'key': '', 'arg': '',
                 'origin': previous.get('origin', 'tools')}
        entry.update({k: v for k, v in fields.items() if v is not None})
        entry['at'] = datetime.now().strftime('%H:%M')
        outputs[name] = entry
        self.update(outputs=outputs)

    def _phase(self, name):
        return (self._state['outputs'].get(name) or {}).get('state', '')

    # ── reads (each on a thread; `loading` while any is out) ─────────
    def _read(self, tag, fn, *args):
        if tag in self._inflight:          # the same read is already out; its answer will come
            return
        self._inflight.add(tag)
        if not self._state.get('loading'):
            self.update(loading=True)
        self.run(tag, fn, *args)

    def _deliver(self, tag, result):
        self._inflight.discard(tag)
        try:
            super()._deliver(tag, result)
        finally:
            loading = bool(self._inflight)
            if loading != self._state.get('loading'):
                self.update(loading=loading)

    @Slot()
    def refresh(self):
        """Read everything the page shows (the self-check only when older than 10 minutes)."""
        self._read_state()
        self._read('plan', moai_tools.get, '/scan', 40)
        if self._clock() - self._diag_at > DIAG_FRESH_S or self._state['diag']['state'] in ('idle', 'error'):
            self.runDiagnosis()
        if not self._state.get('skills'):
            self._read('skills', moai_tools.execute, 'list_skills', {})

    def _read_state(self):
        if self._state.get('os_state') != 'running':
            self.update(os_state='running')
            self._read('os', moai_tools.execute, 'os_state', {})
        self._read_health()

    def _read_health(self):
        if 'health' not in self._inflight:
            self._read('health', moai_tools.get, '/health', 20)

    # ── this MoOS ───────────────────────────────────────────────────
    def on_os(self, _tag, result):
        result = result if isinstance(result, dict) else {}
        if result.get('status') != 'ok':
            self.update(os_state='error')
            self._after_check()
            return
        deployments = parse_os(result.get('output'))
        booted, staged = deployments.get('booted', {}), deployments.get('staged', {})
        update = dict(self._state['update'])
        if booted:                         # the live deployments outrank the daily report's copy
            update.update(staged=bool(staged), staged_version=staged.get('version', ''))
        self.update(os_state='ok' if booted else 'error', booted=booted, staged=staged,
                    kept=deployments.get('kept', {}), update=update)
        self._after_check()
        self._badge()

    def on_health(self, _tag, body):
        body = body if isinstance(body, dict) else {'error': 'shape'}
        if body.get('error') and 'report' not in body:
            self.update(health={**self.initial()['health'], 'state': 'error', 'error': str(body['error'])})
            self._after_check()
            return
        self._apply_report(body.get('report'), bool(body.get('scanning')))
        if body.get('scanning') and not self._scan['active']:
            self._follow_scan()            # a check already running (another window's): show its end
            self._poll.start()
        self._after_check()

    def _apply_report(self, report, scanning=False):
        if not isinstance(report, dict):
            self.update(health={**self.initial()['health'], 'state': 'none'}, findings=[])
            self._badge()
            return
        self._generated = str(report.get('generated_at') or '')
        system = report.get('system') if isinstance(report.get('system'), dict) else {}
        updates = report.get('updates') if isinstance(report.get('updates'), dict) else {}
        summary = report.get('summary') or {}
        raw = [f for f in (report.get('findings') or []) if isinstance(f, dict)]
        findings = [self._item(f, 'finding') for f in raw[:14]]
        real = [f for f in raw if not str(f.get('id', '')).startswith(INCOMPLETE)]
        counts = {sev: sum(1 for f in real if f.get('severity') == sev) for sev in ('important', 'warning', 'info')}
        status = summary.get('status')
        health = {'state': status if status in ('ok', 'attention', 'action-needed', 'incomplete') else 'unknown',
                  **counts, 'incomplete': len(raw) - len(real),
                  'checked': when(report.get('generated_at')), 'error': '', 'scanning': scanning}
        if self._state.get('os_state') == 'ok':      # read live from the deployments: that wins
            staged = bool(self._state['staged'])
            staged_version = self._state['staged'].get('version', '') if staged else ''
        else:
            staged = bool(summary.get('system_update_staged') or system.get('staged'))
            staged_version = clean(system.get('staged') or '')
        # systemd answers Result=success for a unit that never ran (and resets it on every boot):
        # a success is "a run succeeded" only with the run's own time (moos-health's last_nightly_run).
        update = {**self._state['update'], 'known': True,
                  'staged': staged,
                  'staged_version': staged_version,
                  'nightly': updates.get('nightly_system_update'),
                  'last_result': str(updates.get('last_nightly_result') or ''),
                  'last_run': when(updates['last_nightly_run']) if updates.get('last_nightly_run') else {},
                  'app_updates': int(summary.get('app_updates') or len(updates.get('apps') or []) or 0)}
        fields = dict(health=health, findings=findings, update=update,
                      security=self._security(report.get('security'), raw))
        if not self._kernel_live and system.get('kernel'):
            fields['kernel'] = kernel(system['kernel'])
        if not self._state['booted'] and system.get('version'):
            fields['booted'] = {'version': clean(system['version']), 'signed': bool(system.get('signed')),
                                'edition': edition(system.get('image')), 'digest': ''}
        self.update(**fields)
        self._badge()

    @staticmethod
    def _security(sec, findings):
        """The report's security section. A probe that could not answer is unknown, never zero."""
        if not isinstance(sec, dict) or not sec:
            return {'known': False, 'selinux': '', 'selinux_tone': 'off', 'firewall': '', 'firewall_tone': 'off',
                    'ports': 0, 'ports_known': False, 'unknown_ports': 0}
        if sec.get('error'):
            return {'known': True, 'selinux': '', 'selinux_tone': 'off', 'firewall': 'unknown', 'firewall_tone': 'off',
                    'ports': 0, 'ports_known': False, 'unknown_ports': 0}
        selinux = str(sec.get('selinux') or '')
        firewall = sec.get('firewall')
        ports, unknown = set(), set()
        for item in sec.get('open_ports') or []:
            if not isinstance(item, dict):
                continue
            port = (item.get('protocol'), str(item.get('address', '')).rpartition(':')[2])
            ports.add(port)
            if not item.get('known'):
                unknown.add(port)
        ports_known = not any(str(f.get('id', '')) == INCOMPLETE + 'ports' for f in findings or [])
        return {'known': True, 'selinux': selinux if selinux in ('Enforcing', 'Permissive', 'Disabled') else '',
                'selinux_tone': 'ok' if selinux == 'Enforcing' else 'error' if selinux in ('Permissive', 'Disabled') else 'off',
                'firewall': 'running' if firewall == 'running' else 'off' if firewall in ('not running', 'failed')
                else 'unknown',
                'firewall_tone': 'ok' if firewall == 'running' else 'error' if firewall in ('not running', 'failed') else 'off',
                'ports': len(ports) if ports_known else 0, 'ports_known': ports_known,
                'unknown_ports': len(unknown) if ports_known else 0}

    def _fix(self, action):
        """A finding's action → how the page carries it out: a Mo AI tool, or an allowlisted route."""
        action = str(action or '').strip()
        if action.startswith('moos://do/'):
            tool = DO_VERBS.get(action[len('moos://do/'):])
            if tool and tool in moai_tools.names():
                return {'fix': 'tool', 'fix_tool': tool, 'fix_route': '', 'fix_page': False}
        elif moos_routes.allowed(action):
            return {'fix': 'route', 'fix_tool': '', 'fix_route': action,
                    'fix_page': action.startswith(('moos://settings/', 'moos://app/'))}
        return {'fix': '', 'fix_tool': '', 'fix_route': '', 'fix_page': False}

    def _item(self, raw, kind):
        title_ar, title_en = halves(raw.get('title'))
        detail_ar, detail_en = halves(raw.get('detail'))
        severity = raw.get('severity') if raw.get('severity') in ('important', 'warning', 'info') else 'info'
        return {'id': str(raw.get('id') or ''), 'kind': kind, 'severity': severity,
                'incomplete': str(raw.get('id', '')).startswith(INCOMPLETE),
                'title_ar': title_ar, 'title_en': title_en, 'detail_ar': detail_ar, 'detail_en': detail_en,
                **self._fix(raw.get('action') if kind == 'finding' else raw.get('url'))}

    def _badge(self):
        """The rail's badge: important findings and real warnings; a dot for an update waiting to apply."""
        count = sum(1 for f in self._state['findings']
                    if f['severity'] in ('important', 'warning') and not f['incomplete'])
        badge = str(count) if count else ('•' if self._state['update'].get('staged') else '')
        if badge != self._state.get('badge'):
            self.update(badge=badge)

    # ── the hero's actions ──────────────────────────────────────────
    @Slot()
    def updateSystem(self):
        self._run_tool('system_update', 'hero')

    @Slot()
    def rollBack(self):
        self._roll_back('hero')

    def _roll_back(self, origin):
        if not self._state.get('kept'):
            self.host.toast.emit('info', self.text('sy_no_kept'))
            return
        self._run_tool('system_rollback', origin)

    @Slot()
    def checkUpdates(self):
        """The executor's own check when this image declares one (beside a fresh read of the
        deployments and the report); otherwise read those two again and say what they show."""
        if CHECK_TOOL in moai_tools.names():
            self._read_state()
            self._run_tool(CHECK_TOOL, 'hero')
            return
        self._checking = True
        self.update(checking=True, note_key='sy_checking', note_tone='info')
        self._read_state()

    def _after_check(self):
        if not self._checking or {'os', 'health'} & self._inflight:
            return
        self._checking = False
        staged = self._state['update'].get('staged')
        self.update(checking=False, note_key='sy_check_staged' if staged else 'sy_check_none',
                    note_tone='warn' if staged else 'ok')

    @Slot()
    def restartNow(self):
        if RESTART_TOOL in moai_tools.names():
            self._run_tool(RESTART_TOOL, 'hero')
            return
        if self._open(ROUTES['update'], toast=False):
            self.update(note_key='sy_restart_where', note_tone='info')

    @Slot(str)
    def openPage(self, key):
        """A fixed MoOS page: recovery, whats_new, update, updater."""
        if key in ROUTES:
            self._open(ROUTES[key])

    def _open(self, url, toast=True):
        result = moos_routes.open_route(url)
        if result.get('status') == 'ok':
            if toast:
                self.host.toast.emit('ok', self.text('sy_opened'))
            return True
        self.host.toast.emit('error', self.text('sy_open_failed') + f" ({result.get('error', '')})")
        return False

    # ── the daily check, now ────────────────────────────────────────
    @Slot()
    def scanHealth(self):
        if self._scan['active']:
            return
        self._follow_scan()
        self._read('scan:start', moai_tools.post, '/health/scan', {})

    def _follow_scan(self):
        """Watch for a report newer than the one on screen (every 3 s, for up to 15 minutes)."""
        self._scan = {'active': True, 'generated': self._generated, 'started': self._clock()}
        self.update(scan={'running': True, 'elapsed': 0, 'key': '', 'error': '', 'tone': 'info'})

    def on_scan(self, tag, body):
        body = body if isinstance(body, dict) else {'error': 'shape'}
        if tag == 'scan:start':
            if body.get('error'):
                self._scan['active'] = False
                self.update(scan={'running': False, 'elapsed': 0, 'tone': 'error', 'key': 'sy_scan_failed',
                                  'error': str(body['error'])})
                return
            self._poll.start()
            return
        # scan:poll
        elapsed = int(self._clock() - self._scan['started'])
        report = body.get('report') if isinstance(body.get('report'), dict) else None
        generated = (report or {}).get('generated_at', '')
        if report is not None and not body.get('scanning') and generated and generated != self._scan.get('generated'):
            self._stop_scan()
            self._apply_report(report)
            self.update(scan={'running': False, 'elapsed': elapsed, 'tone': 'ok', 'key': 'sy_scan_done', 'error': ''})
            self.host.toast.emit('ok', self.text('sy_scan_done'))
            return
        if not body.get('error') and body.get('scanning') is False:
            # moai-control's scan is over and the report on disk is the one already shown.
            self._stop_scan()
            self.update(scan={'running': False, 'elapsed': elapsed, 'tone': 'error', 'key': 'sy_scan_no_report', 'error': ''})
            return
        if elapsed >= SCAN_GIVE_UP_S:
            self._stop_scan()
            self.update(scan={'running': False, 'elapsed': elapsed, 'tone': 'warn', 'key': 'sy_scan_gave_up', 'error': ''})
            return
        slow = elapsed >= SCAN_LIMIT_S
        self.update(scan={'running': True, 'elapsed': elapsed, 'tone': 'warn' if slow else 'info',
                          'key': 'sy_scan_slow' if slow else '', 'error': ''})

    def _poll_health(self):
        if not self._scan['active'] or 'scan:poll' in self._inflight:
            return
        self._read('scan:poll', moai_tools.get, '/health', 10)

    def _stop_scan(self):
        self._poll.stop()
        self._scan['active'] = False

    # ── self-check ──────────────────────────────────────────────────
    @Slot()
    def runDiagnosis(self):
        if 'diag' in self._inflight:
            return
        self.update(diag={**self._state['diag'], 'state': 'running', 'error': ''})
        self._read('diag', moai_tools.get, '/diagnose', 60)

    def on_diag(self, _tag, body):
        body = body if isinstance(body, dict) else {'error': 'shape'}
        if body.get('error') and 'issues' not in body:
            self.update(diag={**self.initial()['diag'], 'state': 'error', 'error': str(body['error'])})
            return
        self._diag_at = self._clock()
        names = moai_tools.names()
        issues = []
        for index, text in enumerate(body.get('issues') or []):
            ar, en = halves(text)
            issues.append({'id': str(index), 'kind': 'issue', 'severity': 'warning', 'incomplete': False,
                           'title_ar': ar, 'title_en': en, 'detail_ar': '', 'detail_en': '',
                           'fix': '', 'fix_tool': '', 'fix_route': '', 'fix_page': False})
        fixes, seen = [], set()
        for fix in body.get('fixes') or []:
            tool = DO_VERBS.get(str((fix or {}).get('id', '')))
            if tool and tool in names and tool not in seen:
                seen.add(tool)
                fixes.append(self._tile(tool))
        self.update(diag={'state': 'done', 'healthy': bool(body.get('healthy')), 'ok': int(body.get('ok') or 0),
                          'fail': int(body.get('fail') or 0), 'issues': issues, 'fixes': fixes, 'error': ''})

    # ── device plan ─────────────────────────────────────────────────
    def on_plan(self, _tag, body):
        body = body if isinstance(body, dict) else {'error': 'shape'}
        if body.get('kernel'):             # live (uname), where the daily report's copy can be a day old
            self._kernel_live = True
            self.update(kernel=kernel(body['kernel']))
        if body.get('error') and 'device_plan' not in body:
            self.update(device={**self.initial()['device'], 'state': 'error', 'error': str(body['error'])})
            return
        plan = body.get('device_plan')
        if not isinstance(plan, dict):
            self.update(device={**self.initial()['device'], 'state': 'pending' if body.get('device_plan_pending') else 'error'})
            return
        driver = str(plan.get('driver') or '')
        vendor = plan.get('gpu_vendor')
        active = vendor == 'nvidia' and 'nvidia' in driver
        offer = vendor == 'nvidia' and not active and str(plan.get('architecture', '')) in ('x86_64', 'amd64')
        driver_en = clean(plan.get('driver_status') or '')
        firmware = [clean(f) for f in (plan.get('firmware_updates') or []) if f]
        device = {'state': 'done', 'verdict': plan.get('health') if plan.get('health') in ('ready', 'attention', 'action-needed') else '',
                  'gpu': gpu_name(plan.get('gpu')), 'driver_en': driver_en,
                  'driver_ar': clean(plan.get('driver_status_ar') or '') or driver_en,
                  'driver_ok': active or (vendor != 'nvidia' and driver not in ('', 'unavailable')),
                  # Pending firmware has its own list (devices, versions, its button): not a second row here.
                  'problems': [self._item(a, 'device') for a in (plan.get('actions') or [])
                               if isinstance(a, dict) and not (a.get('id') == 'firmware-update' and firmware)],
                  'firmware': firmware,
                  'nvidia_active': active, 'nvidia_offer': offer, 'error': '',
                  'checked': datetime.now().strftime('%H:%M')}
        self.update(device=device, tiles=self._tiles(moai_tools.names(), offer))

    # ── items: fix it, ask Mira ─────────────────────────────────────
    def _find(self, kind, item_id):
        pool = {'finding': self._state['findings'], 'device': self._state['device'].get('problems') or [],
                'issue': self._state['diag'].get('issues') or []}.get(kind, [])
        return next((item for item in pool if item['id'] == item_id), None)

    @Slot(str, str)
    def fixItem(self, kind, item_id):
        item = self._find(kind, item_id)
        if item is None or not item.get('fix'):
            return
        if item['fix'] == 'tool':
            if item['fix_tool'] == 'system_rollback':
                self._roll_back(f'{kind}:{item_id}')
            else:
                self._run_tool(item['fix_tool'], f'{kind}:{item_id}')
        elif item['fix'] == 'route':
            self._open(item['fix_route'])

    @Slot(str, str)
    def askItem(self, kind, item_id):
        item = self._find(kind, item_id)
        if item is None:
            return
        en = self.lang == 'en'
        title = item['title_en' if en else 'title_ar']
        detail = item['detail_en' if en else 'detail_ar']
        key = {'finding': 'sy_q_finding', 'device': 'sy_q_device', 'issue': 'sy_q_issue'}[kind]
        self.host.prefill.emit(self.text(key).format(title=title, detail=f' — {detail}' if detail else ''))
        self.host.toast.emit('info', self.text('sy_asked'))

    # ── tools ───────────────────────────────────────────────────────
    @Slot(str, str)
    def runTool(self, name, origin):
        """A tile or chip (origin: tools | diag | hero | device): a read runs now and shows its
        output there; a change becomes a card. Only this page's own tools."""
        if name not in PAGE_TOOLS:
            return
        origin = origin if origin in ('tools', 'diag', 'hero', 'device') else 'tools'
        if name == 'system_rollback':
            self._roll_back(origin)          # the kept-version guard, wherever it was asked
            return
        self._run_tool(name, origin)

    def _run_tool(self, name, origin):
        if name not in moai_tools.names():
            self._set_output(name, state='error', key='sy_not_available', origin=origin)
            return
        phase = self._phase(name)
        if phase == 'running':               # one run of a tool at a time, wherever it was asked
            self.host.toast.emit('info', self.text('sy_running_already'))
            return
        if phase == 'waiting':
            if self._card_live(name):
                self.host.toast.emit('pending', self.text('sy_waiting'))
                return
            self._release(name)              # its card's time ran out with no word: ask again
        if moai_tools.needs_confirmation(name, {}):
            self._ask(name, origin)
            return
        self._set_output(name, state='running', origin=origin)
        self.run('tool:' + name, moai_tools.execute, name, {})

    def _ask(self, name, origin=None):
        card = self.host.request_confirmation({'kind': 'moai', 'name': name, 'args': {},
                                               'detail': self._detail(name), 'origin': 'system'})
        if not card:
            self._set_output(name, state='error', key='sy_ask_failed', origin=origin)
            return
        card = card if isinstance(card, dict) else {}
        try:
            expires = float(card.get('expires') or 0)
        except (TypeError, ValueError):
            expires = 0.0
        if expires <= 0:
            expires = self._wall() + CARD_TTL_S
        self._cards[str(card.get('id') or f'local-{name}')] = {'name': name, 'expires': expires}
        self._set_output(name, state='waiting', origin=origin)
        if not self._expiry.isActive():
            self._expiry.start()

    def _card_live(self, name):
        now = self._wall()
        return any(c['name'] == name and now < c['expires'] + CARD_GRACE_S for c in self._cards.values())

    def _release(self, name):
        """A card whose time ran out while the tile still waited: no word came back from it, so the
        page does not know whether it ran. It says so, and the tool is free again."""
        for card_id in [k for k, c in self._cards.items() if c['name'] == name]:
            self._cards.pop(card_id, None)
        self._set_output(name, state='lost')

    def _expire_cards(self):
        now = self._wall()
        for card_id, card in list(self._cards.items()):
            phase = self._phase(card['name'])
            if phase == 'waiting' and now >= card['expires'] + CARD_GRACE_S:
                self._release(card['name'])
            elif phase not in ('waiting', 'running'):
                self._cards.pop(card_id, None)          # it ended some other way
        if not any(self._phase(c['name']) == 'waiting' for c in self._cards.values()):
            self._expiry.stop()

    def _detail(self, name):
        """What the owner's card says will happen, in his language, with this machine's facts."""
        if name == 'system_update':
            version = (self._state['booted'] or {}).get('version') or self.text('sy_this_version')
            return self.text('sy_cd_system_update').format(version=version)
        if name == 'system_rollback':
            version = (self._state['kept'] or {}).get('version') or ''
            return self.text('sy_cd_system_rollback').format(version=version).replace('  ', ' ')
        if name == 'update_firmware':
            listed = self._state['device'].get('firmware') or []
            if listed:
                shown = listed[:FIRMWARE_LISTED]
                more = len(listed) - len(shown)
                names = '; '.join(shown) + ('; ' + self.text('sy_cd_firmware_more').format(n=more) if more else '')
                found = self.text('sy_cd_firmware_found').format(
                    time=self._state['device'].get('checked') or '—', count=len(listed), list=names)
            else:
                found = self.text('sy_cd_firmware_any')
            return self.text('sy_cd_update_firmware').format(found=found)
        key = 'sy_cd_' + name
        if key in STRINGS:
            return self.text(key)
        consequence = getattr(moai_tools, 'consequence', None)
        said = consequence(name, self.lang) if callable(consequence) else ''
        if said:
            return said
        return self.text('sy_cd_generic').format(title=self.text('sy_t_' + name) if ('sy_t_' + name) in STRINGS
                                                 else moai_tools.title(name, self.lang))

    def on_tool(self, tag, result):
        name = tag.split(':', 1)[1]
        result = result if isinstance(result, dict) else {'status': 'error', 'error': 'shape'}
        status = result.get('status')
        if status == 'confirm':           # the executor wants the owner's approval for this call
            self._set_output(name, state='')
            self._ask(name)
            return
        output = clean(result.get('output') or '').strip()[-OUTPUT_LIMIT:]
        reason = str(result.get('error') or (f"exit {result['exit_code']}" if result.get('exit_code') is not None else ''))
        if name == CHECK_TOOL:
            self._on_check(status, output, reason)
            return
        if status == 'ok':
            self._set_output(name, state='ok', text=output)
        else:
            self._set_output(name, state='error', text=output, summary=reason)

    def _on_check(self, status, output, reason):
        """check_system_update's verdict goes where the owner reads the update state: the hero."""
        verdict = parse_update_check(output)
        update = dict(self._state['update'])
        at = datetime.now().strftime('%H:%M')
        if status == 'ok' and verdict and verdict['state'] != 'unknown':
            update['check'] = {**verdict, 'at': at}
            self.update(update=update)
            self._set_output(CHECK_TOOL, state='ok', key='sy_check_done')
            return
        ar, en = owner_lines(output)
        update['check'] = {'state': 'unknown', 'latest': '', 'staged': '', 'current': '', 'edition': '', 'at': at}
        self.update(update=update)
        self._set_output(CHECK_TOOL, state='error', text='' if (ar or en) else output, text_ar=ar, text_en=en,
                         summary=reason)

    def action_update(self, card_id, stage, summary, output):
        """The controller's word on a card this page put up: running, ok, error, cancelled, expired,
        or still-running (the job outlived the controller's wait; it goes on in the background)."""
        card = self._cards.get(card_id)
        if card is None:
            return
        name = card['name']
        text = clean(output or '').strip()[-OUTPUT_LIMIT:]
        if stage == 'running':
            self._set_output(name, state='running')
            return
        if stage == 'ok':
            fields = {'state': 'ok', 'text': text}
        elif stage == 'error':
            fields = {'state': 'error', 'text': text, 'summary': _reason(summary)}
        elif stage == 'cancelled':
            fields = {'state': 'cancelled', 'key': 'sy_cancelled'}
        elif stage == 'expired':
            fields = {'state': 'cancelled', 'key': 'sy_expired'}
        elif stage == 'still-running':
            fields = {'state': 'detached', 'key': 'sy_still_running', 'text': text}
        else:
            return
        self._cards.pop(card_id, None)
        self._set_output(name, **fields)
        if stage == 'ok' and name in READ_BACK:
            if name in ('system_update', 'system_rollback', 'install_nvidia'):
                self.update(update={**self._state['update'], 'check': {}})   # that verdict is now stale
            self._read_state()

    @Slot(str)
    def closeOutput(self, name):
        outputs = dict(self._state.get('outputs') or {})
        phase = (outputs.get(name) or {}).get('state')
        if phase == 'running' or (phase == 'waiting' and self._card_live(name)):
            return
        if phase == 'waiting':
            self._release(name)
            outputs = dict(self._state.get('outputs') or {})
        outputs.pop(name, None)
        self.update(outputs=outputs)

    # ── playbooks ───────────────────────────────────────────────────
    def on_skills(self, _tag, result):
        result = result if isinstance(result, dict) else {}
        if result.get('status') != 'ok':
            self.update(skills_state='error')
            return
        skills = []
        for line in str(result.get('output') or '').splitlines():
            skill_id, sep, use_when = line.partition(' — ')
            if sep and SKILL_ID.fullmatch(skill_id.strip()):
                skills.append({'id': skill_id.strip(), 'use_when': clean(use_when.strip())})
        self.update(skills=skills, skills_state='done')

    @Slot(str)
    def readSkill(self, skill_id):
        known = {s['id'] for s in self._state.get('skills') or []}
        if skill_id not in known or not SKILL_ID.fullmatch(skill_id):
            return
        if self._state['skill'].get('id') == skill_id and self._state['skill'].get('state') == 'ok':
            return
        self.update(skill={'id': skill_id, 'state': 'running', 'text': '', 'error': ''})
        self.run('skill:' + skill_id, moai_tools.execute, 'read_skill', {'name': skill_id})

    def on_skill(self, tag, result):
        skill_id = tag.split(':', 1)[1]
        if self._state['skill'].get('id') != skill_id:
            return                         # the owner opened another one meanwhile
        result = result if isinstance(result, dict) else {}
        if result.get('status') != 'ok':
            self.update(skill={'id': skill_id, 'state': 'error', 'text': '',
                               'error': str(result.get('error') or (f"exit {result['exit_code']}"
                                                                    if result.get('exit_code') is not None else ''))})
            return
        body = clean(result.get('output') or '').strip()
        body = re.sub(r'^## skill [^\n]*\n', '', body)        # the reader's own header; the page shows the title
        self.update(skill={'id': skill_id, 'state': 'ok', 'text': body[-OUTPUT_LIMIT:], 'error': ''})

    @Slot()
    def closeSkill(self):
        self.update(skill={'id': '', 'state': '', 'text': '', 'error': ''})

    @Slot(str)
    def askSkill(self, skill_id):
        if not SKILL_ID.fullmatch(skill_id or ''):
            return
        key = 'sy_sk_' + skill_id
        title = self.text(key) if key in STRINGS else skill_id
        self.host.prefill.emit(self.text('sy_q_skill').format(title=title))
        self.host.toast.emit('info', self.text('sy_asked'))

    # ── review renders (MIRA_TEST_MODE only): visibly-sample data ────
    def review(self):
        names = moai_tools.names()
        now = datetime.now().astimezone()
        today = {'day': 'today', 'date': now.strftime('%Y-%m-%d'), 'time': '20:42'}

        def item(kind, fid, severity, title, detail='', action=''):
            return self._item({'id': fid, 'severity': severity, 'title': title, 'detail': detail,
                               'action': action, 'url': action}, kind)

        def out(state, at, origin, text=''):
            return {'state': state, 'text': text, 'text_ar': '', 'text_en': '', 'summary': '', 'key': '', 'arg': '',
                    'at': at, 'origin': origin}

        findings = [
            item('finding', 'open-port-tcp-3389', 'warning',
                 'سطح المكتب البعيد (RDP) مفتوح للشبكة | Remote Desktop (RDP) is open to the network',
                 "tcp *:3389 — krdpserver — MoOS's remote desktop is Mo PC Remote (sample)", 'moos://privacy/stop-sharing'),
            item('finding', 'open-port-tcp-8123', 'warning', 'منفذ مفتوح على الشبكة | A port is open to the network',
                 'tcp 0.0.0.0:8123 — python3 (sample)'),
            item('finding', 'app-updates', 'info', 'تحديثات تطبيقات متاحة (2) | App updates available (2)',
                 'Firefox, VLC (sample)', 'moos://do/update-apps'),
            item('finding', 'broad-file-access', 'info',
                 'تطبيقات تستطيع قراءة كل ملفاتك (2) | Apps that can read all your files (2)',
                 'cn.navclub.ldbfx, com.visualstudio.code (sample)', 'moos://settings/permissions'),
        ]
        issues = [{'id': '0', 'kind': 'issue', 'severity': 'warning', 'incomplete': False,
                   'title_ar': "colour scheme is 'MoOSUI2Aurora', expected MoOSUI2Amethyst (sample)",
                   'title_en': "colour scheme is 'MoOSUI2Aurora', expected MoOSUI2Amethyst (sample)",
                   'detail_ar': '', 'detail_en': '', 'fix': '', 'fix_tool': '', 'fix_route': '', 'fix_page': False}]
        fixes = [self._tile(t) for t in ('list_failed_units', 'check_drivers', 'inspect_boot', 'net_doctor',
                                         'fix_audio', 'optimize_system') if t in names]
        # The executor's verdict appears only on an image that declares the check (what the live page can show).
        check = ({'state': 'available', 'latest': '44.20260929.960', 'staged': '', 'current': '44.20260927.952',
                  'edition': 'moos-nvidia', 'at': '20:44'} if CHECK_TOOL in names else {})
        self.update(
            sample=True, loading=False, checking=False, os_state='ok',
            booted={'version': '44.20260927.952', 'signed': True, 'edition': 'moos-nvidia', 'digest': '91c9ce7b4029'},
            staged={}, kept={'version': '44.20260927.945', 'signed': True, 'edition': 'moos-nvidia', 'digest': 'b09cdc48a1f0'},
            kernel='7.2.7-200',
            update={'known': True, 'staged': False, 'staged_version': '', 'nightly': True, 'last_result': 'success',
                    'last_run': {**today, 'time': '04:38'}, 'app_updates': 2, 'check': check},
            health={'state': 'attention', 'important': 0, 'warning': 2, 'info': 2, 'incomplete': 0,
                    'checked': today, 'error': '', 'scanning': False},
            findings=findings,
            security={'known': True, 'selinux': 'Enforcing', 'selinux_tone': 'ok', 'firewall': 'running',
                      'firewall_tone': 'ok', 'ports': 11, 'ports_known': True, 'unknown_ports': 4},
            diag={'state': 'done', 'healthy': False, 'ok': 49, 'fail': 1, 'issues': issues, 'fixes': fixes, 'error': ''},
            device={'state': 'done', 'verdict': 'attention', 'gpu': 'NVIDIA GeForce RTX 2080 SUPER',
                    'driver_en': 'NVIDIA proprietary driver active', 'driver_ar': 'تعريف NVIDIA الرسمي يعمل',
                    'driver_ok': True,
                    'problems': [item('device', 'kvm', 'info', 'تسريع محاكي أندرويد | Android emulator acceleration',
                                      'فعّل المحاكاة الافتراضية للمعالج من إعدادات البرنامج الثابت (عينة) | '
                                      'Enable CPU virtualization in firmware (sample)')],
                    'firmware': ['UEFI dbx 371 → 409 (sample)'], 'nvidia_active': True, 'nvidia_offer': False,
                    'error': '', 'checked': '20:43'},
            tiles=self._tiles(names, nvidia_offer=False),
            outputs={
                'check_drivers': out('ok', '20:43', 'tools', 'GPU: NVIDIA GeForce RTX 2080 SUPER (sample)\n'
                                                             'Driver: nvidia 580 · loaded\nFirmware: no missing files\n'
                                                             'Secure Boot: disabled'),
                'fix_audio': out('waiting', '20:44', 'tools'),
                'update_apps': out('waiting', '20:45', 'finding:app-updates'),
                'list_failed_units': out('ok', '20:41', 'diag',
                                         '## failed system units\n[none]\n## failed user units\n[none] (sample)'),
            },
            skills=[{'id': s, 'use_when': ''} for s in ('no-sound', 'no-internet', 'slow-system', 'disk-full',
                                                         'update-and-rollback', 'graphics-and-nvidia', 'boot-problems',
                                                         'failed-service')],
            skills_state='done', skill={'id': '', 'state': '', 'text': '', 'error': ''},
            badge='2', note_key='', note_tone='info')


PAGE = SystemPage

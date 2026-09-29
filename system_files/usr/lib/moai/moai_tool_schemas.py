#!/usr/bin/env python3
"""MoOS AI tool schemas — the single source of truth for Mo AI's system capabilities.

Every tool the cloud model can call is declared here. The build gate checks that
every schema maps to a real moai-do action or moos-control subcommand, and that
every user-invokable action has a schema. The QML client reads these schemas to
decide whether to show a confirmation card or auto-execute.

RULES:
  1. No schema may allow arbitrary command execution.
  2. Read-only tools auto-execute. State-changing tools require confirmation.
  3. Privileged tools still go through pkexec (moai-do handles this).
  4. Descriptions are bilingual (Arabic/English) so the model understands both.
  5. This file is the ONLY place schemas are defined; moai-control imports it.
  6. A tool may advertise only what its executor accepts. `set_volume` once offered 'mute' and
     'unmute' (moos-control's `volume` rejects both; they are separate verbs) and `open_settings`
     offered KCM names (it accepts page tokens), so the model was taught calls that always failed.
     tests/test_moai_tool_schemas.py now runs every advertised enum value through the executor.
  7. A `control` tool that can cut the owner off — Wi-Fi or Bluetooth OFF on a machine driven over
     the network or by a Bluetooth keyboard — is confirmed for that value (`confirm_values`), in
     the executor as well as in the card: the client's word is not the boundary.
  8. Every tool that can show a card carries, in both languages, what happens AFTER the yes
     (`consequence_ar` / `consequence_en`): what cannot be undone, what waits for the next
     restart, what asks for the password — and only what its executor really does (the gate
     holds a password claim, and the privileged category, to a `run_priv` its action can
     reach: optimize_system trims the journal through pkexec, so it is privileged). A card that only repeats
     the tool's name asks the owner to approve something he has not been told; each card
     surface must render this text for that to be true (see `consequence()`).

Three executors, three promises:
  moai-do        changes the system; always confirmed; may escalate through polkit.
  moos-control   instant, reversible device control.
  moos-inspect   reads and redacts; changes nothing; never escalates.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Category constants — the QML client uses these to decide the UX
# ---------------------------------------------------------------------------
READ_ONLY = "read_only"            # auto-execute, show result inline
CONTROL = "control"                # auto-execute, instant device control
USER_CONFIRM = "user_confirm"      # show confirmation card, user-space action
PRIV_CONFIRM = "privileged_confirm"  # show confirmation card, needs pkexec

# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------

def _schema(
    name: str,
    description: str,
    *,
    category: str,
    executor: str,
    command: str,
    parameters: dict[str, Any] | None = None,
    required: list[str] | None = None,
    confirm_values: dict[str, list[str]] | None = None,
    argv: list[str] | None = None,
    consequence: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """Build one OpenAI function-calling tool schema with MoOS metadata.

    `consequence` is (Arabic, English): what the owner accepts by confirming. Required for
    every tool that can show a card; tests/test_moai_tool_schemas.py holds that.
    """
    arabic, english = consequence or ("", "")
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters or {},
                "required": required or [],
                "additionalProperties": False,
            },
        },
        # MoOS-specific metadata (stripped before sending to the model,
        # used by the executor and QML client).
        "_moos": {
            "category": category,
            "executor": executor,    # "moai-do", "moos-control" or "moos-inspect"
            "command": command,      # exact subcommand string
            "required": required or [],
            # {"value": ["off"]}: this argument value needs a confirmation card even though the
            # tool's category auto-executes.
            "confirm_values": confirm_values or {},
            # The argv template after the verb, in order (moos-inspect, and every
            # moos-control verb that takes more than one argument). "{name}" is replaced by the
            # validated argument; "--flag={name}" and its flag are dropped when it is absent;
            # "?--user:user" adds --user when the boolean argument `user` is true.
            "argv": argv or [],
            # For the confirmation card, under the action's name. The schema only carries it:
            # Mira's card (controller.request_confirmation) and Mo AI's ToolConfirmationCard
            # show it once they read these two keys; until then a card shows its own text.
            "consequence_ar": arabic,
            "consequence_en": english,
        },
    }


# ---------------------------------------------------------------------------
# moai-do actions
# ---------------------------------------------------------------------------

_MOAI_DO_TOOLS: list[dict[str, Any]] = [
    # --- Read-only diagnostics (auto-execute) ---
    #
    # `diagnose_services` is NOT here, and the P3.3 measurement is why. It ran
    # `systemctl --failed` for system and user units — the same two commands, in the
    # same order, as the inspector's `list_failed_units` — under the description "Show
    # failed systemd services", while the inspector said "List failed system and user
    # services". Two tools, one output, indistinguishable sentences: asked "which
    # services have failed?" in Arabic and in English, a free model picked
    # `diagnose_services` both times and was counted wrong both times. It was not wrong;
    # MoOS was ambiguous, and every wrong pick in the real agent loop costs the owner a
    # turn. The `moai-do diagnose-services` verb still exists for anyone typing it; it
    # is simply no longer one of two identical answers the model has to choose between.
    _schema(
        "inspect_boot",
        "Show boot status and recent error logs — يعرض حالة الإقلاع وسجل الأخطاء الأخيرة",
        category=READ_ONLY, executor="moai-do", command="inspect-boot",
    ),
    _schema(
        "gpu_report",
        "Show GPU memory, driver and active compute processes — يعرض ذاكرة المعالج الرسومي والتعريف والعمليات النشطة",
        category=READ_ONLY, executor="moai-do", command="gpu-report",
    ),
    _schema(
        "net_doctor",
        "REPAIR a network that is not working: runs live ping and DNS tests and checks Tailscale. Use when the internet is broken; to only READ the current state use network_status — يشخّص شبكة لا تعمل بفحوص ping وDNS حيّة؛ لعرض الحالة فقط استخدم network_status",
        category=READ_ONLY, executor="moai-do", command="net-doctor",
    ),
    _schema(
        "check_drivers",
        "Check GPU and firmware status, recommend driver actions — يتحقق من حالة المعالج الرسومي والبرامج الثابتة",
        category=READ_ONLY, executor="moai-do", command="check-drivers",
    ),
    _schema(
        "support_bundle",
        "Generate a redacted support bundle for troubleshooting — ينشئ حزمة دعم منقّحة للتشخيص",
        category=READ_ONLY, executor="moai-do", command="support-bundle",
    ),
    # NOT an inspection tool, and it used to be offered as one. `moai-do hw-report`
    # execs `moai --device`: it OPENS a panel, prints nothing, and exits 0. Asked to
    # inspect this machine on 2026-09-18, the model reached for it as if it returned
    # data, the loop read an empty result and showed the owner a red row — "تقرير
    # العتاد: فشل دون مخرجات" — for a tool that had done exactly what it was built to
    # do. A tool the model can call has to RETURN something the model can use.
    #
    # The health scan does return that: MoOS's own report, as JSON, with the system,
    # the updates, the resources, the security findings and the hardware it can see.
    # So the read-only tool is the report, and opening the panel is left to the person
    # (Mo AI's own Device tab, one click away in the rail).
    _schema(
        "device_report",
        "Report this machine: version, updates, resources, findings — يقرأ حالة الجهاز: النسخة والتحديثات والموارد والملاحظات",
        category=READ_ONLY, executor="moai-do", command="device-report",
    ),
    # Asked "is there an update?", the model had two wrong answers: os_state (what is booted and
    # staged, never what is PUBLISHED) and system_update (which stages it, behind a card and a
    # password). This one reads the same resolver the Updater and the daily timer use and
    # changes nothing.
    _schema(
        "check_system_update",
        "READ whether a newer signed MoOS version is published and whether one is already staged "
        "for the next restart; downloads and changes nothing. To download and stage it use "
        "system_update — يتحقق هل توجد نسخة MoOS موقّعة أحدث أو نسخة مجهّزة للإقلاع القادم، دون "
        "تنزيل أو تغيير أي شيء",
        category=READ_ONLY, executor="moai-do", command="check-update",
    ),

    # --- User-space actions (confirmation card, no pkexec) ---
    _schema(
        "install_app",
        "Install a Flatpak application from the store — يثبّت تطبيق Flatpak من المتجر",
        category=USER_CONFIRM, executor="moai-do", command="install",
        parameters={
            "app_id": {
                "type": "string",
                "description": "Flatpak application ID (e.g. org.mozilla.firefox) — معرّف التطبيق",
            },
        },
        required=["app_id"],
        consequence=("يُثبَّت التطبيق لحسابك عبر Mo Store ثم يُفتح. يمكنك إزالته في أي وقت.",
                     "Installs the app for your account through Mo Store, then opens it. "
                     "You can remove it any time."),
    ),
    _schema(
        "uninstall_app",
        "Remove a Flatpak application — يزيل تطبيق Flatpak",
        category=USER_CONFIRM, executor="moai-do", command="uninstall",
        parameters={
            "app_id": {
                "type": "string",
                "description": "Flatpak application ID to remove — معرّف التطبيق المراد إزالته",
            },
        },
        required=["app_id"],
        consequence=("يُحذف التطبيق من حسابك عبر Mo Store، ويمكنك تثبيته من جديد في أي وقت.",
                     "Removes the app from your account through Mo Store. "
                     "You can install it again any time."),
    ),
    _schema(
        "update_apps",
        "Update all installed Flatpak applications — يحدّث جميع تطبيقات Flatpak المثبّتة",
        category=USER_CONFIRM, executor="moai-do", command="update-apps",
        consequence=("تُحدَّث تطبيقاتك عبر Mo Store. قد يحتاج تطبيق مفتوح إلى إغلاقه وفتحه من جديد.",
                     "Updates your apps through Mo Store. An app that is open may need "
                     "to be closed and opened again."),
    ),
    _schema(
        "fix_audio",
        "Restart PipeWire audio stack to fix sound issues — يعيد تشغيل نظام الصوت PipeWire لإصلاح مشاكل الصوت",
        category=USER_CONFIRM, executor="moai-do", command="fix-audio",
        consequence=("ينقطع الصوت لحظة أثناء إعادة تشغيل خدماته. لا يحتاج كلمة مرور.",
                     "Sound stops for a moment while its services restart. No password needed."),
    ),
    _schema(
        "optimize_system",
        "Clean unused runtimes, images and old logs to free disk space — ينظّف البيانات غير المستخدمة لتحرير مساحة القرص",
        # Privileged: trimming the system journal escalates (moai-do do_optimize runs
        # `run_priv journalctl --vacuum-time=7d`), so the card is the password card.
        category=PRIV_CONFIRM, executor="moai-do", command="optimize",
        consequence=("يحذف مكوّنات التطبيقات وصور الحاويات غير المستخدمة وسجلات النظام الأقدم من 7 أيام. "
                     "ملفاتك لا تُمسّ، وقد تُطلب كلمة المرور لتقليص السجلات.",
                     "Removes unused app runtimes and container images and system logs older "
                     "than 7 days. Your files are untouched; trimming the logs may ask for "
                     "your password."),
    ),
    _schema(
        "setup_gaming",
        "Install Steam, Bottles, Lutris and ProtonUp for gaming — يثبّت أدوات الألعاب: Steam, Bottles, Lutris, ProtonUp",
        category=USER_CONFIRM, executor="moai-do", command="setup-gaming",
        consequence=("يثبّت عبر Mo Store ما ينقص فقط من أدوات الألعاب. قد يكون التنزيل كبيراً.",
                     "Installs only the missing gaming tools through Mo Store. "
                     "The download can be large."),
    ),
    _schema(
        "setup_windows",
        "Install Bottles for Windows application compatibility — يثبّت Bottles لتشغيل تطبيقات Windows",
        category=USER_CONFIRM, executor="moai-do", command="setup-windows",
        consequence=("يثبّت عبر Mo Store بيئة معزولة لتشغيل برامج ‎.exe، مرة واحدة فقط.",
                     "Installs, through Mo Store, an isolated environment for Windows .exe "
                     "programs. It is installed only once."),
    ),
    _schema(
        "smart_setup",
        "Install, through Mo Store, the essential apps this computer's hardware plan says are "
        "missing — يثبّت عبر Mo Store التطبيقات الأساسية الناقصة حسب عتاد هذا الجهاز",
        category=USER_CONFIRM, executor="moai-do", command="smart-setup",
        consequence=("يثبّت عبر Mo Store التطبيقات الأساسية التي تنقص هذا الجهاز فقط. لا يحتاج كلمة مرور.",
                     "Installs through Mo Store only the essential apps this computer is "
                     "missing. No password needed."),
    ),
    # --- Coding and agent runtimes: the user's own home, never a privilege ---
    # moai-do installs each under ~/.local as the user (/usr is read-only here); none of them
    # asks for a password. (OpenClaw once enabled lingering through setup_brain_impl; the
    # cloud-only change removed that call, so it no longer escalates — or promises to.)
    _schema(
        "install_codex",
        "Install the Codex coding agent for this user, in ~/.local — يثبّت وكيل البرمجة Codex "
        "لهذا المستخدم في ~/.local",
        category=USER_CONFIRM, executor="moai-do", command="install-codex",
        consequence=("يُثبَّت في مجلدك (~/.local) دون كلمة مرور، ويطلب تسجيل الدخول إلى مزوّده عند أول تشغيل.",
                     "Installs into your home folder (~/.local) with no password. It asks you "
                     "to sign in to its provider the first time it runs."),
    ),
    _schema(
        "install_claude_code",
        "Install the Claude Code coding agent for this user, in ~/.local — يثبّت وكيل البرمجة "
        "Claude Code لهذا المستخدم في ~/.local",
        category=USER_CONFIRM, executor="moai-do", command="install-claude",
        consequence=("يُثبَّت في مجلدك (~/.local) دون كلمة مرور، ويطلب تسجيل الدخول إلى مزوّده عند أول تشغيل.",
                     "Installs into your home folder (~/.local) with no password. It asks you "
                     "to sign in to its provider the first time it runs."),
    ),
    _schema(
        "install_opencode",
        "Install OpenCode, a coding agent that runs on Mo AI's free cloud brain, for this user — "
        "يثبّت OpenCode، وكيل برمجة يعمل على عقل Mo AI السحابي المجاني",
        category=USER_CONFIRM, executor="moai-do", command="install-opencode",
        consequence=("يُثبَّت في مجلدك دون كلمة مرور، ويُضبط على عقل Mo AI السحابي إن لم يكن لديك إعداد خاص به.",
                     "Installs into your home folder with no password, and points it at Mo AI's "
                     "cloud brain unless you already have your own settings for it."),
    ),
    _schema(
        "install_hermes",
        "Install or repair Hermes, the agent runtime behind Mo AI's agent mode (official release "
        "pinned by hash) — يثبّت أو يصلح Hermes، محرّك وضع الوكيل في Mo AI",
        category=USER_CONFIRM, executor="moai-do", command="install-hermes",
        consequence=("ينزّل الإصدار الرسمي (قرابة 400 MB) إلى مجلدك بعد التحقق من بصمته، ولا يستبدل "
                     "النسخة الحالية إلا إذا نجح فحص التوافق. لا يحتاج كلمة مرور.",
                     "Downloads the official release (about 400 MB) into your home folder, "
                     "verified by hash, and replaces the current copy only if the new one "
                     "passes its check. No password needed."),
    ),
    _schema(
        "install_openclaw",
        "Install the phone agent (OpenClaw) so this computer can be messaged from Telegram — "
        "يثبّت وكيل الهاتف لمراسلة هذا الكمبيوتر من تليجرام",
        category=USER_CONFIRM, executor="moai-do", command="install-openclaw",
        consequence=("يُثبَّت في مجلدك دون كلمة مرور، ويحتاج عقلاً سحابياً مضبوطاً أولاً. بعده تضع "
                     "رمز بوت تليجرام في الإعدادات.",
                     "Installs into your home folder with no password, and needs a cloud brain "
                     "set up first. Afterwards you add your Telegram bot token in Settings."),
    ),
    # A reboot is not privileged here: logind lets the active local session restart the machine,
    # the same way the power menu's Restart does. moai-do asks systemctl to check inhibitors
    # itself (--check-inhibitors=yes), so a program holding a block — or another logged-in
    # user — refuses the restart instead of being overridden or turning into a password prompt.
    # moai-do refuses while a Mo AI job, a Mo Store job or an image deployment is still running.
    _schema(
        "restart_computer",
        "Restart the computer now (also applies a staged MoOS update) — يعيد تشغيل الكمبيوتر "
        "الآن (ويطبّق تحديث MoOS المجهّز إن وُجد)",
        category=USER_CONFIRM, executor="moai-do", command="restart",
        consequence=("يعيد تشغيل الكمبيوتر فوراً: تُغلق التطبيقات المفتوحة ويضيع ما لم يُحفظ، ويُطبَّق "
                     "أي تحديث مجهّز أثناء الإقلاع.",
                     "Restarts the computer now: open apps close and unsaved work is lost. "
                     "A staged update is applied while it starts again."),
    ),

    # --- Privileged actions (confirmation card + pkexec) ---
    _schema(
        "system_update",
        "Check for and stage a signed MoOS system update (applies on reboot) — يتحقق من تحديث النظام ويجهّزه (يُطبَّق عند إعادة التشغيل)",
        category=PRIV_CONFIRM, executor="moai-do", command="update",
        consequence=("تُنزَّل النسخة الموقّعة الجديدة وتُطبَّق عند إعادة التشغيل القادمة. ملفاتك لا تُمسّ، "
                     "وتبقى النسخة الحالية متاحة للرجوع. تُطلب كلمة المرور.",
                     "Downloads the new signed version; it applies at the next restart. Your "
                     "files are untouched and the current version stays available to go back "
                     "to. Asks for your password."),
    ),
    _schema(
        "system_rollback",
        "Roll back to the previous MoOS deployment (applies on reboot) — يرجع إلى النشر السابق (يُطبَّق عند إعادة التشغيل)",
        category=PRIV_CONFIRM, executor="moai-do", command="rollback",
        consequence=("يعود الإقلاع القادم إلى نسخة MoOS السابقة، ويُلغى أي تحديث مجهّز. ملفاتك وإعداداتك "
                     "لا تُمسّ، ويمكنك التقدّم ثانيةً بتحديث. تُطلب كلمة المرور.",
                     "The next restart returns to the previous MoOS version, and a staged "
                     "update is discarded. Your files and settings are untouched, and an "
                     "update moves you forward again. Asks for your password."),
    ),
    _schema(
        "install_nvidia",
        "Switch to the MoOS NVIDIA edition for dedicated GPU support (applies on reboot) — ينتقل إلى إصدار NVIDIA للدعم الكامل للمعالج الرسومي",
        category=PRIV_CONFIRM, executor="moai-do", command="install-nvidia",
        consequence=("ينتقل إلى إصدار MoOS الخاص بـ NVIDIA عند إعادة التشغيل القادمة، وتبقى النسخة "
                     "الحالية متاحة للرجوع. تُطلب كلمة المرور.",
                     "Switches to the MoOS NVIDIA edition at the next restart; the current "
                     "version stays available to go back to. Asks for your password."),
    ),
    _schema(
        "update_firmware",
        "Check for and install firmware updates via fwupd (cannot be rolled back) — يتحقق من تحديثات البرامج الثابتة ويثبّتها (لا يمكن التراجع عنها)",
        category=PRIV_CONFIRM, executor="moai-do", command="update-firmware",
        consequence=("يكتب برنامجاً ثابتاً جديداً في قطع الجهاز. لا يمكن التراجع عنه، وقد يحتاج إعادة "
                     "تشغيل. تُطلب كلمة المرور.",
                     "Writes new firmware into the computer's devices. This cannot be undone "
                     "and may need a restart. Asks for your password."),
    ),
    _schema(
        "setup_waydroid",
        "Initialize and start Waydroid for Android app support — يهيّئ ويشغّل Waydroid لدعم تطبيقات Android",
        category=PRIV_CONFIRM, executor="moai-do", command="setup-waydroid",
        consequence=("ينزّل نظام Android الحر (قرابة 1 GB) في المرة الأولى ويشغّل حاويته. تُطلب كلمة المرور.",
                     "Downloads the free Android system (about 1 GB) the first time and starts "
                     "its container. Asks for your password."),
    ),
    _schema(
        "remote_anywhere",
        "Enable Mo PC Remote access from anywhere via Tailscale HTTPS — يفعّل التحكم عن بعد من أي مكان عبر Tailscale",
        category=PRIV_CONFIRM, executor="moai-do", command="remote-anywhere",
        consequence=("يمنح هذا الكمبيوتر اسماً وشهادة HTTPS على شبكة Tailscale الخاصة بك ليصله هاتفك من "
                     "أي مكان. لا يُنشر شيء على الإنترنت العام. تُطلب كلمة المرور.",
                     "Gives this computer an HTTPS name on your private Tailscale network so "
                     "your phone reaches it from anywhere. Nothing is published on the public "
                     "internet. Asks for your password."),
    ),
    # A package that arrives as a file (App Drop's RPM path, Mira's file picker). The pattern
    # is only its SHAPE: one visible folder of the home, then the .rpm. WHICH folders is
    # moai-do's valid_local_rpm (and the root helper's) to decide — Downloads, Desktop and
    # Documents, by those names or by the names the owner's own XDG folders carry (an Arabic
    # session's desktop is «سطح المكتب»); a list here could only disagree with it. moai-do
    # still resolves the real path, requires the owner, a trusted publisher signature and this
    # computer's architecture, and the root helper checks the confirmed digest again.
    _schema(
        "install_rpm",
        "Install a signed RPM package file from the Downloads, Desktop or Documents folder (by "
        "their English names or the names this session gives them, e.g. ~/سطح المكتب) as a new "
        "system version (applies on the next restart) — يثبّت حزمة RPM موقّعة من مجلد "
        "التنزيلات أو سطح المكتب أو المستندات كنسخة نظام جديدة (تُطبَّق عند إعادة التشغيل)",
        category=PRIV_CONFIRM, executor="moai-do", command="install-rpm",
        parameters={
            "path": {
                "type": "string",
                "pattern": r"^(?:~|/(?:var/)?home/[A-Za-z0-9_][A-Za-z0-9._-]{0,63})"
                           r"/[^/.][^/]{0,127}/[^/]{1,200}\.rpm$",
                "description": "The full path of the .rpm file directly inside the Downloads, "
                               "Desktop or Documents folder, e.g. ~/Downloads/app.rpm or "
                               "~/سطح المكتب/app.rpm — مسار ملف الحزمة",
            },
        },
        required=["path"],
        consequence=("تُضاف الحزمة إلى نسخة نظام جديدة تبدأ عند إعادة التشغيل القادمة، وتبقى النسخة "
                     "الحالية للرجوع. لا تُقبل إلا حزمة بتوقيع ناشر موثوق. تُطلب كلمة المرور.",
                     "Adds the package to a new system version that starts at the next "
                     "restart; the current version stays available to go back to. Only a "
                     "package with a trusted publisher signature is accepted. Asks for your "
                     "password."),
    ),
]

# ---------------------------------------------------------------------------
# moos-control actions
# ---------------------------------------------------------------------------

# The pages moos-control's `settings` verb accepts: the tokens marked `moai: true` in the one
# settings registry (usr/share/moos/settings-destinations.json, SPEC D3). Both read the same
# file through the same module, and the schema test still runs every value through
# moos-control. An unreadable registry offers no page, so open_settings is then not offered
# at all rather than offered with an empty or stale list.
def _settings_pages() -> tuple[str, ...]:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "moos"))
    try:
        import moos_settings_destinations as destinations
    except ImportError:
        return ()
    finally:
        sys.path.pop(0)
    registry = Path(__file__).resolve().parent.parent.parent / "share/moos/settings-destinations.json"
    return destinations.moai_tokens(destinations.safe_load(registry))


SETTINGS_PAGES: tuple[str, ...] = _settings_pages()

_CONTROL_TOOLS: list[dict[str, Any]] = [
    _schema(
        "set_volume",
        "Set speaker volume level, or mute/unmute — يضبط مستوى الصوت أو يكتمه",
        category=CONTROL, executor="moos-control", command="volume",
        parameters={
            "value": {
                "type": "string",
                "description": "Volume level 0-100, or 'up' / 'down'. To silence use set_mute.",
            },
        },
        required=["value"],
    ),
    _schema(
        "set_mute",
        "Mute or unmute the speakers — يكتم الصوت أو يعيده",
        category=CONTROL, executor="moos-control", command="mute",
        parameters={
            "value": {
                "type": "string",
                "enum": ["mute", "unmute"],
                "description": "mute silences the speakers, unmute restores them",
            },
        },
        required=["value"],
    ),
    _schema(
        "set_brightness",
        "Set screen brightness level — يضبط مستوى سطوع الشاشة",
        category=CONTROL, executor="moos-control", command="brightness",
        parameters={
            "value": {
                "type": "string",
                "description": "Brightness level 5-100, 'up', or 'down'",
            },
        },
        required=["value"],
    ),
    _schema(
        "toggle_night_light",
        "Turn night light (blue filter) on, off, or auto — يشغّل أو يطفئ الضوء الليلي",
        category=CONTROL, executor="moos-control", command="night-light",
        parameters={
            "value": {
                "type": "string",
                "enum": ["on", "off", "auto"],
                "description": "Night light state",
            },
        },
        required=["value"],
    ),
    _schema(
        "toggle_wifi",
        "Turn Wi-Fi on or off — يشغّل أو يطفئ الواي فاي",
        category=CONTROL, executor="moos-control", command="wifi",
        parameters={
            "value": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "Wi-Fi state",
            },
        },
        required=["value"],
        # A machine reached over Wi-Fi (Mo PC Remote, SSH) loses its owner when this is "off".
        confirm_values={"value": ["off"]},
        # "the assistant", not a name: Mira on x86, Mo AI where it is still the assistant (ARM).
        consequence=("إيقاف الواي فاي يقطع الإنترنت والمساعد الذكي والتحكم عن بعد حتى تشغّله من جديد.",
                     "Turning Wi-Fi off cuts the internet, the assistant and remote control "
                     "until you turn it on again."),
    ),
    _schema(
        "toggle_bluetooth",
        "Turn Bluetooth on or off — يشغّل أو يطفئ البلوتوث",
        category=CONTROL, executor="moos-control", command="bluetooth",
        parameters={
            "value": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "Bluetooth state",
            },
        },
        required=["value"],
        # A Bluetooth keyboard and mouse stop working the moment this is "off".
        confirm_values={"value": ["off"]},
        consequence=("إيقاف البلوتوث يفصل لوحة المفاتيح والفأرة والسماعات اللاسلكية فوراً.",
                     "Turning Bluetooth off disconnects wireless keyboards, mice and "
                     "headphones at once."),
    ),
    _schema(
        "set_theme_mode",
        "Change the whole MoOS look: dark or light, one of the MoOS palettes, follow the sun "
        "(auto), flip the current palette between light and dark (toggle), or go back to the "
        "previous look (undo) — يغيّر مظهر MoOS كله: داكن أو فاتح أو إحدى لوحات MoOS أو تلقائي "
        "أو قلب الفاتح والداكن أو التراجع",
        category=CONTROL, executor="moos-control", command="theme",
        parameters={
            "value": {
                "type": "string",
                "enum": ["dark", "light", "nova", "amethyst", "midnight", "aurora",
                         "nova-light", "amethyst-light", "aurora-light", "daylight",
                         "gaming", "dev", "study", "gaming-light", "dev-light", "study-light",
                         "auto", "toggle", "undo"],
                "description": "dark is MoOS Graphite and light is MoOS Tidal; nova (cosmic "
                               "navy), amethyst (warm aubergine), midnight (true black) and "
                               "aurora (teal) each have a -light sibling, and midnight's is "
                               "daylight; gaming is MoOS Arena, dev is MoOS Forge, study is "
                               "MoOS Scholar, each with a -light sibling",
            },
        },
        required=["value"],
    ),
    _schema(
        "take_screenshot",
        "Take a screenshot of the current screen — يأخذ لقطة شاشة",
        category=CONTROL, executor="moos-control", command="screenshot",
    ),
    _schema(
        "get_system_status",
        "Get current device status: volume, brightness, night light, Wi-Fi, Bluetooth, theme, "
        "do not disturb, microphone and power profile — يحصل على حالة الجهاز الحالية",
        category=READ_ONLY, executor="moos-control", command="status",
    ),
    _schema(
        "open_app",
        "Open an installed application by its Flatpak ID — يفتح تطبيقاً مثبّتاً",
        category=CONTROL, executor="moos-control", command="open",
        parameters={
            "app_id": {
                "type": "string",
                "description": "Flatpak application ID to launch (e.g. org.mozilla.firefox)",
            },
        },
        required=["app_id"],
    ),
    # SPEC D4: the window manager and the desktop, through their own fixed actions.
    _schema(
        "show_windows",
        "Show the overview of open windows, the grid of every desktop, or the desktop itself "
        "(show-desktop hides the windows; asking again brings them back) — "
        "يعرض نظرة عامة على النوافذ أو شبكة أسطح المكتب أو سطح المكتب نفسه",
        category=CONTROL, executor="moos-control", command="window",
        parameters={"view": {"type": "string", "enum": ["overview", "grid", "show-desktop"],
                             "description": "overview, grid of desktops, or show-desktop"}},
        required=["view"],
    ),
    _schema(
        "arrange_windows",
        "Arrange the windows on the current screen in one step: side by side in halves, thirds "
        "or quarters, one main window and two, or centre the active window — "
        "يرتّب النوافذ على الشاشة الحالية نصفين أو أثلاثاً أو أرباعاً أو نافذة رئيسية أو في المنتصف",
        category=CONTROL, executor="moos-control", command="arrange",
        parameters={"layout": {"type": "string",
                               "enum": ["halves", "thirds", "quarters", "main", "centre"],
                               "description": "how to arrange the windows"}},
        required=["layout"],
    ),
    _schema(
        "switch_desktop",
        "Move to the next or previous virtual desktop — ينتقل إلى سطح المكتب التالي أو السابق",
        category=CONTROL, executor="moos-control", command="desktop",
        parameters={"direction": {"type": "string", "enum": ["next", "previous"],
                                  "description": "which way to move"}},
        required=["direction"],
    ),
    _schema(
        "set_do_not_disturb",
        "Turn do-not-disturb (silence notification pop-ups) on or off — "
        "يشغّل أو يطفئ وضع عدم الإزعاج (إسكات الإشعارات)",
        category=CONTROL, executor="moos-control", command="dnd",
        parameters={"value": {"type": "string", "enum": ["on", "off"],
                              "description": "do not disturb on or off"}},
        required=["value"],
        # On stays on until the owner turns it off, silencing every notification.
        confirm_values={"value": ["on"]},
        consequence=("تبقى الإشعارات صامتة، ومنها تنبيهات النظام، حتى تطفئ عدم الإزعاج بنفسك.",
                     "Notifications stay silent, system warnings included, until you turn "
                     "Do Not Disturb off yourself."),
    ),
    _schema(
        "set_mic_mute",
        "Mute or unmute the microphone (not the speakers; for sound use set_mute) — "
        "يكتم الميكروفون أو يعيده (لا السماعات)",
        category=CONTROL, executor="moos-control", command="mic",
        parameters={"value": {"type": "string", "enum": ["mute", "unmute"],
                              "description": "mute or unmute the microphone"}},
        required=["value"],
        # Muting is always safe. Turning the microphone back ON undoes a privacy choice the
        # owner made, so neither a model's turn nor a link may do it without a yes.
        confirm_values={"value": ["unmute"]},
        consequence=("يعود ميكروفون الكمبيوتر إلى السماع بعد أن كتمته.",
                     "The computer's microphone can hear again after you muted it."),
    ),
    _schema(
        "switch_keyboard_layout",
        "Switch the keyboard to the next typing language/layout — "
        "يبدّل لغة الكتابة في لوحة المفاتيح إلى التالية",
        category=CONTROL, executor="moos-control", command="keyboard-layout",
    ),
    _schema(
        "set_motion",
        "Set how much the MoOS wallpaper moves: still, gentle or alive — "
        "يضبط حركة خلفية MoOS: ثابتة أو هادئة أو حيّة",
        category=CONTROL, executor="moos-control", command="motion",
        parameters={"level": {"type": "string", "enum": ["still", "gentle", "alive"],
                              "description": "still stops the motion"}},
        required=["level"],
    ),
    _schema(
        "set_glass_clarity",
        "Set how see-through MoOS glass surfaces are: clear, balanced or solid — "
        "يضبط شفافية الزجاج في MoOS: شفاف أو متوازن أو صلب",
        category=CONTROL, executor="moos-control", command="clarity",
        parameters={"level": {"type": "string", "enum": ["clear", "balanced", "solid"],
                              "description": "solid is the least transparent"}},
        required=["level"],
    ),
    _schema(
        "set_power_profile",
        "Switch the power profile: power-saver, balanced or performance — "
        "يبدّل وضع الطاقة: توفير أو متوازن أو أداء",
        category=CONTROL, executor="moos-control", command="power-profile",
        parameters={"profile": {"type": "string",
                                "enum": ["power-saver", "balanced", "performance"],
                                "description": "the power profile"}},
        required=["profile"],
    ),
    # W9.10 — the desktop's hands: one named window, one desktop, the media keys, the lock,
    # a reminder, a web page, a folder and three of the desktop's own settings. Each verb
    # reads its result back from its owner (KWin, MPRIS, the locker, systemd, KConfig).
    _schema(
        "list_windows",
        "List the open windows (id, app, title, which desktop, minimized/maximized/full "
        "screen) and the virtual desktops. Use it before acting on a window when the name is "
        "unclear — يعرض النوافذ المفتوحة وأسطح المكتب",
        category=READ_ONLY, executor="moos-control", command="windows",
    ),
    _schema(
        "window_action",
        "Do one thing to ONE open window, found by words from its title or app name (or its id "
        "from list_windows): bring it to the front, minimize, restore, maximize, unmaximize, "
        "full screen, leave full screen, keep it above others or not, or close it (the app "
        "still asks to save). Not for arranging several windows; use arrange_windows — "
        "ينفّذ فعلاً على نافذة واحدة بالاسم: إظهار، تصغير، استعادة، تكبير، ملء الشاشة، "
        "إبقاء فوق النوافذ، إغلاق",
        category=CONTROL, executor="moos-control", command="window-do",
        parameters={
            "action": {"type": "string",
                       "enum": ["focus", "minimize", "restore", "maximize", "unmaximize",
                                "fullscreen", "exit-fullscreen", "keep-above",
                                "no-keep-above", "close"],
                       "description": "focus brings it to the front"},
            "target": {"type": "string", "maxLength": 80,
                       "description": "words from the window's title or app (e.g. firefox), "
                                      "or its {id} from list_windows"},
        },
        required=["action", "target"], argv=["{action}", "{target}"],
        # A close can lose work in an app that does not ask; the person says yes first.
        confirm_values={"action": ["close"]},
        consequence=("تُغلق النافذة كما يغلقها زرّ الإغلاق: التطبيق يسألك عن الحفظ إن كان يسأل، "
                     "وما لم يُحفظ في تطبيق لا يسأل يضيع.",
                     "The window closes as its own close button would: the app asks to save if "
                     "it asks at all, and unsaved work in an app that does not ask is lost."),
    ),
    _schema(
        "move_window_to_desktop",
        "Move ONE open window to another virtual desktop by number — ينقل نافذة إلى سطح مكتب آخر",
        category=CONTROL, executor="moos-control", command="window-move",
        parameters={
            "desktop": {"type": "integer", "minimum": 1, "maximum": 20,
                        "description": "the desktop's number, counting from 1"},
            "target": {"type": "string", "maxLength": 80,
                       "description": "words from the window's title or app, or its {id}"},
        },
        required=["desktop", "target"], argv=["{desktop}", "{target}"],
    ),
    _schema(
        "go_to_desktop",
        "Switch to virtual desktop number N (for the next or previous one use switch_desktop) "
        "— ينتقل إلى سطح المكتب رقم N",
        category=CONTROL, executor="moos-control", command="go-desktop",
        parameters={"number": {"type": "integer", "minimum": 1, "maximum": 20,
                               "description": "the desktop's number, counting from 1"}},
        required=["number"],
    ),
    _schema(
        "add_or_remove_desktop",
        "Add one virtual desktop, or remove the last one (refused while windows are on it) — "
        "يضيف سطح مكتب افتراضياً أو يزيل الأخير",
        category=CONTROL, executor="moos-control", command="desktops",
        parameters={"change": {"type": "string", "enum": ["add", "remove"],
                               "description": "add one, or remove the last one"}},
        required=["change"],
    ),
    _schema(
        "control_media",
        "Control the music or video that is playing: play/pause, play, pause, next, previous "
        "or stop. get_system_status says what is playing — يتحكّم بالموسيقى أو الفيديو: تشغيل، "
        "إيقاف مؤقت، التالي، السابق",
        category=CONTROL, executor="moos-control", command="media",
        parameters={"action": {"type": "string",
                               "enum": ["play-pause", "play", "pause", "next", "previous",
                                        "stop"],
                               "description": "what the media keys would do"}},
        required=["action"],
    ),
    _schema(
        "lock_screen",
        "Lock the screen now (the owner unlocks it with their password) — يقفل الشاشة الآن",
        category=CONTROL, executor="moos-control", command="lock",
    ),
    _schema(
        "set_reminder",
        "Remind the owner of something after N minutes with a notification that stays until "
        "dismissed — يذكّر المالك بشيء بعد عدد من الدقائق بإشعار",
        category=CONTROL, executor="moos-control", command="remind",
        parameters={
            "minutes": {"type": "integer", "minimum": 1, "maximum": 1440,
                        "description": "how many minutes from now (1-1440)"},
            "text": {"type": "string", "maxLength": 160,
                     "description": "what to remember, in the owner's language"},
        },
        required=["minutes", "text"], argv=["{minutes}", "{text}"],
    ),
    _schema(
        "manage_reminders",
        "List the pending reminders, or cancel all of them — يعرض التذكيرات المنتظرة أو يلغيها",
        category=CONTROL, executor="moos-control", command="reminders",
        parameters={"action": {"type": "string", "enum": ["list", "cancel-all"],
                               "description": "list, or cancel every pending reminder"}},
        required=["action"],
    ),
    _schema(
        "open_web_page",
        "Open a web address in the owner's browser (http or https only). For a web search, "
        "open a search engine's address with the words in it — يفتح صفحة ويب في المتصفح",
        category=CONTROL, executor="moos-control", command="open-url",
        parameters={"url": {"type": "string", "maxLength": 2048,
                            "description": "the full http:// or https:// address"}},
        required=["url"],
    ),
    _schema(
        "open_folder",
        "Open one of the owner's folders in the file manager — يفتح مجلداً من مجلدات المالك",
        category=CONTROL, executor="moos-control", command="open-folder",
        parameters={"folder": {"type": "string",
                               "enum": ["home", "documents", "downloads", "pictures", "music",
                                        "videos", "desktop", "screenshots"],
                               "description": "which folder"}},
        required=["folder"],
    ),
    _schema(
        "set_animation_speed",
        "Set how fast windows and menus animate everywhere: off, fast, normal or slow (not "
        "the wallpaper; for that use set_motion) — يضبط سرعة حركة النوافذ والقوائم",
        category=CONTROL, executor="moos-control", command="animations",
        parameters={"speed": {"type": "string", "enum": ["off", "fast", "normal", "slow"],
                              "description": "off makes every change instant"}},
        required=["speed"],
    ),
    _schema(
        "set_screen_lock",
        "Set after how many idle minutes the screen locks by itself, or 0 so it never locks "
        "by itself (to lock now use lock_screen) — يضبط القفل التلقائي للشاشة بعد دقائق الخمول",
        category=CONTROL, executor="moos-control", command="screen-lock",
        parameters={"after_minutes": {"type": "integer", "minimum": 0, "maximum": 120,
                                      "description": "idle minutes before it locks; 0 = never"}},
        required=["after_minutes"],
        # Turning the automatic lock off leaves an unattended desk open.
        confirm_values={"after_minutes": ["0"]},
        consequence=("لن تُقفل الشاشة وحدها بعد الآن: من يجلس إلى الكمبيوتر وأنت بعيد يستطيع استخدامه، "
                     "حتى تعيد ضبط مدة القفل.",
                     "The screen will no longer lock by itself: anyone at the computer while you "
                     "are away can use it, until you set a lock delay again."),
    ),
    _schema(
        "set_click_mode",
        "Choose whether one click or a double-click opens files and folders — "
        "يختار فتح الملفات بنقرة واحدة أو بنقرتين",
        category=CONTROL, executor="moos-control", command="click",
        parameters={"mode": {"type": "string", "enum": ["single", "double"],
                             "description": "single or double click"}},
        required=["mode"],
    ),
    # Mo PC Remote is a user service (the phone app that controls this computer). Both switches
    # are confirmed: ON lets a paired phone control this computer after every start, and OFF
    # cuts off whoever is driving it from the phone right now — possibly the owner himself.
    # restart only reconnects a remote that is already on (try-restart), so it never opens one.
    _schema(
        "remote_control",
        "Turn Mo PC Remote (control this computer from your phone) on or off, or restart it to "
        "fix a stuck connection. For reaching it from outside the home use remote_anywhere — "
        "يشغّل أو يوقف Mo PC Remote (التحكم بالكمبيوتر من الهاتف) أو يعيد تشغيله لإصلاح اتصال عالق",
        category=CONTROL, executor="moos-control", command="remote",
        parameters={"value": {"type": "string", "enum": ["on", "off", "restart"],
                              "description": "on, off, or restart to reconnect"}},
        required=["value"],
        confirm_values={"value": ["on", "off"]},
        consequence=("التشغيل يسمح لهاتفك المقترن بالتحكم بهذا الكمبيوتر ويبقى بعد كل إقلاع؛ "
                     "الإيقاف يقطع أي هاتف يتحكم به الآن.",
                     "On lets your paired phone control this computer, also after every "
                     "restart; off disconnects any phone controlling it right now."),
    ),
    # Fast Remote trades the look for a lighter stream: blur, animations and wallpaper motion
    # pause, the keyboard switches to US for the phone, and a local AI model is paused if one is
    # running (Mo AI's brain is in the cloud, so usually there is none) — until it is turned
    # off, which restores exactly what was saved. So ON asks and OFF does not.
    _schema(
        "fast_remote",
        "Turn Fast Remote on or off: a lighter desktop (no blur, animations or wallpaper motion) "
        "that makes Mo PC Remote smoother — يشغّل أو يطفئ الاتصال السريع: سطح مكتب أخف يجعل "
        "Mo PC Remote أسلس",
        category=CONTROL, executor="moos-control", command="fast-remote",
        parameters={"value": {"type": "string", "enum": ["on", "off"],
                              "description": "on for a lighter desktop, off restores it"}},
        required=["value"],
        confirm_values={"value": ["on"]},
        consequence=("يوقف الضبابية والحركة والرسوم المتحركة، ويبدّل لوحة المفاتيح إلى US، ويوقف نموذج "
                     "ذكاء محلياً إن كان يعمل، حتى تطفئه فيعود كل شيء كما كان.",
                     "Pauses blur, motion and animations, switches the keyboard to US and "
                     "pauses a local AI model if one is running, until you turn it off, which "
                     "restores everything as it was."),
    ),
]

if SETTINGS_PAGES:
    _CONTROL_TOOLS.append(_schema(
        "open_settings",
        "Open a specific settings page (display, sound, network, shortcuts, window behaviour, "
        "appearance, Mo AI, update, recovery and more) — يفتح صفحة إعدادات محددة",
        category=CONTROL, executor="moos-control", command="settings",
        parameters={
            "page": {
                "type": "string",
                "enum": list(SETTINGS_PAGES),
                "description": "The settings page to open",
            },
        },
        required=["page"],
    ))

# ---------------------------------------------------------------------------
# moos-inspect: read-only, redacted, closed grammar. An operator has to LOOK before it repairs.
# ---------------------------------------------------------------------------

# The repair playbooks shipped under usr/share/moos/moai/skills, by id. A fixed tuple like
# SETTINGS_PAGES, so the model is offered an enum and an invented name never reaches argv;
# tests/test_moai_skills.py fails when this and the shipped files disagree in either direction.
SKILLS: tuple[str, ...] = (
    "app-wont-start",
    "bluetooth-device",
    "boot-problems",
    "disk-full",
    "failed-service",
    "gaming-and-windows-apps",
    "graphics-and-nvidia",
    "install-an-app",
    "no-internet",
    "no-sound",
    "slow-system",
    "update-and-rollback",
)

_UNIT_PARAM = {
    "type": "string",
    # The same shape moos-inspect enforces; checked here too so an invented name never reaches argv.
    "pattern": r"^[A-Za-z0-9@._:\\-]{1,120}\.(service|timer|socket|path|target|mount|slice|scope)$",
    "description": "systemd unit name with its suffix, e.g. pipewire.service or NetworkManager.service",
}
_USER_PARAM = {
    "type": "boolean",
    "description": "true for a unit of the logged-in user's session (pipewire, plasma-…, moai-…), "
                   "false for a system unit",
}

_INSPECT_TOOLS: list[dict[str, Any]] = [
    _schema(
        "list_failed_units",
        "List failed system and user services — يعرض الخدمات الفاشلة للنظام والمستخدم",
        category=READ_ONLY, executor="moos-inspect", command="failed-units",
    ),
    _schema(
        "unit_status",
        "Show one service's state and its latest log lines — يعرض حالة خدمة واحدة وآخر أسطر سجلّها",
        category=READ_ONLY, executor="moos-inspect", command="unit",
        parameters={"name": _UNIT_PARAM, "user": _USER_PARAM},
        required=["name"], argv=["{name}", "?--user:user"],
    ),
    _schema(
        "read_journal",
        "Read the system log, newest last, optionally for one unit — يقرأ سجلّ النظام، ويمكن حصره بخدمة",
        category=READ_ONLY, executor="moos-inspect", command="journal",
        parameters={
            "unit": _UNIT_PARAM,
            "user": _USER_PARAM,
            "priority": {"type": "string", "enum": ["err", "warning", "info"],
                         "description": "lowest severity to include; err is the shortest"},
            "since": {"type": "string", "enum": ["boot", "1h", "24h", "7d"],
                      "description": "how far back to read"},
            "lines": {"type": "integer", "minimum": 1, "maximum": 200,
                      "description": "how many of the newest lines to return"},
        },
        argv=["--unit={unit}", "?--user:user", "--priority={priority}", "--since={since}",
              "--lines={lines}"],
    ),
    _schema(
        "top_processes",
        "Show which programs use the most CPU or memory — يعرض أكثر البرامج استهلاكاً للمعالج أو الذاكرة",
        category=READ_ONLY, executor="moos-inspect", command="processes",
        parameters={"by": {"type": "string", "enum": ["cpu", "memory"], "description": "sort key"}},
        required=["by"], argv=["{by}"],
    ),
    _schema(
        "memory_status",
        "Show RAM, swap and memory pressure — يعرض الذاكرة والمبادلة وضغط الذاكرة",
        category=READ_ONLY, executor="moos-inspect", command="memory",
    ),
    _schema(
        "disk_status",
        "Show free space on the filesystems that matter — يعرض المساحة الحرة على الأقراص المهمة",
        category=READ_ONLY, executor="moos-inspect", command="disk",
    ),
    _schema(
        "network_status",
        "READ the current network state: devices, addresses, route and DNS. Runs no tests; to diagnose a network that is not working use net_doctor — يعرض حالة الشبكة الحالية بلا فحوص؛ لتشخيص شبكة معطّلة استخدم net_doctor",
        category=READ_ONLY, executor="moos-inspect", command="network",
    ),
    _schema(
        "list_installed_apps",
        "List installed applications with their ids and versions — يعرض التطبيقات المثبّتة ومعرّفاتها",
        category=READ_ONLY, executor="moos-inspect", command="apps",
    ),
    _schema(
        "os_state",
        "Show the booted, staged and rollback MoOS versions and whether the origin is signed — "
        "يعرض إصدار النظام الحالي والمجهَّز ونسخة الرجوع",
        category=READ_ONLY, executor="moos-inspect", command="os",
    ),
    _schema(
        "read_moos_log",
        "Read one of MoOS's own logs — يقرأ أحد سجلات MoOS",
        category=READ_ONLY, executor="moos-inspect", command="log",
        parameters={"name": {"type": "string", "enum": ["moai", "theme", "store", "remote"],
                             "description": "which MoOS log"}},
        required=["name"], argv=["{name}"],
    ),
    # Skills: what a free cloud model does not know about THIS system — which service carries
    # sound here, that `/` always reads full, that an update is staged and a rollback is kept,
    # which repair exists and which does not. Text the image ships, read through the same
    # redacting, bounded, closed-grammar reader as everything else. A skill grants nothing: every
    # step in it is one of the tools above, under that tool's own confirmation rule.
    _schema(
        "list_skills",
        "List the repair playbooks written for this system, with when to use each — "
        "يعرض أدلة الإصلاح المكتوبة لهذا النظام ومتى يُستخدم كلٌّ منها",
        category=READ_ONLY, executor="moos-inspect", command="skills",
    ),
    _schema(
        "read_skill",
        "Read one repair playbook, then follow it step by step — يقرأ دليل إصلاح واحداً ليتبعه خطوة خطوة",
        category=READ_ONLY, executor="moos-inspect", command="skill",
        parameters={"name": {"type": "string", "enum": list(SKILLS),
                             "description": "the playbook's id, as list_skills prints it"}},
        required=["name"], argv=["{name}"],
    ),
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# All tools, in a deterministic order.
ALL_TOOLS: list[dict[str, Any]] = _MOAI_DO_TOOLS + _CONTROL_TOOLS + _INSPECT_TOOLS

# Names by category for fast lookup.
READ_ONLY_NAMES: frozenset[str] = frozenset(
    t["function"]["name"] for t in ALL_TOOLS
    if t["_moos"]["category"] in (READ_ONLY, CONTROL)
)
CONFIRM_NAMES: frozenset[str] = frozenset(
    t["function"]["name"] for t in ALL_TOOLS
    if t["_moos"]["category"] in (USER_CONFIRM, PRIV_CONFIRM)
)

# Lookup table: schema name → _moos metadata.
TOOL_META: dict[str, dict[str, str]] = {
    t["function"]["name"]: t["_moos"] for t in ALL_TOOLS
}


def get_schemas_for_model() -> list[dict[str, Any]]:
    """Return the tool list suitable for the OpenAI /v1/chat/completions request.

    Strips the _moos metadata since the model does not need it.
    """
    return [
        {"type": t["type"], "function": t["function"]}
        for t in ALL_TOOLS
    ]


def get_schemas_with_meta() -> list[dict[str, Any]]:
    """Return all schemas including MoOS metadata (for the executor and QML)."""
    return list(ALL_TOOLS)


def needs_confirmation(tool_name: str, arguments: dict[str, Any]) -> bool:
    """True when this exact call must be confirmed by the person before it runs."""
    meta = TOOL_META.get(tool_name)
    if meta is None:
        return True
    if meta["category"] in (USER_CONFIRM, PRIV_CONFIRM):
        return True
    for key, values in (meta.get("confirm_values") or {}).items():
        if str(arguments.get(key, "")) in values:
            return True
    return False


def consequence(tool_name: str, lang: str = "ar") -> str:
    """What confirming this tool does, in the card's language ("" when it has no card text)."""
    meta = TOOL_META.get(tool_name) or {}
    return str(meta.get("consequence_en" if lang == "en" else "consequence_ar") or "")


def _properties(tool_name: str) -> dict[str, Any]:
    return next(t["function"]["parameters"]["properties"] for t in ALL_TOOLS
                if t["function"]["name"] == tool_name)


def _valid(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Arguments must be declared, of the declared type, and inside a declared enum/range.

    The executors validate again; this keeps a model's invention out of argv altogether.
    """
    properties = _properties(tool_name)
    for key, value in arguments.items():
        spec = properties.get(key)
        if spec is None:
            return False
        kind = spec.get("type")
        if kind == "boolean":
            if not isinstance(value, bool):
                return False
        elif kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                return False
            if not spec.get("minimum", value) <= value <= spec.get("maximum", value):
                return False
        else:
            if not isinstance(value, str) or not value.strip() \
                    or len(value) > spec.get("maxLength", 256) \
                    or value.startswith("-") or any(ord(c) < 32 or ord(c) == 127 for c in value):
                return False
        if "enum" in spec and value not in spec["enum"]:
            return False
        if "pattern" in spec and not re.fullmatch(spec["pattern"].strip("^$"), str(value)):
            return False
    return True


def _inspect_argv(template: list[str], arguments: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    for part in template:
        if part.startswith("?"):                       # "?--user:user"
            flag, _, key = part[1:].partition(":")
            if arguments.get(key) is True:
                argv.append(flag)
            continue
        key = part[part.index("{") + 1:part.index("}")]
        if key not in arguments:
            continue                                   # optional argument left out
        argv.append(part.replace("{" + key + "}", str(arguments[key])))
    return argv


def build_command(tool_name: str, arguments: dict[str, Any]) -> list[str] | None:
    """Map a tool call to the exact executor command line.

    Returns None if the tool_name is unknown (safety: never guess).
    """
    meta = TOOL_META.get(tool_name)
    if meta is None:
        return None

    for req in meta.get("required", []):
        if req not in arguments:
            return None
    if not _valid(tool_name, arguments):
        return None

    executor = meta["executor"]
    command = meta["command"]

    if executor == "moai-do":
        cmd = ["moai-do", "--confirmed", command]
        # Append the single required argument if present.
        if "app_id" in arguments:
            cmd.append(arguments["app_id"])
        elif "file" in arguments:
            cmd.append(arguments["file"])
        elif "path" in arguments:
            # The model names the owner's folders as ~/Downloads/…; moai-do accepts only an
            # absolute path (and then resolves it, owner and location included, itself).
            path = str(arguments["path"])
            if path.startswith("~/"):
                path = str(Path.home()) + path[1:]
            cmd.append(path)
        return cmd

    if executor == "moos-inspect":
        return ["moos-inspect", command, *_inspect_argv(meta.get("argv") or [], arguments)]

    if executor == "moos-control" and meta.get("argv"):
        # A verb of more than one argument: in the template's fixed order.
        return ["moos-control", command, *_inspect_argv(meta["argv"], arguments)]

    if executor == "moos-control":
        if command == "mute":
            # `mute` and `unmute` are separate argument-less verbs of moos-control.
            return ["moos-control", str(arguments["value"])]
        if command == "keyboard-layout":
            # One direction only: `next`, which a second call undoes on a two-layout desk.
            return ["moos-control", "keyboard-layout", "next"]
        cmd = ["moos-control", command]
        # Every other control verb takes its ONE declared argument, whatever it is called.
        declared = [key for key in _properties(tool_name) if key in arguments]
        if len(declared) > 1:
            return None
        if declared:
            cmd.append(str(arguments[declared[0]]))
        return cmd

    return None


if __name__ == "__main__":
    # Debug: print all schemas as JSON.
    print(json.dumps(get_schemas_for_model(), indent=2, ensure_ascii=False))
    print(f"\n{len(ALL_TOOLS)} tools: "
          f"{len(READ_ONLY_NAMES)} auto-execute, "
          f"{len(CONFIRM_NAMES)} confirm")

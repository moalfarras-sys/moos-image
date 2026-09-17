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
  5. This file is the ONLY place schemas are defined; moai-gateway imports it.
"""

from __future__ import annotations

import json
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
) -> dict[str, Any]:
    """Build one OpenAI function-calling tool schema with MoOS metadata."""
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
            "executor": executor,    # "moai-do" or "moos-control"
            "command": command,      # exact subcommand string
            "required": required or [],
        },
    }


# ---------------------------------------------------------------------------
# moai-do actions
# ---------------------------------------------------------------------------

_MOAI_DO_TOOLS: list[dict[str, Any]] = [
    # --- Read-only diagnostics (auto-execute) ---
    _schema(
        "diagnose_services",
        "Show failed systemd services — يعرض الخدمات المعطّلة",
        category=READ_ONLY, executor="moai-do", command="diagnose-services",
    ),
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
        "Diagnose network: devices, route, DNS, ping, Tailscale — يشخّص الشبكة: الأجهزة، المسار، DNS، ping، Tailscale",
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
    _schema(
        "hw_report",
        "Open the hardware and device health panel — يفتح لوحة صحة العتاد والأجهزة",
        category=READ_ONLY, executor="moai-do", command="hw-report",
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
    ),
    _schema(
        "update_apps",
        "Update all installed Flatpak applications — يحدّث جميع تطبيقات Flatpak المثبّتة",
        category=USER_CONFIRM, executor="moai-do", command="update-apps",
    ),
    _schema(
        "fix_audio",
        "Restart PipeWire audio stack to fix sound issues — يعيد تشغيل نظام الصوت PipeWire لإصلاح مشاكل الصوت",
        category=USER_CONFIRM, executor="moai-do", command="fix-audio",
    ),
    _schema(
        "optimize_system",
        "Clean unused runtimes, images and old logs to free disk space — ينظّف البيانات غير المستخدمة لتحرير مساحة القرص",
        category=USER_CONFIRM, executor="moai-do", command="optimize",
    ),
    _schema(
        "setup_gaming",
        "Install Steam, Bottles, Lutris and ProtonUp for gaming — يثبّت أدوات الألعاب: Steam, Bottles, Lutris, ProtonUp",
        category=USER_CONFIRM, executor="moai-do", command="setup-gaming",
    ),
    _schema(
        "setup_windows",
        "Install Bottles for Windows application compatibility — يثبّت Bottles لتشغيل تطبيقات Windows",
        category=USER_CONFIRM, executor="moai-do", command="setup-windows",
    ),

    # --- Privileged actions (confirmation card + pkexec) ---
    _schema(
        "system_update",
        "Check for and stage a signed MoOS system update (applies on reboot) — يتحقق من تحديث النظام ويجهّزه (يُطبَّق عند إعادة التشغيل)",
        category=PRIV_CONFIRM, executor="moai-do", command="update",
    ),
    _schema(
        "system_rollback",
        "Roll back to the previous MoOS deployment (applies on reboot) — يرجع إلى النشر السابق (يُطبَّق عند إعادة التشغيل)",
        category=PRIV_CONFIRM, executor="moai-do", command="rollback",
    ),
    _schema(
        "install_nvidia",
        "Switch to the MoOS NVIDIA edition for dedicated GPU support (applies on reboot) — ينتقل إلى إصدار NVIDIA للدعم الكامل للمعالج الرسومي",
        category=PRIV_CONFIRM, executor="moai-do", command="install-nvidia",
    ),
    _schema(
        "update_firmware",
        "Check for and install firmware updates via fwupd (cannot be rolled back) — يتحقق من تحديثات البرامج الثابتة ويثبّتها (لا يمكن التراجع عنها)",
        category=PRIV_CONFIRM, executor="moai-do", command="update-firmware",
    ),
    _schema(
        "setup_waydroid",
        "Initialize and start Waydroid for Android app support — يهيّئ ويشغّل Waydroid لدعم تطبيقات Android",
        category=PRIV_CONFIRM, executor="moai-do", command="setup-waydroid",
    ),
    _schema(
        "remote_anywhere",
        "Enable Mo PC Remote access from anywhere via Tailscale HTTPS — يفعّل التحكم عن بعد من أي مكان عبر Tailscale",
        category=PRIV_CONFIRM, executor="moai-do", command="remote-anywhere",
    ),
]

# ---------------------------------------------------------------------------
# moos-control actions
# ---------------------------------------------------------------------------

_CONTROL_TOOLS: list[dict[str, Any]] = [
    _schema(
        "set_volume",
        "Set speaker volume level, or mute/unmute — يضبط مستوى الصوت أو يكتمه",
        category=CONTROL, executor="moos-control", command="volume",
        parameters={
            "value": {
                "type": "string",
                "description": "Volume level 0-100, 'up', 'down', 'mute', or 'unmute'",
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
    ),
    _schema(
        "set_theme_mode",
        "Switch to dark or light mode, or a named palette — ينتقل إلى الوضع الداكن أو الفاتح أو لوحة ألوان محددة",
        category=CONTROL, executor="moos-control", command="theme",
        parameters={
            "value": {
                "type": "string",
                "enum": ["dark", "light", "nova", "amethyst", "midnight", "aurora", "auto"],
                "description": "Theme or mode name",
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
        "Get current device status: volume, brightness, night light, Wi-Fi, Bluetooth, theme — يحصل على حالة الجهاز الحالية",
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
    _schema(
        "open_settings",
        "Open a specific system settings page — يفتح صفحة إعدادات محددة",
        category=CONTROL, executor="moos-control", command="settings",
        parameters={
            "page": {
                "type": "string",
                "description": "Settings KCM module name (e.g. kcm_users, kcm_kscreen, bluetooth)",
            },
        },
        required=["page"],
    ),
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# All tools, in a deterministic order.
ALL_TOOLS: list[dict[str, Any]] = _MOAI_DO_TOOLS + _CONTROL_TOOLS

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

    executor = meta["executor"]
    command = meta["command"]

    if executor == "moai-do":
        cmd = ["moai-do", "--confirmed", command]
        # Append the single required argument if present.
        if "app_id" in arguments:
            cmd.append(arguments["app_id"])
        elif "file" in arguments:
            cmd.append(arguments["file"])
        return cmd

    if executor == "moos-control":
        cmd = ["moos-control", command]
        if "value" in arguments:
            cmd.append(str(arguments["value"]))
        elif "app_id" in arguments:
            cmd.append(arguments["app_id"])
        elif "page" in arguments:
            cmd.append(arguments["page"])
        return cmd

    return None


if __name__ == "__main__":
    # Debug: print all schemas as JSON.
    print(json.dumps(get_schemas_for_model(), indent=2, ensure_ascii=False))
    print(f"\n{len(ALL_TOOLS)} tools: "
          f"{len(READ_ONLY_NAMES)} auto-execute, "
          f"{len(CONFIRM_NAMES)} confirm")

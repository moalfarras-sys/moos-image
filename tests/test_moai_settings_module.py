#!/usr/bin/env python3
"""Gate: Mo AI's settings are ONE page of System Settings, and the Mo AI window no longer has them.

SPEC D1/D5 moved the settings sheet that lived inside the Mo AI window (Brain, OpenClaw, Telegram,
WhatsApp, Voice, Memory, Permissions, Appearance) and the kdialog wizard into kcm_moos_ai, the Mo AI
page of System Settings (moos-settings-kcm/modules/ai). This gate holds what that move promised:

  * the page talks only to the two loopback services the window used, with their own headers, on
    this account's ports, and only on the paths it needs;
  * opening it WRITES NOTHING — every write is a Save (or a default-model pick, or a measurement)
    the owner pressed, and each Save sends only what its section owns;
  * secrets stay write-only: a key or a token is sent when typed and never read, held or shown;
  * the permission tiers and the web warning keep the EXACT words the window used, in both
    languages, and the stored tier — the safe default included — is never written back unasked;
  * the window keeps none of it: no sheet, no second config client, no private language override;
    its gear and "Provider & API key" open the page, its rail lost Apps and Remote, and its device
    tiles open the System Settings pages instead of separate windows.

The page's own logic (what each Save sends) is executed with node, the way test_moos_settings.py
runs the other pages' logic. The loaded page itself is proven by the image build's module load gate
(build_files/verify_settings_modules.sh loads every module named in settings-modules.list).
"""

from __future__ import annotations

import configparser
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "moos-settings-kcm/modules/ai"
PAGE = MODULE / "ui/main.qml"
SERVICE = MODULE / "ui/MoaiService.qml"
APP = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"
DESKTOP = ROOT / "system_files/usr/share/applications/org.moos.moai.desktop"
NODE = shutil.which("node")

# (agent service?, method, path) — every request the page may make.
REQUESTS = {
    (True, "GET", "/api/config"), (True, "GET", "/api/capabilities"), (True, "GET", "/api/channels"),
    (True, "POST", "/api/config"),
    (False, "GET", "/models"), (False, "GET", "/measure"), (False, "GET", "/quick"),
    (False, "POST", "/measure"),
}
# The functions that write, and the only handlers allowed to call them.
WRITERS = {"saveBrain", "saveDefaultModel", "measureFree", "saveTelegram", "savePermissions"}

# The words the Mo AI window used, moved unchanged: (Arabic, English).
EXACT = [
    ("كم يتحكّم الوكيل بجهازك فعلياً من تليجرام (كاميرا، برامج، ترمنال، تحديث، تطوير). ابدأ بـ«مع إذن».",
     "Choose how much Telegram can control on this device. Start with “Ask first”."),
    ("تحكّم البوت بجهازك", "Bot device control"),
    ("مُفعّل — يصل للكاميرا والترمنال وتحديث النظام من تليجرام",
     "Enabled — Telegram can reach the camera, terminal and system actions"),
    ("إعداد مخصّص على القرص — اختر مستوى أدناه ليُعرف حده الحقيقي",
     "Custom on-disk configuration — pick a tier below to normalise it"),
    ("معزول — يردّ فقط، لا يتحكّم بشيء", "Sandboxed — replies only; no device control"),
    ("معطّل — بلا تحكّم", "Disabled — no control"),
    ("يردّ ويحلّل داخل عزل فقط. لا كاميرا ولا برامج ولا ترمنال",
     "Replies inside a sandbox; no camera, apps or terminal"),
    ("تعديل المشروع", "Edit project"),
    ("يقرأ ويعدّل ويختبر داخل مجلد المشروع المعزول، بلا وصول للنظام",
     "Reads, edits and tests inside the sandboxed project; no system access"),
    ("تحكّم بالنظام — بموافقة", "System control — ask first"),
    ("يتحكّم بالجهاز الحقيقي، لكن يعرض كل أمر وتوافق عليه في تليجرام قبل تنفيذه",
     "Can control the device, but every command requires Telegram approval"),
    ("كامل — تحكّم بلا سؤال", "Full — no confirmation"),
    ("ينفّذ أي شيء على جهازك فوراً بلا موافقة. الأقوى والأخطر — لك وحدك",
     "Runs immediately without approval. Most powerful and highest risk"),
    ("الإعداد الحالي على القرص لا يطابق أي مستوى من الأربعة — اختر مستوى ليُوحَّد.",
     "The on-disk configuration matches none of the four tiers — pick one to normalise it."),
    ("نموذج صغير ضعيف أمام حقن التعليمات، والبحث المحلي يتطلب تسجيل دخول Ollama — بدون حساب تفشل الأداة "
     "ويعلق العقل المحلي عليها. فعّله مع العقل السحابي فقط.",
     "A small model is vulnerable to prompt injection, and local search needs an Ollama account sign-in "
     "— without one the tool always fails and the local brain can loop on it. Enable this with the cloud "
     "brain only."),
    ("نماذج سحابية فقط. المجاني افتراضي؛ المدفوع باختيارك. قد تنتهي الحصة المجانية.",
     "Cloud models only. Free by default; paid models require your selection. Free quotas may run out."),
    ("المجاني افتراضي؛ المدفوع باختيارك. لا نماذج محلية.", "Free by default; paid by choice. No local models."),
]


def code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def function(qml: str, name: str) -> str:
    start = qml.index("    function " + name + "(")
    end = qml.index("{", start) + 1
    depth = 1
    while depth:
        depth += {"{": 1, "}": -1}.get(qml[end], 0)
        end += 1
    return qml[start:end]


def flat(text: str) -> str:
    """QML source with its string literals joined: a long sentence may span two lines."""
    return re.sub(r'"\s*\n\s*\+?\s*"', "", text)


class TheModule(unittest.TestCase):
    def test_it_is_the_spec_module(self) -> None:
        metadata = json.loads((MODULE / "kcm_moos_ai.json").read_text(encoding="utf-8"))
        plugin = metadata["KPlugin"]
        self.assertEqual((plugin["Name"], plugin["Name[ar]"]), ("Mo AI", "Mo AI"))
        self.assertEqual(metadata["X-KDE-System-Settings-Parent-Category"], "moos")
        self.assertEqual(metadata["X-KDE-Weight"], 4)
        english = metadata["X-KDE-Keywords"].split(",")
        arabic = metadata["X-KDE-Keywords[ar]"].split(",")
        for word in ("brain", "provider", "model", "key", "telegram", "permissions"):
            self.assertIn(word, english)
        for word in ("مساعد", "ذكاء"):
            self.assertIn(word, arabic)

    def test_the_page_names_every_part_of_the_old_sheet(self) -> None:
        page = code(PAGE.read_text(encoding="utf-8"))
        for heading in ('"العقل", "Brain"', '"النماذج السحابية", "Cloud models"',
                        '"قنوات الهاتف", "Phone channels"', '"الصلاحيات", "Permissions"',
                        '"الوصول إلى Mo AI", "Reaching Mo AI"', '"يتبع نظامك", "Follows your system"'):
            self.assertIn(f"title: root.t({heading})", page)
        for route in ("moos://settings/shortcuts", "moos://app/moai", "moos://agent/whatsapp-login",
                      "moos://do/install-openclaw", "moos://settings/themes", "moos://settings/region"):
            self.assertIn(f'root.open("{route}")', page)
        self.assertIn('MoosKeyCap { keyName: "Meta" }', page)
        self.assertIn('MoosKeyCap { keyName: "Space" }', page)
        self.assertIn("Ctrl+Enter", page, "the Ask Mo AI from Search note lost its key")


class TheServices(unittest.TestCase):
    def test_only_loopback_on_this_accounts_ports_with_each_services_header(self) -> None:
        service = code(SERVICE.read_text(encoding="utf-8"))
        self.assertIn('"http://127.0.0.1:" + service.port("MOAI_AGENT_PORT", 8077)', service)
        self.assertIn('"http://127.0.0.1:" + service.port("MOAI_CONTROL_PORT", 8079)', service)
        self.assertIn('parseInt(kcm.env(name), 10)', service)
        self.assertIn('xhr.setRequestHeader(agent ? "X-Moai-Agent" : "X-Moai-Control", "1")', service)
        self.assertIn('xhr.open(method, (agent ? service.agentBase : service.controlBase) + path)', service)
        self.assertEqual(service.count("xhr.open("), 1, "a second way out of the page")
        for forbidden in ("file:", "localhost", "https://", "QML_XHR_ALLOW_FILE_READ"):
            self.assertNotIn(forbidden, service)
        # An answer counts as done only when the service said so.
        self.assertIn('ok: !timedOut && xhr.status === 200 && object && error === ""', service)

    def test_the_page_asks_only_for_what_it_needs(self) -> None:
        page = code(PAGE.read_text(encoding="utf-8"))
        calls = re.findall(r'moai\.request\((true|false), "(GET|POST)", "(/[a-z/]+)"', page)
        self.assertGreaterEqual(len(calls), 9, "the request pattern moved; this gate must read it")
        found = {(agent == "true", method, path) for agent, method, path in calls}
        self.assertEqual(found, REQUESTS)
        self.assertEqual(page.count("moai.request("), len(calls), "a request this gate cannot read")
        self.assertNotIn("XMLHttpRequest", page, "the page must go through MoaiService")


class NothingIsWrittenByOpening(unittest.TestCase):
    def test_writes_live_only_in_the_save_functions(self) -> None:
        page = code(PAGE.read_text(encoding="utf-8"))
        writers = set()
        for name in re.findall(r"(?m)^    function (\w+)\(", page):
            if '"POST"' in function(page, name):
                writers.add(name)
        self.assertEqual(writers, WRITERS)

    def test_only_a_button_the_owner_pressed_calls_a_writer(self) -> None:
        page = code(PAGE.read_text(encoding="utf-8"))
        for name in WRITERS:
            with self.subTest(writer=name):
                sites = [m.start() for m in re.finditer(rf"\broot\.{name}\(", page)]
                self.assertEqual(len(sites), 1, f"{name} must have exactly one caller")
                line = page[page.rfind("\n", 0, sites[0]) + 1:page.find("\n", sites[0])]
                self.assertRegex(line.strip(), r"^on(Clicked|Picked): ",
                                 f"{name} is reached from something other than an owner's action")

    def test_opening_and_showing_the_page_only_read(self) -> None:
        page = code(PAGE.read_text(encoding="utf-8"))
        self.assertIn('Component.onCompleted: loadAll(["brain", "telegram", "permissions"])', page)
        opening = page.split("onVisibleChanged: if (visible) {", 1)[1].split("}", 1)[0]
        self.assertEqual(sorted(re.findall(r"(\w+)\(\)", opening)),
                         ["loadCapabilities", "loadMeasure", "loadQuick"])
        load_all = function(page, "loadAll")
        self.assertEqual(sorted(re.findall(r"\b(\w+)\(", load_all)[1:]),
                         ["loadCapabilities", "loadConfig", "loadMeasure", "loadModels", "loadQuick"])
        for loader in ("loadConfig", "loadCapabilities", "loadModels", "loadMeasure", "loadQuick",
                       "checkChannels", "applyDrafts"):
            self.assertNotIn('"POST"', function(page, loader), loader)
        # The phone agent is woken only when the owner asks for a channel check.
        self.assertEqual(page.count('"/api/channels"'), 1)
        self.assertIn('onClicked: root.checkChannels()', page)
        self.assertEqual(page.count("root.checkChannels()"), 1)

    def test_a_tier_is_never_written_back_unasked(self) -> None:
        page = code(PAGE.read_text(encoding="utf-8"))
        body = function(page, "permissionsBody")
        self.assertIn('["read", "project", "system", "full"].indexOf(draft.tier) >= 0', body)
        self.assertIn("draft.tier !== saved.tier", body)
        self.assertIn("return { body: Object.keys(change).length > 0 ? { permissions: change } : null }", body)
        self.assertIn("if (request.body === null)\n            return", function(page, "savePermissions"))


class SecretsAreWriteOnly(unittest.TestCase):
    def test_a_saved_key_or_token_is_never_read_held_or_shown(self) -> None:
        page = code(PAGE.read_text(encoding="utf-8"))
        for field in ("keyField", "tokenField"):
            start = page.index(f"id: {field}")
            self.assertIn("FormCard.FormPasswordFieldDelegate {", page[start - 80:start])
        for forbidden in ("apiKey", "botToken", "cloud.key", "telegram.token", ".secret"):
            self.assertNotIn(forbidden, page)
        # Only has_key / has_token are read; the fields are emptied on load and after a save.
        self.assertIn("readonly property bool hasKey: cloud.has_key === true", page)
        self.assertIn("readonly property bool hasToken: telegram.has_token === true", page)
        drafts = function(page, "applyDrafts")
        self.assertIn('keyField.text = ""', drafts)
        self.assertIn('tokenField.text = ""', drafts)
        # Emptied only once the service said it saved (a failed save keeps what was typed).
        for writer, field in (("saveBrain", "keyField"), ("saveTelegram", "tokenField")):
            self.assertRegex(function(page, writer),
                             rf'if \(!r\.ok\) \{{[^\n]*\n[^\n]*\n\s*return\n\s*\}}\s*{field}\.text = ""')
        self.assertEqual(len(re.findall(r"(?:keyField|tokenField)\.text = (?!\"\")", page)), 0,
                         "a secret field was given a value other than empty")


class TheWordsAreTheOnesTheWindowUsed(unittest.TestCase):
    def test_every_warning_is_word_for_word_in_the_page_and_gone_from_the_window(self) -> None:
        page = flat(PAGE.read_text(encoding="utf-8"))
        app = APP.read_text(encoding="utf-8")
        for arabic, english in EXACT:
            with self.subTest(text=english[:50]):
                self.assertIn(f'"{arabic}"', page)
                self.assertIn(f'"{english}"', page)
                self.assertNotIn(english, app, "the window still carries a moved setting")


@unittest.skipUnless(NODE, "needs node to execute the page logic")
class WhatEachSaveSends(unittest.TestCase):
    def test_the_bodies(self) -> None:
        page = code(PAGE.read_text(encoding="utf-8"))
        script = "const assert = require('node:assert/strict');\nlet rtl = false;\n"
        for name in ("t", "localPair", "providerLabel", "providerEntry", "allowList", "brainBody",
                     "defaultBody", "telegramBody", "permissionsBody", "hostControlText", "measureText",
                     "tierChip", "failureText"):
            script += function(page, name) + "\n"
        script += r"""
const catalogue = [{id: 'openrouter-free', base: 'https://openrouter.ai/api/v1', model: 'openrouter/free'},
                   {id: 'opencode-zen', base: 'https://opencode.ai/zen/v1', model: 'deepseek-v4-flash'}];
// The brain: the catalogue's address, the provider's model when none is typed, a key only when typed.
assert.deepEqual(brainBody('openrouter-free', catalogue, '', ''),
  {error: '', body: {mode: 'cloud', cloud: {provider: 'openrouter-free', base: 'https://openrouter.ai/api/v1',
                                            model: 'openrouter/free'}}});
assert.equal(brainBody('opencode-zen', catalogue, ' glm-5 ', '  sk-x ').body.cloud.key, 'sk-x');
assert.equal(brainBody('opencode-zen', catalogue, ' glm-5 ', '').body.cloud.model, 'glm-5');
assert.ok(!('key' in brainBody('opencode-zen', catalogue, '', '   ').body.cloud));
assert.equal(brainBody('elsewhere', catalogue, '', 'sk').body, null);
// The default model is written on the SAVED provider, without the route prefix.
assert.deepEqual(defaultBody('openrouter-free', catalogue, 'cloud:vendor/m:free').body.cloud,
  {provider: 'openrouter-free', base: 'https://openrouter.ai/api/v1', model: 'vendor/m:free'});
assert.equal(defaultBody('', catalogue, 'cloud:x').body, null);
// Telegram: no token unless typed; a username is refused instead of dropped by the service.
assert.deepEqual(telegramBody(true, '', '123, 456 ,,'), {error: '', body: {telegram: {enabled: true, allow: ['123', '456']}}});
assert.equal(telegramBody(false, ' 1:abc ', '').body.telegram.token, '1:abc');
assert.equal(telegramBody(true, '', '@owner').body, null);
assert.equal(telegramBody(true, '', '').body.telegram.allow.length, 0);
// Permissions: only what changed; never a tier that is not one of the four; web re-applied with a tier.
const saved = {tier: 'read', web: false, project: ''};
assert.equal(permissionsBody(saved, {tier: 'read', web: false, project: ''}, true).body, null);
assert.equal(permissionsBody({tier: 'custom', web: false, project: ''}, {tier: 'custom', web: false, project: ''}, true).body, null);
assert.equal(permissionsBody({tier: '', web: false, project: ''}, {tier: '', web: false, project: ''}, true).body, null);
assert.equal(permissionsBody(saved, {tier: 'custom', web: false, project: ''}, true).body, null);
assert.deepEqual(permissionsBody(saved, {tier: 'system', web: false, project: ''}, true).body,
                 {permissions: {tier: 'system', web: false}});
assert.deepEqual(permissionsBody(saved, {tier: 'system', web: false, project: ''}, false).body,
                 {permissions: {tier: 'system'}});
assert.deepEqual(permissionsBody(saved, {tier: 'read', web: true, project: ''}, true).body,
                 {permissions: {web: true}});
assert.equal(permissionsBody(saved, {tier: 'read', web: true, project: ''}, false).body, null);
assert.deepEqual(permissionsBody(saved, {tier: 'read', web: false, project: ' /home/o/p '}, true).body,
                 {permissions: {project: '/home/o/p'}});
// Words: the saved tier in the window's own sentences; a bilingual answer shows one language.
assert.equal(hostControlText('full'), 'Enabled — Telegram can reach the camera, terminal and system actions');
assert.equal(hostControlText('project'), 'Sandboxed — replies only; no device control');
assert.equal(hostControlText('custom'), 'Custom on-disk configuration — pick a tier below to normalise it');
assert.ok(hostControlText('').startsWith('Unknown'));
assert.equal(tierChip('full').tone, 'negative');
assert.equal(providerLabel('OpenRouter (مجاني فقط | free only)'), 'OpenRouter (free only)');
assert.equal(localPair('عربي | English'), 'English');
assert.equal(measureText({measuring: true, done: 2, total: 9}), 'Measuring — 2 of 9');
assert.ok(measureText({}).startsWith('Nothing measured here yet'));
assert.ok(failureText({offline: true}).includes('nothing was saved'));
// A write that timed out may still land: it is never reported as not saved.
assert.ok(!failureText({offline: true, timedOut: true}).includes('nothing was saved'));
assert.ok(failureText({offline: true, timedOut: true}).includes('Refresh'));
assert.equal(failureText({status: 400, error: 'شكل | Bad token'}), 'Bad token');
rtl = true;
assert.equal(providerLabel('OpenRouter (مجاني فقط | free only)'), 'OpenRouter (مجاني فقط)');
assert.equal(localPair('عربي | English'), 'عربي');
assert.ok(/[؀-ۿ]/.test(hostControlText('read')));
assert.ok(/[؀-ۿ]/.test(telegramBody(true, '', 'x').error));
"""
        result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])


class TheWindowNoLongerDuplicatesIt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = code(APP.read_text(encoding="utf-8"))

    def test_no_sheet_no_second_config_client_no_private_language(self) -> None:
        for gone in ("id: settingsDialog", "settingsOpen", "cfgTab", "cfgSave", "cfgLoad",
                     '"/api/config"', "langOverride", "ui: { language", "cfgSaveUiLanguage",
                     "ttsSwitch", "keepBox", '"/measure"'):
            self.assertNotIn(gone, self.app)
        # Mo AI follows the one locale authority; the only other direction is a review knob.
        self.assertIn('readonly property bool moaiRtl: layoutDirectionOverride === "rtl"\n'
                      '        || (layoutDirectionOverride === "" && MoUI.Locale.rtl)', self.app)

    def test_every_settings_door_opens_the_page(self) -> None:
        self.assertIn('function openAssistantSettings() {\n'
                      '        root.launch("moos://settings/assistant"', self.app)
        gear = self.app.split("id: gearMa", 1)[1].split("}", 1)[0]
        self.assertIn("onTriggered: root.openAssistantSettings()", gear)
        footer = self.app.split('label: root.local("المزوّد والمفتاح", "Provider & API key")', 1)[1]
        self.assertIn("root.openAssistantSettings()", footer.split("}", 1)[0])
        cloud = self.app.split('"Set up the cloud brain")', 1)[1].split("}", 1)[0]
        self.assertIn("onClicked: root.openAssistantSettings()", cloud)

    def test_the_rail_and_the_device_panel_hand_off(self) -> None:
        items = self.app.split("readonly property var navItems: [", 1)[1].split("]", 1)[0]
        self.assertEqual(re.findall(r'\{ id: "([a-z]+)"', items), ["chat", "device", "compat", "agent"])
        for route in ("moos://settings/update", "moos://settings/recovery", "moos://settings/about",
                      "moos://app/store", "moos://settings/remote", "moos://do/remote-anywhere"):
            self.assertIn(f'"{route}"', self.app)
        for gone in ("moos://app/updater", "moos://app/recovery", "moos://do/hw-report",
                     "moos://remote/start", "moos://remote/stop", "moos://remote/restart"):
            self.assertNotIn(gone, self.app)
        self.assertIn('label: root.local("ثبّت RPM", "Install RPM")', self.app)

    def test_the_launcher_actions_hand_off_too(self) -> None:
        entry = configparser.ConfigParser(interpolation=None, strict=False)
        entry.optionxform = str
        entry.read(DESKTOP, encoding="utf-8")
        self.assertEqual(entry["Desktop Entry"]["Actions"], "Device;Settings;Apps;Remote;")
        self.assertEqual(entry["Desktop Entry"]["X-KDE-Shortcuts"], "Meta+Space")
        expected = {"Device": ("Check this device", "moai --panel device"),
                    "Settings": ("Mo AI settings", "moos-settings --section=assistant"),
                    "Apps": ("Install apps", "moos-store"),
                    "Remote": ("Remote control", "moos-settings --section=remote")}
        for action, (name, command) in expected.items():
            with self.subTest(action=action):
                section = entry[f"Desktop Action {action}"]
                self.assertEqual((section["Name"], section["Exec"]), (name, command))
                self.assertRegex(section["Name[ar]"], r"[؀-ۿ]")


if __name__ == "__main__":
    unittest.main(verbosity=2)

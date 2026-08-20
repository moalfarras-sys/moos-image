#!/usr/bin/env python3
"""The terminal settings twin must delegate to the OpenClaw config authority."""

from __future__ import annotations

from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "system_files/usr/bin/moai-config"


class MoAIConfigClientTests(unittest.TestCase):
    def load(self) -> dict:
        return runpy.run_path(str(TOOL), run_name="moai_config_test")

    def test_cloud_choice_uses_api_catalog_and_posts_one_authoritative_shape(self):
        module = self.load()
        scope = module["main"].__globals__
        answers = iter([
            "cloud",
            "openai",
            "https://api.openai.com/v1",
            "gpt-5.4-mini",
            "secret-in-memory",
        ])
        calls = []
        notices = []
        scope["shutil_which"] = lambda _name: "/usr/bin/kdialog"
        scope["dialog"] = lambda *_args: next(answers)
        scope["notice"] = lambda kind, message: notices.append((kind, message))
        scope["current_config"] = lambda: {
            "brain": {"mode": "local", "local_model": "ollama/default"},
            "cloud": {"base": "", "model": "", "has_key": False},
            "providers": [{
                "id": "openai",
                "name": "OpenAI",
                "base": "https://api.openai.com/v1",
                "model": "gpt-5.4-mini",
                "api": "openai-responses",
            }],
        }
        scope["request"] = (
            lambda method, path, body=None:
            calls.append((method, path, body)) or {"ok": True}
        )
        self.assertEqual(module["main"](), 0)
        self.assertEqual(calls, [(
            "POST",
            "/api/config",
            {
                "mode": "cloud",
                "cloud": {
                    "provider": "openai",
                    "base": "https://api.openai.com/v1",
                    "model": "gpt-5.4-mini",
                    "key": "secret-in-memory",
                },
            },
        )])
        self.assertEqual(notices[0][0], "msgbox")

    def test_local_choice_preserves_the_agent_reported_model(self):
        module = self.load()
        scope = module["main"].__globals__
        answers = iter(["local"])
        calls = []
        scope["shutil_which"] = lambda _name: "/usr/bin/kdialog"
        scope["dialog"] = lambda *_args: next(answers)
        scope["notice"] = lambda *_args: None
        scope["current_config"] = lambda: {
            "brain": {"mode": "cloud", "local_model": "ollama/qwen3:4b"},
            "providers": [],
        }
        scope["request"] = (
            lambda method, path, body=None:
            calls.append((method, path, body)) or {"ok": True}
        )
        self.assertEqual(module["main"](), 0)
        self.assertEqual(calls, [(
            "POST", "/api/config",
            {"mode": "local", "local_model": "ollama/qwen3:4b"},
        )])

    def test_tool_contains_no_legacy_config_writer(self):
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("config.json", source)
        self.assertNotIn("openclaw.json", source)
        self.assertNotIn("MOAI_CREDENTIAL_STORE", source)
        self.assertIn('"/api/config"', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Deterministic privacy and fallback contracts for Mo AI Hybrid routing."""
from __future__ import annotations

import runpy
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "system_files/usr/bin/moai-gateway"


def main() -> None:
    gateway = runpy.run_path(str(GATEWAY), run_name="moai_gateway_hybrid_test")
    globals_ = gateway["load_product_cfg"].__globals__
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        globals_["CONFIG"] = str(td / "legacy.json")
        globals_["OPENCLAW_CONFIG"] = str(td / "openclaw.json")
        Path(globals_["CONFIG"]).write_text(json.dumps({"mode": "local"}))
        Path(globals_["OPENCLAW_CONFIG"]).write_text(json.dumps({
            "agents": {"defaults": {"model": {"primary": "cloud/live"}}},
            "models": {"providers": {"cloud": {
                "baseUrl": "https://cloud.example/v1", "apiKey": "shared-key",
                "api": "openai-responses", "models": [{"id": "live"}],
            }}},
        }))
        product = gateway["load_product_cfg"]()
        assert product["mode"] == "cloud"
        assert product["cloud_base"] == "https://cloud.example/v1"
        assert product["cloud_model"] == "live"
        assert product["cloud_key"] == "shared-key"
    parse = gateway["parse_model"]
    resolve = gateway["resolve"]
    choose = gateway["choose_hybrid"]
    assert parse("hybrid") == ("hybrid", "")
    assert parse("hybrid:qwen") == ("hybrid", "qwen")
    assert resolve("", {"mode": "hybrid"}) == ("hybrid", "")

    cloud = {"cloud_base": "https://provider.invalid/v1", "cloud_key": "secret"}
    private = {"messages": [{"role": "user", "content": "secret"}],
               "moai": {"privacy": "private"}}
    assert choose(private, cloud, False) == ("local", "privacy", False)

    image = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": "describe"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}},
    ]}]}
    assert choose(image, cloud, False) == ("local", "private-attachment", False)
    image["moai"] = {"allow_cloud_attachments": True, "prefer": "cloud"}
    assert choose(image, cloud, False) == ("cloud", "complex-task", True)

    simple = {"messages": [{"role": "user", "content": "hello"}]}
    assert choose(simple, cloud, False) == ("local", "fast-private-default", True)
    difficult = {"messages": [{"role": "user", "content": "Refactor this architecture"}]}
    assert choose(difficult, cloud, False) == ("cloud", "complex-task", True)
    assert choose(difficult, {}, False) == ("local", "cloud-not-configured", False)

    client = {
        "primary": "cloud/cloud-default",
        "providers": {
            "cloud": {"models": [{"id": "cloud-default"}, {"id": "hard"}]},
            "ollama": {"models": [{"id": "local-default"}]},
        },
    }
    assert gateway["openclaw_model"](client, "cloud", "hard", {}) == "cloud/hard"
    assert gateway["openclaw_model"](client, "local", "", {}) == "ollama/local-default"
    client["providers"]["ollama"]["baseUrl"] = "http://127.0.0.1:11434/v1"
    # OpenClaw's gateway enforces the provider catalog as a model ALLOWLIST
    # (measured live 2026-08-18: an uncatalogued pulled tag came back HTTP 400
    # "Model 'ollama/qwen2.5:7b-instruct' is not allowed for agent 'main'" and
    # the desktop chat showed only a generic apology). An uncatalogued local
    # model must therefore return "" — the caller then takes the DIRECT path,
    # which serves any pulled tag, vision included — never a guaranteed 400.
    assert gateway["openclaw_model"](
        client, "local", "qwen3-vl:4b", {}) == ""
    # Catalog ids and Ollama tags disagree about ":latest"; match by identity
    # and forward the id OpenClaw actually knows.
    assert gateway["openclaw_model"](
        client, "local", "local-default:latest", {}) == "ollama/local-default"
    assert gateway["openclaw_model"](
        client, "local", "bad\nheader", {}) == ""

    # Desktop agent mode must forward only to the fixed loopback OpenClaw API,
    # preserve the multimodal latest turn, and keep its bearer token out of QML.
    globals_ = gateway["Handler"]._to_agent.__globals__
    with tempfile.TemporaryDirectory() as td:
        fake_bin = Path(td) / "openclaw"
        fake_bin.write_text("", encoding="utf-8")
        globals_["OPENCLAW_BIN"] = str(fake_bin)
        globals_["load_openclaw_client"] = lambda: {**client, "token": "private-token"}
        globals_["ensure_openclaw_gateway"] = lambda: ""
        handler = object.__new__(gateway["Handler"])
        captured = {}
        handler._proxy = lambda method, url, headers, body, wire, streaming: captured.update({
            "method": method, "url": url, "headers": headers,
            "body": json.loads(body), "wire": wire, "streaming": streaming,
        })
        handler._err = lambda code, message: (_ for _ in ()).throw(
            AssertionError(f"unexpected agent error {code}: {message}"))
        request = {
            "messages": [
                {"role": "system", "content": "old system"},
                {"role": "user", "content": "old turn"},
                {"role": "assistant", "content": "old answer"},
                {"role": "user", "content": [
                    {"type": "text", "text": "latest"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,eA=="}},
                ]},
            ],
            "stream": True,
            "moai": {"agent": True, "session": "moai-desktop-test123"},
        }
        assert handler._to_agent(request, "cloud", "hard", {}) is True
        assert captured["url"] == "http://127.0.0.1:18789/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer private-token"
        assert captured["headers"]["x-openclaw-model"] == "cloud/hard"
        assert captured["body"]["user"] == "moai-desktop-test123"
        assert captured["body"]["messages"] == [request["messages"][-1]]
        assert captured["streaming"] is True
        captured.clear()
        assert handler._to_agent(request, "cloud", "cloud-default", {}) is True
        assert "x-openclaw-model" not in captured["headers"]
        request["moai"]["session_key"] = "agent:main:main"
        captured.clear()
        assert handler._to_agent(request, "cloud", "cloud-default", {}) is True
        assert captured["headers"]["x-openclaw-session-key"] == "agent:main:main"
        assert "user" not in captured["body"]
    qml = (ROOT / "system_files/usr/share/moos/apps/moai/main.qml").read_text(encoding="utf-8")
    assert 'agent: true' in qml and 'session: root.chatSessionId' in qml
    assert 'session_key = root.chatOpenClawSessionKey' in qml
    assert 'function agentOpenPrimary(id, key, label)' in qml
    assert 'chatModel.clear()' in qml and 'root.chatModel.clear()' not in qml
    assert 'argv.indexOf("--open-history")' in qml
    assert 'Text.MarkdownText' in qml and 'body.copy()' in qml
    assert 'msg.role.indexOf("tool-") === 0' in qml
    assert 'msg.role === "tool-error" ? root.badColor' in qml
    # Eight tabs: the brain decision (mode + provider + key + local models) has
    # ONE home. The retired Models/Providers/Privacy trio and the door-only
    # Projects/Terminal tabs must not come back, and their old deep-link names
    # must keep landing somewhere sensible.
    for section in ("brain", "openclaw", "telegram", "whatsapp",
                    "voice", "permissions", "memory", "appearance"):
        assert f'{{ id: "{section}"' in qml, f"missing settings section: {section}"
    for retired in ("models", "providers", "privacy", "projects", "terminal"):
        assert f'cfgTab === "{retired}"' not in qml, (
            f"retired settings tab returned: {retired}")
    assert 'models: "brain"' in qml and 'privacy: "brain"' in qml \
        and 'projects: "permissions"' in qml, \
        "old --settings section names must be remapped, not dropped"
    assert '{ id: "hybrid", ar: "هجين ذكي", en: "Smart hybrid"' in qml
    assert 'visible: root.cfgTab === "health"' not in qml
    assert 'root.launch("moos://settings/themes", "MoOS themes")' in qml
    assert 'argv.indexOf("--window-size")' in qml
    assert 'value >= minimum && value <= 7680' in qml
    assert 'function regenerateLast()' in qml
    assert 'root.lastSubmissionContent' in qml
    assert 'root.retryPending = true' in qml
    assert 'Regenerate last reply' in qml
    assert 'xhr.getResponseHeader("X-MoAI-Agent")' in qml
    assert 'argv.indexOf("--prompt")' in qml
    preflight = (ROOT / "system_files/usr/libexec/moai-openclaw-preflight").read_text(
        encoding="utf-8")
    assert "moai/hybrid)" in preflight
    print("Mo AI Hybrid routing tests passed")


if __name__ == "__main__":
    main()

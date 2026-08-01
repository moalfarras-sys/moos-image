#!/usr/bin/env python3
"""Deterministic privacy and fallback contracts for Mo AI Hybrid routing."""
from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "system_files/usr/bin/moai-gateway"


def main() -> None:
    gateway = runpy.run_path(str(GATEWAY), run_name="moai_gateway_hybrid_test")
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
    print("Mo AI Hybrid routing tests passed")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Mo AI's brain is a cloud API. Nothing is ever downloaded to the machine.

OWNER DECISION, 2026-09-06 (docs/MOAI_CLOUD_ONLY_PLAN.md): Mo AI must never
download or run a model on the user's computer, and the default must be usable
without paying and without a credit card.

The measurements behind it, from this repo's own files and the live Oracle A1:

  * first message against a local qwen3:8b on CPU: 923 s, because the agent's
    own ~8.5k-token system prompt is read cold. The KV cache does not survive
    the gaps between phone messages, so most messages pay it again.
  * the engine image alone: 4.21 GB of podman storage, before any weights.
  * cloud, same agent, same language: 9 s flat from the first message.

This gate holds the CATALOGUE half of the contract (stage C1). It deliberately
checks the list's SHAPE, never that a third party is still generous: free tiers
change, and one source already reports Cerebras moving to a card trial. A gate
that asserted "Cerebras is free" would fail on someone else's business decision
rather than on a MoOS regression.

Stages C2-C6 (removing the gateway's local branch, retiring moos-ensure-brain /
moai-idle / moai-local-engine, dropping the engine from the builds) get their
own gates as they land. Until C2 ships, this file must NOT claim the local path
is gone.
"""

import ast
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENT_API = REPO / "system_files/usr/bin/moai-agent-api"
PLAN = REPO / "docs/MOAI_CLOUD_ONLY_PLAN.md"


def catalogue():
    """Parse PROVIDERS out of the shipped file without importing it."""
    src = AGENT_API.read_text(encoding="utf-8")
    block = src.split("PROVIDERS = ", 1)[1]
    depth, end = 0, None
    for i, ch in enumerate(block):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return ast.literal_eval(block[:end])


class Catalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.providers = catalogue()
        cls.free = [p for p in cls.providers if p.get("free")]

    def test_there_are_free_providers_at_all(self) -> None:
        self.assertGreaterEqual(
            len(self.free), 3,
            "Mo AI must offer several no-card providers. Each rate-limits "
            "independently, which is the only reason a free default is usable "
            "at all — one provider's daily cap is not a product.")

    def test_free_providers_come_first(self) -> None:
        """The settings UI renders this order. Free must not be buried."""
        first_paid = next((i for i, p in enumerate(self.providers)
                           if not p.get("free")), len(self.providers))
        last_free = max(i for i, p in enumerate(self.providers) if p.get("free"))
        self.assertLess(
            last_free, first_paid,
            "every free provider must precede every paid one in the catalogue")

    def test_every_free_provider_is_usable_as_shipped(self) -> None:
        """A catalogue entry with no model is a dead menu item."""
        for p in self.free:
            with self.subTest(provider=p["id"]):
                self.assertTrue(p.get("base", "").startswith("https://"),
                                "free providers need an https endpoint")
                self.assertTrue(p.get("model"),
                                "a free entry must pre-select a free model, or "
                                "the user lands on an empty field")
                self.assertIn(p.get("api"), ("openai-completions",
                                             "openai-responses",
                                             "google-generative-ai",
                                             "anthropic-messages"))

    def test_free_labels_say_so_in_both_languages(self) -> None:
        """Arabic is first-class; a free tier the owner cannot identify is not
        discoverable, and this is the one screen where cost is the decision."""
        for p in self.free:
            with self.subTest(provider=p["id"]):
                self.assertIn("free", p["name"].lower())
                self.assertIn("مجاني", p["name"])

    def test_paid_providers_are_kept(self) -> None:
        """Free-by-default is not free-only. The owner asked for both."""
        paid = {p["id"] for p in self.providers if not p.get("free")}
        for keep in ("openai", "anthropic", "google", "custom"):
            self.assertIn(keep, paid)

    def test_ids_are_unique(self) -> None:
        ids = [p["id"] for p in self.providers]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate provider id: {ids}")


class PlanIsRecorded(unittest.TestCase):
    """The owner asked for the plan to live in the repo so every Mo AI follows it."""

    def test_the_plan_exists_and_states_the_contract(self) -> None:
        self.assertTrue(PLAN.is_file(), "docs/MOAI_CLOUD_ONLY_PLAN.md is missing")
        text = PLAN.read_text(encoding="utf-8")
        for required in ("never download", "moai-gateway", "C1", "C2"):
            self.assertIn(required, text, f"the plan must cover: {required}")

    def test_the_plan_keeps_the_privilege_rule(self) -> None:
        """Borrowing Hermes' capabilities must never borrow its local backend:
        AGENTS.md's unbreakable rule is that the model names an action from
        moai-do's allowlist and never executes anything it wrote."""
        text = PLAN.read_text(encoding="utf-8")
        self.assertIn("moai-do", text)
        self.assertRegex(text, r"never.{0,80}execute|execute.{0,80}never")


if __name__ == "__main__":
    unittest.main(verbosity=2)

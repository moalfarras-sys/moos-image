#!/usr/bin/env python3
"""Regression tests for Mo AI's local-engine handoff.

The gateway can be pointed at Ollama through MOAI_LOCAL_UNIT.  moai-control used
to ignore that variable, rewrite RamaLama's environment to Ollama's port, and
keep starting the old moai.service.  On the live workstation that produced more
than 300 failed restarts in one session while the real Ollama brain was healthy.
"""

import os
import re
import runpy
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "system_files/usr/bin/moai-control"
GATEWAY = ROOT / "system_files/usr/bin/moai-gateway"
ENGINE = ROOT / "system_files/usr/libexec/moai-local-engine"
OPENCLAW_BOOTSTRAP = ROOT / "system_files/usr/libexec/moai-openclaw-bootstrap"
MOAI_DO = ROOT / "system_files/usr/bin/moai-do"
WAKE = ROOT / "system_files/usr/bin/moai-wake"


def load_script(path: Path, home: str, local_unit: str | None = None):
    env = {"HOME": home}
    if local_unit is not None:
        env["MOAI_LOCAL_UNIT"] = local_unit
    with mock.patch.dict(os.environ, env, clear=False):
        for name in ("MOAI_LOCAL_UNIT", "MOAI_LOCAL_BACKEND", "MOAI_LOCAL_PORT",
                     "MOAI_LOCAL_MODEL"):
            if name not in env:
                os.environ.pop(name, None)
        return runpy.run_path(str(path), run_name=path.name.replace("-", "_") + "_test")


def load_control(home: str, local_unit: str | None = None):
    return load_script(CONTROL, home, local_unit)


class LocalEngineMigrationTests(unittest.TestCase):
    def test_ollama_selection_disables_legacy_ramalama_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as home:
            env_file = Path(home) / ".config/moos/moai.env"
            env_file.parent.mkdir(parents=True)
            original = "MOAI_PORT=8081\nMOAI_MODEL=ollama://default\n"
            env_file.write_text(original, encoding="utf-8")

            control = load_control(home, "ollama.service")
            calls = []
            scope = control["ensure_front_door"].__globals__
            scope["ENV_FILE"] = str(env_file)
            scope["sysctl"] = lambda *args: calls.append(args)
            scope["user_unit_active"] = lambda _unit: False

            with mock.patch.dict(os.environ, {"HOME": home}, clear=False):
                control["ensure_front_door"]()

            self.assertEqual(control["LOCAL_UNIT"], "ollama.service")
            self.assertIn(("disable", "--now", "moai.service"), calls)
            self.assertIn(("enable", "--now", "moai-gateway.service"), calls)
            self.assertEqual(env_file.read_text(encoding="utf-8"), original)

    def test_ramalama_selection_repairs_only_its_own_port(self):
        with tempfile.TemporaryDirectory() as home:
            env_file = Path(home) / ".config/moos/moai.env"
            env_file.parent.mkdir(parents=True)
            env_file.write_text(
                "MOAI_PORT=8080\nMOAI_MODEL=ollama://qwen3:4b-instruct\n",
                encoding="utf-8",
            )

            control = load_control(home)
            calls = []
            scope = control["ensure_front_door"].__globals__
            scope["ENV_FILE"] = str(env_file)
            scope["sysctl"] = lambda *args: calls.append(args)
            scope["user_unit_active"] = lambda _unit: False

            with mock.patch.dict(os.environ, {"HOME": home}, clear=False):
                control["ensure_front_door"]()

            self.assertEqual(control["LOCAL_UNIT"], "moai.service")
            repaired = env_file.read_text(encoding="utf-8")
            self.assertIn("MOAI_PORT=8081", repaired)
            self.assertIn("MOAI_MODEL=ollama://qwen2.5:7b-instruct", repaired)
            self.assertNotIn("qwen3:4b-instruct", repaired)
            self.assertNotIn(("disable", "--now", "moai.service"), calls)

    def test_ramalama_migration_never_changes_a_custom_model(self):
        with tempfile.TemporaryDirectory() as home:
            env_file = Path(home) / ".config/moos/moai.env"
            env_file.parent.mkdir(parents=True)
            original = "MOAI_PORT=8081\nMOAI_MODEL=ollama://my-private-model:7b\n"
            env_file.write_text(original, encoding="utf-8")
            control = load_control(home)
            scope = control["ensure_front_door"].__globals__
            scope["ENV_FILE"] = str(env_file)
            scope["sysctl"] = lambda *_args: None
            scope["user_unit_active"] = lambda _unit: False
            control["ensure_front_door"]()
            self.assertEqual(env_file.read_text(encoding="utf-8"), original)

    def test_untrusted_unit_name_falls_back_to_fixed_legacy_unit(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home, "evil.service;reboot")
            self.assertEqual(control["LOCAL_UNIT"], "moai.service")
            self.assertEqual(control["LOCAL_BACKEND"], "ramalama")


class OllamaAdapterTests(unittest.TestCase):
    def test_control_lists_real_ollama_tags_and_marks_default_alias(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home, "ollama.service")
            scope = control["local_models"].__globals__
            scope["ollama_models"] = lambda: [
                {"name": "default:latest", "size": 4_700_000_000,
                 "input": ["text", "image"]},
                {"name": "qwen3:4b", "size": 2_500_000_000,
                 "input": ["text"]},
            ]
            rows = control["local_models"]()
            by_name = {row["label"]: row for row in rows}
            self.assertTrue(by_name["default:latest"]["pulled"])
            self.assertTrue(by_name["default:latest"]["serving"])
            self.assertTrue(by_name["qwen3:4b"]["pulled"])
            self.assertEqual(by_name["default:latest"]["input"],
                             ["text", "image"])
            self.assertEqual(by_name["qwen3:4b"]["input"], ["text"])
            self.assertNotIn("qwen3:4b-instruct", by_name)

    def test_ollama_vision_is_taken_from_show_not_the_model_name(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home, "ollama.service")
            scope = control["ollama_models"].__globals__
            scope["ensure_local_api"] = lambda: True
            def request(path, **kwargs):
                if path == "/api/tags":
                    return {"models": [
                        {"name": "plain-name:latest", "size": 10},
                        {"name": "vision-in-name:latest", "size": 20},
                    ]}
                model = kwargs["payload"]["model"]
                return {"capabilities": ["completion", "vision"]} \
                    if model.startswith("plain-name") \
                    else {"capabilities": ["completion"]}
            scope["ollama_request"] = request
            rows = {row["name"]: row for row in control["ollama_models"]()}
            self.assertEqual(rows["plain-name:latest"]["input"],
                             ["text", "image"])
            self.assertEqual(rows["vision-in-name:latest"]["input"], ["text"])

    def test_missing_ollama_default_never_becomes_a_fake_download_button(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home, "ollama.service")
            scope = control["local_models"].__globals__
            scope["ollama_models"] = lambda: []
            rows = control["local_models"]()
            missing = {row["label"] for row in rows if not row["pulled"]}
            allowed = {row["id"] for row in scope["RECOMMENDED_LOCAL"]}
            self.assertNotIn("default", missing)
            self.assertNotIn("default:latest", missing)
            self.assertEqual(missing, allowed)

    def test_control_uses_ollama_json_delete_not_a_shell_command(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home, "moai-brain.service")
            calls = []
            scope = control["delete_model"].__globals__
            scope["local_models"] = lambda: [
                {"label": "default:latest", "pulled": True},
                {"label": "qwen3:4b", "pulled": True},
            ]
            scope["ensure_local_api"] = lambda: True
            scope["ollama_request"] = lambda *args, **kwargs: calls.append((args, kwargs)) or {}
            self.assertEqual(control["delete_model"]("qwen3:4b"), {"ok": True})
            self.assertEqual(
                calls,
                [(("/api/delete",), {
                    "method": "DELETE", "payload": {"model": "qwen3:4b"},
                    "timeout": 120,
                })],
            )

    def test_control_streams_real_ollama_pull_progress(self):
        class Reply:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return iter([
                    b'{"status":"pulling","total":100,"completed":40}\n',
                    b'{"status":"success","total":100,"completed":100}\n',
                ])

        with tempfile.TemporaryDirectory() as home:
            control = load_control(home, "ollama.service")
            seen = []
            scope = control["pull_worker"].__globals__
            scope["ensure_local_api"] = lambda: True

            def fake_open(req, timeout):
                seen.append((req.full_url, req.get_method(),
                             json.loads(req.data.decode("utf-8")), timeout))
                return Reply()

            with mock.patch.object(scope["urllib"].request, "urlopen", fake_open):
                control["pull_worker"]("qwen3:4b", 2.5)
            self.assertEqual(seen[0][0:3], (
                "http://127.0.0.1:11434/api/pull",
                "POST",
                {"model": "qwen3:4b", "stream": True},
            ))
            self.assertEqual(scope["_pull"]["state"], "done")
            self.assertEqual(scope["_pull"]["percent"], 100)

    # THESE THREE TESTS WERE NOT DELETED — THEY WERE STRENGTHENED.
    #
    # They were written to guarantee one thing: a chat message must never start
    # a model download. Stage C2 (docs/MOAI_CLOUD_ONLY_PLAN.md) makes that
    # guarantee absolute rather than conditional — ensure_local() now refuses
    # before it can take its lock or reach systemd, so there is no longer a
    # "substitute an installed model" path to get right, and no "no model is
    # downloaded" error to phrase honestly. The same intent, enforced harder.
    #
    # Each keeps its original hostile stub: if any future edit reopens the door,
    # these fail on the systemctl/env-write the stubs forbid, not merely on a
    # changed string.

    def test_gateway_never_touches_a_unit_or_env_for_a_model(self):
        with tempfile.TemporaryDirectory() as home:
            gateway = load_script(GATEWAY, home, "ollama.service")
            scope = gateway["ensure_local"].__globals__
            scope["local_online"] = lambda *args, **kwargs: self.fail(
                "ensure_local probed a local engine after C2 closed the door")
            scope["pulled_models"] = lambda: self.fail(
                "ensure_local read models from disk after C2 closed the door")
            scope["systemctl"] = lambda _verb: self.fail(
                "ensure_local touched systemd after C2 closed the door")
            scope["set_env_model"] = lambda _model: self.fail(
                "ensure_local rewrote moai.env after C2 closed the door")
            error, model = gateway["ensure_local"]("qwen3:4b")
            self.assertEqual(model, "", "no local model may be selected")
            self.assertTrue(error, "the refusal must explain itself to the user")

    def test_a_chat_message_can_never_start_a_download(self):
        # The original reason this file guards ensure_local: the shipped default
        # once named a model that was never on disk, and a first message died
        # with a 503 while the orb said Online. Neither outcome is reachable now
        # — with no engine and no disk read, there is nothing to be wrong about.
        for unit, installed in (("moai-brain.service", ["default:latest"]),
                                ("moai-brain.service", []),
                                ("ollama.service", ["qwen3:4b"])):
            with self.subTest(unit=unit, installed=installed):
                with tempfile.TemporaryDirectory() as home:
                    gateway = load_script(GATEWAY, home, unit)
                    scope = gateway["ensure_local"].__globals__
                    scope["pulled_models"] = lambda: self.fail(
                        "a chat message reached the model list on disk")
                    scope["systemctl"] = lambda _verb: self.fail(
                        "a chat message reached systemd")
                    error, model = gateway["ensure_local"]("qwen3:4b")
                    self.assertEqual(model, "")
                    self.assertTrue(error)

    def test_the_refusal_sends_the_user_somewhere_useful(self):
        """A dead end is not an answer. It must name the free way out, in both
        languages, because this is the screen where the user is stuck."""
        with tempfile.TemporaryDirectory() as home:
            gateway = load_script(GATEWAY, home, "moai-brain.service")
            error, _ = gateway["ensure_local"]("qwen3:4b")
            for provider in ("Cerebras", "Groq", "NVIDIA NIM", "OpenRouter"):
                self.assertIn(provider, error)
            self.assertIn("سحابي", error)
            self.assertIn("cloud", error.lower())


class RuntimeRelationshipTests(unittest.TestCase):
    def test_shell_resolver_accepts_only_known_units(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as bin_dir:
            config = Path(home) / ".config/moos/moai-local.env"
            config.parent.mkdir(parents=True)
            systemctl = Path(bin_dir) / "systemctl"
            systemctl.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            systemctl.chmod(0o755)
            env = {
                **os.environ,
                "HOME": home,
                "XDG_CONFIG_HOME": str(Path(home) / ".config"),
                "PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
            }
            config.write_text("MOAI_LOCAL_UNIT=ollama.service\n", encoding="utf-8")
            good = subprocess.run([str(ENGINE), "unit"], env=env,
                                  capture_output=True, text=True, check=True)
            self.assertEqual(good.stdout.strip(), "ollama.service")
            config.write_text("MOAI_LOCAL_UNIT=evil.service;reboot\n", encoding="utf-8")
            bad = subprocess.run([str(ENGINE), "unit"], env=env,
                                 capture_output=True, text=True, check=True)
            self.assertEqual(bad.stdout.strip(), "moai.service")

    def test_selection_file_wins_over_unexpanded_systemd_default(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as bin_dir:
            config = Path(home) / ".config/moos/moai-local.env"
            config.parent.mkdir(parents=True)
            config.write_text("MOAI_LOCAL_UNIT=ollama.service\n", encoding="utf-8")
            systemctl = Path(bin_dir) / "systemctl"
            systemctl.write_text(
                "#!/bin/sh\n"
                "echo 'MOAI_LOCAL_UNIT=moai.service MOAI_LOCAL_BACKEND=ramalama'\n",
                encoding="utf-8",
            )
            systemctl.chmod(0o755)
            env = {
                **os.environ,
                "HOME": home,
                "XDG_CONFIG_HOME": str(Path(home) / ".config"),
                "PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
            }
            resolved = subprocess.run(
                [str(ENGINE), "unit"], env=env,
                capture_output=True, text=True, check=True,
            )
            self.assertEqual(resolved.stdout.strip(), "ollama.service")

    def test_all_runtime_helpers_use_the_shared_resolver(self):
        for relative in (
            "system_files/usr/bin/moai-start",
            "system_files/usr/bin/moai-idle",
            "system_files/usr/bin/moos-gpu-headroom",
            "system_files/usr/bin/moos-fast-remote",
            "system_files/usr/bin/openclaw-idle",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("/usr/libexec/moai-local-engine", text, relative)

    def test_retired_brain_scheduler_is_not_shipped_or_enabled(self):
        text = (ROOT / "system_files/usr/bin/moai-do").read_text(encoding="utf-8")
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
        for unit in ("moos-ensure-brain.service", "moos-ensure-brain.timer",
                     "moai-idle.service", "moai-idle.timer"):
            with self.subTest(unit=unit):
                self.assertFalse(
                    (ROOT / "system_files/usr/lib/systemd/user" / unit).exists())
                self.assertNotIn(f"systemctl --global enable {unit}", build)
        # Upgrade migration must keep retiring copies left by an older image.
        migration = (ROOT / "system_files/usr/libexec/moai-cloud-migrate").read_text(
            encoding="utf-8")
        self.assertIn("'moos-ensure-brain.service'", migration)
        self.assertIn("'moai-idle.timer'", migration)

    def test_setup_brain_opens_cloud_settings_without_touching_model_container(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as bin_dir:
            systemctl_log = Path(home) / "systemctl.log"
            podman = Path(bin_dir) / "podman"
            podman.write_text("#!/bin/sh\necho ollama\n", encoding="utf-8")
            podman.chmod(0o755)
            systemctl = Path(bin_dir) / "systemctl"
            systemctl.write_text(
                f"#!/bin/sh\necho \"$*\" >> {systemctl_log}\nexit 0\n",
                encoding="utf-8",
            )
            systemctl.chmod(0o755)
            env = {
                **os.environ,
                "HOME": home,
                "XDG_CONFIG_HOME": str(Path(home) / ".config"),
                "PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
            }
            # SPEC D1/D5: the brain is set up on the Mo AI page of System Settings — one
            # surface, no terminal wizard, no privilege.
            opened = Path(home) / "settings.argv"
            settings = Path(bin_dir) / "moos-settings"
            settings.write_text(f"#!/bin/sh\necho \"$*\" > {opened}\n", encoding="utf-8")
            settings.chmod(0o755)
            config = Path(bin_dir) / "moai-config"
            config.write_text(f"#!/bin/sh\necho wizard >> {opened}\n", encoding="utf-8")
            config.chmod(0o755)
            result = subprocess.run(
                [str(MOAI_DO), "setup-brain"], input="y\n", env=env,
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(opened.read_text(encoding="utf-8").strip(), "--section=assistant")
            self.assertFalse(
                (Path(home) / ".config/moos/moai-local.env").exists(),
            )
            self.assertFalse(systemctl_log.exists())

    def test_gateway_and_control_read_the_same_selection_file(self):
        for unit in ("moai-gateway.service", "moai-control.service"):
            text = (ROOT / "system_files/usr/lib/systemd/user" / unit).read_text(
                encoding="utf-8")
            self.assertIn(
                "EnvironmentFile=-%h/.config/moos/moai-local.env", text, unit)

    def test_brain_and_speech_quadlets_are_woken_on_demand(self):
        for name in ("moai-brain.container", "speaches.container"):
            text = (
                ROOT / "system_files/usr/share/moos/containers" / name
            ).read_text(encoding="utf-8")
            lines = {line.strip() for line in text.splitlines()}
            self.assertNotIn("[Install]", lines, name)
            self.assertNotIn("WantedBy=default.target", lines, name)

        action = MOAI_DO.read_text(encoding="utf-8")
        self.assertIn("strip_legacy_moos_quadlet_autostart", action)
        self.assertIn("$'[Install]\\nWantedBy=default.target'", action)
        self.assertIn("chmod --reference=", action)

    def test_phone_wake_reports_systemd_start_failure_instead_of_fake_success(self):
        with tempfile.TemporaryDirectory() as home:
            wake = load_script(WAKE, home)
            scope = wake["start_gateway"].__globals__
            calls = []

            class Result:
                returncode = 1

            with mock.patch.object(
                scope["subprocess"], "run",
                side_effect=lambda argv, **_kwargs: calls.append(tuple(argv)) or Result(),
            ):
                self.assertFalse(wake["start_gateway"]())
            self.assertIn(
                ("systemctl", "--user", "start", "openclaw-gateway.service"),
                calls,
            )

    def test_phone_wake_systemctl_calls_are_bounded(self):
        with tempfile.TemporaryDirectory() as home:
            wake = load_script(WAKE, home)
            scope = wake["gateway_active"].__globals__

            class Result:
                returncode = 0

            calls = []
            with mock.patch.object(
                scope["subprocess"], "run",
                side_effect=lambda argv, **kwargs: calls.append((argv, kwargs)) or Result(),
            ):
                self.assertTrue(wake["gateway_active"]())
            self.assertEqual(calls[0][1]["timeout"], 5)
            self.assertIs(calls[0][1]["stdout"], subprocess.DEVNULL)
            self.assertIs(calls[0][1]["stderr"], subprocess.DEVNULL)

    def test_phone_wake_recovers_from_a_wedged_systemctl_client(self):
        with tempfile.TemporaryDirectory() as home:
            wake = load_script(WAKE, home)
            scope = wake["start_gateway"].__globals__
            calls = []

            class Result:
                returncode = 0

            def run(argv, **kwargs):
                calls.append((tuple(argv), kwargs.get("timeout")))
                if "start" in argv:
                    raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
                return Result()

            scope["gateway_active"] = lambda: False
            with mock.patch.object(scope["subprocess"], "run", side_effect=run):
                self.assertFalse(wake["start_gateway"]())
            self.assertIn(
                (("systemctl", "--user", "start", "openclaw-gateway.service"), 110),
                calls,
            )

    def test_phone_wake_accepts_a_gateway_that_won_the_timeout_race(self):
        with tempfile.TemporaryDirectory() as home:
            wake = load_script(WAKE, home)
            scope = wake["start_gateway"].__globals__

            class Result:
                returncode = 0

            def run(argv, **kwargs):
                if "start" in argv:
                    raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
                return Result()

            scope["gateway_active"] = lambda: True
            with mock.patch.object(scope["subprocess"], "run", side_effect=run):
                self.assertTrue(wake["start_gateway"]())

    def test_phone_wake_acks_only_after_gateway_is_active(self):
        with tempfile.TemporaryDirectory() as home:
            wake = load_script(WAKE, home)
            scope = wake["poll_until_wake"].__globals__
            events = []
            updates = iter([
                {
                    "ok": True,
                    "result": [{
                        "update_id": 42,
                        "message": {
                            "from": {"id": 7},
                            "chat": {"id": 70},
                        },
                    }],
                },
            ])
            scope["gateway_active"] = lambda: False
            scope["tg_call"] = lambda *_args, **_kwargs: next(updates)
            scope["start_gateway"] = lambda: events.append("start") or True
            scope["send_ack"] = lambda *_args: events.append("ack")
            wake["poll_until_wake"]("secret", {"7"})
            self.assertEqual(events, ["start", "ack"])


class OpenClawBootstrapTests(unittest.TestCase):
    def test_memory_defaults_to_keyword_only_without_hidden_paid_embeddings(self):
        with tempfile.TemporaryDirectory() as home:
            bootstrap = load_script(OPENCLAW_BOOTSTRAP, home)
            fresh = bootstrap["merge_baseline"]({})
            self.assertEqual(fresh["memory"]["search"]["provider"], "none")

            configured = bootstrap["merge_baseline"]({
                "memory": {"search": {"provider": "ollama", "model": "owner/embed"}}
            })
            self.assertEqual(
                configured["memory"]["search"],
                {"provider": "ollama", "model": "owner/embed"},
            )

    def test_desktop_endpoint_and_hybrid_provider_share_the_agent_runtime(self):
        with tempfile.TemporaryDirectory() as home:
            bootstrap = load_script(OPENCLAW_BOOTSTRAP, home)
            merged = bootstrap["merge_baseline"]({
                "agents": {"defaults": {"model": {"primary": "cloud/current"}}},
                "models": {"providers": {"cloud": {
                    "baseUrl": "https://provider.invalid/v1",
                    "apiKey": "secret", "api": "openai-responses",
                    "models": [{"id": "current"}],
                }}},
            })
            endpoint = merged["gateway"]["http"]["endpoints"]["chatCompletions"]
            self.assertTrue(endpoint["enabled"])
            self.assertEqual(endpoint["maxBodyBytes"], 20 * 1024 * 1024)
            hybrid = merged["models"]["providers"]["moai"]
            self.assertEqual(hybrid["baseUrl"], "http://127.0.0.1:8080/v1")
            self.assertEqual(hybrid["api"], "openai-completions")
            self.assertIn("moai/hybrid", merged["agents"]["defaults"]["models"])
            self.assertIn("cloud/current", merged["agents"]["defaults"]["models"])

    def test_whatsapp_uses_an_explicit_trusted_plugin_inventory(self):
        with tempfile.TemporaryDirectory() as home:
            bootstrap = load_script(OPENCLAW_BOOTSTRAP, home)
            merged = bootstrap["merge_baseline"]({
                "channels": {"whatsapp": {"enabled": True}},
                "plugins": {"entries": {"whatsapp": {"enabled": True}}},
            })
            self.assertEqual(
                merged["plugins"]["allow"],
                bootstrap["MOAI_WHATSAPP_PLUGIN_ALLOW"],
            )

            custom = ["memory-core", "whatsapp", "owner-plugin"]
            preserved = bootstrap["merge_baseline"]({
                "channels": {"whatsapp": {"enabled": True}},
                "plugins": {"allow": custom.copy()},
            })
            self.assertEqual(preserved["plugins"]["allow"], custom)

            fresh = bootstrap["merge_baseline"]({})
            self.assertNotIn("allow", fresh.get("plugins", {}))

    def test_exact_legacy_gateway_shadow_is_backed_up_but_custom_unit_is_preserved(self):
        with tempfile.TemporaryDirectory() as home:
            bootstrap = load_script(OPENCLAW_BOOTSTRAP, home)
            scope = bootstrap["retire_legacy_gateway_unit"].__globals__
            system_unit = Path(home) / "usr/openclaw-gateway.service"
            system_unit.parent.mkdir(parents=True)
            system_unit.write_text("signed image unit\n", encoding="utf-8")
            scope["SYSTEM_GATEWAY_UNIT"] = system_unit
            legacy = scope["LEGACY_GATEWAY_UNIT"]
            legacy.parent.mkdir(parents=True)
            legacy_text = (
                "[Unit]\n"
                "Description=OpenClaw Gateway (local agent, Telegram channel)\n"
                "Requires=ollama.service\n"
                "[Service]\n"
                "ExecStart=%h/.local/bin/openclaw gateway\n"
            )
            legacy.write_text(legacy_text, encoding="utf-8")
            real_run = scope["subprocess"].run
            calls = []
            scope["subprocess"].run = lambda argv, **_kwargs: (
                calls.append(argv) or subprocess.CompletedProcess(argv, 0, "", "")
            )
            try:
                self.assertTrue(bootstrap["retire_legacy_gateway_unit"]())
            finally:
                scope["subprocess"].run = real_run
            self.assertFalse(legacy.exists())
            backups = list(scope["MIGRATION_DIR"].glob("openclaw-gateway.service.legacy*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), legacy_text)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(calls, [["systemctl", "--user", "daemon-reload"]])

            custom = "[Service]\nExecStart=/owner/custom-agent\n"
            legacy.write_text(custom, encoding="utf-8")
            self.assertFalse(bootstrap["retire_legacy_gateway_unit"]())
            self.assertEqual(legacy.read_text(encoding="utf-8"), custom)

    def test_existing_only_does_not_create_a_fresh_account_config(self):
        with tempfile.TemporaryDirectory() as home:
            result = subprocess.run(
                [str(OPENCLAW_BOOTSTRAP), "--existing-only"],
                env={**os.environ, "HOME": home},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((Path(home) / ".openclaw").exists())

    def test_retired_audio_key_migrates_to_media_cli_schema(self):
        with tempfile.TemporaryDirectory() as home:
            bootstrap = load_script(OPENCLAW_BOOTSTRAP, home)
            config = {
                "audio": {
                    "transcription": {
                        "command": ["/old/transcribe", "{input}"],
                    }
                }
            }
            merged = bootstrap["merge_baseline"](config)
            self.assertNotIn("audio", merged)
            audio = merged["tools"]["media"]["audio"]
            self.assertTrue(audio["enabled"])
            self.assertEqual(
                audio["models"],
                [
                    {
                        "type": "cli",
                        "command": "/usr/bin/moai-transcribe",
                        "args": ["{{MediaPath}}"],
                        "timeoutSeconds": 300,
                    }
                ],
            )

    def test_existing_media_model_is_preserved(self):
        with tempfile.TemporaryDirectory() as home:
            bootstrap = load_script(OPENCLAW_BOOTSTRAP, home)
            existing = {
                "provider": "openai",
                "model": "gpt-4o-transcribe",
            }
            merged = bootstrap["merge_baseline"](
                {
                    "tools": {
                        "media": {
                            "audio": {
                                "enabled": False,
                                "models": [existing.copy()],
                            }
                        }
                    }
                }
            )
            audio = merged["tools"]["media"]["audio"]
            self.assertFalse(audio["enabled"])
            self.assertEqual(audio["models"], [existing])

    def test_existing_working_docker_command_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as home:
            bootstrap = load_script(OPENCLAW_BOOTSTRAP, home)
            local_bin = Path(home) / ".local/bin"
            local_bin.mkdir(parents=True)
            docker = local_bin / "docker"
            original = "#!/bin/sh\necho 'Docker version 28.0.0'\n"
            docker.write_text(original, encoding="utf-8")
            docker.chmod(0o755)
            fake_podman = Path(home) / "podman"
            fake_podman.write_text(
                "#!/bin/sh\necho 'podman version 5.6.0'\n", encoding="utf-8"
            )
            fake_podman.chmod(0o755)
            scope = bootstrap["ensure_podman_docker_shim"].__globals__
            scope["PODMAN"] = fake_podman
            bootstrap["ensure_podman_docker_shim"]()
            self.assertEqual(docker.read_text(encoding="utf-8"), original)


class AgentDetectionTests(unittest.TestCase):
    """Mo AI must not report its OWN installs as missing.

    `moai-do install-codex|install-claude|install-opencode` install into ~/.local/bin
    (npm --global --prefix ~/.local). But a systemd USER service inherits a minimal
    PATH — measured live on the maintainer's machine, moai-control ran with
    PATH=/usr/local/sbin:/usr/local/bin:/usr/bin and no ~/.local/bin — so a
    shutil.which() check answered False for all three while they sat installed and on
    the user's own interactive PATH.

    That was not cosmetic: /quick feeds `agents` into the UI's agent cards AND into the
    machine context handed to the model ("Coding agents installed: codex=no"), so Mo AI
    installed a tool and then told both the user and itself that it did not exist.
    """

    def test_agents_installed_in_local_bin_are_found_without_them_on_PATH(self):
        with tempfile.TemporaryDirectory() as home:
            local_bin = Path(home) / ".local/bin"
            local_bin.mkdir(parents=True)
            for agent in ("codex", "claude", "opencode"):
                tool = local_bin / agent
                tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                tool.chmod(0o755)
            control = load_control(home)
            command_exists = control["command_exists"]
            # Exactly the PATH the live user service has: no ~/.local/bin in it.
            with mock.patch.dict(os.environ,
                                 {"HOME": home,
                                  "PATH": "/usr/local/sbin:/usr/local/bin:/usr/bin"},
                                 clear=False):
                for agent in ("codex", "claude", "opencode"):
                    with self.subTest(agent=agent):
                        self.assertTrue(
                            command_exists(agent),
                            f"{agent} is installed in ~/.local/bin (where moai-do puts it) "
                            "but Mo AI reports it missing — the user installs an agent "
                            "through Mo AI and Mo AI keeps saying it is not installed")
                # A tool that really is absent must still be False, or the check is useless.
                self.assertFalse(command_exists("moos-definitely-not-installed"))



class ToolResultsForTheModelTests(unittest.TestCase):
    """What a moai-do tool prints reaches a CLOUD model, so it is redacted first."""

    def test_moai_do_output_is_redacted_and_others_are_only_clipped(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home)
            raw = ("default via 192.168.1.1 dev wlp3s0\nnameserver 192.168.1.53\n"
                   "token = sk-abcdefghijklmnopqrstuv\nlink/ether 3c:22:fb:12:34:56\n"
                   "/var/home/moos/.config/secret\nlo 127.0.0.1 ok\n")
            shown = control["_for_model"]("moai-do", raw)
            for leaked in ("192.168.1.1", "192.168.1.53", "sk-abcdefghijklmnopqrstuv",
                           "3c:22:fb:12:34:56", "/var/home/moos"):
                self.assertNotIn(leaked, shown)
            self.assertIn("[redacted]", shown)
            self.assertIn("127.0.0.1", shown, "loopback identifies nobody and explains a service")
            self.assertEqual(control["_for_model"]("moos-control", "Volume 40%"), "Volume 40%")

    def test_the_owners_own_paths_stay_findable_and_nobody_elses_do(self):
        """The support bundle's location is the owner's own path: `~`, never `[redacted]`."""
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home)
            raw = ("✓ /var/home/owner/.cache/moos/support/moos-support-20260924.txt\n"
                   "also /home/owner/Downloads and /var/home/owner\n"
                   "not /var/home/ownerx/notes, /home/alice/secret or /mnt/var/home/owner/x\n")
            with mock.patch.dict(os.environ, {"HOME": "/var/home/owner"}):
                shown = control["_for_model"]("moai-do", raw)
            self.assertIn("✓ ~/.cache/moos/support/moos-support-20260924.txt", shown)
            self.assertIn("also ~/Downloads and ~\n", shown)
            for leaked in ("ownerx", "alice", "/var/home/owner", "/home/owner"):
                self.assertNotIn(leaked, shown)
            self.assertEqual(shown.count("[redacted]"), 3, shown)

    def test_a_missing_redactor_withholds_instead_of_sending_raw(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home)
            scope = control["_for_model"].__globals__
            scope["_redactor"] = lambda: None
            self.assertEqual(control["_for_model"]("moai-do", "ip 10.1.2.3"), scope["WITHHELD"])

    def test_read_only_moai_do_tools_go_through_the_redactor(self):
        """Executed end to end: a read-only report with an address in it comes back redacted."""
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as bin_dir:
            fake = Path(bin_dir) / "moai-do"
            fake.write_text("#!/bin/sh\necho \"gateway 10.20.30.40 via wlan0\"\n",
                            encoding="utf-8")
            fake.chmod(0o755)
            control = load_control(home)
            with mock.patch.dict(os.environ, {"PATH": bin_dir + os.pathsep + os.environ["PATH"]}):
                code, result = control["execute_tool"]({"name": "net_doctor", "arguments": {}})
            self.assertEqual(code, 200, result)
            self.assertNotIn("10.20.30.40", result["output"])
            self.assertIn("[redacted]", result["output"])


class IslandJobTokenTests(unittest.TestCase):
    """SPEC D6: a confirmed job is a FILE NAME the Island can watch — never its arguments."""

    def run_job(self, home, runtime, tool, script, arguments=None):
        bin_dir = Path(home) / "bin"
        bin_dir.mkdir(exist_ok=True)
        fake = bin_dir / "moai-do"
        fake.write_text(script, encoding="utf-8")
        fake.chmod(0o755)
        control = load_control(home)
        scope = control["execute_tool"].__globals__
        scope["JOB_TOKEN_LINGER"] = 0.4
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime,
                                          "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}):
            code, started = control["execute_tool"]({"name": tool, "confirmed": True,
                                                     "arguments": arguments or {}})
            self.assertEqual(code, 202, started)
            return control, started["job"]

    def tokens(self, runtime):
        # What the Island's `job-*` filter sees: a half-written temporary is never a token.
        folder = Path(runtime) / "moai-jobs"
        return sorted(path.name for path in folder.glob("job-*")) if folder.is_dir() else []

    def wait_for(self, runtime, predicate, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            names = self.tokens(runtime)
            if predicate(names):
                return names
            time.sleep(0.05)
        return self.tokens(runtime)

    def test_a_job_moves_running_to_done_and_then_leaves(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as runtime:
            control, job = self.run_job(home, runtime, "install_app",
                                        "#!/bin/sh\nsleep 0.6\necho installed\n",
                                        {"app_id": "org.example.Secret"})
            running = self.wait_for(runtime, lambda names: any("-running-" in n for n in names))
            self.assertEqual(running, [f"job-{job[:8]}-running-install_app"])
            done = self.wait_for(runtime, lambda names: any("-done-" in n for n in names))
            self.assertEqual(done, [f"job-{job[:8]}-done-install_app"])
            self.assertEqual(self.wait_for(runtime, lambda names: not names), [],
                             "a finished job's token must leave after its linger")
            for name in running + done:
                self.assertNotIn("Secret", name, "an argument leaked into the token")
            folder = Path(runtime) / "moai-jobs"
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)

    def test_a_failed_job_says_failed(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as runtime:
            _control, job = self.run_job(home, runtime, "update_apps",
                                         "#!/bin/sh\necho nope\nexit 3\n")
            failed = self.wait_for(runtime, lambda names: any("-failed-" in n for n in names))
            self.assertEqual(failed, [f"job-{job[:8]}-failed-update_apps"])

    def test_names_are_only_ever_the_fixed_shape(self):
        with tempfile.TemporaryDirectory() as home:
            name = load_control(home)["_job_token_name"]
            self.assertEqual(name("0123abcd99", "running", "system_update"),
                             "job-0123abcd-running-system_update")
            for args in (("0123abcd", "running", "../x"), ("0123abcd", "paused", "x"),
                         ("ZZZZZZZZ", "done", "x"), ("0123abcd", "done", "a" * 41),
                         ("0123abcd", "done", "install app")):
                self.assertIsNone(name(*args), args)

    def test_no_runtime_dir_publishes_nothing_and_still_runs(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("XDG_RUNTIME_DIR", None)
                self.assertIsNone(control["_publish_job_token"]("0123abcd", "x_y", "running"))

    def test_the_folder_is_chosen_when_the_job_is_accepted(self):
        """The worker thread must not read the environment: it may run after it changed.

        A test that patched XDG_RUNTIME_DIR around execute_tool, and whose worker thread ran
        after the patch ended, put its tokens in the owner's real runtime directory. The
        thread is held back here until the environment points somewhere else.
        """
        import threading as real_threading
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as accepted, \
                tempfile.TemporaryDirectory() as later:
            bin_dir = Path(home) / "bin"
            bin_dir.mkdir()
            (bin_dir / "moai-do").write_text("#!/bin/sh\necho done\n", encoding="utf-8")
            (bin_dir / "moai-do").chmod(0o755)
            control = load_control(home)
            scope = control["execute_tool"].__globals__
            scope["JOB_TOKEN_LINGER"] = 60.0
            held = []
            scope["threading"] = SimpleNamespace(Thread=lambda target, args, daemon: (
                SimpleNamespace(start=lambda: held.append((target, args)))))
            try:
                with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": accepted,
                                                  "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}):
                    code, started = control["execute_tool"]({"name": "update_apps",
                                                             "confirmed": True, "arguments": {}})
            finally:
                scope["threading"] = real_threading
            self.assertEqual(code, 202, started)
            self.assertEqual(len(held), 1)
            target, args = held[0]
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": later}):
                target(*args)
            self.assertEqual(self.tokens(accepted), [f"job-{started['job'][:8]}-done-update_apps"])
            self.assertEqual(self.tokens(later), [], "the job wrote where the environment "
                             "pointed when it RAN, not where it was accepted")

    def test_an_ended_token_is_stamped_when_it_ends(self):
        """A rename keeps the old mtime; the Island and the sweep read it as the state's age."""
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as runtime:
            control = load_control(home)
            folder = Path(runtime) / "moai-jobs"
            publish = control["_publish_job_token"]
            running = publish("0123abcd", "system_update", "running", folder=folder)
            hour_ago = time.time() - 3600
            os.utime(folder / running, (hour_ago, hour_ago))
            before = time.time() - 5
            done = publish("0123abcd", "system_update", "done", running, folder=folder)
            self.assertEqual(done, "job-0123abcd-done-system_update")
            self.assertGreaterEqual((folder / done).stat().st_mtime, before,
                                    "a job that ran for an hour ended 'an hour ago'")

    def test_ended_tokens_nobody_removed_are_swept_on_the_next_publish(self):
        """A process that exits before its linger timer fires must not leave a chip forever."""
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as runtime:
            control = load_control(home)
            folder = Path(runtime) / "moai-jobs"
            folder.mkdir(mode=0o700)
            old = time.time() - 60
            planted = {"job-00000001-done-optimize_system": old,
                       "job-00000002-failed-fix_audio": old,
                       "job-00000003-done-install_app": time.time() - 1,
                       "job-00000004-running-system_update": time.time() - 3600}
            for name, stamp in planted.items():
                (folder / name).write_text("")
                os.utime(folder / name, (stamp, stamp))
            control["_publish_job_token"]("0123abcd", "update_apps", "running", folder=folder)
            self.assertEqual(self.tokens(runtime), [
                "job-00000003-done-install_app",       # still inside its linger
                "job-00000004-running-system_update",  # running: only start-up clears these
                "job-0123abcd-running-update_apps",
            ])

    def test_every_test_that_runs_a_confirmed_job_owns_its_runtime_directory(self):
        """A confirmed job writes an Island token: from a test, never into the live session.

        tests/test_moai_confirmation_flow.py ran confirmed jobs in-process with the owner's
        XDG_RUNTIME_DIR, and every gate run on the station left 'job done/failed' tokens the
        live Island would show. Any test that sends a confirmed job to moai-control must set
        its own XDG_RUNTIME_DIR.
        """
        offenders = []
        for test in sorted((ROOT / "tests").glob("*.py")):
            text = test.read_text(encoding="utf-8")
            runs_confirmed = re.search(r'"confirmed"\s*:\s*True', text) is not None
            loads_control = "usr/bin/moai-control" in text
            if runs_confirmed and loads_control and "XDG_RUNTIME_DIR" not in text:
                offenders.append(test.name)
        self.assertEqual(offenders, [])

    def test_startup_clears_tokens_of_a_previous_run(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as runtime:
            folder = Path(runtime) / "moai-jobs"
            folder.mkdir()
            (folder / "job-0123abcd-running-system_update").write_text("")
            control = load_control(home)
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}):
                control["_clear_job_tokens"]()
            self.assertEqual(list(folder.iterdir()), [])
            source = CONTROL.read_text(encoding="utf-8")
            main = source[source.index('if __name__ == "__main__":'):]
            self.assertIn("_clear_job_tokens()", main)


class BootedVersionTests(unittest.TestCase):
    """The version Mo AI quotes is the booted image's, not the base's os-release stamp."""

    def test_scan_reports_the_booted_deployment_version(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home)
            status = json.dumps({"deployments": [
                {"booted": False, "version": "44.20260924.925"},
                {"booted": True, "version": "44.20260924.929"}]})

            class Done:
                returncode = 0
                stdout = status

            scope = control["booted_image_version"].__globals__
            with mock.patch.object(scope["subprocess"], "run", return_value=Done()):
                self.assertEqual(control["booted_image_version"](), "44.20260924.929")

    def test_os_release_is_only_the_fallback(self):
        with tempfile.TemporaryDirectory() as home:
            control = load_control(home)
            scope = control["booted_image_version"].__globals__
            scope["_image_version_cache"].update(at=0.0, value="")
            with mock.patch.object(scope["subprocess"], "run", side_effect=OSError("no rpm-ostree")), \
                    mock.patch.dict(scope, {"_first_line": lambda *_a: "44.20260924.0"}):
                self.assertEqual(control["booted_image_version"](), "44.20260924.0")
            source = CONTROL.read_text(encoding="utf-8")
            scan = source[source.index("def scan() -> dict:"):source.index("def scan() -> dict:") + 900]
            self.assertIn('"version": booted_image_version()', scan)
            self.assertNotIn('"version": _first_line("/etc/os-release"', scan)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Regression tests for Mo AI's local-engine handoff.

The gateway can be pointed at Ollama through MOAI_LOCAL_UNIT.  moai-control used
to ignore that variable, rewrite RamaLama's environment to Ollama's port, and
keep starting the old moai.service.  On the live workstation that produced more
than 300 failed restarts in one session while the real Ollama brain was healthy.
"""

import os
import runpy
import json
import subprocess
import tempfile
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

    def test_gateway_passes_ollama_model_without_restarting_or_rewriting(self):
        with tempfile.TemporaryDirectory() as home:
            gateway = load_script(GATEWAY, home, "ollama.service")
            scope = gateway["ensure_local"].__globals__
            scope["local_online"] = lambda *args, **kwargs: True
            scope["pulled_models"] = lambda: ["default:latest", "qwen3:4b"]
            scope["systemctl"] = lambda _verb: self.fail("Ollama model switch restarted a unit")
            scope["set_env_model"] = lambda _model: self.fail("Ollama rewrote moai.env")
            self.assertEqual(gateway["ensure_local"]("qwen3:4b"), "")

    def test_gateway_refuses_missing_model_without_downloading(self):
        with tempfile.TemporaryDirectory() as home:
            gateway = load_script(GATEWAY, home, "moai-brain.service")
            scope = gateway["ensure_local"].__globals__
            scope["local_online"] = lambda *args, **kwargs: True
            scope["pulled_models"] = lambda: ["default:latest"]
            message = gateway["ensure_local"]("qwen3:4b")
            self.assertIn("not downloaded", message)
            self.assertIn("Settings", message)


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

    def test_setup_brain_selects_ollama_once_and_retires_legacy(self):
        text = (ROOT / "system_files/usr/bin/moai-do").read_text(encoding="utf-8")
        body = text.split("setup_brain_impl() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("MOAI_LOCAL_UNIT=$model_unit", body)
        self.assertIn("MOAI_LOCAL_BACKEND=ollama", body)
        self.assertIn("MOAI_LOCAL_PORT=11434", body)
        self.assertIn("Environment=OLLAMA_NO_CLOUD=true", body)
        self.assertIn("/^\\[Container\\]$/a Environment=OLLAMA_NO_CLOUD=true", body)
        self.assertIn("disable --now moai.service", body)
        self.assertIn('run_priv /usr/bin/loginctl enable-linger "$login_user"', body)
        self.assertGreaterEqual(
            body.count('loginctl show-user "$login_user" -p Linger --value'),
            2,
        )
        self.assertLess(
            body.index('systemctl --user start "$model_unit"'),
            body.index("MOAI_LOCAL_UNIT=$model_unit"),
        )
        self.assertIn(
            "After=network-online.target ollama.service moai-brain.service",
            (ROOT / "system_files/usr/lib/systemd/user/moos-ensure-brain.service")
            .read_text(encoding="utf-8"),
        )
        self.assertIn("restart moos-ensure-brain.service", body)
        self.assertIn("http://127.0.0.1:11434/api/tags", body)
        self.assertIn('"default" in names', body)
        self.assertLess(
            body.index("restart moos-ensure-brain.service"),
            body.index("http://127.0.0.1:11434/api/tags"),
        )
        self.assertLess(
            body.index("http://127.0.0.1:11434/api/tags"),
            body.index("MOAI_LOCAL_UNIT=$model_unit"),
        )
        self.assertLess(
            body.index("restart moos-ensure-brain.service"),
            body.index('echo "${G}✓ جاهز | ready${N}"'),
        )
        self.assertLess(
            body.index('"default" in names'),
            body.index('echo "${G}✓ جاهز | ready${N}"'),
        )

    def test_setup_brain_refuses_an_unmanaged_model_container(self):
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
            result = subprocess.run(
                [str(MOAI_DO), "setup-brain"], input="y\n", env=env,
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unmanaged model container", result.stderr)
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
                side_effect=lambda argv, check=False: calls.append(tuple(argv)) or Result(),
            ):
                self.assertFalse(wake["start_gateway"]())
            self.assertIn(
                ("systemctl", "--user", "start", "openclaw-gateway.service"),
                calls,
            )

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


if __name__ == "__main__":
    unittest.main(verbosity=2)

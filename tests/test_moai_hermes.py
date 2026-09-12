#!/usr/bin/env python3
"""Hermes adapter input, authentication and isolated provider contract."""
import json
import os
from pathlib import Path
import runpy
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from test_moai_runtime import RuntimeTests

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'system_files/usr/libexec/moai-hermes'))
class AdapterTests(unittest.TestCase):
    def test_environment_never_inherits_provider_credentials(self):
        with patch.dict(os.environ,{'OPENROUTER_API_KEY':'private','ANTHROPIC_API_KEY':'private',
                                    'HTTPS_PROXY':'https://untrusted','HERMES_HOME':'/owner'}):
            env=m['worker_environment'](Path('/isolated'),18080)
        self.assertNotIn('OPENROUTER_API_KEY',env)
        self.assertNotIn('ANTHROPIC_API_KEY',env)
        self.assertNotIn('HTTPS_PROXY',env)
        self.assertEqual(env['HERMES_HOME'],'/isolated')
        self.assertEqual(env['OPENAI_BASE_URL'],'http://127.0.0.1:18080/v1')
    def test_configuration_has_no_tools_or_external_fallback(self):
        cfg=m['configuration'](18080)
        self.assertEqual(cfg['agent']['toolsets'],[])
        self.assertEqual(cfg['fallback_providers'],[])
        self.assertEqual(cfg['mcp_servers'],{})
        self.assertFalse(cfg['compression']['enabled'])
    def test_rejects_provider_overrides_and_nontext_inputs(self):
        for body in ({'provider':'paid'}, {'model':'paid/model','messages':[]},
                     {'messages':[{'role':'user','content':[{'type':'image_url'}]}]},
                     {'messages':[{'role':'user','content':'hi'}],'tools':[]}):
            with self.subTest(body=body),self.assertRaises(ValueError):m['parse_chat'](body)
    def test_text_history_preserved(self):
        user,system,history,limit,stream=m['parse_chat']({'messages':[
            {'role':'user','content':'first'},{'role':'assistant','content':'answer'},
            {'role':'user','content':'مرحبا'}]})
        self.assertEqual(user,'مرحبا');self.assertEqual(len(history),2)
        self.assertIn('cannot execute commands',system)
    def test_http_auth_browser_boundary_and_real_response_shape(self):
        class Agent:
            def run_conversation(self,**kw):return {'final_response':'جاهز'}
            def close(self):pass
        srv=m['Server'](('127.0.0.1',0),'fixture-private',lambda maximum:Agent())
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(srv.server_port)
        try:
            for headers,code in [({},401),({'Authorization':'Bearer fixture-private','Origin':'https://evil'},403)]:
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(urllib.request.Request(base+'/healthz',headers=headers),timeout=3)
                self.assertEqual(ctx.exception.code,code)
            body={'messages':[{'role':'user','content':'مرحبا'}],'stream':True}
            req=urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(body).encode(),
                headers={'Content-Type':'application/json','Authorization':'Bearer fixture-private'})
            def broker(action, body):
                return {'id':'review-session','run':'private-run','history':[]} if action=='begin' else {'ok':True}
            with patch.dict(m['Handler'].do_POST.__globals__, {'broker': broker}):
                with urllib.request.urlopen(req,timeout=3) as response:result=response.read().decode()
            self.assertIn('جاهز',result);self.assertIn('data: [DONE]',result)
        finally:srv.shutdown();srv.server_close();thread.join()
    def test_a_follow_up_waits_for_the_previous_turn_instead_of_429(self):
        # Measured 2026-09-12: a follow-up sent the moment a reply arrived got 429 while
        # the previous turn was still releasing its lock.
        class Agent:
            def run_conversation(self,**kw):return {'final_response':'تم'}
            def close(self):pass
        srv=m['Server'](('127.0.0.1',0),'fixture-private',lambda maximum:Agent())
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        body=json.dumps({'messages':[{'role':'user','content':'التالي'}]}).encode()
        def post():
            return urllib.request.urlopen(urllib.request.Request(
                'http://127.0.0.1:'+str(srv.server_port)+'/v1/chat/completions',data=body,
                headers={'Content-Type':'application/json','Authorization':'Bearer fixture-private'}),timeout=10)
        def broker(action, body):
            return {'id':'review-session','run':'private-run','history':[]} if action=='begin' else {'ok':True}
        try:
            with patch.dict(m['Handler'].do_POST.__globals__, {'broker': broker}):
                srv.busy.acquire()
                threading.Timer(0.4, srv.busy.release).start()
                with post() as response:
                    self.assertEqual(response.status,200);self.assertIn('تم',response.read().decode())
                srv.busy.acquire()
                try:
                    with patch.dict(m['Handler'].do_POST.__globals__, {'BUSY_WAIT_SECONDS': 0.2}):
                        with self.assertRaises(urllib.error.HTTPError) as ctx:post()
                    self.assertEqual(ctx.exception.code,429)
                finally:srv.busy.release()
        finally:srv.shutdown();srv.server_close();thread.join()


class PackagedRuntimeTests(unittest.TestCase):
    """Hermes on fresh systems: the official package, pinned by hash, found by the adapter."""

    ROOT = Path(__file__).resolve().parents[1]

    def read(self, relative):
        return (self.ROOT / relative).read_text(encoding="utf-8")

    def test_adapter_discovers_the_packaged_venv_layout(self):
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            runtime = Path(home) / ".local/lib/hermes-agent"
            python = runtime / "venv/bin/python"
            site = runtime / "venv/lib/python3.12/site-packages"
            python.parent.mkdir(parents=True)
            site.mkdir(parents=True)
            python.write_text("#!/bin/sh\n")
            python.chmod(0o755)
            with patch.dict(os.environ, {"HOME": home, "MOAI_HERMES_RUNTIME_ROOT": "", "PATH": "/nonexistent"}):
                adapter = runpy.run_path(str(self.ROOT / "system_files/usr/libexec/moai-hermes"),
                                         run_name="moai_hermes_packaged_test")
                self.assertIsNone(adapter["discover_runtime"](), "found a runtime with no run_agent")
                (site / "run_agent.py").write_text("")
                found = adapter["discover_runtime"]()
            self.assertIsNotNone(found)
            self.assertEqual(found[0], site.resolve())
            self.assertEqual(found[1], python)

    def test_dependency_lock_pins_every_package_by_version_and_hash(self):
        lock = self.read("system_files/usr/share/moos/hermes/requirements.lock").splitlines()
        entries = [index for index, line in enumerate(lock) if line and not line.startswith((" ", "#"))]
        self.assertGreater(len(entries), 20)
        for index in entries:
            with self.subTest(requirement=lock[index]):
                self.assertRegex(lock[index], r"^[A-Za-z0-9_.-]+(\[[a-z0-9,_-]+\])?==")
                self.assertTrue(lock[index].rstrip().endswith("\\"))
                self.assertIn("--hash=sha256:", lock[index + 1])
        # The runtime is the verified release checkout, never a package pip would build.
        self.assertFalse(any(lock[index].startswith("hermes-agent") for index in entries))

    def test_release_archive_is_pinned_in_one_place(self):
        moai_do = self.read("system_files/usr/bin/moai-do")
        url = "https://github.com/NousResearch/hermes-agent/archive/refs/tags/v2026.9.11.tar.gz"
        self.assertIn(f'HERMES_URL="{url}"', moai_do)
        self.assertRegex(moai_do, r'HERMES_SHA256="[0-9a-f]{64}"')
        self.assertIn(url, self.read("system_files/usr/share/moos/hermes/requirements.in"))

    def test_install_action_verifies_before_it_unpacks_imports_and_can_roll_back(self):
        moai_do = self.read("system_files/usr/bin/moai-do")
        body = moai_do[moai_do.index("do_install_hermes() {"):moai_do.index("do_install_codex() {")]
        order = ['curl -fL --proto \'=https\'', "sha256sum -c --quiet -", "tar -xzf",
                 '"$HERMES_PYTHON" -m venv', '--require-hashes --no-deps -r "$HERMES_LOCK"',
                 "./venv/bin/python -c 'import run_agent'", 'mv "$staging" "$root"',
                 "/usr/libexec/moai-hermes check", 'mv "${root}.old" "$root"']
        positions = [body.index(step) for step in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("confirm || return 0", body)
        # After an upgrade the running adapter must not keep the moved runtime.
        self.assertIn("try-restart moai-agent-api.service moai-hermes.service", body)
        help_text = moai_do[moai_do.index("${C}install-opencode${N}"):moai_do.index("${C}install-openclaw${N}")]
        self.assertLess(help_text.index("Install OpenCode"), help_text.index("${C}install-hermes${N}"),
                        "each action's English line stays under its own name in moai-do help")
        self.assertIn("        install-hermes) do_install_hermes ;;", moai_do)
        self.assertIn("do/install-hermes|", self.read("system_files/usr/bin/moos-open"))
        qml = self.read("system_files/usr/share/moos/apps/moai/main.qml")
        self.assertIn("install-opencode|install-hermes|install-openclaw|", qml)
        self.assertIn("`moai-do install-hermes` installs Hermes Agent", qml)
        self.assertIn("    python3.12\n)", self.read("build_files/build.sh"))
        self.assertIn("python3 python3-gobject python3.12", self.read("build_files/build-arm.sh"))

    def test_agent_switch_reports_what_the_adapter_discovers(self):
        # Mo AI shows its Agent switch from moai-control's /quick; the gateway routes by the
        # adapter. Both must read the same discovery, or the switch offers a refused runtime.
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            runtime = Path(home) / ".local/lib/hermes-agent"
            python = runtime / "venv/bin/python"
            site = runtime / "venv/lib/python3.12/site-packages"
            python.parent.mkdir(parents=True)
            site.mkdir(parents=True)
            python.write_text("#!/bin/sh\n")
            python.chmod(0o755)
            with patch.dict(os.environ, {"HOME": home, "MOAI_HERMES_RUNTIME_ROOT": "", "PATH": "/nonexistent",
                                         "MOAI_HERMES_ADAPTER": str(self.ROOT / "system_files/usr/libexec/moai-hermes")}):
                control = runpy.run_path(str(self.ROOT / "system_files/usr/bin/moai-control"),
                                         run_name="moai_control_agent_switch_test")
                self.assertFalse(control["agent_state"]()["hermes"], "switch offered with no run_agent")
                (site / "run_agent.py").write_text("")
                self.assertTrue(control["agent_state"]()["hermes"])
                self.assertTrue(control["quick"].__code__.co_names.count("agent_state"))

    def test_both_prompts_carry_the_identity_rule(self):
        qml = self.read("system_files/usr/share/moos/apps/moai/main.qml")
        rule = qml[qml.index("readonly property string identityRule:"):qml.index("readonly property string systemPrompt:")]
        self.assertIn("this computer runs MoOS", rule)
        self.assertIn(".fc44", rule)
        # The image identity gate fails any app QML naming the base distribution, even here.
        self.assertNotIn("fedora", rule.lower())
        prompt = qml[qml.index("readonly property string systemPrompt:"):]
        self.assertLess(prompt.index("root.identityRule"), prompt.index("WHAT YOU CAN DO"))
        self.assertIn('(s.os || "MoOS") + (s.version ? " " + s.version : "") + ", kernel "', qml)
        _, system, _, _, _ = m["parse_chat"]({"messages": [{"role": "user", "content": "hi"}]})
        self.assertIn("This computer runs MoOS", system)
        self.assertIn("packaging tags such as .fc44", system)
        self.assertNotIn("fedora", system.lower())

if __name__=='__main__':unittest.main()

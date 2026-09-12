#!/usr/bin/env python3
"""Execute the free-only boundary, not merely catalogue labels."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

# ── ISOLATE THE OWNER'S OWN SETTINGS BEFORE ANYTHING IS IMPORTED ─────────────────────────────
#
# `selected_provider()` reads $XDG_CONFIG_HOME/moai-agent/state.json — the LIVE choice the person
# using this machine made — and `selected_cost_policy()` turns that into free-or-paid, which is
# what decides whether a paid model is refused with 409 or admitted.
#
# So two of these tests asserted the free-only behaviour while reading whatever the owner had
# selected. On a CI runner there is no such file, they pass, and the gate looks green forever. On
# the maintainer's own Oracle A1, where Settings says `openrouter-paid`, they FAIL — and `just
# check` is exactly what AGENTS.md tells every contributor to run before pushing. A gate that only
# passes on a machine shaped like CI teaches people that a red gate means nothing, which is the
# one thing this repository cannot afford.
#
# Pointing HOME and XDG_CONFIG_HOME at an empty directory for the whole module fixes it for every
# test here, not just the two that happened to notice: none of them is about the host's config.
_ISOLATED = tempfile.TemporaryDirectory()
os.environ["XDG_CONFIG_HOME"] = str(Path(_ISOLATED.name) / "config")
os.environ["HOME"] = _ISOLATED.name

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(ROOT/path))
    spec=importlib.util.spec_from_loader(name,loader)
    module=importlib.util.module_from_spec(spec);loader.exec_module(module)
    return module
policy=load('moai_cloud_policy','system_files/usr/lib/moai/moai_cloud_policy.py')
gateway=load('moai_free_gateway','system_files/usr/bin/moai-gateway')
migration=load('moai_cloud_migrate','system_files/usr/libexec/moai-cloud-migrate')

class FreePolicy(unittest.TestCase):
    def test_paid_local_untrusted_and_ambiguous_routes_rejected(self):
        for base,model in [('http://127.0.0.1:11434','qwen3'),
                           ('https://openrouter.ai.evil/api/v1','openrouter/free'),
                           (policy.BASE,'openai/gpt-oss-120b'),
                           (policy.BASE,'vendor/model:free:online'),
                           (policy.BASE+'?key=x','openrouter/free')]:
            with self.subTest(base=base,model=model), self.assertRaises(ValueError):
                policy.validate(base,model)
    def test_caller_cannot_enable_paid_plugins_or_fallbacks(self):
        result=policy.request_body({'messages':[], 'plugins':[{'id':'web'}],
            'models':['paid/model'],'provider':{'max_price':{'prompt':100}},
            'audio':{'voice':'paid'},'modalities':['audio']},'openrouter/free')
        self.assertEqual(set(result),{'messages','model','provider'})
        self.assertTrue(all(v==0 for v in result['provider']['max_price'].values()))
    def test_model_catalog_rejects_nonzero_missing_nan_and_paid(self):
        items=[{'id':'vendor/model:free','pricing':{'prompt':'0','completion':'0'}},
               {'id':'vendor/other:free','pricing':{'prompt':'NaN'}},
               {'id':'vendor/paid:free','pricing':{'request':'1'}},
               {'id':'vendor/no-price:free'}, {'id':'vendor/paid','pricing':{'prompt':'0'}}]
        self.assertEqual(policy.visible_models(items),items[:1])
    def test_paid_requires_explicit_selection_and_free_stays_zero(self):
        with self.assertRaises(ValueError):
            policy.request_body({'messages':[]},'openai/gpt-5.4-mini')
        paid=policy.request_body({'messages':[]},'openai/gpt-5.4-mini',allow_paid=True)
        self.assertEqual(paid['model'],'openai/gpt-5.4-mini')
        free=policy.request_body({'models':['paid/model']},policy.DEFAULT_MODEL,allow_paid=True)
        self.assertNotIn('models',free)
        self.assertEqual(free['provider']['max_price']['prompt'],0)

    def catalogue(self, *entries):
        return policy.visible_models([
            {'id': model_id, 'pricing': {'prompt': '0', 'completion': '0'},
             'supported_parameters': params, 'context_length': 262144}
            for model_id, params in entries])

    def test_automatic_route_prefers_measured_speed_over_size(self):
        items = self.catalogue(('nvidia/nemotron-3-ultra-550b-a55b:free', ['tools', 'reasoning']),
                               ('nex-agi/nex-n2.5-mini:free', ['tools', 'reasoning']),
                               ('nex-agi/nex-n2.5-pro:free', ['tools', 'reasoning']))
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            # The 550B model is the largest and was 25 s per answer when measured; size loses.
            self.assertEqual(policy.automatic_model(require_tools=True), 'nex-agi/nex-n2.5-pro:free')
            self.assertEqual(policy.automatic_model(), 'nex-agi/nex-n2.5-pro:free')
            self.assertEqual(policy.automatic_candidates(limit=3)[-2:],
                             ['nvidia/nemotron-3-ultra-550b-a55b:free', policy.DEFAULT_MODEL])

    def test_measured_preference_never_admits_a_priced_model(self):
        items = policy.visible_models([
            {'id': 'nex-agi/nex-n2.5-pro:free', 'pricing': {'prompt': '0.1'},
             'supported_parameters': ['tools']},
            {'id': 'vendor/big-400b:free', 'pricing': {'prompt': '0', 'completion': '0'},
             'supported_parameters': ['tools']}])
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            self.assertEqual(policy.automatic_candidates(require_tools=True, limit=5),
                             ['vendor/big-400b:free', policy.DEFAULT_MODEL])

    def test_catalogue_failure_uses_official_zero_price_router(self):
        with patch.object(policy, '_catalogue', (0, [])), \
                patch.object(policy.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertEqual(policy.automatic_candidates(require_tools=True),
                             [policy.DEFAULT_MODEL])
        body = policy.request_body({'messages': [], 'tools': [{'type': 'function'}]},
                                   policy.DEFAULT_MODEL)
        self.assertTrue(all(value == 0 for value in body['provider']['max_price'].values()))

    def test_catalogue_refresh_failure_keeps_last_verified_models(self):
        items = self.catalogue(('nex-agi/nex-n2.5-pro:free', ['tools']))
        with patch.object(policy, '_catalogue', (0, items)), \
                patch.object(policy.urllib.request, 'urlopen', side_effect=OSError('offline')), \
                patch.dict(policy._cooldown, {}, clear=True):
            self.assertEqual(policy.automatic_candidates(),
                             ['nex-agi/nex-n2.5-pro:free', policy.DEFAULT_MODEL])

    def test_refused_free_model_cools_down_then_returns(self):
        items = self.catalogue(('nex-agi/nex-n2.5-pro:free', ['tools']),
                               ('dots-studio/dots-3-note-preview:free', ['tools']))
        now = policy.time.monotonic()
        with patch.object(policy, '_catalogue', (now, items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            policy.note_upstream_failure('nex-agi/nex-n2.5-pro:free', 429)
            self.assertEqual(policy.automatic_model(), 'dots-studio/dots-3-note-preview:free')
            policy.note_upstream_failure('dots-studio/dots-3-note-preview:free', 401)
            self.assertEqual(policy.automatic_model(), 'dots-studio/dots-3-note-preview:free')
            with patch.object(policy, '_catalogue', (now + 601, items)), \
                    patch.object(policy.time, 'monotonic', return_value=now + 601):
                self.assertEqual(policy.automatic_model(), 'nex-agi/nex-n2.5-pro:free')

    def test_curated_models_are_free_measured_and_named_in_both_languages(self):
        ids = [entry[0] for entry in policy.CURATED_FREE]
        self.assertEqual(len(ids), len(set(ids)))
        for model_id, name, arabic, english in policy.CURATED_FREE:
            with self.subTest(model=model_id):
                self.assertTrue(model_id.endswith(':free'))
                self.assertTrue(policy.free_model(model_id))
                self.assertTrue(name and english)
                self.assertRegex(arabic, '[\u0600-\u06ff]')
        for route in policy.MEASURED_PREFERENCE.values():
            self.assertTrue(set(route) <= set(ids), route)
        self.assertNotIn('dots-studio/dots-3-note-preview:free', ids)

    def test_every_candidate_cooled_still_answers(self):
        items = self.catalogue(('nex-agi/nex-n2.5-pro:free', ['tools']))
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            policy.note_upstream_failure('nex-agi/nex-n2.5-pro:free', 503)
            self.assertEqual(policy.automatic_model(), 'nex-agi/nex-n2.5-pro:free')

    def test_gateway_refuses_paid_before_network(self):
        handler=object.__new__(gateway.Handler)
        handler._cloud_cfg=lambda cfg:(policy.BASE,'fixture','openai')
        errors=[];calls=[]
        handler._err=lambda code,msg:errors.append(code)
        handler._proxy=lambda *args,**kwargs:calls.append((args,kwargs))
        handler._to_cloud({'messages':[]},b'{}','vendor/paid',{})
        self.assertEqual(errors,[409]);self.assertEqual(calls,[])
        opened=[]
        handler._open_upstream=lambda method,url,headers,body:(opened.append(json.loads(body)),'upstream')[1]
        with patch.object(gateway.cloud_policy,'automatic_candidates',return_value=['vendor/model:free']):
            handler._to_cloud({'messages':[],'plugins':[{'id':'web'}]},b'{}',policy.DEFAULT_MODEL,{})
        self.assertEqual([kwargs.get('upstream') for _,kwargs in calls],['upstream'])
        self.assertNotIn('plugins',opened[0])
        self.assertTrue(all(v==0 for v in opened[0]['provider']['max_price'].values()))

    def gateway_handler(self):
        handler=object.__new__(gateway.Handler)
        handler._cloud_cfg=lambda cfg:(policy.BASE,'fixture','openai')
        handler.errors=[];handler.opened=[];handler.relayed=[]
        handler._err=lambda code,msg:handler.errors.append(code)
        real_proxy=gateway.Handler._proxy
        def proxy(method,url,headers,body,wire,streaming,upstream=None):
            if upstream is not None:
                handler.relayed.append(upstream); return None
            return real_proxy(handler,method,url,headers,body,wire,streaming)
        handler._proxy=proxy
        return handler

    def http_error(self,code):
        import io, urllib.error
        return urllib.error.HTTPError(policy.BASE,code,'upstream',{},io.BytesIO(b'{"error":"busy"}'))

    def test_automatic_route_skips_a_refused_free_model_before_answering(self):
        handler=self.gateway_handler()
        replies=iter([self.http_error(429),'second'])
        def open_upstream(method,url,headers,body):
            handler.opened.append(json.loads(body)['model'])
            reply=next(replies)
            if isinstance(reply,Exception): raise reply
            return reply
        handler._open_upstream=open_upstream
        with patch.object(gateway.cloud_policy,'automatic_candidates',
                          return_value=['a/one:free','b/two:free','c/three:free']), \
                patch.dict(gateway.cloud_policy._cooldown,{},clear=True):
            handler._to_cloud({'messages':[]},b'{}',policy.DEFAULT_MODEL,{})
            self.assertIn('a/one:free',gateway.cloud_policy._cooldown)
        self.assertEqual(handler.opened,['a/one:free','b/two:free'])
        self.assertEqual(handler.relayed,['second']);self.assertEqual(handler.errors,[])
        self.assertEqual(handler.moai_model,'b/two:free')

    def test_explicit_models_and_auth_errors_are_never_retried(self):
        for model,candidates,code in (('a/one:free',[],429),(policy.DEFAULT_MODEL,['a/one:free','b/two:free'],401)):
            with self.subTest(model=model,code=code):
                handler=self.gateway_handler()
                def open_upstream(method,url,headers,body,handler=handler,code=code):
                    handler.opened.append(json.loads(body)['model']); raise self.http_error(code)
                handler._open_upstream=open_upstream
                with patch.object(gateway.cloud_policy,'automatic_candidates',return_value=candidates), \
                        patch.dict(gateway.cloud_policy._cooldown,{},clear=True):
                    handler._to_cloud({'messages':[]},b'{}',model,{})
                self.assertEqual(handler.opened,['a/one:free']);self.assertEqual(handler.errors,[code])

    def test_automatic_route_reports_the_last_refusal_when_every_free_model_fails(self):
        handler=self.gateway_handler()
        def open_upstream(method,url,headers,body):
            handler.opened.append(json.loads(body)['model']); raise self.http_error(429)
        handler._open_upstream=open_upstream
        with patch.object(gateway.cloud_policy,'automatic_candidates',return_value=['a/one:free','b/two:free']), \
                patch.dict(gateway.cloud_policy._cooldown,{},clear=True):
            handler._to_cloud({'messages':[]},b'{}',policy.DEFAULT_MODEL,{})
        self.assertEqual(handler.opened,['a/one:free','b/two:free']);self.assertEqual(handler.errors,[429])

    def test_absent_hermes_runtime_answers_directly_and_says_so(self):
        handler=object.__new__(gateway.Handler)
        errors=[]
        handler._err=lambda code,msg:errors.append(code)
        started=[]
        with patch.object(gateway,'hermes_runtime_installed',return_value=False), \
                patch.object(gateway.subprocess,'run',side_effect=lambda *a,**k:started.append(a)):
            self.assertIs(handler._to_hermes({'messages':[]}),False)
        self.assertEqual(handler.moai_agent,'direct-fallback')
        self.assertEqual(errors,[]);self.assertEqual(started,[])

    def test_installed_or_unknown_hermes_is_never_silently_substituted(self):
        for installed in (True,None):
            with self.subTest(installed=installed), tempfile.TemporaryDirectory() as runtime:
                handler=object.__new__(gateway.Handler)
                errors=[]
                handler._err=lambda code,msg,errors=errors:errors.append(code)
                with patch.object(gateway,'hermes_runtime_installed',return_value=installed), \
                        patch.object(gateway,'PORT',8095), \
                        patch.dict(gateway.os.environ,{'XDG_RUNTIME_DIR':runtime}):
                    self.assertIs(handler._to_hermes({'messages':[]}),True)
                self.assertEqual(errors,[503])

    def test_first_message_waits_for_the_adapter_it_just_started(self):
        # Measured 2026-09-12 after a reboot: the adapter reported ready 2 s after the first
        # message started it, and a single 1 s probe had already answered 503.
        class Healthy:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return False
        for ready_on_probe,wait,expected in ((3,5.0,[]),(None,0.3,[503])):
            with self.subTest(ready_on_probe=ready_on_probe), tempfile.TemporaryDirectory() as runtime:
                (Path(runtime)/'moai-hermes').mkdir()
                (Path(runtime)/'moai-hermes/token').write_text('fixture-token')
                handler=object.__new__(gateway.Handler)
                errors=[];proxied=[];probes=[];started=[]
                handler._err=lambda code,msg,errors=errors:errors.append(code)
                handler._proxy=lambda *args,**kwargs:proxied.append(args[1])
                def urlopen(req,timeout=0,probes=probes,ready_on_probe=ready_on_probe):
                    probes.append(req.full_url)
                    if ready_on_probe is None or len(probes)<ready_on_probe:
                        raise gateway.urllib.error.URLError('adapter still starting')
                    return Healthy()
                with patch.object(gateway,'hermes_runtime_installed',return_value=True), \
                        patch.object(gateway,'PORT',8080), patch.object(gateway,'HERMES_START_WAIT',wait), \
                        patch.object(gateway.subprocess,'run',side_effect=lambda *a,**k:started.append(a[0])), \
                        patch.object(gateway.urllib.request,'urlopen',side_effect=urlopen), \
                        patch.object(gateway._hermes_time,'sleep',lambda seconds:None), \
                        patch.dict(gateway.os.environ,{'XDG_RUNTIME_DIR':runtime}):
                    self.assertIs(handler._to_hermes({'messages':[],'moai':{'session':'s'}}),True)
                self.assertEqual(errors,expected)
                self.assertEqual(started,[['systemctl','--user','start','moai-agent-api.service','moai-hermes.service']])
                if expected:
                    self.assertEqual(proxied,[])
                else:
                    self.assertEqual(len(probes),3)
                    self.assertEqual(proxied,['http://127.0.0.1:8090/v1/chat/completions'])

    def test_runtime_status_comes_from_the_adapter_and_is_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter=Path(directory)/'moai-hermes'
            adapter.write_text('#!/bin/sh\nprintf \'{"installed": false, "ready": false}\\n\'\n')
            adapter.chmod(0o755)
            with patch.object(gateway,'HERMES_ADAPTER',str(adapter)), \
                    patch.object(gateway,'_hermes_status',(0.0,None)):
                self.assertIs(gateway.hermes_runtime_installed(),False)
                adapter.write_text('#!/bin/sh\nprintf \'{"installed": true}\\n\'\n')
                self.assertIs(gateway.hermes_runtime_installed(),False)
                later=gateway._hermes_time.monotonic()+61
                with patch.object(gateway._hermes_time,'monotonic',return_value=later):
                    self.assertIs(gateway.hermes_runtime_installed(),True)
                adapter.write_text('#!/bin/sh\nprintf \'not json\'\n')
                with patch.object(gateway._hermes_time,'monotonic',return_value=later+61):
                    self.assertIsNone(gateway.hermes_runtime_installed())

    def test_migration_preserves_key_and_backup_disables_local_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'openclaw.json'
            original={'models':{'providers':{'cloud':{'apiKey':'private-fixture','baseUrl':policy.BASE,
                'models':[{'id':'vendor/paid'}]},'ollama':{}}},
                'agents':{'defaults':{'model':{'primary':'ollama/qwen','fallbacks':['cloud/paid']}}}}
            p.write_text(json.dumps(original));migration.migrate(p)
            changed=json.loads(p.read_text())
            self.assertEqual(changed['models']['providers']['cloud']['apiKey'],'private-fixture')
            self.assertEqual(set(changed['models']['providers']),{'cloud'})
            self.assertEqual(changed['agents']['defaults']['model'],{'primary':'cloud/openrouter/free','fallbacks':[]})
            self.assertEqual(json.loads(p.with_name(p.name+'.before-free-cloud').read_text()),original)
            first=p.read_bytes();migration.migrate(p);self.assertEqual(p.read_bytes(),first)
            self.assertEqual(p.stat().st_mode & 0o777,0o600)

    # ── OpenCode Zen: billed by explicit choice, chat-completions models only ──
    def zen(self, module=None):
        return patch.object(module or policy,'selected_provider',return_value='opencode-zen')

    def test_zen_needs_explicit_selection_and_a_chat_completions_model(self):
        with self.assertRaises(ValueError):
            policy.validate(policy.ZEN_BASE,'deepseek-v4-flash',allow_paid=True)
        with self.zen():
            policy.validate(policy.ZEN_BASE,'deepseek-v4-flash',allow_paid=True)
            policy.validate(policy.ZEN_BASE+'/','big-pickle',allow_paid=True)
            for model in ('gpt-5.5','grok-4.6','claude-opus-5','qwen3.6-plus','gemini-3.5-flash',
                          'muse-spark-1.3-contributor-free','openrouter/free','kimi-k3/../x'):
                with self.subTest(model=model), self.assertRaises(ValueError):
                    policy.validate(policy.ZEN_BASE,model,allow_paid=True)
            for base,model,paid in (('https://opencode.ai.evil/zen/v1','deepseek-v4-flash',True),
                                    (policy.ZEN_BASE,'deepseek-v4-flash',False),
                                    (policy.BASE,'deepseek-v4-flash',True)):
                with self.subTest(base=base,paid=paid), self.assertRaises(ValueError):
                    policy.validate(base,model,allow_paid=paid)

    def test_settings_choice_is_checked_against_the_provider_being_selected(self):
        policy.validate_selection('openrouter-free',policy.DEFAULT_MODEL)
        policy.validate_selection('openrouter-paid','openai/gpt-5.4-mini')
        policy.validate_selection('opencode-zen','kimi-k3')
        for provider,model in (('openrouter-free','openai/gpt-5.4-mini'),('openrouter-free','kimi-k3'),
                               ('opencode-zen','gpt-5.5'),('opencode-zen',policy.DEFAULT_MODEL),
                               ('openrouter-paid','kimi-k3'),('someone-else','kimi-k3')):
            with self.subTest(provider=provider,model=model), self.assertRaises(ValueError):
                policy.validate_selection(provider,model)

    def test_zen_body_carries_no_openrouter_routing(self):
        with self.zen():
            body=policy.request_body({'messages':[],'provider':{'max_price':{'prompt':9}},'models':['x'],
                                      'reasoning':{'effort':'high'},'plugins':[{'id':'web'}]},
                                     'glm-5.3',allow_paid=True,base=policy.ZEN_BASE)
            self.assertEqual(set(body),{'messages','model'})
            with self.assertRaises(ValueError):
                policy.request_body({'messages':[]},'gpt-5.5',allow_paid=True,base=policy.ZEN_BASE)
        with self.assertRaises(ValueError):
            policy.request_body({'messages':[]},'glm-5.3',allow_paid=True,base=policy.ZEN_BASE)

    def test_selected_provider_reads_settings_and_only_billed_ones_are_paid(self):
        with tempfile.TemporaryDirectory() as home:
            state=Path(home)/'moai-agent/state.json'; state.parent.mkdir()
            with patch.dict(policy.os.environ,{'XDG_CONFIG_HOME':home}):
                for stored,provider,cost in ((None,'','free'),('[]','','free'),('{"provider":7}','','free'),
                                             ('{"provider":"openrouter-free"}','openrouter-free','free'),
                                             ('{"provider":"openrouter-paid"}','openrouter-paid','paid'),
                                             ('{"provider":"opencode-zen"}','opencode-zen','paid')):
                    with self.subTest(stored=stored):
                        if stored is None:
                            state.unlink(missing_ok=True)
                        else:
                            state.write_text(stored)
                        self.assertEqual(policy.selected_provider(),provider)
                        self.assertEqual(policy.selected_cost_policy(),cost)
        self.assertTrue(policy.paid_model('kimi-k3','opencode-zen'))
        self.assertFalse(policy.paid_model('openai/gpt-5.4-mini','opencode-zen'))
        self.assertTrue(policy.paid_model('openai/gpt-5.4-mini','openrouter-paid'))
        self.assertFalse(policy.paid_model('kimi-k3','openrouter-free'))

    def test_gateway_sends_zen_requests_to_zen_with_the_chosen_model(self):
        handler=self.gateway_handler()
        handler._cloud_cfg=lambda cfg:(policy.ZEN_BASE,'zen-fixture','openai')
        sent=[]
        handler._proxy=lambda method,url,headers,body,wire,streaming,upstream=None:sent.append((url,headers,json.loads(body)))
        with self.zen(gateway.cloud_policy):
            # "Automatic" on Zen is the model the owner chose for Zen, and a GPT id is refused.
            handler._to_cloud({'messages':[{'role':'user','content':'hi'}]},b'{}',policy.DEFAULT_MODEL,
                              {'cloud_model':'deepseek-v4-flash'})
            handler._to_cloud({'messages':[]},b'{}','gpt-5.5',{'cloud_model':'deepseek-v4-flash'})
        self.assertEqual(handler.errors,[409]);self.assertEqual(len(sent),1)
        url,headers,body=sent[0]
        self.assertEqual(url,policy.ZEN_BASE+'/chat/completions')
        self.assertEqual(headers.get('Authorization'),'Bearer zen-fixture')
        self.assertEqual(body['model'],'deepseek-v4-flash');self.assertNotIn('provider',body)
        self.assertEqual(handler.moai_model,'deepseek-v4-flash')
        # Without the owner's Zen selection the same configuration is refused before any request.
        handler.errors.clear();sent.clear()
        with patch.object(gateway.cloud_policy,'selected_provider',return_value='openrouter-free'):
            handler._to_cloud({'messages':[]},b'{}','deepseek-v4-flash',{})
        self.assertEqual((handler.errors,sent),([409],[]))

    def test_control_sends_the_key_only_to_routable_services_and_lists_only_zen_chat_models(self):
        control=load('moai_control_zen','system_files/usr/bin/moai-control')
        opened=[]
        catalogue={'data':[{'id':m} for m in ('deepseek-v4-flash','gpt-5.5','claude-opus-5','big-pickle',
                                               'muse-spark-1.3-contributor-free','kimi-k3')]}
        class Reply:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self): return json.dumps(catalogue).encode()
        def urlopen(req,timeout=0):
            opened.append((req.full_url,req.get_header('Authorization')));return Reply()
        with patch.object(control.urllib.request,'urlopen',side_effect=urlopen):
            with self.zen(control.cloud_policy):
                models,error=control.cloud_models({'cloud_base':policy.ZEN_BASE,'cloud_key':'zen-fixture'})
                self.assertEqual(error,'')
                self.assertEqual([m['id'] for m in models],['cloud:deepseek-v4-flash','cloud:big-pickle','cloud:kimi-k3'])
                self.assertEqual(control.cloud_models({'cloud_base':'https://collector.example/v1','cloud_key':'zen-fixture'}),
                                 ([],policy.ERROR))
            with patch.object(control.cloud_policy,'selected_provider',return_value='openrouter-free'):
                self.assertEqual(control.cloud_models({'cloud_base':policy.ZEN_BASE,'cloud_key':'or-fixture'}),
                                 ([],policy.ERROR))
        self.assertEqual(opened,[(policy.ZEN_BASE+'/models','Bearer zen-fixture')])

if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
"""Execute the free-only boundary, not merely catalogue labels."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
                               ('dots-studio/dots-3-note-preview:free', ['tools', 'reasoning']),
                               ('nex-agi/nex-n2.5-pro:free', ['tools', 'reasoning']))
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            self.assertEqual(policy.automatic_model(require_tools=True),
                             'dots-studio/dots-3-note-preview:free')
            self.assertEqual(policy.automatic_model(), 'nex-agi/nex-n2.5-pro:free')
            self.assertEqual(policy.automatic_candidates(limit=3)[-1],
                             'nvidia/nemotron-3-ultra-550b-a55b:free')

    def test_measured_preference_never_admits_a_priced_model(self):
        items = policy.visible_models([
            {'id': 'dots-studio/dots-3-note-preview:free', 'pricing': {'prompt': '0.1'},
             'supported_parameters': ['tools']},
            {'id': 'vendor/big-400b:free', 'pricing': {'prompt': '0', 'completion': '0'},
             'supported_parameters': ['tools']}])
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            self.assertEqual(policy.automatic_candidates(require_tools=True, limit=5),
                             ['vendor/big-400b:free'])

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

if __name__=='__main__':unittest.main()

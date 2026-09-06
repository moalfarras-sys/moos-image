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

    def test_gateway_refuses_paid_before_network(self):
        handler=object.__new__(gateway.Handler)
        handler._cloud_cfg=lambda cfg:(policy.BASE,'fixture','openai')
        errors=[];calls=[]
        handler._err=lambda code,msg:errors.append(code)
        handler._proxy=lambda *args:calls.append(args)
        handler._to_cloud({'messages':[]},b'{}','vendor/paid',{})
        self.assertEqual(errors,[409]);self.assertEqual(calls,[])
        handler._to_cloud({'messages':[],'plugins':[{'id':'web'}]},b'{}',policy.DEFAULT_MODEL,{})
        self.assertEqual(len(calls),1)
        self.assertEqual(json.loads(calls[0][3])['provider']['max_price']['request'],0)
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

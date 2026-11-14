"""A request's free-only requirement survives selected paid gateway settings."""
from contextlib import ExitStack
import http.client
import importlib.util
from importlib.machinery import SourceFileLoader
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'system_files/usr/lib/moai'))
loader=SourceFileLoader('_mira_free_gateway',os.environ.get('MOAI_GATEWAY_COST_SOURCE',str(ROOT/'system_files/usr/bin/moai-gateway')))
spec=importlib.util.spec_from_loader(loader.name,loader)
gateway=importlib.util.module_from_spec(spec);loader.exec_module(gateway)

class FreeOnly(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.cfg={'base':gateway.cloud_policy.ZEN_BASE,'key':'PRIVATE-FAKE-KEY','wire':'openai','cloud_model':'deepseek-v4-flash'}
        self.calls=[];self.agent_calls=[];self.client_allowed=True
        owner=self
        class Handler(gateway.Handler):
            def log_message(self,*_):pass
            def _cloud_cfg(self,cfg):return cfg['base'],cfg['key'],cfg['wire']
            def _to_hermes(self,req):
                owner.agent_calls.append(True)
                self._send_json(200,{'agent':True});return True
            def _proxy(self,method,url,headers,body,wire,streaming,upstream=None):
                payload=json.loads(body) if body else owner.calls[-1]['payload']
                if upstream:upstream.close()
                owner.calls.append({'url':url,'payload':payload,'free_only':getattr(self,'moai_free_only',False)})
                return self._send_json(200,{'model':payload.get('model'),'price':(payload.get('provider') or {}).get('max_price')})
            def _open_upstream(self,method,url,headers,body):
                owner.calls.append({'url':url,'payload':json.loads(body),'free_only':getattr(self,'moai_free_only',False)})
                class Response:
                    def close(self):pass
                return Response()
        self.stack.enter_context(patch.object(gateway,'same_user',side_effect=lambda _:self.client_allowed))
        self.stack.enter_context(patch.object(gateway,'load_product_cfg',side_effect=lambda:dict(self.cfg)))
        self.stack.enter_context(patch.object(gateway.cloud_policy,'selected_cost_policy',return_value='paid'))
        self.stack.enter_context(patch.object(gateway.cloud_policy,'selected_provider',return_value='opencode-zen'))
        self.stack.enter_context(patch.object(gateway.cloud_policy,'automatic_candidates',return_value=['review/model:free']))
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def request(self,*,free=True,model='cloud:openrouter/free',agent=False,origin=None,policy=None,connection=None,path='/v1/chat/completions'):
        body=json.dumps({'model':model,'messages':[{'role':'user','content':'private synthetic test'}],'moai':{'agent':agent}})
        client=connection or http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        headers={'Content-Type':'application/json'}
        if free:headers['X-MoAI-Cost-Policy']='free' if policy is None else policy
        if origin:headers['Origin']=origin
        client.request('POST',path,body,headers)
        response=client.getresponse();result=(response.status,json.loads(response.read()))
        if connection is None:client.close()
        return result
    def test_zen_router_and_explicit_paid_model_are_refused_before_any_proxy(self):
        for model in ('cloud:openrouter/free','cloud:deepseek-v4-flash'):
            self.assertEqual(self.request(model=model)[0],409)
        self.assertEqual(self.calls,[])
    def test_default_paid_openrouter_and_unknown_routes_are_refused(self):
        self.cfg.update(base=gateway.cloud_policy.BASE,cloud_model='vendor/billed')
        self.assertEqual(self.request(model='cloud:vendor/billed')[0],409)
        self.cfg['base']='https://unreviewed.invalid/v1'
        self.assertEqual(self.request()[0],409)
        self.assertEqual(self.calls,[])
    def test_explicit_free_model_stays_zero_price_even_on_paid_account_selection(self):
        self.cfg['base']=gateway.cloud_policy.BASE
        status,data=self.request(model='cloud:review/model:free')
        self.assertEqual(status,200)
        self.assertTrue(self.calls[0]['free_only'])
        self.assertEqual(data['price'],{'prompt':0,'completion':0,'request':0,'image':0})
    def test_automatic_candidates_cannot_smuggle_a_billed_model(self):
        self.cfg['base']=gateway.cloud_policy.BASE
        with patch.object(gateway.cloud_policy,'automatic_candidates',return_value=['vendor/billed']):
            self.assertEqual(self.request()[0],409)
        self.assertEqual(self.calls,[])
    def test_free_agent_delegation_is_refused_before_agent_start(self):
        self.assertEqual(self.request(agent=True)[0],409)
        self.assertEqual(self.agent_calls,[])
        self.assertEqual(self.calls,[])
    def test_free_endpoint_enforces_the_boundary_without_a_header(self):
        self.assertEqual(self.request(free=False,path='/v1/free/chat/completions')[0],409)
        self.assertEqual(self.calls,[])
    def test_absent_header_preserves_the_explicit_existing_paid_selection(self):
        status,data=self.request(free=False)
        self.assertEqual((status,data['model']),(200,'deepseek-v4-flash'))
        self.assertIsNone(data['price'])
    def test_policy_is_reset_between_requests_on_the_same_socket(self):
        self.cfg['base']=gateway.cloud_policy.BASE
        client=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            self.assertEqual(self.request(model='cloud:review/model:free',connection=client)[0],200)
            self.cfg['base']=gateway.cloud_policy.ZEN_BASE
            self.assertEqual(self.request(free=False,connection=client)[1]['model'],'deepseek-v4-flash')
            self.assertEqual([x['free_only'] for x in self.calls],[True,False])
        finally:client.close()
    def test_bad_policy_and_existing_identity_origin_boundaries_remain_refusals(self):
        self.assertEqual(self.request(policy='paid')[0],400)
        self.assertEqual(self.request(origin='https://foreign.invalid')[0],403)
        self.client_allowed=False
        self.assertEqual(self.request()[0],403)
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()

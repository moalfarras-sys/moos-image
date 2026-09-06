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
            with urllib.request.urlopen(req,timeout=3) as response:result=response.read().decode()
            self.assertIn('جاهز',result);self.assertIn('data: [DONE]',result)
        finally:srv.shutdown();srv.server_close();thread.join()

if __name__=='__main__':unittest.main()

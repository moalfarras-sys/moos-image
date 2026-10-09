import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from community.outbox import Outbox
from community.transport import Api,ApiError,MAX_RESPONSE,NoRedirects


class Reply(io.BytesIO):
    status=200
    def __enter__(self):return self
    def __exit__(self,*_):self.close()


class Transport(unittest.TestCase):
    def test_real_credentials_cannot_use_http_redirects_or_url_credentials(self):
        for url in ('http://127.0.0.1:8000','http://localhost:8000','https://user:password@example.test',
                    'https://example.test/path','https://example.test?token=hidden'):
            with self.subTest(url=url),self.assertRaises(ValueError):Api(url)
        Api('http://127.0.0.1:8000',review=True)
        with self.assertRaises(ValueError):Api('http://example.test',review=True)
        with self.assertRaises(ApiError):NoRedirects().redirect_request(None,None,302,'',{},'https://elsewhere.test')

    def test_malformed_oversized_and_fake_success_records_are_refused(self):
        api=Api('https://community.example.test')
        for raw in (b'not json',b'[]',b'{"schema":true}',b'{"schema":2}',b'x'*(MAX_RESPONSE+1)):
            with patch.object(api.opener,'open',return_value=Reply(raw)),self.assertRaises(ApiError):
                api.request('GET','/v1/health')
        with patch.object(api.opener,'open',return_value=Reply(b'{"schema":1,"status":"ready"}')):
            self.assertEqual(api.request('GET','/v1/health')['status'],'ready')

    def test_tokens_are_headers_only_and_failure_text_does_not_echo_content(self):
        api=Api('https://community.example.test');token='a'*43
        with patch.object(api.opener,'open',return_value=Reply(b'{"schema":1}')) as call:
            api.request('GET','/v1/threads',token=token)
        request=call.call_args.args[0]
        self.assertNotIn(token,request.full_url)
        self.assertEqual(request.get_header('Authorization'),'Bearer '+token)
        error=urllib.error.HTTPError(request.full_url,401,'',{},io.BytesIO(
            json.dumps({'detail':{'code':'invalid_credentials','password':'private'}}).encode()))
        with patch.object(api.opener,'open',side_effect=error),self.assertRaises(ApiError) as result:
            api.request('GET','/v1/threads',token=token)
        self.assertEqual(str(result.exception),'invalid_credentials')


class Drafts(unittest.TestCase):
    def test_thread_and_reply_images_are_transferred_atomically_and_retry_once(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox=Outbox(directory,'https://community.example.test','alice')
            report=outbox.add('thread',{'title':'خاص','body':'خاص'},image=b'private pixels')
            child=outbox.accept_thread(report,{'received':True,'id':'thread-id'})
            self.assertIsNone(outbox.accept_thread(report,{'received':True,'id':'thread-id'}))
            self.assertIsNone(outbox.get(report)['image'])
            outbox.close();outbox=Outbox(directory,'https://community.example.test','alice')
            self.assertEqual(outbox.pending()[0]['id'],child)
            self.assertEqual(outbox.get(child)['image'],b'private pixels')
            message=outbox.add('message',{'body':'رد'},image=b'reply pixels',thread='thread-id')
            reply=outbox.accept_message(message,{'received':True,'id':5})
            self.assertEqual(outbox.get(reply)['thread'],'thread-id')
            self.assertIsNone(outbox.accept_message(message,{'received':True,'id':5}))
            self.assertEqual(len(outbox.pending()),2);outbox.close()

    def test_unsent_composer_survives_restart_and_remains_account_private(self):
        with tempfile.TemporaryDirectory() as directory:
            alice=Outbox(directory,'https://community.example.test','alice')
            alice.save_composer('report',{'body':'مسودة خاصة'},b'private image');alice.close()
            alice=Outbox(directory,'https://community.example.test','alice')
            bob=Outbox(directory,'https://community.example.test','bob')
            self.assertEqual(alice.composer('report'),({'body':'مسودة خاصة'},b'private image'))
            self.assertEqual(bob.composer('report'),({},None))
            alice.clear_composer('report');self.assertEqual(alice.composer('report'),({},None))
            alice.close();bob.close()

    def test_network_failure_and_process_restart_keep_the_same_retry_id(self):
        with tempfile.TemporaryDirectory() as directory:
            first=Outbox(directory,'https://community.example.test','alice')
            identity=first.add('thread',{'title':'مشكلة','body':'وصف المشكلة','kind':'problem'})
            body=first.get(identity)['payload'];first.close()
            second=Outbox(directory,'https://community.example.test','alice')
            self.assertEqual(second.pending()[0]['payload'],body)
            self.assertEqual(body['client_id'],identity)
            second.received(identity,{'schema':1,'received':True,'id':'real-receipt'})
            self.assertEqual(second.pending(),[]);second.close()

    def test_accounts_and_service_origins_cannot_see_each_others_drafts(self):
        with tempfile.TemporaryDirectory() as directory:
            alice=Outbox(directory,'https://community.example.test','alice')
            identity=alice.add('message',{'body':'خاص'},thread='thread-id')
            bob=Outbox(directory,'https://community.example.test','bob')
            other=Outbox(directory,'https://elsewhere.example.test','alice')
            self.assertIsNone(bob.get(identity));self.assertIsNone(other.get(identity))
            for outbox in (alice,bob,other):
                self.assertEqual(outbox.path.stat().st_mode & 0o777,0o600);outbox.close()

    def test_credentials_and_unproven_success_cannot_enter_durable_state(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox=Outbox(directory,'https://community.example.test','alice')
            with self.assertRaises(ValueError):outbox.add('message',{'password':'secret'})
            identity=outbox.add('message',{'body':'خاص'})
            for receipt in ({'received':False,'id':'x'},{'received':'true','id':'x'},{}):
                with self.assertRaises(ValueError):outbox.received(identity,receipt)
            self.assertEqual(len(outbox.pending()),1);outbox.close()


if __name__=='__main__':unittest.main()

"""Real ASGI requests, private databases and decoded images, never owner data."""
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from community.service import BoundedRequests, MAX_BODY, MAX_UPLOAD, Store, create_app


def key():
    return str(uuid.uuid4())


class Participation(unittest.TestCase):
    def test_paginated_messages_keep_all_entries_and_reject_negative_cursors(self):
        identity,_=self.thread()
        with self.app.state.store.connect(write=True) as db:
            owner=db.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
            db.executemany('INSERT INTO messages(thread,author,body,created,client_id) VALUES (?,?,?,?,?)',
                          [(identity,owner,'private '+str(i),i,key()) for i in range(105)])
        first=self.client.get('/v1/threads/'+identity,headers=self.headers['alice']).json()
        self.assertTrue(first['has_more']);self.assertEqual(len(first['messages']),100)
        second=self.client.get('/v1/threads/'+identity+'?after='+str(first['messages'][-1]['id']),
                               headers=self.headers['alice']).json()
        self.assertFalse(second['has_more']);self.assertEqual(len(second['messages']),6)
        self.assertEqual(self.client.get('/v1/threads/'+identity+'?after=-1',headers=self.headers['alice']).status_code,422)

    def test_transparent_image_cannot_reveal_hidden_rgb_after_upload(self):
        identity,_=self.thread();raw=io.BytesIO()
        Image.new('RGBA',(12,12),(255,0,0,0)).save(raw,format='PNG')
        image=self.client.post('/v1/threads/'+identity+'/images',content=raw.getvalue(),
            headers=self.headers['alice']|{'Idempotency-Key':key()}).json()['id']
        read=self.client.get('/v1/images/'+image,headers=self.headers['alice'])
        with Image.open(io.BytesIO(read.content)) as decoded:
            self.assertEqual(decoded.convert('RGB').getpixel((0,0)),(255,255,255))

    def test_session_identity_is_authenticated_and_retained_sessions_are_bounded(self):
        self.assertEqual(self.client.get('/v1/session').status_code,401)
        me=self.client.get('/v1/session',headers=self.headers['alice']).json()['user']
        self.assertEqual(me,{'username':'alice','display_name':'alice','role':'member'})
        for _ in range(5):
            self.assertEqual(self.client.post('/v1/session',json={'username':'alice',
                'password':'private-fixture-pass-alice'}).status_code,200)
        with self.app.state.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions WHERE user=(SELECT id FROM users WHERE username='alice')").fetchone()[0],5)
        self.assertEqual(self.client.get('/v1/session',headers=self.headers['alice']).status_code,401)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.verifier = lambda *_args: False
        self.app = create_app(self.root, public_origin='https://community.example.test',
                              registration_open=True,
                              release_verifier=lambda *args: self.verifier(*args))
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers = {}
        for name in ('alice', 'bob', 'staff'):
            credentials = {'username':name, 'password':'private-fixture-pass-'+name}
            r = self.client.post('/v1/accounts', json=credentials | {'display_name':name})
            self.assertEqual(r.status_code,201,r.text)
            r = self.client.post('/v1/session',json=credentials)
            self.assertEqual(r.status_code,200,r.text)
            self.headers[name] = {'Authorization':'Bearer '+r.json()['token']}
        with self.app.state.store.connect(write=True) as db:
            db.execute("UPDATE users SET role='maintainer' WHERE username='staff'")

    def thread(self, name='alice', **extra):
        body={'client_id':key(),'kind':'problem','title':'تعليق النافذة',
              'body':'تفاصيل مشكلة المستخدم الخاصة.'} | extra
        r=self.client.post('/v1/threads',json=body,headers=self.headers[name])
        self.assertEqual(r.status_code,201,r.text)
        return r.json()['id'],body

    def png(self):
        image=Image.new('RGB',(16,16),'teal')
        metadata=PngImagePlugin.PngInfo();metadata.add_text('private-coordinate','should disappear')
        out=io.BytesIO();image.save(out,format='PNG',pnginfo=metadata)
        return out.getvalue()

    def test_member_cannot_choose_a_role_or_impersonate_a_maintainer(self):
        r=self.client.post('/v1/accounts',json={'username':'mallory','password':'fixture-password-123',
                                              'display_name':'اختبار','role':'maintainer'})
        self.assertEqual(r.status_code,422)
        identity,_=self.thread()
        self.assertEqual(self.client.patch('/v1/threads/'+identity+'/state',
            json={'state':'triage'},headers=self.headers['alice']).status_code,403)

    def test_threads_are_private_even_when_another_account_knows_the_id(self):
        identity,_=self.thread()
        self.assertEqual(self.client.get('/v1/threads/'+identity,headers=self.headers['bob']).status_code,404)
        self.assertEqual(self.client.get('/v1/threads',headers=self.headers['bob']).json()['threads'],[])
        self.assertEqual(self.client.post('/v1/threads/'+identity+'/messages',
            json={'client_id':key(),'body':'unauthorized'},headers=self.headers['bob']).status_code,404)
        self.assertEqual(self.client.get('/v1/threads/'+identity,headers=self.headers['staff']).status_code,200)
        self.assertEqual(self.client.get('/v1/suggestions').json()['suggestions'],[])

    def test_public_suggestion_requires_consent_and_never_publishes_private_replies(self):
        self.assertEqual(self.client.post('/v1/threads',headers=self.headers['alice'],
            json={'client_id':key(),'kind':'suggestion','title':'فكرة','body':'اقتراح واضح',
                  'public':True}).status_code,422)
        identity,_=self.thread(kind='suggestion',public=True,publish_consent=True,
                              title='فكرة لتطوير MoOS',body='اقتراح عام اختاره المستخدم.')
        self.client.post('/v1/threads/'+identity+'/messages',headers=self.headers['staff'],
                         json={'client_id':key(),'body':'رد خاص لا يجوز نشره'})
        public=self.client.get('/v1/suggestions').json()
        self.assertEqual(len(public['suggestions']),1)
        self.assertNotIn('رد خاص',json.dumps(public,ensure_ascii=False))
        self.assertNotIn('messages',public['suggestions'][0])
        self.assertEqual(self.client.get('/v1/threads/'+identity,headers=self.headers['bob']).status_code,404)

    def test_uploads_are_private_normalized_and_retry_without_duplicates(self):
        identity,_=self.thread(kind='suggestion',public=True,publish_consent=True)
        image=self.png();headers=self.headers['alice'] | {'Idempotency-Key':key()}
        route='/v1/threads/'+identity+'/images'
        first=self.client.post(route,content=image,headers=headers)
        self.assertEqual(first.status_code,201,first.text)
        second=self.client.post(route,content=image,headers=headers)
        self.assertEqual(first.json(),second.json())
        picture='/v1/images/'+first.json()['id']
        self.assertEqual(self.client.get(picture,headers=self.headers['bob']).status_code,404)
        self.assertEqual(self.client.get(picture).status_code,401)
        read=self.client.get(picture,headers=self.headers['alice'])
        self.assertEqual(read.status_code,200)
        self.assertEqual(read.headers['content-type'],'image/png')
        with Image.open(io.BytesIO(read.content)) as decoded:
            self.assertEqual(decoded.size,(16,16));self.assertNotIn('private-coordinate',decoded.info)
        self.assertNotIn('images',self.client.get('/v1/suggestions').text)
        self.assertEqual(self.client.post(route,content=b'changed',headers=headers).status_code,409)

    def test_foreign_upload_is_refused_before_an_image_decoder_runs(self):
        identity,_=self.thread()
        with patch('community.service.normalized_image',side_effect=AssertionError('decoded foreign bytes')):
            r=self.client.post('/v1/threads/'+identity+'/images',content=b'not an image',
                headers=self.headers['bob'] | {'Idempotency-Key':key()})
        self.assertEqual(r.status_code,404)

    def test_invalid_truncated_animated_oversized_and_nonimage_uploads_fail(self):
        identity,_=self.thread();route='/v1/threads/'+identity+'/images'
        samples=[b'<svg onload="alert(1)"></svg>',self.png()[:30],b'not an image',b'x'*(MAX_UPLOAD+1)]
        large=io.BytesIO();Image.new('RGB',(2100,2100)).save(large,format='PNG');samples.append(large.getvalue())
        animated=io.BytesIO()
        Image.new('RGB',(8,8),'red').save(animated,format='GIF',save_all=True,
            append_images=[Image.new('RGB',(8,8),'blue')]);samples.append(animated.getvalue())
        for data in samples:
            r=self.client.post(route,content=data,headers=self.headers['alice'] | {'Idempotency-Key':key()})
            self.assertIn(r.status_code,(413,422),r.text)
        self.assertEqual(self.client.get('/v1/threads/'+identity,headers=self.headers['alice']).json()['images'],[])

    def test_retry_identity_is_transactional_and_content_changes_are_refused(self):
        identity,body=self.thread()
        repeat=self.client.post('/v1/threads',json=body,headers=self.headers['alice'])
        self.assertEqual(repeat.json()['id'],identity)
        self.assertEqual(self.client.post('/v1/threads',json=body | {'body':'changed proposal'},
            headers=self.headers['alice']).status_code,409)
        message={'client_id':key(),'body':'رسالة أخرى'}
        route='/v1/threads/'+identity+'/messages'
        first=self.client.post(route,json=message,headers=self.headers['alice'])
        second=self.client.post(route,json=message,headers=self.headers['alice'])
        self.assertEqual(first.json(),second.json())
        self.assertEqual(len(self.client.get('/v1/threads/'+identity,
            headers=self.headers['alice']).json()['messages']),2)

    def test_a_source_merge_cannot_be_announced_as_a_released_fix(self):
        identity,_=self.thread();route='/v1/threads/'+identity+'/state'
        self.assertEqual(self.client.patch(route,json={'state':'released','release_id':'unverified'},
            headers=self.headers['staff']).status_code,422)
        metadata={'edition':'moos','version':'44.20261009.1','digest':'sha256:'+'a'*64}
        self.assertEqual(self.client.post('/v1/releases',json=metadata,
            headers=self.headers['staff']).status_code,422)
        self.verifier=lambda *_: True  # isolated signature/promotion fixture, not a real release
        release=self.client.post('/v1/releases',json=metadata,headers=self.headers['staff'])
        self.assertEqual(release.status_code,201,release.text)
        fixed=self.client.patch(route,json={'state':'released','release_id':release.json()['id']},
            headers=self.headers['staff'])
        self.assertEqual(fixed.status_code,200,fixed.text)
        updates=self.client.get('/v1/notifications',headers=self.headers['alice']).json()['notifications']
        self.assertEqual(updates[0]['event'],'released')
        self.assertEqual(self.client.get('/v1/notifications',headers=self.headers['bob']).json()['notifications'],[])

    def test_maintainer_reply_notifies_only_its_author_and_public_moderation_is_guarded(self):
        identity,_=self.thread(kind='suggestion',public=True,publish_consent=True)
        self.client.post('/v1/threads/'+identity+'/messages',headers=self.headers['staff'],
            json={'client_id':key(),'body':'رد فريق التطوير'})
        records=self.client.get('/v1/notifications',headers=self.headers['alice']).json()['notifications']
        self.assertEqual(records[0]['event'],'reply')
        self.client.post('/v1/notifications/'+str(records[0]['id'])+'/seen',headers=self.headers['bob'])
        self.assertEqual(self.client.get('/v1/notifications',headers=self.headers['alice']).json()['notifications'][0]['seen'],0)
        route='/v1/moderation/'+identity+'/hide'
        self.assertEqual(self.client.post(route,headers=self.headers['bob']).status_code,403)
        self.assertEqual(self.client.post(route,headers=self.headers['staff']).status_code,200)
        self.assertEqual(self.client.get('/v1/suggestions').json()['suggestions'],[])

    def test_session_logout_expiry_and_account_suspension_revoke_access(self):
        identity,_=self.thread()
        self.assertEqual(self.client.delete('/v1/session',headers=self.headers['alice']).status_code,204)
        self.assertEqual(self.client.get('/v1/threads/'+identity,headers=self.headers['alice']).status_code,401)
        with self.app.state.store.connect(write=True) as db:
            db.execute("UPDATE users SET active=0 WHERE username='bob'")
            db.execute("UPDATE sessions SET expires=0 WHERE user=(SELECT id FROM users WHERE username='staff')")
        for name in ('bob','staff'):
            self.assertEqual(self.client.get('/v1/threads',headers=self.headers[name]).status_code,401)

    def test_foreign_origin_unknown_fields_empty_content_and_guessed_tokens_are_refused(self):
        self.assertEqual(self.client.get('/v1/threads',headers=self.headers['alice'] | {'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/v1/threads',headers={'Authorization':'Bearer guessed'}).status_code,401)
        identity,body=self.thread()
        self.assertEqual(self.client.post('/v1/threads',headers=self.headers['alice'],
            json=body | {'client_id':key(),'body':'     '}).status_code,422)
        response=self.client.get('/v1/threads/'+identity,headers=self.headers['alice'])
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.headers['x-content-type-options'],'nosniff')

    def test_private_database_has_no_raw_password_or_session_token(self):
        db=self.app.state.store.database
        self.assertEqual(db.stat().st_mode & 0o777,0o600)
        with self.app.state.store.connect() as connection:
            rows=connection.execute('SELECT password FROM users').fetchall()
            self.assertTrue(all(row[0].startswith('$argon2id$') for row in rows))
            hashes=connection.execute('SELECT hash FROM sessions').fetchall()
            for headers in self.headers.values():
                self.assertNotIn(headers['Authorization'][7:],[r[0] for r in hashes])

    def test_moderation_revokes_access_without_granting_member_privileges(self):
        identity,_=self.thread(kind='suggestion',public=True,publish_consent=True)
        route='/v1/moderation/'+identity+'/account'
        self.assertEqual(self.client.post(route,json={'active':False},headers=self.headers['bob']).status_code,403)
        self.assertEqual(self.client.post(route,json={'active':False},headers=self.headers['staff']).status_code,200)
        self.assertEqual(self.client.get('/v1/threads',headers=self.headers['alice']).status_code,401)
        self.assertEqual(self.client.get('/v1/suggestions').json()['suggestions'],[])

    def test_explicit_thread_deletion_removes_only_its_messages_images_and_notifications(self):
        first,_=self.thread();second,_=self.thread('bob')
        picture=self.client.post('/v1/threads/'+first+'/images',content=self.png(),
            headers=self.headers['alice']|{'Idempotency-Key':key()}).json()['id']
        route='/v1/threads/'+first
        self.assertEqual(self.client.delete(route,headers=self.headers['bob']).status_code,404)
        self.assertEqual(self.client.delete(route,headers=self.headers['alice']).status_code,204)
        self.assertEqual(self.client.get('/v1/images/'+picture,headers=self.headers['alice']).status_code,404)
        self.assertEqual(self.client.get('/v1/threads/'+second,headers=self.headers['bob']).status_code,200)


class StorageAndWire(unittest.TestCase):
    def test_unsafe_data_directory_and_database_links_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o755)
            with self.assertRaises(ValueError):Store(root)
            root.chmod(0o700);target=root/'other';target.write_text('preserve')
            (root/'participation.sqlite3').symlink_to(target)
            with self.assertRaises(OSError):Store(root)
            self.assertEqual(target.read_text(),'preserve')

    def test_chunked_input_without_content_length_is_still_bounded(self):
        calls=[];sent=[]
        async def app(*args):calls.append(True)
        messages=iter([{'type':'http.request','body':b'x'*(MAX_BODY//2),'more_body':True},
                       {'type':'http.request','body':b'x'*(MAX_BODY//2+1),'more_body':False}])
        async def receive():return next(messages)
        async def send(message):sent.append(message)
        asyncio.run(BoundedRequests(app,'https://community.example.test')(
            {'type':'http','headers':[]},receive,send))
        self.assertEqual(calls,[])
        self.assertEqual(sent[0]['status'],413)


if __name__=='__main__':
    unittest.main()

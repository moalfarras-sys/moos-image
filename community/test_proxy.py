"""Negative controls and a real private TCP connection for proxy attribution."""
import asyncio
import io
import os
import socket
import unittest
from unittest.mock import patch

from community.proxy import address, forwarded_ip, peer_uid
from community.service import BoundedRequests


class ProxyIdentity(unittest.TestCase):
    def test_real_peer_and_reversed_full_tuple(self):
        with socket.socket() as listener, socket.socket() as client:
            listener.bind(('127.0.0.1', 0)); listener.listen()
            client.connect(listener.getsockname())
            accepted, _ = listener.accept()
            with accepted:
                scope={'client':accepted.getpeername(),'server':accepted.getsockname()}
                self.assertEqual(peer_uid(scope),os.getuid())
                headers=[(b'x-forwarded-for',b'203.0.113.15')]
                self.assertEqual(forwarded_ip(scope,headers,os.getuid()),'203.0.113.15')
                self.assertIsNone(forwarded_ip(scope,headers,os.getuid()+1))
                altered=dict(scope,client=('127.0.0.1',scope['client'][1]+1))
                self.assertIsNone(peer_uid(altered))

    def test_accepted_server_uid_missing_records_and_header_lists_are_not_trusted(self):
        scope={'client':('127.0.0.1',32001),'server':('127.0.0.1',8939)}
        # A server socket with the expected UID is insufficient.
        line=f"0: {address(scope['server'])} {address(scope['client'])} 01 0 0 0 0 0 123\n"
        with patch('builtins.open',return_value=io.StringIO(line)):
            self.assertIsNone(peer_uid(scope))
        for value in (b'1.2.3.4, 5.6.7.8',b'not ip',b'1.2.3.4:22'):
            with patch('community.proxy.peer_uid',return_value=0):
                self.assertIsNone(forwarded_ip(scope,[(b'x-forwarded-for',value)],0))
        with patch('community.proxy.peer_uid',return_value=0):
            self.assertIsNone(forwarded_ip(scope,[(b'x-forwarded-for',b'1.2.3.4')]*2,0))
        self.assertIsNone(peer_uid({'client':('::1',1),'server':('::1',2)}))

    def test_public_middleware_rejects_forged_proxy_and_passes_verified_ip(self):
        async def exercise(verified):
            calls=[];sent=[]
            async def app(scope,receive,send):calls.append(scope['client'][0])
            async def receive():return {'type':'http.request','body':b'','more_body':False}
            async def send(message):sent.append(message)
            scope={'type':'http','client':('127.0.0.1',12345),'server':('127.0.0.1',8939),
                   'headers':[(b'x-forwarded-for',b'203.0.113.10')]}
            with patch('community.proxy.peer_uid',return_value=verified):
                await BoundedRequests(app,'https://community.example.test',proxy_uid=0)(scope,receive,send)
            return calls,sent
        calls,sent=asyncio.run(exercise(1001))
        self.assertEqual(calls,[]);self.assertEqual(sent[0]['status'],403)
        calls,sent=asyncio.run(exercise(0))
        self.assertEqual(calls,['203.0.113.10'])


if __name__=='__main__':unittest.main()

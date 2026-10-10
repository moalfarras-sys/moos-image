import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from community.releases import verify_promoted


class ReleaseVerification(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.key=str(Path(self.tmp.name)/'public.pem');Path(self.key).write_text('public fixture only')
        self.digest='sha256:'+'a'*64
        self.metadata={'Digest':self.digest,'Labels':{'org.opencontainers.image.version':'44.20261009.728'}}
        self.payload=[{'critical':{'image':{'docker-manifest-digest':self.digest}}}]
        self.calls=[]
    def command(self,args,**kwargs):
        self.calls.append(args)
        return SimpleNamespace(stdout=json.dumps(self.payload if args[0]=='cosign' else self.metadata))
    def verify(self,**kwargs):
        return verify_promoted('moos-arm','44.20261009.728',self.digest,key=self.key,run=self.command,**kwargs)
    def test_exact_promoted_digest_uses_the_unweakened_public_key_verifier(self):
        self.assertTrue(self.verify())
        self.assertEqual(self.calls[1],['cosign','verify','--key',self.key,'--output','json',
            'ghcr.io/moalfarras-sys/moos-arm@'+self.digest])
        self.assertEqual(len(self.calls),3)
    def test_candidate_stale_version_wrong_signature_payload_or_unavailable_tools_fail_closed(self):
        self.metadata['Digest']='sha256:'+'b'*64;self.assertFalse(self.verify())
        self.metadata['Digest']=self.digest
        self.metadata['Labels']['org.opencontainers.image.version']='44.OLD';self.assertFalse(self.verify())
        self.metadata['Labels']['org.opencontainers.image.version']='44.20261009.728'
        for payload in ([],{},[{'critical':{'image':{'docker-manifest-digest':'sha256:'+'b'*64}}}]):
            self.payload=payload;self.assertFalse(self.verify())
        def unavailable(*_args,**_kwargs):raise subprocess.TimeoutExpired('cosign',30)
        self.assertFalse(verify_promoted('moos-arm','44.20261009.728',self.digest,key=self.key,run=unavailable))
    def test_invalid_target_cannot_reach_a_command(self):
        self.assertFalse(verify_promoted('moos-arm;bad','44.20261009.728',self.digest,key=self.key,run=self.command))
        self.assertEqual(self.calls,[])
    def test_a_concurrent_promotion_change_invalidates_the_receipt(self):
        def moving(args,**kwargs):
            result=self.command(args,**kwargs)
            if args[0]=='cosign':self.metadata['Digest']='sha256:'+'b'*64
            return result
        self.assertFalse(verify_promoted('moos-arm','44.20261009.728',self.digest,key=self.key,run=moving))


if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
"""SDK selection, failed-download controls and the real workflow callers."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('dotnet_sdk_resolver', ROOT/'scripts/ci/resolve-dotnet-sdk.py')
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)


def metadata():
    return {'channel-version':'10.0', 'release-type':'lts', 'support-phase':'active',
            'latest-sdk':'10.0.403', 'releases':[{'release-version':'10.0.14',
            'sdk':{'version':'10.0.403'}, 'sdks':[{'version':'10.0.403'}]}]}


class Response(io.BytesIO):
    def __init__(self, body, url=resolver.URL):
        super().__init__(body)
        self.url = url

    def geturl(self):
        return self.url


class DotnetSDKResolver(unittest.TestCase):
    def test_current_supported_channel_and_stable_catalogue(self):
        self.assertEqual(resolver.sdk_version(metadata()), '10.0.403')
        data=metadata();data['support-phase']='maintenance'
        self.assertEqual(resolver.sdk_version(data), '10.0.403')

    def test_unknown_preview_eol_and_injected_versions_are_refused(self):
        mutations=[('channel-version','11.0'),('release-type','sts'),('support-phase','eol')]
        mutations += [('latest-sdk',v) for v in ('10.0.x','10.0.403-preview.1','11.0.100',403,'10.0.403\nother=value','../../SDK')]
        for key,value in mutations:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                data=metadata();data[key]=value;resolver.sdk_version(data)
        for data in (None,[],metadata() | {'releases':[]}, metadata() | {'releases':[{'release-version':'10.0.14-preview','sdk':{'version':'10.0.403'}}]}):
            with self.subTest(data=data),self.assertRaises(ValueError):resolver.sdk_version(data)

    def test_only_reviewed_endpoint_and_bounded_utf8_json_are_read(self):
        opener=Mock(return_value=Response(json.dumps(metadata()).encode()))
        self.assertEqual(resolver.sdk_version(resolver.read_metadata(opener)), '10.0.403')
        args,kwargs=opener.call_args
        self.assertEqual(args[0].full_url,resolver.URL)
        self.assertEqual(kwargs,{'timeout':20})
        for body,url in [(b'not-json',resolver.URL),(b'\xff',resolver.URL),
                         (b' '* (resolver.MAX_BYTES+1),resolver.URL),
                         (b'{}','https://dotnetorigin.blob.core.windows.net/metadata')]:
            bad=Mock(return_value=Response(body,url))
            with self.subTest(url=url,size=len(body)),self.assertRaises(ValueError):resolver.read_metadata(bad)
            self.assertEqual(bad.call_count,1)

    def test_observed_409_is_a_failure_and_transient_retry_is_finite(self):
        refused=Mock(side_effect=urllib.error.HTTPError(resolver.URL,409,'Conflict',{},None))
        sleep=Mock()
        with self.assertRaises(urllib.error.HTTPError):resolver.read_metadata(refused,sleep)
        self.assertEqual(refused.call_count,1);sleep.assert_not_called()
        temporary=Mock(side_effect=[urllib.error.URLError('reset'),urllib.error.HTTPError(resolver.URL,503,'Unavailable',{},None),Response(json.dumps(metadata()).encode())])
        self.assertEqual(resolver.sdk_version(resolver.read_metadata(temporary,sleep)), '10.0.403')
        self.assertEqual(temporary.call_count,3)
        self.assertEqual([x.args[0] for x in sleep.call_args_list],[1,2])
        failed=Mock(side_effect=TimeoutError('deadline'))
        with self.assertRaises(TimeoutError):resolver.read_metadata(failed,Mock())
        self.assertEqual(failed.call_count,3)

    def test_no_output_is_published_before_successful_validation(self):
        with tempfile.TemporaryDirectory(prefix='moos-dotnet-sdk-') as td:
            output=Path(td)/'github-output';output.write_text('prior=preserved\n')
            with patch.dict(os.environ,{'GITHUB_OUTPUT':str(output)}),patch.object(resolver,'read_metadata',return_value=metadata()),contextlib.redirect_stdout(io.StringIO()) as stdout:
                resolver.main()
            self.assertEqual(output.read_text(),'prior=preserved\nversion=10.0.403\n')
            self.assertIn('MOOS_DOTNET_SDK_VERSION=10.0.403',stdout.getvalue())
            before=output.read_bytes()
            with patch.dict(os.environ,{'GITHUB_OUTPUT':str(output)}),patch.object(resolver,'read_metadata',return_value=metadata() | {'latest-sdk':'10.0.x'}),self.assertRaises(ValueError):resolver.main()
            self.assertEqual(output.read_bytes(),before)

    def test_release_and_both_native_fast_callers_keep_the_pinned_installer(self):
        for name,count in [('build.yml',2),('moremote-fast.yml',2)]:
            text=(ROOT/'.github/workflows'/name).read_text()
            self.assertEqual(text.count('run: python scripts/ci/resolve-dotnet-sdk.py'),count)
            self.assertEqual(text.count('dotnet-version: ${{ steps.dotnet.outputs.version }}'),count)
            self.assertEqual(text.count('actions/setup-dotnet@26b0ec14cb23fa6904739307f278c14f94c95bf1'),count)
            self.assertNotIn('dotnet-version: "10.0.x"',text)
        fast=(ROOT/'.github/workflows/moremote-fast.yml').read_text()
        self.assertIn('runs-on: windows-latest',fast)
        self.assertEqual(fast.count('DOTNET_INSTALL_DIR: ${{ runner.temp }}/moos-dotnet-sdk'),2)
        self.assertIn('dotnet build moremote/agent/MoRemoteAgent.csproj -c Release --nologo',fast)
        trigger=fast.split('concurrency:',1)[0]
        self.assertIn('"scripts/ci/resolve-dotnet-sdk.py"',trigger)
        self.assertIn('".github/workflows/build.yml"',trigger)


if __name__ == '__main__':
    unittest.main()

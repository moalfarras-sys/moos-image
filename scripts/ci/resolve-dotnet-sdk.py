#!/usr/bin/env python3
"""Resolve the current supported SDK without aka.ms archive redirects.

Keep Microsoft's pinned installer as the installation owner. Giving it an
exact version selects its official builds feed, while reading the channel
metadata here retains normal .NET 10 security updates.
"""
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

URL = 'https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json'
MAX_BYTES = 4 * 1024 * 1024
VERSION = re.compile(r'10\.0\.[1-9][0-9]{2,3}')


def sdk_version(data):
    if not isinstance(data, dict) or data.get('channel-version') != '10.0':
        raise ValueError('Expected Microsoft .NET 10 channel metadata')
    if data.get('release-type') != 'lts' or data.get('support-phase') not in ('active', 'maintenance'):
        raise ValueError('Expected a supported stable LTS channel')
    version = data.get('latest-sdk')
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError('Expected an exact stable .NET 10 SDK version')
    releases = data.get('releases')
    if not isinstance(releases, list):
        raise ValueError('SDK release catalogue is missing')
    for release in releases:
        if not isinstance(release, dict) or not re.fullmatch(r'10\.0\.[0-9]+', str(release.get('release-version', ''))):
            continue
        sdks = release.get('sdks', [])
        if not isinstance(sdks, list):
            raise ValueError('Unexpected SDK release list')
        if any(isinstance(sdk, dict) and sdk.get('version') == version
               for sdk in [release.get('sdk'), *sdks]):
            return version
    raise ValueError('Latest SDK is absent from the stable release catalogue')


def read_metadata(opener=urllib.request.urlopen, sleep=time.sleep):
    for attempt in range(3):
        try:
            request = urllib.request.Request(URL, headers={'User-Agent': 'MoOS-CI-SDK-resolver'})
            with opener(request, timeout=20) as response:
                if response.geturl() != URL:
                    raise ValueError('SDK metadata left the reviewed Microsoft endpoint')
                payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise ValueError('SDK metadata exceeds its size bound')
            return json.loads(payload.decode('utf-8'))
        except urllib.error.HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        sleep(attempt + 1)
    raise AssertionError('unreachable')


def main():
    version = sdk_version(read_metadata())
    # The validated numeric value cannot inject another GitHub output record.
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8', newline='\n') as output:
            output.write('version=' + version + '\n')
    print('MOOS_DOTNET_SDK_VERSION=' + version)


if __name__ == '__main__':
    main()

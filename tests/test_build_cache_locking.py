#!/usr/bin/env python3
"""DNF payload cache leases must cover each whole native image transaction."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


def require_cache_leases(text):
    runs=re.findall(r'^RUN(?:[^\n]*\\\n)*[^\n]*',text,re.M)
    seen=set()
    for run in runs:
        mounts=[]
        for options in re.findall(r'--mount=([^\s]+)',run):
            fields=dict(part.split('=',1) for part in options.split(',') if '=' in part)
            if fields.get('type')=='cache' and fields.get('dst') in ('/var/cache','/var/log'):
                if fields.get('sharing')!='locked':raise AssertionError('package/log cache lease is shared')
                mounts.append(fields['dst']);seen.add(fields['dst'])
        if mounts and mounts!=['/var/cache','/var/log']:
            raise AssertionError('cache lease ordering/pair drifted')
    if seen!={'/var/cache','/var/log'}:raise AssertionError('no protected package/log cache mounts')


class ImageCacheLease(unittest.TestCase):
    def test_all_native_image_package_and_log_mounts_hold_consistent_exclusive_leases(self):
        for name in ('Containerfile','Containerfile.arm'):
            with self.subTest(name=name):require_cache_leases((ROOT/name).read_text())

    def test_restored_shared_mode_missing_lease_and_inverted_order_are_rejected(self):
        text=(ROOT/'Containerfile').read_text()
        broken=[text.replace('type=cache,sharing=locked','type=cache',1),
                text.replace('sharing=locked','sharing=shared',1),
                text.replace('dst=/var/cache','dst=/var/temporary-placeholder',1).replace('dst=/var/log','dst=/var/cache',1).replace('dst=/var/temporary-placeholder','dst=/var/log',1)]
        for variant in broken:
            with self.subTest(variant=variant[:60]),self.assertRaises(AssertionError):require_cache_leases(variant)


if __name__=='__main__':unittest.main()

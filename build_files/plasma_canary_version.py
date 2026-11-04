#!/usr/bin/python3
"""Describe a next-Plasma lane using the container's native RPM comparison.

An absent or stale beta offer is unavailable evidence, never a qualified next
image. A newer offer must be reached by composition and by the final image.
Repository query failure belongs to the caller and must not become absence.
"""
import json
import re
import sys


def evaluate(baseline, offered, actual, *, image_gates_passed=False):
    import rpm
    version = re.compile(r'[0-9][A-Za-z0-9._+~^]{0,127}\Z')
    if not version.fullmatch(baseline) or not version.fullmatch(actual) or (
            offered and not version.fullmatch(offered)):
        raise ValueError('Invalid or ambiguous Plasma VERSION readback')
    receipt = {'schema': 1, 'reviewedVersion': baseline, 'offeredVersion': offered or None,
               'actualVersion': actual, 'qualifiedNextImage': False}
    if not offered or rpm.labelCompare(('0', offered, ''), ('0', baseline, '')) <= 0:
        receipt.update(status='unavailable', reason='No newer Plasma is offered by the beta repository')
    elif actual != offered:
        receipt.update(status='failed', reason='The image did not reach the offered next Plasma')
    else:
        receipt.update(status='image-gates-passed' if image_gates_passed else 'ready-for-image-gates',
                       qualifiedNextImage=image_gates_passed)
    return receipt


if __name__ == '__main__':
    if len(sys.argv) not in (4, 5) or (len(sys.argv) == 5 and sys.argv[4] != '--image-gates-passed'):
        raise SystemExit('Usage: plasma_canary_version.py REVIEWED OFFERED ACTUAL [--image-gates-passed]')
    try:
        result = evaluate(*sys.argv[1:4], image_gates_passed=len(sys.argv) == 5)
    except (ImportError, ValueError) as error:
        print(json.dumps({'schema': 1, 'status': 'failed', 'qualifiedNextImage': False, 'reason': str(error)}))
        raise SystemExit(1)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(1 if result['status'] == 'failed' else 0)

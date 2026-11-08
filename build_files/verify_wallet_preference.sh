#!/usr/bin/bash
# Exercise final installed wallet bytes in private profiles, with no owner data.
set -euo pipefail
[ -s /ctx/test_wallet_preference.py ] || {
    echo 'GATE FAIL: native wallet proof driver is missing'
    exit 1
}
wallet_log="$(mktemp /tmp/moos-wallet-lifecycle.XXXXXX.log)"
trap 'rm -f "$wallet_log"' EXIT
set +e
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -s /ctx/test_wallet_preference.py --installed >"$wallet_log" 2>&1
wallet_exit=$?
set -e
if [ "$wallet_exit" -ne 0 ]; then
    cat "$wallet_log"
    echo 'GATE FAIL: installed native wallet lifecycle proof failed'
    exit "$wallet_exit"
fi
grep -qx 'MOOS_IMAGE_WALLET_LIFECYCLE_PASS' "$wallet_log" || {
    cat "$wallet_log"
    echo 'GATE FAIL: wallet lifecycle proof did not execute'
    exit 1
}
echo 'MOOS_IMAGE_WALLET_LIFECYCLE_PASS'

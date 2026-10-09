#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin=${COMMUNITY_PYTHON:-python3}
"$python_bin" -m unittest community.test_service community.test_releases community.test_transport community.test_proxy -v
if [[ ${1:-} == --native ]]; then
    # An explicit native check fails if Qt is unavailable; it never calls a skip a pass.
    "$python_bin" -m unittest community.test_client -v
fi

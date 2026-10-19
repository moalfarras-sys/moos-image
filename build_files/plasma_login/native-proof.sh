#!/usr/bin/bash
set -euxo pipefail
# This runs on the actual native SDK architecture before the vendor compiles.
g++ -std=c++20 -fPIC -I src/frontend/settings/models \
    /src/build_files/plasma_login/metadata-proof.cpp \
    $(pkg-config --cflags --libs Qt6Core) -o /work/fingerprint-metadata-proof
timeout 5 /work/fingerprint-metadata-proof
MOOS_REQUIRE_AUTO_FINGERPRINT_QT=1 python3 /src/tests/test_greeter_autofingerprint.py -v
python3 /src/tests/test_fingerprint_login.py -v

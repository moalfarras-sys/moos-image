#!/usr/bin/bash
set -euxo pipefail
# This runs on the actual native SDK architecture before the vendor compiles.
g++ -std=c++20 -fPIC -I src/frontend/settings/models \
    /src/build_files/plasma_login/metadata-proof.cpp \
    $(pkg-config --cflags --libs Qt6Core) -o /work/fingerprint-metadata-proof
timeout 5 /work/fingerprint-metadata-proof
g++ -std=c++20 -fPIC -I src/frontend/kcm -I /usr/include/KF6/KConfig -I /usr/include/KF6/KConfigCore -I /usr/include/KF6/KAuth -I /usr/include/KF6/KAuthCore \
    /src/build_files/plasma_login/appearance-proof.cpp \
    $(pkg-config --cflags --libs Qt6Core) -lKF6ConfigCore -lKF6AuthCore -o /work/login-appearance-proof
timeout 5 /work/login-appearance-proof
MOOS_REQUIRE_AUTO_FINGERPRINT_QT=1 python3 /src/tests/test_greeter_autofingerprint.py -v
python3 /src/tests/test_fingerprint_login.py -v

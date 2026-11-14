#!/usr/bin/bash
set -euxo pipefail
task_root=/work/plasma-login-rpmbuild
source_root=/src/build_files/plasma_login
case "${1:-}" in
prepare)
    mkdir -p "$task_root/SOURCES" "$task_root/SPECS" /out
    current="$(rpm -q --qf '%{VERSION}-%{RELEASE}' plasma-login-manager)"
    python3 "$source_root/rpms.py" source "$current" > /work/plasma-login-source.json
    source_url="$(python3 -c 'import json;print(json.load(open("/work/plasma-login-source.json"))["source_url"])')"
    source_sha="$(python3 -c 'import json;print(json.load(open("/work/plasma-login-source.json"))["source_sha256"])')"
    # TLS connection resets (curl35) are outside curl's default retry list.
    # At mostfour attempts; the480s retry budget plus a last120s transfer also
    # bounds server Retry-After delays, which can override the fixed2s delay.
    # exhausted/permanent failures still stop before digest/signature admission.
    source_http="$(curl --fail --location --retry 3 --retry-all-errors --retry-delay 2 \
        --connect-timeout 30 --max-time 120 --retry-max-time 480 \
        --write-out '%{http_code}' "$source_url" -o /work/plasma-login.src.rpm)"
    # Some curl versions return0 when Retry-After exceeds the retry budget.
    # An old matching output file must never clear a failed HTTP response.
    if [ "$source_http" != 200 ]; then
        echo "Refused plasma-login source HTTP status: $source_http" >&2
        exit 22
    fi
    echo "$source_sha  /work/plasma-login.src.rpm" | sha256sum --check
    LC_ALL=C rpmkeys --checksig --verbose /work/plasma-login.src.rpm > /work/plasma-login-source-signature.txt
    grep -F '96bdf4e8710b8f9ffb11d83ddb51f4cb6c33bdbb: OK' /work/plasma-login-source-signature.txt
    rpm2cpio /work/plasma-login.src.rpm > /work/plasma-login-source.cpio
    (cd "$task_root/SOURCES" && cpio -idm --no-absolute-filenames --no-preserve-owner < /work/plasma-login-source.cpio)
    cp "$task_root/SOURCES/plasma-login-manager.spec" "$task_root/SPECS/plasma-login-manager.spec"
    cp "$source_root/automatic-fingerprint.patch" "$task_root/SOURCES/moos-automatic-fingerprint.patch"
    cp "$source_root/moos-login-scene.patch" "$task_root/SOURCES/moos-login-scene.patch"
    python3 - <<'PY'
from pathlib import Path
path = Path('/work/plasma-login-rpmbuild/SPECS/plasma-login-manager.spec')
text = path.read_text()
assert text.count('Release:        1%{?dist}') == 1
text = text.replace('Release:        1%{?dist}', 'Release:        1.2.moos1%{?dist}')
assert text.count('%description\n') == 1 and text.count('%build\n') == 1
text = text.replace('%description\n', 'Patch2001: moos-automatic-fingerprint.patch\nPatch2002: moos-login-scene.patch\n\n%description\n', 1)
text = text.replace('%build\n', '%build\npython3 /src/build_files/plasma_login/rpms.py prepared\n'
                    'bash /src/build_files/plasma_login/native-proof.sh\n', 1)
path.write_text(text)
PY
    dnf5 -y --setopt=install_weak_deps=False builddep "$task_root/SPECS/plasma-login-manager.spec"
    test "$(rpm -q --qf '%{VERSION}-%{RELEASE}' plasma-login-manager)" = "$current"
    ;;
compile)
    rpmbuild -bb --define "_topdir $task_root" --define '_buildhost moos-build' \
        --define '_smp_mflags -j4' "$task_root/SPECS/plasma-login-manager.spec"
    python3 "$source_root/rpms.py" collect "$task_root/RPMS" /out
    ;;
*) echo 'usage: build.sh prepare | compile' >&2; exit 2 ;;
esac

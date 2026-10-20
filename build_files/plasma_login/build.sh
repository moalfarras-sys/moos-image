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
    curl --fail --location --retry 3 --connect-timeout 30 "$source_url" -o /work/plasma-login.src.rpm
    echo "$source_sha  /work/plasma-login.src.rpm" | sha256sum --check
    LC_ALL=C rpmkeys --checksig --verbose /work/plasma-login.src.rpm > /work/plasma-login-source-signature.txt
    grep -F '96bdf4e8710b8f9ffb11d83ddb51f4cb6c33bdbb: OK' /work/plasma-login-source-signature.txt
    rpm2cpio /work/plasma-login.src.rpm > /work/plasma-login-source.cpio
    (cd "$task_root/SOURCES" && cpio -idm --no-absolute-filenames --no-preserve-owner < /work/plasma-login-source.cpio)
    cp "$task_root/SOURCES/plasma-login-manager.spec" "$task_root/SPECS/plasma-login-manager.spec"
    cp "$source_root/automatic-fingerprint.patch" "$task_root/SOURCES/moos-automatic-fingerprint.patch"
    python3 - <<'PY'
from pathlib import Path
path = Path('/work/plasma-login-rpmbuild/SPECS/plasma-login-manager.spec')
text = path.read_text()
assert text.count('Release:        1%{?dist}') == 1
text = text.replace('Release:        1%{?dist}', 'Release:        1.1.moos1%{?dist}')
assert text.count('%description\n') == 1 and text.count('%build\n') == 1
text = text.replace('%description\n', 'Patch2001: moos-automatic-fingerprint.patch\n\n%description\n', 1)
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

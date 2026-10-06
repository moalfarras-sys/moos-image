#!/usr/bin/env bash
# SDK stage only: rebuild the exact vendor source, retaining its complete spec.
set -euxo pipefail
_logout_top=/work/plasma-logout-rpmbuild
_logout_mode="${1:-}"
case "$_logout_mode" in
    prepare)
mkdir -p "${_logout_top}/SOURCES" "${_logout_top}/SPECS" /out
curl --fail --location --retry 3 --connect-timeout 30 \
    https://kojipkgs.fedoraproject.org/packages/plasma-workspace/6.7.5/1.fc44/src/plasma-workspace-6.7.5-1.fc44.src.rpm \
    -o /work/plasma-workspace.src.rpm
echo '7ed5cf4427c852286f9835ebb2a6bc1482758dcde411318ad8e4a5b2517c9263  /work/plasma-workspace.src.rpm' | sha256sum --check
(cd "${_logout_top}/SOURCES"; rpm2cpio /work/plasma-workspace.src.rpm | cpio -idm --no-absolute-filenames --no-preserve-owner)
cp "${_logout_top}/SOURCES/plasma-workspace.spec" "${_logout_top}/SPECS/plasma-workspace.spec"
cp /src/logout-transaction.patch "${_logout_top}/SOURCES/moos-logout-transaction.patch"
python3 - <<'PY'
from pathlib import Path
spec = Path('/work/plasma-logout-rpmbuild/SPECS/plasma-workspace.spec')
text = spec.read_text()
assert text.count('Release:') == 1
import re
text, count = re.subn(r'^Release:.*$', 'Release: 1.1.moos1%{?dist}', text, flags=re.M)
assert count == 1
# Append after all vendor patches; the vendor's autosetup applies them together.
marker = '%description\n'
assert text.count(marker) == 1
text = text.replace(marker, 'Patch: moos-logout-transaction.patch\n\n' + marker, 1)
# Verify the prepared, vendor-patched source immediately before compilation;
# modern rpmbuild removes BUILD after successfully packaging the RPMs.
assert text.count('%build\n') == 1
text = text.replace('%build\n', '%build\n' +
    "echo '76ed150d4931b20295c53cd3100298056db4814d5b750ba9ad86659bbbf04ae8  startkde/plasma-shutdown/shutdown.cpp' | sha256sum --check\n", 1)
spec.write_text(text)
PY
dnf5 -y builddep "${_logout_top}/SPECS/plasma-workspace.spec"
test "$(rpm -q --qf '%{VERSION}-%{RELEASE}' plasma-workspace)" = 6.7.5-1.fc44
        ;;
    compile)
rpmbuild -bb --define "_topdir ${_logout_top}" --define '_buildhost moos-build' \
    --define '_smp_mflags -j4' "${_logout_top}/SPECS/plasma-workspace.spec"
        ;;
    *) echo 'usage: build.sh prepare | compile' >&2; exit 2 ;;
esac

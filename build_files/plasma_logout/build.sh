#!/usr/bin/env bash
# SDK stage only: rebuild the exact vendor source, retaining its complete spec.
set -euxo pipefail
_logout_top=/work/plasma-logout-rpmbuild
_logout_mode="${1:-}"
case "$_logout_mode" in
    prepare)
mkdir -p "${_logout_top}/SOURCES" "${_logout_top}/SPECS" /out
_logout_base="$(rpm -q --qf '%{VERSION}-%{RELEASE}' plasma-workspace)"
# The selector must finish successfully before a download or package change.
# No range, downgrade, environment override or experimental guard bypass.
python3 /src/rpms.py source "$_logout_base" > /work/plasma-logout-source.json
_logout_url="$(python3 -c 'import json; print(json.load(open("/work/plasma-logout-source.json"))["source_url"])')"
_logout_sha="$(python3 -c 'import json; print(json.load(open("/work/plasma-logout-source.json"))["source_sha256"])')"
curl --fail --location --retry 3 --connect-timeout 30 \
    "$_logout_url" \
    -o /work/plasma-workspace.src.rpm
echo "$_logout_sha  /work/plasma-workspace.src.rpm" | sha256sum --check
(cd "${_logout_top}/SOURCES"; rpm2cpio /work/plasma-workspace.src.rpm | cpio -idm --no-absolute-filenames --no-preserve-owner)
cp "${_logout_top}/SOURCES/plasma-workspace.spec" "${_logout_top}/SPECS/plasma-workspace.spec"
cp /src/logout-transaction.patch "${_logout_top}/SOURCES/moos-logout-transaction.patch"
python3 - <<'PY'
from pathlib import Path
spec = Path('/work/plasma-logout-rpmbuild/SPECS/plasma-workspace.spec')
text = spec.read_text()
import json
review = json.loads(Path('/work/plasma-logout-source.json').read_text())
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
    f"echo '{review['prepared_shutdown_sha256']}  startkde/plasma-shutdown/shutdown.cpp' | sha256sum --check\n", 1)
spec.write_text(text)
PY
dnf5 -y builddep "${_logout_top}/SPECS/plasma-workspace.spec"
test "$(rpm -q --qf '%{VERSION}-%{RELEASE}' plasma-workspace)" = "$_logout_base"
        ;;
    compile)
rpmbuild -bb --define "_topdir ${_logout_top}" --define '_buildhost moos-build' \
    --define '_smp_mflags -j4' "${_logout_top}/SPECS/plasma-workspace.spec"
        ;;
    *) echo 'usage: build.sh prepare | compile' >&2; exit 2 ;;
esac

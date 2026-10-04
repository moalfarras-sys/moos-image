#!/usr/bin/env bash
# Native SDK stage only. Preserve the complete vendor spec/patch set and flags.
set -euxo pipefail
_top=/work/plymouth-rpmbuild
mkdir -p "${_top}/SOURCES" "${_top}/SPECS" /out
curl --fail --location --retry 3 --connect-timeout 30 \
    https://kojipkgs.fedoraproject.org/packages/plymouth/24.004.60/24.fc44/src/plymouth-24.004.60-24.fc44.src.rpm \
    -o /work/plymouth.src.rpm
echo 'e45ef414519b4c9d441b086fbb6b3456df523d61890c9cc3876c069f0eaf57a4  /work/plymouth.src.rpm' | sha256sum --check
(cd "${_top}/SOURCES"; rpm2cpio /work/plymouth.src.rpm | cpio -idm --no-absolute-filenames --no-preserve-owner)
cp "${_top}/SOURCES/plymouth.spec" "${_top}/SPECS/plymouth.spec"
cp /src/frame-lifetime.patch "${_top}/SOURCES/moos-frame-lifetime.patch"
python3 - <<'PY'
from pathlib import Path
spec = Path('/work/plymouth-rpmbuild/SPECS/plymouth.spec')
text = spec.read_text()
assert text.count('Release: %autorelease') == 1
text = text.replace('Release: %autorelease', 'Release: 24.1.moos1%{?dist}', 1)
# The final vendor patch follows every original patch; %autosetup applies it.
marker = 'BuildRequires: meson'
assert text.count(marker) == 1
text = text.replace(marker, 'Patch: moos-frame-lifetime.patch\n\n' + marker, 1)
spec.write_text(text)
PY
dnf5 -y builddep "${_top}/SPECS/plymouth.spec"
# Compiler/runtime testing is in this stage, never on the workstation or final image.
python3 /src/plymouth-frame-lifetime.py --srpm /work/plymouth.src.rpm --output /work/plymouth-proof
cmp /src/frame-lifetime.patch /work/plymouth-proof/proposed-frame-lifetime.patch
rpmbuild -bb --define "_topdir ${_top}" --define '_buildhost moos-build' \
    "${_top}/SPECS/plymouth.spec"
python3 /src/plymouth_rpms.py collect "${_top}/RPMS" /out
mkdir /out/proof
cp /work/plymouth-proof/proof.json /out/proof/
python3 /src/verify_plymouth_package.py

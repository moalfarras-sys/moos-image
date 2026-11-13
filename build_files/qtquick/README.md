# Qt Quick item-view lifetime backport

P0.6/P5.8 preserves Qt's native item-view owner and fixes the reproduced
QTBUG-150769 use-after-free during ListView teardown. The exact source and
publisher signature are pinned in `sources.json`. Unknown package inputs refuse
the build; retire this backport only after a newer vendor package passes the
same native destruction fixture and the complete image/boot gates.

`itemview-lifetime.patch` retains Vladimir Belyavsky's production hunk from
[Qt commit 83d091d](https://github.com/qt/qtdeclarative/commit/83d091dcb160d3f0c4a8bc9df8b8a9a934ac82a1).
The original source headers, vendor patch/spec, configure flags, subpackages and
installed LGPL licence are preserved. The source RPM URL and digest, unmodified
source archive digest and this patch provide the rebuild inputs. Image signing
and promotion remain separate from these development RPMs.

`teardown.qml` is the byte-identical upstream
`tests/auto/quick/qquicklistview/data/destroyWithInvalidatedContexts.qml` at that
commit. Its copyright/licence annotation is retained in `teardown.qml.license`,
following Qt's root `REUSE.toml` rule for `tests/**`; the GPL-3.0 text is included
in `LICENSE.GPL3`. This fixture and the native probe are build-only and are not
installed in the finished OS. `native-proof.cpp` is MoOS's MIT-licensed QQuickView
owner for that fixture.

The native probe requires the reviewed `qt6-qtdeclarative-devel` package in both
clean build stages, separately from the vendor RPM's own BuildRequires. A reused
SDK already carrying QQuickView headers is not a clean-stage dependency proof.
No source or test command installs RPMs on the physical workstation.

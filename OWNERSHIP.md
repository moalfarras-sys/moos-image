# MoOS ownership, licensing and official identity

MoOS is maintained and released by Mohammad Alfarras (`moalfarras-sys`).
The official project is [moos-image](https://github.com/moalfarras-sys/moos-image)
and its public site is [moalfarras.space](https://moalfarras.space/ar/moos).
The 2026-10-08 collaborator readback lists only that account with write/admin
permission. CODEOWNERS identifies maintenance responsibility; it cannot prevent
copying source.

## Software rights

This repository has mixed licensing. Existing copyright, SPDX notices,
component licences and third-party licences remain authoritative. KDE/Linux
components and derivatives retain their free-software rights; Remote retains
its existing personal-use terms in `moremote/LICENSE`. This document neither
relicenses those works nor assigns their ownership to MoOS.

No repository-wide MIT/GPL grant should be inferred for original files without
one. Public GitHub repositories permit viewing/forking under platform terms;
publication alone does not permit removing required attribution or claiming
another author's work. A complete rights inventory remains required before a
new general licence is applied. Previously distributed licence grants cannot
be withdrawn retroactively.

The installer's Arabic/English timezone labels are derived from Unicode CLDR
through Babel 2.18.0, against tzdata 2026e. The original Babel and Unicode v3
notices ship in `/usr/share/doc/moos/installer-timezones/`; they govern that
derived data, not the rest of this repository. Refresh with
`artwork/generate_installer_timezones.py --output system_files/usr/share/moos/installer-timezones.json`
in a disposable SDK containing those reviewed versions, then run the native
timezone gate. Babel is not a runtime dependency. CLDR historical-ID exemplar
cities are resolved through the tzdata alias family. Coyhaique currently keeps
its proper-name fallback with an Arabic country label; do not invent a CLDR
translation. The image gate rejects new selectable zones without labels.
Primary data API: [Babel timezone location](https://babel.pocoo.org/en/latest/api/dates.html#babel.dates.get_timezone_location).

## Name and endorsement

The MoOS name, original logo and official-release presentation identify the
maintainer's product. Independent or modified builds must not be presented as
official releases or as endorsed by the maintainer. Preserve all attribution
required by software/artwork licences. This policy does not prohibit truthful
references, override licence rights or claim registered/worldwide exclusivity.

## Authentic releases

Official images are signed with the key represented by `cosign.pub`; installed
MoOS enforces its trusted key. A source clone, passing build or fork signature
does not prove an official release. Follow `RELEASE.md` and verify the exact
image/ISO and signature from the official site. This distinguishes delivery;
it cannot technically stop independent development or a fork with its own key.

Signing/provider/upload credentials stay private. No author-only login, remote
kill switch or copy-protection backdoor is added. Protection must preserve the
computer owner's control and upstream authors' rights.

Primary references, read 2026-10-08:
[GitHub licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository),
[KDE software freedoms](https://kde.org/community/whatiskde/).

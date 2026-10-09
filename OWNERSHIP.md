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

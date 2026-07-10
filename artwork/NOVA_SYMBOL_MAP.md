# Nova symbolic UI map

These original SVGs replace platform-dependent emoji in MoOS system apps. They
ship under `/usr/share/icons/hicolor/scalable/actions/` and resolve by icon name
through the Nova icon-theme fallback chain.

## NEEDS-CLAUDE-WIRING

Do not keep the emoji beside the icon. Replace each emoji prefix with a
`Kirigami.Icon` (or the equivalent verified Qt icon item) using this map:

| Claude-owned surface | Current glyph | Nova icon name |
|---|---:|---|
| Welcome — Full identity | `✦` | `moos-identity` |
| Welcome / Compatibility — Mo AI | `🧠` | `moos-ai` |
| Welcome / Compatibility — Gaming | `🎮` | `moos-gaming` |
| Welcome / Compatibility — Android apps | `🤖` | `moos-android-apps` |
| Welcome — Safe updates | `🛡️` | `moos-safe-update` |
| Welcome — Nova UI | `🎨` | `moos-nova-ui` |
| Hardware — CPU | `🧠` | `moos-cpu` |
| Hardware — Memory | `🧮` | `moos-memory` |
| Hardware — GPU | `🎨` | `moos-gpu` |
| Hardware — Disks | `💾` | `moos-storage` |
| Hardware — Network | `🌐` | `moos-network` |
| Hardware — System | `🖥` | `moos-system` |
| Copy buttons | `📋` | `moos-copy` |
| Hardware — Full report | `📄` | `moos-report` |
| Warning callouts | `⚠` | `moos-warning` |
| Compatibility — iPhone Companion | `📱` | `moos-phone` |

Use a logical 24 px icon beside button labels and 30–36 px inside feature/card
headers. Preserve the Arabic/English text after removing only the leading
emoji. Welcome currently imports plain QtQuick only, so Claude must add the
verified icon component/import rather than hardcoding absolute file paths.

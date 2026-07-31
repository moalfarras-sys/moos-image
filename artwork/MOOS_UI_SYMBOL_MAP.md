# MoOS Tidal Cut symbolic icon map

`Tidal Cut` is MoOS's owned action-icon language. Its single geometry source is
[`generate_moos_symbolic_icons.py`](generate_moos_symbolic_icons.py), which
generates all 93 SVGs and
[`moos_symbolic_manifest.js`](moos_symbolic_manifest.js). The visual harness
imports that manifest; it does not carry a second hand-maintained name list.
Application launch icons and the MoOS / Mo AI identity marks remain separate
full-colour assets. These symbols are interface actions, states, and categories.

## Measured rendering contract

- Grid: 24 × 24 units; painted geometry stays within 2.25…21.75 so the outer
  pixel remains empty at 16, 20, 24, 64, and 128 px.
- Structural weight: 2.0–2.25 units for primary ribbons and terminals
  (1.33–1.50 physical px at the 16 px target). Rounded capsules prevent brittle
  diagonal ends and make small icons read at a glance.
- Construction: filled `<path>` elements only. There are no SVG strokes,
  `fill="none"`, filters, gradients, raster images, or background plates.
- `ColorScheme-Text` follows the live foreground in KDE.
  `ColorScheme-Highlight` follows the live accent in KDE and degrades to the
  foreground channel under GTK's symbolic-mask renderer. Accent details are
  never required to understand the silhouette.
- Warning uses both KDE's `ColorScheme-NeutralText` and GTK's `warning`
  channel. Critical danger uses `ColorScheme-NegativeText` / GTK `error`, and
  has a deliberately different octagonal silhouette rather than relying on
  colour alone.
- Review targets: 16 and 20 px for compact chrome, 24 px for controls, 64 and
  128 px for feature surfaces. Glyph size never substitutes for a minimum
  40-logical-pixel hit target.

## Why the family is different

The family uses a solid silhouette plus one deliberate open counter — the
“cut” — instead of generic monoline outlines. Its rounded tidal ribbons carry
enough ink at 16 px, while offset highlight facets add depth in KDE without
turning the glyph into a multicolour illustration. Semantics remain legible in
one colour and in high-contrast GTK masking.

## Inventory

| Name (without `moos-` / `-symbolic`) | Meaning | Category |
|---|---|---|
| `ai` | Mo AI | assistant |
| `android-apps` | Android apps | platform |
| `arrow` | Next | navigation |
| `arrow-back` | Back | navigation |
| `audio` | Audio | media |
| `bluetooth` | Bluetooth | connectivity |
| `bolt` | Power | status |
| `boxes` | Packages | software |
| `briefcase` | Work | places |
| `bulb` | Idea | status |
| `camera` | Camera | media |
| `car` | Vehicle | devices |
| `chat` | Chat | communication |
| `check` | Complete | status |
| `close` | Close | navigation |
| `code` | Code | development |
| `compass` | Explore | navigation |
| `container` | Container | software |
| `copy` | Copy | editing |
| `cpu` | Processor | hardware |
| `cube` | Cube | objects |
| `danger` | Critical warning | status |
| `database` | Database | data |
| `diamond` | Diamond | objects |
| `document` | Document | files |
| `external` | Open externally | navigation |
| `flask` | Laboratory | development |
| `gaming` | Gaming | media |
| `gem` | Gem | objects |
| `globe` | Web | connectivity |
| `gpu` | Graphics | hardware |
| `grid` | Grid | layout |
| `home` | Home | places |
| `identity` | MoOS identity | identity |
| `install` | Install | software |
| `joystick` | Joystick | devices |
| `keyboard` | Keyboard | devices |
| `lock` | Lock | security |
| `mail` | Mail | communication |
| `memory` | Memory | hardware |
| `microphone` | Microphone | media |
| `moon` | Dark appearance | appearance |
| `mouse` | Mouse | devices |
| `music` | Music | media |
| `network` | Network | connectivity |
| `optimize` | Optimise | system |
| `orbit` | Orbit | science |
| `pen` | Create | editing |
| `phone` | Phone | devices |
| `power` | Power | system |
| `refresh` | Refresh | navigation |
| `repair` | Repair | system |
| `report` | Report | files |
| `safe-update` | Safe update | security |
| `search` | Search | navigation |
| `settings` | Settings | system |
| `shield` | Shield | security |
| `spark` | Spark | status |
| `star` | Favourite | status |
| `storage` | Storage | hardware |
| `sun` | Light appearance | appearance |
| `system` | System | system |
| `target` | Target | navigation |
| `trash` | Remove | editing |
| `ui` | MoOS UI | identity |
| `usb` | USB | devices |
| `video` | Video | media |
| `warning` | Warning | status |
| `wave` | Audio wave | media |
| `notification` | Notifications | system |
| `download` | Download | actions |
| `upload` | Upload | actions |
| `folder` | Folder | files |
| `terminal` | Terminal | development |
| `clock` | Clock | time |
| `calendar` | Calendar | time |
| `battery` | Battery | hardware |
| `wifi` | WiFi | connectivity |
| `menu` | Menu | navigation |
| `about` | About | status |
| `user` | User | system |
| `heart` | Favourite | status |
| `play` | Play | media |
| `pause` | Pause | media |
| `volume` | Volume | media |
| `volume-off` | Volume off | media |
| `image` | Image | media |
| `pin` | Pin | navigation |
| `cast` | Cast | connectivity |
| `help` | Help | status |
| `pulse` | Activity | status |
| `login` | Login | navigation |
| `logout` | Logout | navigation |

## Verification

```bash
python3 artwork/generate_moos_symbolic_icons.py --check
python3 tests/test_moos_symbolic_icons.py
python3 tests/test_moos_symbolic_runtime.py
```

The static gate proves source determinism and the path-only/role contract. The
runtime gate asks GTK's real `IconTheme` and KDE's `kiconfinder6` to resolve the
assets, then rasterises both light and dark symbolic palettes at all five
review sizes. It rejects empty or clipped output, missing internal counters,
and indistinguishable alpha silhouettes.

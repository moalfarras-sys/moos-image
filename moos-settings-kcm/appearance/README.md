# Native session appearance

This module extends the existing KDE login owners. It is not another greeter,
authentication implementation, account chooser or background service.

`moos-theme` reconciles the actual Plasma wallpaper into the native lock-screen
setting and an inert owner-only selection file, in the existing snapshot and
rollback transaction. The existing launcher activates one event-driven native
observer inside plasmashell. It reads only native desktop image/plugin keys,
rearms atomic config replacements and coalesces bursts. Unrelated widget moves
and equivalent file URIs produce no event. Only a changed image selection writes
an inert hash to `moos-wallpaper-intent.conf`; the existing path/service pair
consumes it. The containment file itself is never a systemd path trigger. No new
daemon, idle poll, executor or second wallpaper authority is added. Unknown,
symlinked or multiply linked event destinations remain untouched.
`moos-session-appearance publish` exports that user's
own selection through AccountsService's vendor-extension property. The existing
AccountsService own-account UID check applies; administrative changes retain its
ordinary policy. No new privileged executor or authentication action is added.

The public record contains schema1, one of the18 immutable catalogue look IDs,
bounded native colour roles, an optional serialized font (4–96pt or4–192px) and a metadata-free
JPEG thumbnail (at most1920×1080 and786432 decoded bytes). It contains no home
path, URI, command or QML. Choosing a login wallpaper intentionally makes this
thumbnail available to the greeter. Original full-resolution files stay put.

Only the actual `plasmalogin` service UID activates the reader. The existing
native `UserList.selectedUser` is observed without changing selection or login
handlers. One process reads the selected user's public record; the separately
owned wallpaper process reads/subscribes to its finite snapshot on the greeter
session bus. Account changes and stale asynchronous replies are generation
checked. Images use a mutex-protected immutable current/previous frame store,
independent of the GUI object's lifetime and Qt's asynchronous loading thread.

The real `PlasmaQuick::globalEngine()` uses KirigamiPlasmaStyle, whose palette
owner is `Plasma::Theme`. Updating only QGuiApplication leaves its existing
colours stale. The module reuses that shared Plasma owner with private data-only
skins, falling back to the selected immutable style's SVGs. Temporary palette
files have content identities; skin names are bounded by the18 styles.
KConfig's additional source and public `setUseGlobalSettings()` reload retain
administrator/main-source precedence. They never persist a temporary theme
name. The native Qt and KDE icon loaders are both reconfigured. Invalid metadata
restores original palette/font/icons/Plasma settings and original data paths.
No persistent greeter config is rewritten during account or theme switching.

The canonical CMake contract starts two native consumers using the real greeter
engine and a complete matched initial style. It tests two themes, a second
personal palette within the same style, actual asynchronous image pixels,
Window/Complementary/selection colours, native glyphs, invalid-data restoration,
unchanged service settings, immutable administrator-style refusal and AccountsService restart persistence. The final
image gate requires that receipt and the exact tested daemon/module hashes,
then imports the actual installed module through the shared source bridge.
An unavailable older signed-host publisher is a development compatibility case;
the new immutable image must contain and qualify all these pieces.

Private live review copies are listed in the task's compatibility manifests.
Retire them only after matching signed installed payloads and cold physical
acceptance; they are not immutable OS delivery. Never install a global user-local
Breeze module or replace the authentication/backend owners for review.

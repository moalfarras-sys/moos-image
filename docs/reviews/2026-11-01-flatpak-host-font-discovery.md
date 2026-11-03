# Flatpak host-font discovery — source qualification, 2026-11-01

Scope: P2.3/P2.5 cross-application typography and P4.1/P4.5 lifecycle evidence.
The integration owner remains the root session. This topic is based on frozen
`fc97ef3bca6e7dba14d99ebcdfa0001ff7787adb`; it is separate from that signed release.

## Reproduced problem and existing owners

On physical V3 signed1114, OpenCode2.1.3 uses freedesktop26.08 Fontconfig2.18.3.
Its native remap of `/run/host/fonts` to `/usr/share/fonts` selects the runtime's
root cache, omitting every host face. The five immutable Meyar files themselves
match the source. Snapshot51's same Fontconfig version instead selects an older
host-user cache with855 host faces but no Meyar. KRecorder/KDE6.11 already sees
Meyar. These contrary controls remain; this is not a universal Flatpak failure.

One shared `moos_flatpak_fonts.py` policy extends existing `moos-fonts-migrate`
at login, Mo Store's libflatpak install/update completion, and the existing
per-user Flatpak updater. It writes only an owned normal per-app Fontconfig
`conf.d/00-moos-host-font-cache.conf` remap with the image's exact two named mono
scan rules and qualified named Arabic append-last aliases. No environment wrapper, new daemon,
filesystem grant, font copy, generic-default replacement or cache deletion is
introduced. Native Fontconfig owns its ordinary configuration reload. No app
is stopped or reloaded by the policy.

The salt hashes the policy revision, exact scan/pairing bytes, exact **booted signed** MoOS deployment checksum and sorted
unique `(full runtime ref, actual globally selected runtime commit)` tuples for
every installed branch of that app. One app home serves user/system and all
branches. Native unscoped `flatpak info --show-commit runtime/FULL_REF` follows
the same user-first/global runtime lookup as normal Flatpak1.18.4 launch.
Earlier designs assuming app scope determines runtime scope, or guessing the
active branch from a bare app name, were rejected before qualification.
Custom installations are explicitly refused in this initial scope.

An installed app is prepared before its first Store launch. Only native
installed app IDs are visited. A CLI install/update outside Mo Store is picked
up by the next login, scheduled user update, or explicit `moos-fonts-migrate`;
immediate reconciliation on every external Flatpak operation is not claimed.
Running apps may retain toolkit font objects until their ordinary restart.

The fragment contains its canonical generation inputs in a bounded XML comment;
ownership validation recomputes its exact full bytes. The independent review's
salt-only edit was initially admitted by a template check and is now a retained
refusal, alongside outer-content edits. No separate partial receipt is needed.
Only exact historical prototype1 and current policy2 bodies are admitted.
Future policy changes must explicitly review historical-body migration;
changing the rule digest alone safely refuses an earlier policy2 body.
Each path is opened relative to an owned directory with no link following;
unknown edits, non-owned/writable ancestors, hardlinked files, mounts (including
same-filesystem binds), busy/unknown locks and refused recovery remain failures.
Every replaced owned generation has a unique durable private recovery. Personal
`fonts.conf`, other fragments, explicit names and matching rules remain intact.
Store/updater failures stay visible even when package updates have completed.

## Executed native controls

`tests/native_flatpak_font_delivery.py ai.opencode.opencode` runs native CLI
queries after sandbox entry with private XDG config/cache. It requires the
measured2.18.3/freedesktop26.08 input; it is not a generic test of healthy KDE or
GNOME runtimes. Captures and full native command receipts remain private.

The original empty-user control fails all four named Meyar requests. The exact
source-generated fragment restores Meyar Sans, Arabic, Mono and Mono Arabic
cold and warm through `/run/host/fonts/meyar`. CJK eligible faces change0→148;
explicit DejaVu and generic sans/mono requests remain unchanged. This proves
discovery, not complete language shaping or a generic Meyar default.
The earlier709-byte be3 prototype passes this discovery proof and the full source
gate0/937.491s with14735 stable inputs, but **is refused for integration**:
salted native rescans lose the image's mono scan metadata, changing healthy
KDE6.11/Chrome25.08 spacing100→90. The actual native Qt fixed-font chooser then
omits both families. A same-cache rule-added-without-rekey control stays90.
Policy2 carries only the existing two exact named scan rules and hashes their
bytes/revision into a fresh generation. Actual2.17.1 and2.18.3 cold/warm
be3→successor upgrades retain all12 enumerated mono instances per runtime and
restore spacing100, including Regular/Bold, without removing any cache.
Independent native Qt chooser controls pass be3 false→scan-successor true.
The final combined source also passes that native KDE6.11 chooser cold/warm
with the retained cache; the first hardcoded fragment-size guard refusal stays
preserved, replaced by canonical ownership/current-source byte validation.

The combined1415-byte policy2 also passes discovery, scan and named-pairing
native proofs. Its two aliases use strong/default append-last only for Meyar
Sans→Arabic and Mono→Mono Arabic. Forty-nine queries per runtime, across all four
installed runtimes, preserve primary Latin/IPA/Vietnamese/Greek/Cyrillic and
foreign-script fallback, explicit DejaVu in both orders, Inter and generic
requests. Arabic letters/marks, Farsi/Urdu and bold select the paired Meyar
family. Personal native fonts.conf assign_replace still wins and survives
refresh. Matching is not rendered language acceptance. Pairing test profiles
retain that deliberate personal negative; use the separate clean discovery/scan
profiles for subsequent GUI acceptance.
An isolated four-app refresh measured0.199s cold and0.104/0.106s unchanged, seven
bounded native metadata queries per refresh on the
active V3; this is not application launch performance or a whole-system speedup.

The native zero-mtime private tree retains a plausible old cache after adding
a font under the same salt. A new generation discovers it. Restoring tree A and
generation A restores the earlier exact inventory. A separate predecessor
control keeps generation B while restoring tree A: the stale B cache still
advertises the now-missing face. That failure is preserved separately from the
helper-aware A→B→A pass.

Root also exercised the **real installed OpenCode Appearance UI** in verified
private XDG config/cache/data. With the same native `Meyar Arabic` setting,
before the fragment its caption paints DejaVu Sans17 glyphs plus Inter2;
after an ordinary private-app restart, retained cache and the earlier332-byte
semantically equivalent prototype fragment, it paints Meyar Arabic24 glyphs.
That prototype and the later709-byte discovery prototype are historical Arabic
painting evidence; neither qualifies combined1415-byte policy2. Final policy2
GUI requalification remains separate.
No CSS injection or canonical owner
app setting change occurred. The first `flatpak --env` GUI attempt was not
isolated because the app wrapper reset XDG/userData; it remains a refused
control. Later isolation uses environment assignment **after sandbox entry**.
Mixed-text/editor and full lifecycle acceptance remain separate.

## Rollback and remaining acceptance

Helper-aware generation rollback passes. An older signed predecessor without
this helper cannot update a persisted new salt. Automatic GRUB rollback across
that boundary is **not qualified**. The existing font owner provides explicit
`moos-fonts-migrate --retire-flatpak-discovery`: before such a rollback it can
recover the exact owned fragments uniquely and retire only those fragments,
keeping personal configuration and every cache. Unknown edits refuse. This is
an explicit preparation/recovery command, not a new automatic boot authority or
proof that a real predecessor reboot has passed.

The13 maintained controls cover signed boot selection, malformed/nested metadata,
first launch, duplicate app/runtime scopes and branches, runtime changes,
order/dedup stability, new/unchanged/rollback recovery, absent apps, custom
installation refusal, links/hardlinks/UID/modes/locks, injected mount-set
refusals, exact retirement,
cache retention and visible Store/update failure. Existing36 Store,29 pinned
update and8 Meyar controls plus updater recovery pass at this source checkpoint.
An additional actual same-filesystem bind in a private user/mount namespace is
refused through mountinfo while Python ismount=false; original bytes remain.
Nested zero-mtime Meyar child-directory transitions also pass privately.
These receipts supplement, rather than replace, the maintained native scripts.
Final repository qualification, signed delivery, real native lifecycle/update,
predecessor rollback, other architectures and broader rendered-language
acceptance remain required. Generic Meyar defaults inside Flatpak remain a
separate typography scope. No whole-language or whole-OS acceptance is inferred.

Primary contracts: [Fontconfig native configuration](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-user.html),
[Flatpak font integration](https://docs.flatpak.org/en/latest/desktop-integration.html#fonts),
[Flatpak1.18.4 runtime lookup](https://github.com/flatpak/flatpak/blob/1.18.4/common/flatpak-run.c),
[deployment search](https://github.com/flatpak/flatpak/blob/1.18.4/common/flatpak-dir-utils.c),
and [native info selection](https://github.com/flatpak/flatpak/blob/1.18.4/app/flatpak-builtins-info.c).

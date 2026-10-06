# Oracle cloud workstation — measured owner setup

This is a private deployment profile on the Oracle A1, not a shipped-image claim
or a second product backlog. Open work belongs to DEVELOPMENT_PLAN P5.5/P5.7.

| Capability | Installed implementation | Owner access |
| --- | --- | --- |
| Desktop | signed MoOS ARM .710, 1280×720 virtual seat | existing Mo PC Remote, HTTPS 443 |
| General files | FileBrowser Quantum 1.5.8, private `~/CloudFiles` | HTTPS 8443 / authenticated WebDAV |
| iPhone Files | rootless Samba 4.23.8, same CloudFiles | SMB3 through tailnet TCP Serve 445 |
| Development | code-server 4.140.0, existing Projects/repositories | HTTPS 8444, password auth |
| Photos/video | Immich 3.2.4, stable exact-release rootless Compose | HTTPS 8445, separate local account |
| Resources | `System-Status.json` every five minutes | authenticated file portal; native System Monitor |
| Backup tooling | restic 0.19.1, rclone 1.75.1 | private user commands, verified ARM64 binaries |

Use `https://<Oracle tailnet hostname>:<port>`, with Tailscale active on the
phone. The general file portal also links to Photos, Development and Remote.
No public Funnel or public database/Redis port was enabled. Private handoff
credentials live in `~/MoOS-Cloud-Access.txt` (0600); never add them to Git.

## Persistent data and lifecycle

`~/.config/moos-photos/compose.yaml` and its private `.env` describe three
rootless Podman containers. Images are pinned by digest to the publisher's
3.2.4 release, including its selected vector-enabled PostgreSQL and Valkey.
`moos-photos.service` starts the stack at sign-in. It owns only new directories
under `~/.local/share/moos-photos/{library,postgres,redis}`. Podman's `:Z,U`
options label/map these dedicated paths to container UID 1000; never apply
`:U` recursively to the owner's general home or existing unrelated data.

The application listens only on loopback 2283, with tailnet HTTPS as the
transport. Postgres and Valkey have no host-published ports. Password signup was
completed locally before publication. The owner account starts with a 60 GiB
quota for original assets; allowance for previews, video derivatives, updates
and development remains outside it. Originals are retained. ML is disabled and
its container is absent; all job queues use concurrency 1, FFmpeg one thread,
and required 720p previews. Limits bound the new service, not the whole desktop.

The app's configuration remains editable through authenticated Administration.
Use a matching mobile release. On iPhone, select backup albums and enable
Background App Refresh; iOS decides when background work runs. Host-side tests
cannot authorize the phone's Photos access or prove its background scheduling.

## Verified flows and practical limits

On signed .710: maintained next-boot selfcheck 51 passed and post-update 55/0;
zero failed units/kernel errors. Generated JPEG and MP4: authenticated upload,
SHA-256-identical original download, generated thumbnail HTTP 200; anonymous
original HTTP 401. A real browser loaded the Arabic phone-size onboarding.
Originals survived stack recreation with the same hashes and processed video playback returned 200. This is server evidence, not owner-device backup/endurance evidence.

The packaged Tailscale daemon path was restored in the existing custom system
unit after backing it up under `/etc/moos/local-backups/20261006/`. The same
node remained logged in, and the four private Serve routes were verified.
The old standalone daemon must not shadow later signed system updates again.

`moos-cloud-backup.timer` runs a private encrypted restic snapshot at 03:15
(with jitter). It first creates a consistent `pg_dump`, then backs up database
and service/account configuration. Retention is 7 daily / 4 weekly / 3 monthly;
under 20 GiB free it refuses work. `restic check` and restore passed with the
same dump hash. This is local configuration recovery on the same disk: it
neither replicates original photos nor survives loss of the Oracle volume.
An external destination requires the owner's selection and its credentials.

`systemd-oomd` still monitors no cgroup on this ARM host (P5.7). Memory pressure
was zero while this batch ran; caps on new services do not qualify a global OOM
policy. Cloud graphics still use software rendering, so bandwidth/frame and
phone acceptance are separate from an HTTP response or an active process.

Sources: [Immich installation](https://docs.immich.app/install/docker-compose/),
[requirements](https://docs.immich.app/install/requirements/),
[mobile backup](https://docs.immich.app/features/mobile-backup/),
[backup/restore](https://docs.immich.app/administration/backup-and-restore/).

## Native iPhone Files connection

The owner-requested native Files route uses `smb://<Oracle tailnet IP>`.
Activate Tailscale on the iPhone, then Files → Browse → … → Connect to Server →
Registered User. Use the private SMB username/password section in the owner
handoff, not the gallery's email login; choose `CloudFiles` and add it to Favorites.
It is the same folder as the web file portal, so documents/photos/videos saved
there remain visible from both interfaces. Immich still handles automatic album
uploads; a network Files share alone does not implement camera-roll backup.

A rootless ARM64 `ghcr.io/servercontainers/samba` image is pinned at
`sha256:31b90ea7fe3258d30fccd971c85743b92694605f4b43dc8a4df23a202fced06a`.
Backend 127.0.0.1:1445 reaches only the dedicated CloudFiles mount; Tailscale TCP
Serve exposes 445 on tailnet addresses. No public port, privileged-port sysctl or
SELinux exception is needed. Registered-user-only access, SMB3 minimum, mandatory
signing and disabled symlink/wide-link traversal are read back from Samba.
Container UID 0 maps to the ordinary host owner in rootless Podman; file ownership
is preserved. The new user service is enabled with 192 MiB/.5-core bounds.

Wire proof to the tailnet endpoint: authenticated mkdir/put/get/rename/delete/
rmdir succeeded and bytes matched; anonymous access failed; an owned symlink to
outside the share failed with NT_STATUS_STOPPED_ON_SYMLINK. Only test artifacts
were removed. An unsupported systemd socket-proxy trial was archived/uninstalled
before using native Tailscale forwarding; host confinement was retained. Actual
iPhone navigation is still owner-device acceptance.

References: [Apple Files server connection](https://support.apple.com/en-au/guide/iphone/iphe9aff429a/ios),
[Tailscale file-server access](https://tailscale.com/docs/use-cases/personal-or-at-home-use/access-nas-media-file-servers),
[Samba image](https://github.com/ServerContainers/samba).

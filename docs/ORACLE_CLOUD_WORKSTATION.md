# Oracle cloud workstation — measured owner setup

This is a private deployment profile on the Oracle A1, not a shipped-image claim
or a second product backlog. Open work belongs to DEVELOPMENT_PLAN P5.5/P5.7.

| Capability | Installed implementation | Owner access |
| --- | --- | --- |
| Desktop | signed MoOS ARM .710, 1280×720 virtual seat | existing Mo PC Remote, HTTPS 443 |
| General files | FileBrowser Quantum 1.5.8, private `~/CloudFiles` | HTTPS 8443 / authenticated WebDAV |
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

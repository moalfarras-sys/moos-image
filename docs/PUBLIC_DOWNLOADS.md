# Public MoOS ISO delivery

The release contract in `RELEASE.md` proves the OS. This procedure proves that
the public receives the same bytes. It never substitutes for boot, offline
installation, installed-system login/reboot/poweroff, or production promotion.
Delivery is tracked as P0.12 in `DEVELOPMENT_PLAN.md`; the October 11 receipt
qualifies public release .1026. Future releases must repeat this procedure.

## Preserve the qualified artifact

After the exact candidate passes promotion, download **`moos-live-iso`** from its
successful, first-attempt ISO run. Keep the `.iso`, `.iso.sig`, `.iso.sha256`,
source revision and build/disk/ISO/promotion run IDs together. Never use
`moos-live-iso-unproven-debug`, or distribute the credential-less x86 CI QCOW2.

```sh
gh run download ISO_RUN --repo moalfarras-sys/moos-image \
  --name moos-live-iso --dir /absolute/path/to/preserved-release
```

CI artifact retention is seven days. Archive the final files outside the source
tree before expiry; keep them out of Git. GitHub Releases allows only 2 GiB per
asset, while the measured October 4 ISO artifact is about 5.8 GB. A normal,
single-file ISO download therefore needs a large-file host. Do not manufacture
a URL, split the consumer download into obscure pieces, or enable the button
because the artifact exists in Actions.

`gh run download` first buffers the complete artifact ZIP in `TMPDIR`, then
extracts it. On the development hosts the default `/tmp` is memory-backed.
Use a private, task-owned temporary directory on the real writable disk
(`/var/tmp` on these hosts), budget space for both ZIP and extracted ISO, and
bound the download unit's memory. Check the native filesystem, not the IDE
sandbox's `/var`. The CLI removes its ZIP after successful extraction; retire
only the resulting empty owned scratch directory. The October 11 download
measured this trap, moved to disk and preserved the exact .1026 signed bytes.

If no suitable existing host is available, Cloudflare R2 **Standard** is a
practical default: its monthly allowance includes 10 GB-month of storage and
egress is free; extra storage/operations remain billable
([current pricing](https://developers.cloudflare.com/r2/pricing/)). Use a dedicated release bucket, not a private backup bucket. Either expose it
through a custom domain ([public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)),
or keep it private and stream only explicit release files through a persistent
named Worker ([R2 bindings](https://developers.cloudflare.com/r2/api/workers/workers-api-usage/)),
with a stable download entry on the existing website. Do not use expiring
previews or the development-only `r2.dev` endpoint. The October 8 delivery
uses the latter private-bucket path without changing the site/mail DNS.
Upload a multi-GB ISO through the S3 multipart API, for example with `rclone`;
the consumer still downloads **one file**. Single PUT uploads are limited to
5 GiB ([upload limits](https://developers.cloudflare.com/r2/objects/upload-objects/)).
Account activation and upload credentials belong to the website/hosting owner;
this procedure does not activate billing or change DNS.

## Qualify the public endpoint

Upload the preserved files to the chosen host. Keep the independent website worker
responsible for its reviewed static publication; send it delivery evidence rather than editing
the website from an OS branch. Run this on the host with Python 3 and OpenSSL available:

```sh
python3 scripts/verify-public-iso.py \
  --iso /absolute/path/to/moos.iso \
  --signature /absolute/path/to/moos.iso.sig \
  --url https://downloads.example.org/moos.iso \
  --output /absolute/path/to/public-download-proof.json
```

The command checks the CI's detached ECDSA/SHA-256 signature with the
repository's **public** key before
network access. It requests no credentials or cookies, requires HTTPS even
through redirects, verifies ranges at both ends (including a nonzero resume
offset), and streams the entire HTTP 200 download to verify its exact length
and SHA-256. It pipes the local bytes through OpenSSL while hashing those same
bytes, so neither signature verification nor download loads the ISO into RAM.
It does not save another ISO copy. A 200
error page, truncated/changed file, wrong range, transformed body, or signature
failure stops the check. The JSON is written atomically after success only.
Check the command's exit status and `checkedAt`; an old report is not evidence
for a failed new check. Use a stable initial URL, not an expiring signed URL.

## Website handoff

Provide the website worker with the qualified ISO URL, `.sig` and `.sha256`
URLs, byte size, SHA-256, release date, source revision and exact proof run IDs.
The website must show availability only after this delivery check and the
matching promotion succeed. Recheck delivery after moving/replacing the file.
If hosting credentials are absent, preserve the release and leave availability
false; record hosting as the remaining dependency.

The default live ISO is an **x86-64** artifact. NVIDIA and cloud are separately
qualified signed editions; an ARM QCOW2/UTM bundle is a separate artifact, not
this ISO. Name architecture, target and proof honestly. An installer shell script
must be labelled a script, never presented as an ISO.

The download page should describe current product behavior: Arabic/English
system switching; cloud Mo AI requiring the owner's provider configuration;
Linux apps plus tested, limited Windows/Android compatibility. German keyboard
support is not a German system translation. Installing Wine or an Android
runtime is not proof that all Windows/Android apps work. P4.3–P4.5 owns the
remaining managed Windows app journey and compatibility matrix.

Sources: [GitHub release asset limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases),
the [cosign SHA-256 and legacy blob verifier](https://github.com/sigstore/cosign/blob/v3.1.3/cmd/cosign/cli/verify/verify_blob.go),
the workflow's `retention-days` in `.github/workflows/build-iso.yml`, and measured
delivery results in `test-results/readiness-20261005/` (local, ignored).

## Current public release

Exact .1026 ISO run 38133979283 and promotion 38136731168 passed. Anonymous
full transfer, detached signature, size/SHA-256 and resumed ranges pass in
[the public receipt](releases/2026-10-11-public-download-proof.json); both
verification sidecars match. Current download:
https://moos-downloads.moalfarras-moos.workers.dev/releases/44.20261011.1026/x86_64/moos-offline.iso .
The paired manifest/proof and AR/EN page are independently published at
https://moos-site.moalfarras-moos.workers.dev/ar/ . Eight public browser views
and actual Worker/installer responses pass. Website PR56 holds this publication;
its handoff records the exact Worker versions without mixing OS and site source.
PR56 is merged at `11cb5052`; web/admin/dashboard source CI all pass. Existing
Vercel previews retain the separate account-block error. Frontend version:
`7fc92c0a-3f66-4114-8a74-dda39cf1681f`; download Worker:
`72141578-1b4c-4a48-8e2c-e3e70295bb05`.
Fourteen fresh public entrypoint/paired metadata/exact installer/query/resumed-range
checks pass at 21:56:52 UTC, including the >4 GiB resume and an unrelated
MoPlayer page remaining on its original host. Initial redirects still count as
small Vercel CDN requests; subsequent MoOS assets/downloads execute on Cloudflare.

Superseded .1011 keys are deleted and return explicit 410. .1018 preserved its
original immutable bytes through 2026-10-11 15:00 UTC; guarded retirement
deleted only its three keys at 15:05:09 UTC (5,808,128,179 bytes). Never redirect an old immutable ISO
URL to new bytes or expire the only qualified publication. Installed signed
rollback is separate and retained. The completed Oracle upload scratch is
retired. The exact .1026 three-file archive is preserved on Oracle. Old local
.989 ISO/signature/checksum are retired only after full hash, source ancestry
and no-holder checks; its small historical verification/key remain.

.1022's immutable original bytes remain until 2026-10-12 12:00 UTC (14:00 Berlin).
Oracle's persistent `moos-owner-retire-1022.timer` runs at 12:05 UTC and refuses
early execution, a different current publication, a failed .1026 qualification,
unexpected old objects or missing immutable 410 responses. Five read-only
negative controls pass; actual .1022 deletion has not occurred.

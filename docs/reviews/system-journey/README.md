# Evidence for the MoOS installation-to-desktop journey

Execution contract: [owner milestones](../../OWNER_EXECUTION_20261009_AR.md).
Pictures are reviewed runtime evidence, not generated mockups or shipping assets.
Keep private captures local. Publish only selected redacted frames with a manifest
as a CI/review artifact; this directory contains the small index and receipts.

Each entry identifies the source SHA, signed image digest, language, logical and
physical geometry, scale, stage and environment (installed host / final ISO VM /
source review). Missing stages stay missing until captured. Passing a screenshot
does not replace offline installation, installed reboot and hardware acceptance.

[2026-10-09 manifest](20261009.json): 16 unique actual frames, two duplicate PNGs
removed. CI evidence is from signed generic `.1011`, run `37558755639`, at
640×480; the private station desktop is 3840×2160 at 250%. Raw CI logs were moved
out of the picture gallery into private audit state. No owner pixels are in Git.
The manifest explicitly retains missing installer stages and failed/incomplete
visual readbacks: mixed fixture language, clipping, black early MoPlayer window,
unreadable Updater/Recovery state. App open/close/reopen is narrower evidence.
Two additional AR/EN native GTK source fixtures verify the corrected unknown
Recovery state. They record the exact dirty source-file hash, rather than
pretending the checkout HEAD already contained that change.

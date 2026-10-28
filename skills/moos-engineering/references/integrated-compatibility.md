# Integrated Arabic-first OS acceptance

Use this reference for cross-engine compatibility, tablet or whole-system
performance requests. MoOS is an operating system with native KDE/Qt/KWin and
Wayland owners; Android and Windows compatibility extend that system. Do not
replace these owners with a second shell or a parallel settings authority.

## Choose the implementation owner

Use the existing `app-engines.json` registry and read-only `moos-app-engine`
resolver, `moos-storectl` lifecycle jobs, `moos-run-foreign` / `moos-app-drop`
entry paths and `moai-do` privilege boundary. The guide maps their source paths.
A public API wraps the same owner with a versioned contract; do not implement
another package manager, generic shell executor or duplicate Settings backend.

Linux packaging, Windows runtime/prefix and Android system/vendor image are
separate compatibility inputs. Native Wine has no sandbox merely because it has
a private prefix. Record the actual isolation and permission policy. Keep app
data on ordinary remove, and verify the canonical launcher and URI route rather
than launching a review binary by hand. ARM and NVIDIA need their own evidence;
x86 translation and software graphics are explicit limitations, not silent
substitutes for a native/hardware-accelerated claim.

## Pick a measurable journey

Record the booted edition/digest, architecture, engine/package version,
application provenance, display scale, input method and the actual loaded
component. Resolve the installed bytes before relying on an earlier review:
a new vendor image may already be installed even when the plan describes an
older failure. Keep a failed journey until its replacement is actually tested.

| Surface | Evidence needed for the claim |
| --- | --- |
| Arabic and mixed scripts | Joining, marks, IPA/extended letters, cursor/backspace, selection/copy and native fallback in the actual destination; no missing-glyph IDs alone proves typography quality |
| Android | Visible app content, pointer/keyboard, resize, switch away/back, normal close/reopen and persistence; boot-completed and RUNNING are only prerequisites |
| Windows | Exact Wine/prefix/architecture, real application window, file open/save/reopen and launch lifetime; a PE inventory is not compatibility |
| Linux | Canonical launcher/URI, actual native or Flatpak owner, portal/file access and update persistence; version output is not a rendered app |
| Store and themes | Discover, preview, install, use/open, update, cancel/failure and remove through existing owners; catalogue size is not successful application coverage |
| Tablet and desktop | Actual output/scale/orientation, inner ink bounds, focus and physical input where available; pointer simulation is not touch/pen acceptance |
| Kernel and drivers | Actual loaded driver/firmware, device operation and bounded kernel logs; zero failed units does not clear driver timeouts |
| API integration | Named versioned owner, authorization, request/result/readback and failure/cancellation; do not add a competing executor |

## Carry a result through the whole product

For a chosen application, exercise discovery/file-open, consent/install, launch,
useful input and file save/reopen, window switch/resize/close/reopen, ordinary
session restart, update and data-preserving remove. Include a failed download,
refused permission or cancellation appropriate to that adapter, with actual
readback and bounded recovery. Cover mixed Arabic/Latin paths and clipboard/URI
handoff across engines. Do not silently replace a failing app with an easier
one and erase its failure. The plan owns suite membership/coverage targets.

Report evidence with these fields in the existing task/compatibility record:
plan ID and journey; source SHA; booted digest/edition; application source/version/
ABI; runtime and image versions; GPU/driver/rendering path; locale/scale/input;
steps and expected result; observed result; logs/capture references; limitation
and recovery. Private captures stay local. Use passed, failed, unavailable,
not-tested and inapplicable with a reason. A source change affecting those inputs
requires relevant requalification; preserve the earlier receipt as historical.
Publish through the existing compatibility-matrix path instead of a second
catalogue or a blanket “supported” badge.

For visual integration, compare the full connected installed journey as well as
the changed component. Check actual ink/marks, focus order, light/dark materials,
small/narrow/portrait and fractional scale, keyboard/physical touch, accessible
names and reduced motion. Preserve personal themes and the owner's feedback.
For APIs, identify schema/version and authorized caller, exercise real request,
pending/result/readback, cancellation, repeated requests and failure/restart.
Use the existing service lifecycle and fixed executor.

## Performance and release decisions

State the workload, power profile, thermal state, concurrent builds and sample
duration before comparing CPU, memory, frame timing, latency or energy. Preserve
an old baseline and repeat the same workload after a scoped change. Never tune
kernel values, disable security or swap graphics drivers to manufacture a win.
An idle sample or offscreen fixture does not establish desktop smoothness.
Choose the performance question and acceptable regression budget before editing.
Separate cold/warm launch and setup/download time; collect repeated latency
samples and frame misses at the actual refresh rate, not only average FPS. Include
mixed-engine use and bounded pressure, and retain battery/thermal/memory costs
alongside speed. A missing probe is unavailable evidence. Do not compare a quiet
baseline to a build-loaded run or report a speedup smaller than observed variance.
Read new upstream documentation/source when an engine API or driver changes;
retain exact versions, licences and provenance rather than copying a workaround
from a superficially similar bug.

Use passed, failed, unavailable and not-tested explicitly. A headless/cloud
edition need not run a desktop journey; record why it is inapplicable and test
its actual service contract. Each architecture still needs its own signed
artifact and required boot proofs. Local font/policy/library overrides remain
recorded compatibility copies until the matching signed payload is booted and
verified. Preserve rollback and exact recovery; retire only recorded matching
bytes. No universal compatibility or zero-defect claim follows from a finite
acceptance matrix.

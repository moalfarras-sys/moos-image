# Integrated Arabic-first OS acceptance

Use this reference for cross-engine compatibility, tablet or whole-system
performance requests. MoOS is an operating system with native KDE/Qt/KWin and
Wayland owners; Android and Windows compatibility extend that system. Do not
replace these owners with a second shell or a parallel settings authority.

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

## Performance and release decisions

State the workload, power profile, thermal state, concurrent builds and sample
duration before comparing CPU, memory, frame timing, latency or energy. Preserve
an old baseline and repeat the same workload after a scoped change. Never tune
kernel values, disable security or swap graphics drivers to manufacture a win.
An idle sample or offscreen fixture does not establish desktop smoothness.

Use passed, failed, unavailable and not-tested explicitly. A headless/cloud
edition need not run a desktop journey; record why it is inapplicable and test
its actual service contract. Each architecture still needs its own signed
artifact and required boot proofs. Local font/policy/library overrides remain
recorded compatibility copies until the matching signed payload is booted and
verified. Preserve rollback and exact recovery; retire only recorded matching
bytes. No universal compatibility or zero-defect claim follows from a finite
acceptance matrix.

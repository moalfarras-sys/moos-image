# Mo Store: installed experience repair — 2026-10-16

The owner reports a slow, repetitive Store, missing installed apps, Android failures and a frozen Remote picture on the actual signed `.1062` NVIDIA boot. The current slice is a usable application journey: find one product, choose its version, install/open it and manage what is already on the computer. Source fixes and review runs below are not a new signed release.

## Product decisions and primary references

[Microsoft's application manager](https://learn.microsoft.com/en-us/windows/package-manager/winget/) keeps discovery, installed inventory, upgrade and removal as explicit operations. [Apple's application installation guide](https://support.apple.com/en-asia/guide/app-store/fir0fb69db23/mac) distinguishes App Store purchases from other installation paths. [Google Play's management flow](https://support.google.com/googleplay/answer/13627402?hl=en-GB) places installed apps and removal in a management view. [Flathub's metadata contract](https://docs.flathub.org/docs/for-app-authors/metainfo-guidelines) gives application IDs, publisher metadata and catalogue descriptions separate roles.

MoOS uses these familiar jobs with its own Arabic-first shared visual system. One product appears once in browsing/search, with explicit versions on its page. Grouping uses reviewed IDs and matching canonical desktop IDs, never display names: unrelated calculators and product editions remain separate. Filtering Android or Windows still offers that version. All actual installed versions remain individually addressable; selecting a version changes only the app acted on.

`My apps` also reads effective native desktop entries, including image applications and external owner applications. XDG priority, hidden overrides, visibility, TryExec and existing managed exports are respected. An image application is updated with MoOS; arbitrary native executables and private settings are never silently deleted. An untracked external application is explicitly identified as managed at its source. Existing Store-owned kinds retain their actual update/remove/data/permission controls.

## Design-system specification

| Role | Contract |
| --- | --- |
| Palette | Existing MoOS UI Liquid Glass `canvas`, `cardColor`, `accent`, `txt`, `txt2`, semantic positive/warning/danger ink. Inherit the running palette and contrast policy; no global theme replacement. |
| Typography | Existing `uiFont`, `typePx`, Arabic shaping and font scaling; 24px entry heading, 15px app names, 13px useful detail, 12px metadata before scaling. |
| Spacing and shape | Existing space1–space6, radiusControl/Card/Panel; consistent with the native navigation and app pages. |
| Signature | A direct library heading with the real available count and prominent “تصفّح كل التطبيقات / Browse all apps”, followed by the current editorial hero. |
| Browsing | One product per grid/search result; explicit version chips on the app page; each Discover row previews at most eight products and avoids repeating previews from earlier rows. “See all” retains the complete collection. |
| Rendering | Exactly one card layout exists at a time. Collection delegates are populated only near the current viewport and while their page is visible; virtual grid/list reuse remains. |
| Motion | Existing shared spring and duration tokens; no animation when disabled; no new idle animation or recurrent catalogue polling. |
| Interaction | Ctrl+K/F search, visible focus, arrow navigation, Enter/Space, Back/Escape and native mouse/touch scrolling retain the existing contracts. Real AR/EN Qt walks include the negative warning controls. |
| Library ownership | Open native apps through their effective desktop service; label OS versus external ownership. Preserve user data and explicit per-version actions. |
| Failure state | Android startup waits up to90s for its application service, stays cancellable and never starts an install/update merely because its process says RUNNING. Errors have Arabic/English words. |

## Measured review evidence

On the same 3,395-entry actual index, isolated native Qt/Arabic at250% with software rendering: the Apps-page object count falls from12,003 to2,784; Discover cards from70 to15. Peak child RSS with screenshot captures is580,748→433,192KiB. Both completed review processes exit0 with no QML warnings. This is a bounded source review, not whole-desktop GPU/frame pacing or weak-hardware acceptance. Earlier failed instrumentation is retained privately.

The native inventory first finds30 previously omitted launchers, including Firefox, ChatGPT, Antigravity, Settings and KDE applications. Managed Android shortcuts are then excluded when the package already has its own indexed entry. Inventory does not adopt or delete an arbitrary external executable.

Android support is owned by a separate on-demand user unit, not the Store operation's process group. A native source-backend run opens the already-installed F-Droid app; its actual Wayland window and continuing independent session unit are verified. This is not the ten-Android-app acceptance matrix.

Remote has a separate source-geometry defect: an encoded640px startup image can be mistaken for the upstream desktop. The callback now reads its own pipeline's raw source caps and does not publish a healthy picture when source geometry is unknown. Five changing JPEG frames from an actual isolated1920×1080→640×360 GStreamer chain verify both the source geometry and decoded output; all four new controls fail against old source. This is not an owner-phone/WAN soak.

The installed `.1062` native postcheck also retains14 actual Baloo extractor display-startup errors. The service has no DISPLAY/WAYLAND_DISPLAY in its process environment. A scoped offscreen backend lets the nonvisual extractor initialize without either display; native proof exits0. Preserve its database, indexing policy, regexp guard and vendor resource weights. The original failed boot verdict remains; do not erase the journal or call it a clean boot.

## التسليم / Handoff

The production QML changes live in `AppCard`, `DiscoverPage`, `CollectionRow`, `AppPage`, `LibraryPage`, `StoreProducts.js` and the existing window state. Native inventory and the fixed launcher route use `moos_store_desktop.py`, the indexer and Store executor. Android service readiness and independent lifetime use the shared runtime reader and `moos-android-session.service`. The Remote fix stays in its existing capture helper.

Required closure: complete repo and image gates, AR/EN rendered review and source old/fixed controls; then one exact-source signed four-edition release cycle and actual installed readback. Phone decoded-picture endurance, native Windows/Android application matrices, inaccessible external uninstallers and wider hardware acceptance remain explicit plan work. No identity, signature, authentication or boot gate is weakened.

Oct17 combined integration retains the reviewed card/native-inventory work alongside PR248's newer launch, APK and capture-target guards. Installed platform filters now select variants before grouping/counting (real AR/EN old-source negatives fail). The final Baloo choice preserves its native idle backend and orders startup after plasma-core.target; the earlier offscreen experiment above is historical. Same-ID Finamp/Shattered Pixel Dungeon use their native Linux recipes, with old APK receipts preserved separately. Current counts and signed/native acceptance belong to the owner audit and PROJECT_STATE.

# Exact-head Store corrections

These correction artifacts were prepared against
`382f593578b0a046290e86120faa17f4f04016af` for the station's reserved integration
branch. At the owner's subsequent explicit instruction, the complete five-patch
set is now applied on isolated `integrate/owner-unified-20261015`, preserving
the station's head and Oracle archive ancestry. Original worktrees and the
owner's source/index are unchanged. This is not signed or installed acceptance. Scope and independent findings are in
[the Arabic review](../STORE_20261015_AR.md).

Apply the completed set to a clean integration worktree, inspect the resulting
diff, run the maintained gates and rendered controls, and read back the final
image's bytes. Do not apply only the Windows keep-data UI over the destructive
old backend. Do not move production tags or bypass signed delivery.

| Patch | Purpose | SHA-256 |
| --- | --- | --- |
| [install-safety.patch](install-safety.patch) | Preserve Windows prefix data; recover interrupted Windows/vendor swaps; refuse unknown Windows directories | `392469789d8e529f9ee2b9afb9e8c2f9a4e61e8b1dad2da8cde33ea4aee6a427` |
| [appdrop-ownership-and-budget.patch](appdrop-ownership-and-budget.patch) | Require an owned receipt; bound and account compressed symlink bodies before reading | `7e3ec22efced3a759d08235738c14363fdb22f4edc6bb04f94595270dd129a05` |
| [android-index-shared-policy.patch](android-index-shared-policy.patch) | Use the backend's actual APK policy; preserve validated signer and receipt fields; memoize complete APK facts; register executable controls in both entry points | `823626b00699345c9c7d91a81e05d0064a419a879f7ad6f16e5c9e1de6175fb7` |
| [appdrop-index-receipt-alignment.patch](appdrop-index-receipt-alignment.patch) | Match index receipt ownership to the corrected executor; preserve valid file installs | `5f5eec7d7a12d63bcf950905ecf312740bf4fb25eeb0a90a0da6956452a4c348` |
| [ui-lifecycle-and-rail.patch](ui-lifecycle-and-rail.patch) | Publisher app actions, truthful Windows keep/delete choice, keyboard-reachable large-font rail; real Qt regression in existing suite | `e750b657553e8c93b61437ed8b62e726b7721490605c38b5c0a35b94cfbeb195` |

Apply in the table order; Android precedes the App Drop index alignment.
The final UI patch replaces its earlier two-file draft and must accompany the backend fix.

The App Drop patch replaces the earlier budget-only draft. The Android patch
also corrects a general App Drop fixture's architecture; production Windows
architecture restrictions remain intact. No waiting exclusions or skips were
added. User settings/data stored alongside a portable executable are outside
the preserved Windows prefix contract, and the updated sheet must say so.

Receipts: [install safety](../../releases/2026-10-15-oracle-store-install-review.json),
[App Drop](../../releases/2026-10-15-oracle-appdrop-review.json),
[Android policy](../../releases/2026-10-15-oracle-android-index-review.json),
[App Drop index](../../releases/2026-10-15-oracle-appdrop-index-review.json),
[UI](../../releases/2026-10-15-oracle-store-ui-review.json),
[branch inventory](../../releases/2026-10-15-oracle-branch-review.json),
[canary](../../releases/2026-10-15-oracle-plasma-review.json).
Native source renders remain task artifacts; no generated review screenshots
or fixture-only applications are shipped as product payload.

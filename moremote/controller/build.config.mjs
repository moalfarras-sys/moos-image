// Mo PC Remote controller build settings: the one place the shipped bundle's shape is declared.
//
// This replaced vite.config.ts on 2026-11-18. Vite 8 (and the vite-plugin-pwa/Workbox build
// chain) depend on picomatch, and GHSA-fc5q-39xc-vjpf covers every picomatch release with no
// patched version; the unchanged high-severity npm audit gate correctly refused every signed
// x86 build. scripts/build.mjs now drives the same engines Vite 8 used underneath (rolldown
// for JavaScript, lightningcss for CSS) and bundles the Workbox *runtime* modules into sw.js
// itself, so the build input carries no glob matcher at all and the audit stays unchanged.

// Build: output straight into the agent's wwwroot so it is served from one origin.
export const OUT_DIR = "../agent/wwwroot";

// The same JavaScript target the Vite build used (build.target "es2020"), and the CSS
// browser floor Vite derived from it for lightningcss.
export const JS_TARGET = "es2020";
export const CSS_TARGETS = {
  chrome: 80, edge: 80, safari: [14, 1], ios_saf: [14, 5], firefox: 80, opera: 67,
};

// Dev: the agent runs on :8765. scripts/dev.mjs proxies /api and /ws to it so the controller
// can be developed on :5173 while talking to the real backend. MO_AGENT lets a dev session aim
// the proxy at any live agent (e.g. a cloud screen over its Tailscale HTTPS name) instead of a
// local one — the UI can then be tested against a real stream without deploying. Dev-only: the
// built app always talks to its own origin.
export const DEV_PORT = 5173;
export const DEV_PROXY = ["/api", "/ws"];

// Installed, this stops being a page in a browser and becomes the app: no address bar, no
// tab strip, no toolbar sliding back in from the bottom. On a phone that is most of the
// screen returned to the desktop you are actually trying to look at.
//
// It has never been installable in practice, and not for want of a manifest — this one has
// always been generated, and the icons have always existed. The service worker is
// registered manually and only in a secure context (see main.tsx), and until the control
// panel started handing out the Tailscale HTTPS name, the only address anyone ever had was
// a LAN IP over plain http. So the install prompt could not appear, on any phone, ever.
//
// orientation: "any" — NEVER force the phone to rotate.
//
// This used to say "landscape", which is the DECLARATIVE twin of
// screen.orientation.lock("landscape"): Android/Chrome applies it to every launch of
// the INSTALLED app. Since this same app tells the user to "Add to Home Screen", that
// is the common case — so the phone spun sideways on its own every time the remote was
// opened. That is the "الشاشة عم تعمل عرضي على الجوال" the owner reported, and removing
// the imperative lock in RemoteScreen.tsx alone did not fix it; both had to go.
//
// The picture now follows the phone (see shouldRotate), and the user turns the phone,
// or picks the Sideways lock, when THEY want the wide view. "any" is stated explicitly
// rather than omitted so the intent is on the record and cannot be "restored" by
// someone reading the old rationale.
//
// Key order and the "lang" default match the manifest vite-plugin-pwa wrote, so an
// installed copy sees the same document.
export const MANIFEST = {
  name: "Mo PC Remote",
  short_name: "Mo Remote",
  description: "Control your MoOS desktop from your phone, over your own private tailnet.",
  start_url: "/",
  display: "standalone",
  background_color: "#14191c",
  theme_color: "#14191c",
  lang: "en",
  scope: "/",
  display_override: ["fullscreen", "standalone"],
  orientation: "any",
  icons: [
    { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
    { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ],
};

// Workbox owns caching; public/notification-sw.js (imported by sw/sw.js) owns only the
// notification-click route back to the already-open controller.
//
// Cache only the app shell; the live stream and every API call are never precached, and
// no navigation fallback is registered, so /api/..., /ws and /audio/... always reach the
// network. TAKE OVER AS SOON AS THERE IS SOMETHING NEWER: sw/sw.js calls skipWaiting() and
// clientsClaim() — see the comment there.
export const PRECACHE_EXTENSIONS = [".js", ".css", ".html", ".png", ".svg", ".woff2"];

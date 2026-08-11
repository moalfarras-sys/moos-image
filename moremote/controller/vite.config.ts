import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Dev: the agent runs on :8765. We proxy /api and /ws to it so the controller can
// be developed on :5173 while talking to the real backend.
// Build: output straight into the agent's wwwroot so it's served from one origin.
// MO_AGENT lets a dev session aim the proxy at any live agent (e.g. a cloud screen over
// its Tailscale HTTPS name) instead of a local one — the UI can then be tested against a
// real stream without deploying. Dev-only: the built app always talks to its own origin.
const AGENT = process.env.MO_AGENT || "http://localhost:8765";

export default defineConfig({
  base: "/",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: false, // we register manually (only in secure contexts) in main.tsx
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
      manifest: {
        name: "Mo PC Remote",
        short_name: "Mo Remote",
        description: "Control your MoOS desktop from your phone, over your own private tailnet.",
        theme_color: "#14191c",
        background_color: "#14191c",
        display: "standalone",
        display_override: ["fullscreen", "standalone"],
        orientation: "any",
        start_url: "/",
        scope: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Generated Workbox owns caching; this tiny reviewed script owns only the
        // notification-click route back to the already-open controller.
        importScripts: ["/notification-sw.js"],
        // Cache only the app shell; the live stream is never cached.
        globPatterns: ["**/*.{js,css,html,png,svg,woff2}"],
        navigateFallback: null,
        // TAKE OVER AS SOON AS THERE IS SOMETHING NEWER, INSTEAD OF WAITING TO BE ASKED.
        //
        // A workbox worker installs a new precache and then WAITS for every tab of the old version
        // to close before activating. On a phone that has this on the home screen, the tab does not
        // close — so an updated agent kept serving the old controller indefinitely, and the user had
        // no way to tell and no way to force it. Together with the controllerchange reload in
        // main.tsx these two flags turn "a newer app exists" into "you are now running it".
        skipWaiting: true,
        clientsClaim: true,
        // The stream and every API call must never be answered from a cache. globPatterns already
        // excludes them, but a stale index.html served to /api/... would be an unexplainable failure.
        navigateFallbackDenylist: [/^\/api\//, /^\/ws$/, /^\/audio\//],
      },
    }),
  ],
  build: {
    outDir: "../agent/wwwroot",
    emptyOutDir: true,
    target: "es2020",
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      // headers.Origin: changeOrigin rewrites Host but NOT Origin, and the agent's
      // cross-origin check (rightly) 403s a WebSocket that claims to come from
      // localhost:5173 — so a remote MO_AGENT stream never starts in dev without this.
      "/api": { target: AGENT, changeOrigin: true, headers: { Origin: AGENT } },
      "/ws": { target: AGENT, ws: true, changeOrigin: true, headers: { Origin: AGENT } },
    },
  },
});

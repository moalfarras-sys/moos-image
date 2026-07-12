import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Dev: the agent runs on :8765. We proxy /api and /ws to it so the controller can
// be developed on :5173 while talking to the real backend.
// Build: output straight into the agent's wwwroot so it's served from one origin.
const AGENT = "http://localhost:8765";

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
      // orientation: a remote desktop is a landscape object. Fitted into a portrait phone it
      // becomes a stamp between two black bars — most of the display spent on nothing. Asking for
      // landscape costs nothing where it is ignored (iOS ignores it) and is exactly right
      // everywhere it is honoured.
      manifest: {
        name: "Mo PC Remote",
        short_name: "Mo Remote",
        description: "Control your MoOS desktop from your phone, over your own private tailnet.",
        theme_color: "#0b0f19",
        background_color: "#0b0f19",
        display: "standalone",
        display_override: ["fullscreen", "standalone"],
        orientation: "landscape",
        start_url: "/",
        scope: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Cache only the app shell; the live stream is never cached.
        globPatterns: ["**/*.{js,css,html,png,svg,woff2}"],
        navigateFallback: null,
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
      "/api": { target: AGENT, changeOrigin: true },
      "/ws": { target: AGENT, ws: true, changeOrigin: true },
    },
  },
});

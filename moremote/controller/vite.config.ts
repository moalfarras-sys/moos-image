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
      manifest: {
        name: "Mo Remote",
        short_name: "Mo Remote",
        description: "Private remote control for my own PC over Tailscale.",
        theme_color: "#0b0f19",
        background_color: "#0b0f19",
        display: "standalone",
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

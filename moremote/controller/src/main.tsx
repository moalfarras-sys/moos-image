import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Register the service worker only in a secure context (https / localhost).
// Over a plain-http Tailscale IP iOS won't allow it — and we don't need offline caching.
//
// AND MAKE AN UPDATE ACTUALLY ARRIVE, WHICH IS THE HALF THAT WAS MISSING.
//
// A precaching service worker is a cache that outranks the network, so after the agent is updated
// the phone keeps running the OLD controller — the new worker installs, then waits, and the page in
// front of the user is still served the previous bundle. This is not theoretical: it happened twice
// while testing this very change, and both times the new build was on the server and the phone was
// showing the old one with no indication that anything was stale. From the user's chair the update
// simply did not happen, and the natural next step — reloading — does not fix it either, because
// the reload is served by the same worker.
//
// `updateViaCache: "none"` stops the browser HTTP-caching sw.js itself (it may otherwise serve a
// day-old worker), and the updatefound/controllerchange pair swaps the app the moment a new worker
// takes over. The reload guard matters: without it, a worker that claims control immediately would
// reload, register, claim, reload — for ever.
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", async () => {
    try {
      const reg = await navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" });
      // A remote desktop is a long-lived page. Somebody who leaves it open for a day would otherwise
      // never ask whether there is a newer app; an hourly check costs one conditional request.
      setInterval(() => reg.update().catch(() => {}), 60 * 60 * 1000);
      let reloading = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (reloading) return;
        reloading = true;
        location.reload();
      });
    } catch {
      /* PWA caching unavailable — the app still works fully online */
    }
  });
}

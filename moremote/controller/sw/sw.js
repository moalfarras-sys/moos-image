// Mo PC Remote service worker source. scripts/build.mjs bundles this, with the Workbox
// runtime modules it imports, into one classic-script agent/wwwroot/sw.js.
//
// The precache list is generated from the built files ("virtual:precache-manifest"); hashed
// assets carry no revision, everything else an MD5 revision, as Workbox's own generator did.
// The default Workbox precache cache name is unchanged, so a phone that installed the earlier
// generated worker upgrades through the ordinary install/activate path and
// cleanupOutdatedCaches() retires any older Workbox cache format.
import { clientsClaim } from "workbox-core";
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";
import manifest from "virtual:precache-manifest";

// The notification-click route (public/notification-sw.js). Classic importScripts must run
// during the worker's first evaluation, before any event.
importScripts("/notification-sw.js");

// TAKE OVER AS SOON AS THERE IS SOMETHING NEWER, INSTEAD OF WAITING TO BE ASKED.
//
// A workbox worker installs a new precache and then WAITS for every tab of the old version
// to close before activating. On a phone that has this on the home screen, the tab does not
// close — so an updated agent kept serving the old controller indefinitely, and the user had
// no way to tell and no way to force it. Together with the controllerchange reload in
// main.tsx these two calls turn "a newer app exists" into "you are now running it".
self.skipWaiting();
clientsClaim();

precacheAndRoute(manifest);
cleanupOutdatedCaches();

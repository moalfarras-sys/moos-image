import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {remoteAlertPermission, requestRemoteAlertPermission, showRemoteAlert} from "../src/lib/notifications.ts";

const here = dirname(fileURLToPath(import.meta.url));
const calls: Array<{title: string; options: NotificationOptions}> = [];
let permission: NotificationPermission = "default";

class TestNotification {
  static get permission(): NotificationPermission { return permission; }
  static async requestPermission(): Promise<NotificationPermission> {
    permission = "granted";
    return permission;
  }
}

function installBrowser({secure = true, hidden = true}: {secure?: boolean; hidden?: boolean} = {}) {
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {isSecureContext: secure, setTimeout, clearTimeout},
  });
  Object.defineProperty(globalThis, "document", {configurable: true, value: {hidden}});
  Object.defineProperty(globalThis, "Notification", {configurable: true, value: TestNotification});
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {serviceWorker: {ready: Promise.resolve({
      showNotification: async (title: string, options: NotificationOptions) => {
        calls.push({title, options});
      },
    })}},
  });
}

installBrowser({secure: false});
assert.equal(remoteAlertPermission(), "unsupported", "insecure origins must never request notifications");

installBrowser();
permission = "default";
assert.equal(await requestRemoteAlertPermission(), true, "an explicit user action may grant alerts");

Object.defineProperty(globalThis, "document", {configurable: true, value: {hidden: false}});
assert.equal(await showRemoteAlert("connection-interrupted"), false, "visible controllers must stay quiet");
assert.equal(calls.length, 0);

Object.defineProperty(globalThis, "document", {configurable: true, value: {hidden: true}});
assert.equal(await showRemoteAlert("upload-complete"), true);
assert.deepEqual(calls, [{
  title: "Mo PC Remote",
  options: {
    body: "The file upload completed.",
    tag: "remote-upload",
    icon: "/icons/icon-192.png",
    badge: "/icons/favicon-64.png",
  },
}]);

const worker = readFileSync(resolve(here, "../public/notification-sw.js"), "utf8");
for (const contract of ["notificationclick", "notification.close()", "clients.matchAll", "includeUncontrolled: true", "existing.focus()", 'clients.openWindow("/")']) {
  assert.ok(worker.includes(contract), `notification click worker misses ${contract}`);
}

console.log("PASS: background alerts are opt-in, hidden-only, generic and return to the controller");

/** Privacy-safe, opt-in phone alerts for events produced by Mo PC Remote itself. */

export type AlertPermission = "unsupported" | NotificationPermission;
export type RemoteAlert = "connection-interrupted" | "upload-complete";

const ALERTS: Record<RemoteAlert, { body: string; tag: string }> = {
  "connection-interrupted": {
    body: "The desktop connection was interrupted.",
    tag: "remote-connection",
  },
  "upload-complete": {
    body: "The file upload completed.",
    tag: "remote-upload",
  },
};

export function remoteAlertPermission(): AlertPermission {
  if (typeof window === "undefined" || !window.isSecureContext ||
      typeof Notification === "undefined" || !("serviceWorker" in navigator)) {
    return "unsupported";
  }
  return Notification.permission;
}

/** Must be called directly from a user gesture; browsers intentionally reject silent prompts. */
export async function requestRemoteAlertPermission(): Promise<boolean> {
  const state = remoteAlertPermission();
  if (state === "unsupported" || state === "denied") return false;
  if (state === "granted") return true;
  return (await Notification.requestPermission()) === "granted";
}

/**
 * Show a generic event only while the app is hidden. No desktop notification text,
 * filenames, clipboard data or credentials cross this boundary.
 */
export async function showRemoteAlert(kind: RemoteAlert): Promise<boolean> {
  if (remoteAlertPermission() !== "granted" || typeof document === "undefined" || !document.hidden) {
    return false;
  }
  const alert = ALERTS[kind];
  let timeout = 0;
  try {
    const registration = await Promise.race([
      navigator.serviceWorker.ready,
      new Promise<never>((_, reject) => {
        timeout = window.setTimeout(() => reject(new Error("service_worker_timeout")), 2000);
      }),
    ]);
    await registration.showNotification("Mo PC Remote", {
      body: alert.body,
      tag: alert.tag,
      icon: "/icons/icon-192.png",
      badge: "/icons/favicon-64.png",
    });
    return true;
  } catch {
    return false;
  } finally {
    if (timeout) window.clearTimeout(timeout);
  }
}

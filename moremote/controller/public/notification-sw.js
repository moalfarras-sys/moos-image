/* Mo PC Remote notification click contract. Imported by the generated Workbox worker. */
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true })
    .then(windows => {
      const existing = windows.find(client => new URL(client.url).origin === self.location.origin);
      return existing ? existing.focus() : self.clients.openWindow("/");
    }));
});

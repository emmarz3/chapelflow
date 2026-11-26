self.addEventListener("push", (event) => {
  let message = {};
  try { message = event.data ? event.data.json() : {}; } catch { message = {}; }
  const href = typeof message.href === "string" && /^\/app(?:\/|$)/.test(message.href) ? message.href : "/app/notifications";
  event.waitUntil(self.registration.showNotification(String(message.title || "ChapelFlow"), {
    body: String(message.body || "You have a new chapel update."),
    icon: "/chapelflow-mark.svg",
    data: { href },
  }));
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const href = event.notification.data && event.notification.data.href || "/app/notifications";
  event.waitUntil(self.clients.openWindow(href));
});

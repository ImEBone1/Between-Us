self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : {};
  const vibration = data.vibration_enabled ? [120, 60, 120] : [];
  event.waitUntil(
    self.registration.showNotification(data.title || "BetweenUs", {
      body: data.body || "A feeling just arrived.",
      icon: "/static/images/betweenus-logo.svg",
      badge: "/static/images/betweenus-logo.svg",
      tag: "betweenus-feeling",
      renotify: true,
      vibrate: vibration,
      silent: data.sound_enabled === false,
      // Kept as metadata for browsers/platforms that support custom notification sounds.
      sound: data.sound || "default",
      data: { url: data.url || "/dashboard/", moodType: data.mood_type || null },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/dashboard/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    }),
  );
});


// Check for new phone-app assets on launch and when returning to the app.
if ('serviceWorker' in navigator) {
  let registration;
  let updating = false;
  const hadController = Boolean(navigator.serviceWorker.controller);
  navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })
    .then(value => { registration = value; return value.update(); })
    .catch(() => {});
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') registration?.update().catch(() => {});
  });
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!hadController || updating) return;
    // Never interrupt a live set or staff recording to apply a visual update.
    if (document.querySelector('#rep-count, #cal-progress')) return;
    updating = true;
    location.reload();
  });
}

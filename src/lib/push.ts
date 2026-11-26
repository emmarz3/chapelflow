import { notificationService } from "../services/chapelflow";

function keyBytes(value: string): Uint8Array<ArrayBuffer> {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const data = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "="));
  const bytes = new Uint8Array(new ArrayBuffer(data.length));
  for (let index = 0; index < data.length; index++) bytes[index] = data.charCodeAt(index);
  return bytes;
}

export async function enableBrowserPush() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) throw new Error("Browser push is unavailable on this device.");
  const { data } = await notificationService.pushConfig();
  if (!data.enabled) throw new Error("Browser push is not configured yet.");
  if (await Notification.requestPermission() !== "granted") throw new Error("Notification permission was not granted.");
  const worker = await navigator.serviceWorker.ready;
  const subscription = await worker.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(data.public_key) });
  try { await notificationService.subscribePush(subscription.toJSON()); }
  catch (error) { await subscription.unsubscribe(); throw error; }
}

export async function disableBrowserPush() {
  if (!("serviceWorker" in navigator)) return;
  const worker = await navigator.serviceWorker.ready;
  const subscription = await worker.pushManager.getSubscription();
  if (!subscription) return;
  await notificationService.unsubscribePush(subscription.endpoint);
  await subscription.unsubscribe();
}

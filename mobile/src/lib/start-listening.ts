/** A cancelled/permission-revoked activation must never reopen the microphone later. */
export async function startListeningIfCurrent(
  current: () => boolean,
  activate: () => Promise<void>,
  start: () => Promise<void>,
): Promise<void> {
  if (!current()) return;
  await activate();
  if (!current()) return;
  await start();
}

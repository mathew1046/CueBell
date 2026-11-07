import type { Connection } from './types';

type StopDependencies = {
  stopCapture: () => Promise<unknown>;
  clearLocal: () => void;
  setConnection: (connection: Connection | null) => void;
  save: (connection: Connection) => Promise<void>;
  remove: () => Promise<void>;
  remote: (connection: Connection, action: 'pause' | 'stop') => Promise<unknown>;
};

/** Turn capture off first; report storage and remote cleanup failures independently. */
export async function stopListening(
  action: 'pause' | 'stop', connection: Connection | null, dependencies: StopDependencies,
): Promise<void> {
  await dependencies.stopCapture();
  const problems: string[] = [];
  if (action === 'stop') {
    dependencies.clearLocal();
    const next = connection ? { ...connection, suppressMonitor: true } : null;
    dependencies.setConnection(next);
    try {
      if (next) await dependencies.save(next);
      else await dependencies.remove();
    } catch {
      // A stale saved connection must not restore a monitor after a privacy stop.
      try {
        await dependencies.remove();
        dependencies.setConnection(null);
        problems.push('Could not save the cleared state; the saved session was removed instead.');
      } catch {
        problems.push('Could not update or remove the saved session. Retry Stop before closing the app, ' +
          'or clear CueBell storage in Android settings to prevent old session data returning.');
      }
    }
  }
  if (connection) {
    try { await dependencies.remote(connection, action); }
    catch { problems.push('Backend cleanup failed; its session will expire.'); }
  }
  if (problems.length) {
    throw new Error(`${action === 'stop' ? 'Stopped and cleared on this phone.' : 'Microphone is off.'} ${problems.join(' ')}`);
  }
}

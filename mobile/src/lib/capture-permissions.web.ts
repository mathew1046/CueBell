import { primeAudio, releasePreparedMicrophone, requestMicrophone } from '../../modules/queue-listener/browser';

export const prepareCaptureGesture = primeAudio;
export const releaseCapturePermission = releasePreparedMicrophone;

/** Announce browser permission setup and retain the shared microphone stream for capture. */
export async function requestCapturePermissions(requesting: () => void): Promise<void> {
  requesting();
  await requestMicrophone();
}

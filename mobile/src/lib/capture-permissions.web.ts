import { primeAudio, releasePreparedMicrophone, requestMicrophone } from '../../modules/queue-listener/browser';

export const prepareCaptureGesture = primeAudio;
export const releaseCapturePermission = releasePreparedMicrophone;

export async function requestCapturePermissions(requesting: () => void): Promise<void> {
  requesting();
  await requestMicrophone();
}

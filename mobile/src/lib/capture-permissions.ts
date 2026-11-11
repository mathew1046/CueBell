import { PermissionsAndroid, Platform, type Permission } from 'react-native';

export function prepareCaptureGesture() {}
export function releaseCapturePermission() {}

export async function requestCapturePermissions(requesting: () => void): Promise<void> {
  const permissions: Permission[] = [PermissionsAndroid.PERMISSIONS.RECORD_AUDIO];
  if (Number(Platform.Version) >= 33) permissions.push(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS);
  const checks = await Promise.all(permissions.map(permission => PermissionsAndroid.check(permission)));
  const missing = permissions.filter((_, index) => !checks[index]);
  if (!missing.length) return;
  requesting();
  const granted = await PermissionsAndroid.requestMultiple(missing);
  if (missing.some(permission => granted[permission] !== PermissionsAndroid.RESULTS.GRANTED)) {
    throw new Error('Allow microphone and notification access to start listening.');
  }
}

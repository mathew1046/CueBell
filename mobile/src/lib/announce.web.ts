let timer: ReturnType<typeof setTimeout> | undefined;

/** React Native Web's announcement method is a no-op. Use a persistent ARIA live region. */
export function announce(message: string): void {
  if (typeof document === 'undefined') return;
  let region = document.getElementById('cuebell-announcements');
  if (!region) {
    region = document.createElement('div');
    region.id = 'cuebell-announcements';
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', 'polite');
    region.setAttribute('aria-atomic', 'true');
    Object.assign(region.style, { position: 'absolute', width: '1px', height: '1px', overflow: 'hidden',
      clipPath: 'inset(50%)', whiteSpace: 'nowrap' });
    document.body.append(region);
  }
  clearTimeout(timer);
  region.textContent = '';
  timer = setTimeout(() => { region.textContent = message; }, 50);
}

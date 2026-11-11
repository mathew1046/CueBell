import { useEffect, useRef } from 'react';
import Listener from '../../modules/queue-listener/browser';

/** Canvas owns its frame updates so microphone activity never rerenders the screen. */
export function ListeningWaveform({ animate, color, height }: { animate: boolean; color: string; height: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const element = canvas.current;
    const drawing = element?.getContext('2d');
    if (!element || !drawing) return;
    let frame = 0;
    let last = performance.now();
    let level = 0;
    const bars = new Float32Array(37);
    const draw = (now: number) => {
      const width = element.clientWidth;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (element.width !== Math.round(width * ratio) || element.height !== Math.round(height * ratio)) {
        element.width = Math.round(width * ratio);
        element.height = Math.round(height * ratio);
      }
      const delta = Math.min((now - last) / 1000, 0.1);
      last = now;
      const rms = animate ? Listener.audioLevel() : 0;
      const target = Math.min(1, Math.log1p(Math.max(0, rms - 0.003) * 60) / Math.log1p(30));
      level += (target - level) * (1 - Math.exp(-delta / (target > level ? 0.045 : 0.22)));
      bars.copyWithin(0, 1);
      bars[bars.length - 1] = level;
      drawing.setTransform(ratio, 0, 0, ratio, 0, 0);
      drawing.clearRect(0, 0, width, height);
      drawing.strokeStyle = window.matchMedia('(forced-colors: active)').matches ? 'CanvasText' : color;
      drawing.lineCap = 'round';
      drawing.lineWidth = Math.max(2, Math.min(4, width / 75));
      const gap = width / (bars.length + 1);
      for (let index = 0; index < bars.length; index++) {
        const envelope = 0.45 + 0.55 * Math.sin(Math.PI * (index + 1) / (bars.length + 1));
        const size = Math.max(3, bars[index] * (height - 8) * envelope);
        drawing.beginPath();
        drawing.moveTo(gap * (index + 1), (height - size) / 2);
        drawing.lineTo(gap * (index + 1), (height + size) / 2);
        drawing.stroke();
      }
      if (animate) frame = requestAnimationFrame(draw);
    };
    draw(last);
    return () => cancelAnimationFrame(frame);
  }, [animate, color, height]);
  return <canvas ref={canvas} aria-hidden="true" style={{ display: 'block', width: '100%', height, pointerEvents: 'none' }} />;
}

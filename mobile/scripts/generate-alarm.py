"""Generate CueBell's original, offline three-pulse alarm. No external audio/license."""
import math
from pathlib import Path
import struct
import wave

rate = 22050
duration = 2.4
destination = Path(__file__).resolve().parents[1] / 'modules/queue-listener/android/src/main/res/raw/cuebell_alarm.wav'
destination.parent.mkdir(parents=True, exist_ok=True)
samples = bytearray()
for frame in range(round(rate * duration)):
    t = frame / rate
    pulse = t % 0.8
    value = 0.0
    if pulse < 0.55:
        # Short ramps avoid clicks; alternating pitches make a distinct call signal.
        envelope = min(1.0, pulse / 0.025, (0.55 - pulse) / 0.06)
        frequency = 660 if pulse < 0.275 else 880
        value = 0.58 * envelope * (math.sin(2 * math.pi * frequency * t) + 0.22 * math.sin(4 * math.pi * frequency * t))
    samples.extend(struct.pack('<h', round(value * 32767)))
with wave.open(str(destination), 'wb') as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(rate)
    output.writeframes(samples)
print(destination)

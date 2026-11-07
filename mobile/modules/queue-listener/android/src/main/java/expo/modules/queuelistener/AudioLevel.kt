package expo.modules.queuelistener

import kotlin.math.ln1p
import kotlin.math.sqrt

/** Only a normalized level crosses from the capture thread to the UI. */
internal class AudioLevel {
  @Volatile var value = 0f
    private set
  private var noiseFloor = 0.0015

  fun update(samples: ShortArray) {
    var squares = 0.0
    for (sample in samples) {
      val normalized = sample / 32768.0
      squares += normalized * normalized
    }
    val rms = sqrt(squares / samples.size)
    // Follow quiet background noise slowly without adapting to speech peaks.
    if (rms < 0.012) {
      noiseFloor += (rms.coerceAtLeast(0.0015) - noiseFloor) * if (rms < noiseFloor) 0.15 else 0.025
    }
    val signal = (rms - 1.5 * noiseFloor).coerceAtLeast(0.0)
    val target = (ln1p(100 * signal) / ln1p(100.0)).toFloat()
    value += (target - value) * if (target > value) 0.58f else 0.16f
  }
}

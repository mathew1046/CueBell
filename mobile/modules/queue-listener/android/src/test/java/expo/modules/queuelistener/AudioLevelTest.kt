package expo.modules.queuelistener

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioLevelTest {
  private fun frame(amplitude: Int) = ShortArray(512) {
    if (it % 2 == 0) amplitude.toShort() else (-amplitude).toShort()
  }

  @Test fun silenceAndSteadyLowNoiseSettle() {
    val level = AudioLevel()
    level.update(frame(0))
    assertEquals(0f, level.value, 0f)
    val quietRoom = frame(210)
    repeat(180) { level.update(quietRoom) }
    assertTrue(level.value < 0.01f)
  }

  @Test fun speechAndPeaksHaveDistinctLevels() {
    val level = AudioLevel()
    fun measure(amplitude: Int): Float {
      val samples = frame(amplitude)
      repeat(10) { level.update(samples) }
      return level.value
    }
    val quiet = measure(400)
    val normal = measure(2500)
    val loud = measure(15000)
    val peak = measure(Short.MAX_VALUE.toInt())
    assertTrue(quiet > 0.05f)
    assertTrue(quiet < normal && normal < loud && loud < peak && peak < 1f)
  }

  @Test fun attackRespondsQuicklyAndReleaseEasesBackToSilence() {
    val level = AudioLevel()
    val loud = frame(18000)
    level.update(loud)
    val first = level.value
    level.update(loud)
    val second = level.value
    assertTrue(first > 0.4f && second > first)
    val silence = frame(0)
    level.update(silence)
    assertTrue(level.value in 0.0f..<second && level.value > second * 0.7f)
    repeat(35) { level.update(silence) }
    assertTrue(level.value < 0.003f)
  }
}

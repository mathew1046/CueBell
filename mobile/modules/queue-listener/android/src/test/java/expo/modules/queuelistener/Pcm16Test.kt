package expo.modules.queuelistener

import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.sin

class Pcm16Test {
  @Test fun signedExtremesAreLittleEndian() {
    val samples = ShortArray(512)
    samples[0] = Short.MIN_VALUE; samples[1] = Short.MAX_VALUE
    samples[2] = -1; samples[3] = 1
    val bytes = ByteArray(1024)
    Pcm16.encode(samples, bytes)
    assertArrayEquals(byteArrayOf(0, -128, -1, 127, -1, -1, 1, 0), bytes.copyOfRange(0, 8))
    assertEquals(32, samples.size * 1000 / 16000)
  }

  @Test fun knownWaveformAcrossChunkBoundariesPreservesEverySample() {
    val waveform = ShortArray(16000) { (sin(it * 2.0 * Math.PI * 440 / 16000) * 28000).toInt().toShort() }
    val decoded = ArrayList<Short>()
    // 16000 has a partial trailing frame: it is withheld, never padded or relabelled.
    for (offset in 0 until waveform.size - 511 step 512) {
      val bytes = ByteArray(1024)
      Pcm16.encode(waveform.copyOfRange(offset, offset + 512), bytes)
      val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
      repeat(512) { decoded.add(buffer.get()) }
    }
    assertEquals(31 * 512, decoded.size)
    assertArrayEquals(waveform.copyOfRange(0, decoded.size), decoded.toShortArray())
    assertEquals(992, decoded.size * 1000 / 16000)
  }

  @Test(expected = IllegalArgumentException::class)
  fun rejectsWrongFrameSize() { Pcm16.encode(ShortArray(511), ByteArray(1024)) }
}

package expo.modules.queuelistener

/** One provider frame: 512 signed mono samples, 1024 little-endian bytes, 32 ms at 16 kHz. */
object Pcm16 {
  fun encode(samples: ShortArray, frame: ByteArray) {
    require(samples.size == 512 && frame.size == 1024)
    for (i in samples.indices) {
      frame[i * 2] = (samples[i].toInt() and 255).toByte()
      frame[i * 2 + 1] = (samples[i].toInt() shr 8).toByte()
    }
  }
}

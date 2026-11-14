package expo.modules.queuelistener

/** Read snapshots outside the PCM loop. Durations use the monotonic nanosecond clock. */
data class NoiseReductionDiagnostics(
  val requestedMode: String = "gtcrn",
  val activeMode: String = "gtcrn",
  val sampleRate: Int = 16000,
  val frameSamples: Int = 512,
  /** Output alignment while open, including retained raw-fallback delay; zero when closed. */
  val algorithmicDelaySamples: Int = if (activeMode == "gtcrn") 256 else 0,
  /** Padding actually emitted; retained as history after close. */
  val startupPaddingSamples: Int = 0,
  val initializationNanos: Long = 0,
  val processedFrames: Long = 0,
  val lastProcessNanos: Long = 0,
  val maxProcessNanos: Long = 0,
  val overloadCount: Long = 0,
  val fallbackReason: String? = null,
) {
  companion object {
    fun off() = NoiseReductionDiagnostics(requestedMode = "off", activeMode = "off",
      algorithmicDelaySamples = 0, startupPaddingSamples = 0)
  }
}

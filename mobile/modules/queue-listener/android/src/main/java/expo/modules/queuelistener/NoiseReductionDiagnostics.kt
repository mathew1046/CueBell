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
  /** Estimate after the last inference attempt; frozen on fallback/close, not microphone age. */
  val processingDebtNanos: Long = 0,
  val maxProcessingDebtNanos: Long = 0,
  /** Configured limit, including on fallback; no processing policy is active in explicit off mode. */
  val processingDebtLimitNanos: Long = if (requestedMode == "gtcrn") 64_000_000L else 0,
) {
  companion object {
    fun off() = NoiseReductionDiagnostics(requestedMode = "off", activeMode = "off",
      algorithmicDelaySamples = 0, startupPaddingSamples = 0)
  }
}

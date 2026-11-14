package expo.modules.queuelistener

import kotlin.math.roundToInt

/** Small seam for deterministic framing/failure/deadline tests without JNI or Android. */
internal interface StreamingDenoiser : AutoCloseable {
  fun run(input: FloatArray): FloatArray
  override fun close()
}

/**
 * Fixed-size adapter: first native result has 256 samples, later results have 512.
 * Prefixing exactly one zero hop preserves packet cadence with a 16 ms sample delay.
 * One call at or above the 32 ms capture budget permanently bypasses inference: no
 * queued work or retry loop. Once introduced, the sample delay is retained by a
 * fixed raw-input tail, so fail-open switches processing without skipping time.
 */
internal class StreamingNoiseReducer(
  private var engine: StreamingDenoiser?,
  private val initializationNanos: Long = 0,
  initialFailure: String? = null,
  private val clock: () -> Long = System::nanoTime,
) : PcmNoiseReducer {
  private val normalized = FloatArray(FRAME_SAMPLES)
  private val candidate = ShortArray(FRAME_SAMPLES)
  private val rawTail = ShortArray(DELAY_SAMPLES)
  private var closed = false
  private var delayIntroduced = false
  private var frames = 0L
  private var lastNanos = 0L
  private var maxNanos = 0L
  private var overloads = 0L
  var fallbackReason: String? = initialFailure
    private set

  val diagnostics: NoiseReductionDiagnostics
    get() {
      val active = !closed && engine != null && fallbackReason == null
      return NoiseReductionDiagnostics(activeMode = if (active) "gtcrn" else "off",
        algorithmicDelaySamples = if (!closed && (active || delayIntroduced)) DELAY_SAMPLES else 0,
        startupPaddingSamples = if (delayIntroduced) DELAY_SAMPLES else 0,
        initializationNanos = initializationNanos, processedFrames = frames,
        lastProcessNanos = lastNanos, maxProcessNanos = maxNanos,
        overloadCount = overloads, fallbackReason = fallbackReason)
    }

  override fun process(input: ShortArray, output: ShortArray) {
    require(input.size == FRAME_SAMPLES && output.size == FRAME_SAMPLES) { "Expected 512 mono PCM16 samples at 16000 Hz" }
    check(!closed) { "Noise reducer is closed" }
    val current = engine
    if (current == null || fallbackReason != null) {
      writeRaw(input, output)
      return
    }
    val start = clock()
    try {
      for (i in input.indices) normalized[i] = input[i] / 32768f
      val result = current.run(normalized)
      val expected = if (delayIntroduced) FRAME_SAMPLES else FRAME_SAMPLES - DELAY_SAMPLES
      check(result.size == expected) { "Unexpected denoiser frame size: ${result.size}, expected $expected" }
      check(result.all { it.isFinite() }) { "Non-finite denoiser output" }
      // Stage until the deadline check: input/output may alias even on fail-open.
      val offset = FRAME_SAMPLES - result.size
      for (i in result.indices) candidate[offset + i] =
        (result[i].coerceIn(-1f, 32767f / 32768f) * 32768f).roundToInt().toShort()
      if (offset > 0) candidate.fill(0, 0, offset)
    } catch (error: Exception) {
      fallbackReason = "inference_error:${error.javaClass.simpleName}"
    } catch (error: LinkageError) {
      fallbackReason = "native_error:${error.javaClass.simpleName}"
    }
    lastNanos = (clock() - start).coerceAtLeast(0)
    maxNanos = maxOf(maxNanos, lastNanos)
    frames++
    if (lastNanos >= FRAME_BUDGET_NANOS) {
      overloads++
      fallbackReason = "processing_deadline_exceeded"
    }
    if (fallbackReason != null) {
      writeRaw(input, output)
    } else {
      // Save before writing output, since callers may use the same input/output array.
      input.copyInto(rawTail, 0, FRAME_SAMPLES - DELAY_SAMPLES, FRAME_SAMPLES)
      candidate.copyInto(output)
      delayIntroduced = true
    }
  }

  private fun writeRaw(input: ShortArray, output: ShortArray) {
    if (!delayIntroduced) {
      // Initialization/first-call failure has emitted no padding: remain zero-delay raw.
      input.copyInto(output)
      return
    }
    // Continue at the next un-emitted input sample: previous tail, then current head.
    // Stage and save the new tail before touching output to support aliased buffers.
    rawTail.copyInto(candidate)
    input.copyInto(candidate, DELAY_SAMPLES, 0, FRAME_SAMPLES - DELAY_SAMPLES)
    input.copyInto(rawTail, 0, FRAME_SAMPLES - DELAY_SAMPLES, FRAME_SAMPLES)
    candidate.copyInto(output)
  }

  override fun close() {
    if (closed) return
    closed = true
    val current = engine
    engine = null
    try {
      current?.close()
    } catch (error: Exception) {
      if (fallbackReason == null) fallbackReason = "release_error:${error.javaClass.simpleName}"
    } catch (error: LinkageError) {
      if (fallbackReason == null) fallbackReason = "release_error:${error.javaClass.simpleName}"
    } finally { normalized.fill(0f); candidate.fill(0); rawTail.fill(0) }
  }

  companion object {
    const val FRAME_SAMPLES = 512
    const val SAMPLE_RATE = 16000
    const val DELAY_SAMPLES = 256
    const val FRAME_BUDGET_NANOS = 32_000_000L
  }
}

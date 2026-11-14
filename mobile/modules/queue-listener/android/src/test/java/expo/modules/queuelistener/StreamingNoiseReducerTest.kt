package expo.modules.queuelistener

import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class StreamingNoiseReducerTest {
  /** Models upstream's first-hop deficit without doing any filtering. */
  private class DelayedIdentity : StreamingDenoiser {
    var calls = 0
    var closes = 0
    private val tail = FloatArray(256)
    override fun run(input: FloatArray): FloatArray {
      val output = if (calls++ == 0) input.copyOfRange(0, 256) else
        FloatArray(512) { if (it < 256) tail[it] else input[it - 256] }
      input.copyInto(tail, 0, 256, 512)
      return output
    }
    override fun close() { closes++ }
  }

  private enum class Failure {
    SHORT_FRAME, LONG_FRAME, NAN, POSITIVE_INFINITY, NEGATIVE_INFINITY, EXCEPTION, LINKAGE, DEBT;

    val reason: String get() = when (this) {
      EXCEPTION -> "inference_error:IllegalArgumentException"
      LINKAGE -> "native_error:UnsatisfiedLinkError"
      DEBT -> "processing_debt_exceeded"
      else -> "inference_error:IllegalStateException"
    }
  }

  private class FaultingIdentity(
    private val failureAt: Int,
    private val failure: Failure,
    private val failureNanos: Long = if (failure == Failure.DEBT) 96_000_000L else 31_999_999L,
  ) : StreamingDenoiser {
    private val identity = DelayedIdentity()
    var calls = 0
    var closes = 0
    var now = 0L
    override fun run(input: FloatArray): FloatArray {
      val frame = calls++
      // A 96 ms call adds exactly 64 ms debt when earlier calls have incurred none.
      now += if (frame == failureAt) failureNanos else 31_999_999L
      if (frame != failureAt) return identity.run(input)
      val expected = if (frame == 0) 256 else 512
      return when (failure) {
        Failure.SHORT_FRAME -> FloatArray(expected - 1)
        Failure.LONG_FRAME -> FloatArray(expected + 1)
        Failure.NAN -> FloatArray(expected) { Float.NaN }
        Failure.POSITIVE_INFINITY -> FloatArray(expected) { Float.POSITIVE_INFINITY }
        Failure.NEGATIVE_INFINITY -> FloatArray(expected) { Float.NEGATIVE_INFINITY }
        Failure.EXCEPTION -> throw IllegalArgumentException("injected inference failure")
        Failure.LINKAGE -> throw UnsatisfiedLinkError("injected missing symbol")
        Failure.DEBT -> identity.run(input)
      }
    }
    override fun close() { closes++; identity.close() }
  }

  private class TimedIdentity(private val durations: LongArray) : StreamingDenoiser {
    private val identity = DelayedIdentity()
    var now = 0L
    val calls: Int get() = identity.calls
    override fun run(input: FloatArray): FloatArray {
      now += durations[calls]
      return identity.run(input)
    }
    override fun close() = identity.close()
  }

  @Test fun allSamplesStayOrderedAcrossFramesWithExactlyOneHopOfStartupPadding() {
    val engine = DelayedIdentity()
    val reducer = StreamingNoiseReducer(engine, clock = { 0L })
    val input = ShortArray(512)
    val output = ShortArray(512)
    val actual = ShortArray(512 * 30)
    val expected = ShortArray(actual.size)
    repeat(30) { frame ->
      for (i in input.indices) input[i] = ((frame * 512 + i) * 31 - 32000).toShort()
      reducer.process(input, output)
      output.copyInto(actual, frame * 512)
      for (i in input.indices) {
        val at = frame * 512 + i + 256
        if (at < expected.size) expected[at] = input[i]
      }
    }
    assertArrayEquals(expected, actual)
    assertEquals(30L, reducer.diagnostics.processedFrames)
    assertEquals("gtcrn", reducer.diagnostics.activeMode)
    assertEquals(256, reducer.diagnostics.algorithmicDelaySamples)
    assertEquals(256, reducer.diagnostics.startupPaddingSamples)
    reducer.close()
    reducer.close()
    assertEquals(1, engine.closes)
  }

  @Test fun unavailableEngineKeepsOriginalPcmBytesIncludingSilenceAndExtremes() {
    val reducer = StreamingNoiseReducer(null, initialFailure = "missing_model")
    val input = ShortArray(512) { (it * 257).toShort() }
    input[0] = Short.MIN_VALUE; input[1] = Short.MAX_VALUE
    val output = ShortArray(512)
    val bytes = ByteArray(1024)
    repeat(3) { frame ->
      if (frame == 1) input.fill(0)
      reducer.process(input, output)
      Pcm16.encode(output, bytes)
      val reference = ByteBuffer.allocate(1024).order(ByteOrder.LITTLE_ENDIAN)
      input.forEach { reference.putShort(it) }
      assertArrayEquals(reference.array(), bytes)
    }
    assertEquals("off", reducer.diagnostics.activeMode)
    assertEquals("missing_model", reducer.fallbackReason)
    assertEquals(0L, reducer.diagnostics.processedFrames)
    assertEquals(0, reducer.diagnostics.algorithmicDelaySamples)
    assertEquals(0, reducer.diagnostics.startupPaddingSamples)
    assertEquals(0L, reducer.diagnostics.processingDebtNanos)
    assertEquals(0L, reducer.diagnostics.maxProcessingDebtNanos)
    reducer.close()
  }

  @Test fun oneDebtLimitHitReturnsCurrentRawFrameAndNeverRunsInferenceAgain() {
    val engine = DelayedIdentity()
    var now = 0L
    val reducer = StreamingNoiseReducer(engine, clock = { now.also { now += 96_000_000L } })
    val input = ShortArray(512) { (it - 255).toShort() }
    val original = input.copyOf()
    // Aliasing must also preserve raw input when an inference finishes too late.
    reducer.process(input, input)
    assertArrayEquals(original, input)
    reducer.process(input, input)
    assertArrayEquals(original, input)
    assertEquals(1, engine.calls)
    assertEquals(1L, reducer.diagnostics.overloadCount)
    assertEquals(96_000_000L, reducer.diagnostics.lastProcessNanos)
    assertEquals("processing_debt_exceeded", reducer.fallbackReason)
    assertEquals(64_000_000L, reducer.diagnostics.processingDebtNanos)
    assertEquals(64_000_000L, reducer.diagnostics.maxProcessingDebtNanos)
    assertEquals(64_000_000L, reducer.diagnostics.processingDebtLimitNanos)
    assertEquals(0, reducer.diagnostics.algorithmicDelaySamples)
    assertEquals(0, reducer.diagnostics.startupPaddingSamples)
    reducer.close()
  }

  @Test fun startupFailuresKeepNumberedInputAtZeroDelay() {
    for (failure in Failure.entries) for (aliased in listOf(false, true)) {
      val engine = FaultingIdentity(0, failure)
      val reducer = StreamingNoiseReducer(engine, clock = { engine.now })
      val input = ShortArray(512)
      val output = if (aliased) input else ShortArray(512)
      repeat(4) { frame ->
        val original = ShortArray(512) { (frame * 512 + it + 1).toShort() }
        original.copyInto(input)
        reducer.process(input, output)
        assertArrayEquals("$failure aliased=$aliased frame=$frame", original, output)
      }
      assertEquals(1, engine.calls)
      assertEquals(1L, reducer.diagnostics.processedFrames)
      assertEquals("off", reducer.diagnostics.activeMode)
      assertEquals(failure.reason, reducer.fallbackReason)
      assertEquals(0, reducer.diagnostics.algorithmicDelaySamples)
      assertEquals(0, reducer.diagnostics.startupPaddingSamples)
      assertEquals(if (failure == Failure.DEBT) 1L else 0L, reducer.diagnostics.overloadCount)
      reducer.close()
      assertEquals(1, engine.closes)
    }
  }

  @Test fun midstreamFailuresPreserveEveryNumberedSampleWithTheAlreadyIntroducedDelay() {
    val source = ShortArray(512 * 12) { (it + 1).toShort() }
    source[256] = Short.MIN_VALUE
    source[511] = Short.MAX_VALUE
    val expected = ShortArray(source.size) { if (it < 256) 0 else source[it - 256] }
    for (failure in Failure.entries) for (aliased in listOf(false, true)) for (failureAt in listOf(1, 3)) {
      val engine = FaultingIdentity(failureAt, failure)
      val reducer = StreamingNoiseReducer(engine, clock = { engine.now })
      val input = ShortArray(512)
      val output = if (aliased) input else ShortArray(512)
      val actual = ShortArray(source.size)
      repeat(12) { frame ->
        source.copyInto(input, 0, frame * 512, (frame + 1) * 512)
        reducer.process(input, output)
        output.copyInto(actual, frame * 512)
        assertEquals(if (frame < failureAt) "gtcrn" else "off", reducer.diagnostics.activeMode)
        assertEquals(256, reducer.diagnostics.algorithmicDelaySamples)
        assertEquals(256, reducer.diagnostics.startupPaddingSamples)
      }
      assertArrayEquals("$failure aliased=$aliased failureAt=$failureAt", expected, actual)
      assertEquals(failureAt + 1, engine.calls)
      assertEquals((failureAt + 1).toLong(), reducer.diagnostics.processedFrames)
      assertEquals(failure.reason, reducer.fallbackReason)
      assertEquals(if (failure == Failure.DEBT) 1L else 0L, reducer.diagnostics.overloadCount)
      assertEquals(if (failure == Failure.DEBT) 96_000_000L else 31_999_999L,
        reducer.diagnostics.lastProcessNanos)
      reducer.close()
      assertEquals(1, engine.closes)
    }
  }

  @Test fun observedTransientOverrunsRecoverWhileKeepingEnhancedOutput() {
    val durations = longArrayOf(54_796_847, 3_119_384, 39_127_154, 4_800_000,
      39_105_769, 4_800_000, 85_034_154, 4_800_000, 4_800_000, 50_059_461, 4_800_000, 32_000_000)
    val debts = longArrayOf(22_796_847, 0, 7_127_154, 0, 7_105_769, 0,
      53_034_154, 25_834_154, 0, 18_059_461, 0, 0)
    val source = ShortArray(512 * durations.size) { ((it + 1) * 2).toShort() }
    val expected = ShortArray(source.size) { if (it < 256) 0 else (source[it - 256] / 2).toShort() }
    for (aliased in listOf(false, true)) {
      val identity = TimedIdentity(durations)
      val engine = object : StreamingDenoiser {
        override fun run(input: FloatArray) = identity.run(input).also { samples ->
          for (i in samples.indices) samples[i] *= 0.5f
        }
        override fun close() = identity.close()
      }
      val reducer = StreamingNoiseReducer(engine, initializationNanos = 675_000_000L, clock = { identity.now })
      val input = ShortArray(512)
      val output = if (aliased) input else ShortArray(512)
      val actual = ShortArray(source.size)
      assertEquals(0L, reducer.diagnostics.processingDebtNanos)
      repeat(durations.size) { frame ->
        source.copyInto(input, 0, frame * 512, (frame + 1) * 512)
        reducer.process(input, output)
        output.copyInto(actual, frame * 512)
        assertEquals("frame=$frame", debts[frame], reducer.diagnostics.processingDebtNanos)
        assertEquals("gtcrn", reducer.diagnostics.activeMode)
        assertNull(reducer.fallbackReason)
      }
      assertArrayEquals("aliased=$aliased", expected, actual)
      assertEquals(durations.size, identity.calls)
      assertEquals(6L, reducer.diagnostics.overloadCount)
      assertEquals(53_034_154L, reducer.diagnostics.maxProcessingDebtNanos)
      assertEquals(675_000_000L, reducer.diagnostics.initializationNanos)
      reducer.close()
    }
  }

  @Test fun sustainedOverloadFallsBackExactlyAtTheDebtLimitAndStopsInference() {
    val engine = TimedIdentity(LongArray(8) { 40_000_000L })
    val reducer = StreamingNoiseReducer(engine, clock = { engine.now })
    val source = ShortArray(512 * 10) { (it + 1).toShort() }
    val expected = ShortArray(source.size) { if (it < 256) 0 else source[it - 256] }
    val input = ShortArray(512)
    val output = ShortArray(512)
    val actual = ShortArray(source.size)
    repeat(10) { frame ->
      source.copyInto(input, 0, frame * 512, (frame + 1) * 512)
      reducer.process(input, output)
      output.copyInto(actual, frame * 512)
      assertEquals(minOf(frame + 1, 8) * 8_000_000L, reducer.diagnostics.processingDebtNanos)
      assertEquals(if (frame < 7) "gtcrn" else "off", reducer.diagnostics.activeMode)
    }
    assertArrayEquals(expected, actual)
    assertEquals(8, engine.calls)
    assertEquals(8L, reducer.diagnostics.processedFrames)
    assertEquals(8L, reducer.diagnostics.overloadCount)
    assertEquals(64_000_000L, reducer.diagnostics.maxProcessingDebtNanos)
    assertEquals("processing_debt_exceeded", reducer.fallbackReason)
    assertEquals(256, reducer.diagnostics.algorithmicDelaySamples)
    reducer.close()
  }

  @Test fun exactDebtBoundaryDoesNotBankAdvanceCreditFromFastCalls() {
    val durations = LongArray(100) { 1_000_000L } + longArrayOf(95_999_999L, 32_000_000L, 32_000_001L)
    val engine = TimedIdentity(durations)
    val reducer = StreamingNoiseReducer(engine, clock = { engine.now })
    val output = ShortArray(512)
    repeat(100) {
      reducer.process(ShortArray(512), output)
      assertEquals(0L, reducer.diagnostics.processingDebtNanos)
    }
    repeat(2) {
      reducer.process(ShortArray(512), output)
      assertEquals(63_999_999L, reducer.diagnostics.processingDebtNanos)
      assertEquals("gtcrn", reducer.diagnostics.activeMode)
    }
    reducer.process(ShortArray(512), output)
    assertEquals(64_000_000L, reducer.diagnostics.processingDebtNanos)
    assertEquals(64_000_000L, reducer.diagnostics.maxProcessingDebtNanos)
    assertEquals(3L, reducer.diagnostics.overloadCount)
    assertEquals("processing_debt_exceeded", reducer.fallbackReason)
    reducer.close()
  }

  @Test fun invalidResultsKeepTheirFailureReasonEvenWhenTheSameCallExceedsTheDebtLimit() {
    for (failure in Failure.entries.filter { it != Failure.DEBT }) for (failureAt in listOf(0, 1)) {
      val engine = FaultingIdentity(failureAt, failure, failureNanos = 96_000_000L)
      val reducer = StreamingNoiseReducer(engine, clock = { engine.now })
      val source = ShortArray(512 * (failureAt + 2)) { (it + 1).toShort() }
      val expected = if (failureAt == 0) source else
        ShortArray(source.size) { if (it < 256) 0 else source[it - 256] }
      val input = ShortArray(512)
      val output = ShortArray(512)
      val actual = ShortArray(source.size)
      repeat(failureAt + 2) { frame ->
        source.copyInto(input, 0, frame * 512, (frame + 1) * 512)
        reducer.process(input, output)
        output.copyInto(actual, frame * 512)
      }
      assertArrayEquals("$failure failureAt=$failureAt", expected, actual)
      assertEquals(failure.reason, reducer.fallbackReason)
      assertEquals("off", reducer.diagnostics.activeMode)
      assertEquals(failureAt + 1, engine.calls)
      assertEquals(1L, reducer.diagnostics.overloadCount)
      assertEquals(64_000_000L, reducer.diagnostics.processingDebtNanos)
      reducer.close()
    }
  }

  @Test fun extremeDurationCannotWrapAccumulatedDebtNegative() {
    val engine = TimedIdentity(longArrayOf(95_999_999L, Long.MAX_VALUE))
    val reducer = StreamingNoiseReducer(engine, clock = { engine.now })
    repeat(2) { reducer.process(ShortArray(512), ShortArray(512)) }
    assertEquals(Long.MAX_VALUE, reducer.diagnostics.processingDebtNanos)
    assertEquals(Long.MAX_VALUE, reducer.diagnostics.maxProcessingDebtNanos)
    assertEquals("processing_debt_exceeded", reducer.fallbackReason)
    reducer.close()
  }

  @Test fun clipsNormalizedOutputWithoutWrappingSignedPcm() {
    val engine = object : StreamingDenoiser {
      override fun run(input: FloatArray) = FloatArray(256) { if (it % 2 == 0) 2f else -2f }
      override fun close() = Unit
    }
    val reducer = StreamingNoiseReducer(engine, clock = { 0L })
    val output = ShortArray(512)
    reducer.process(ShortArray(512), output)
    assertEquals(Short.MAX_VALUE, output[256])
    assertEquals(Short.MIN_VALUE, output[257])
  }

  @Test fun fallbackTailComesFromRawInputWhileSuccessfulOutputRemainsEnhanced() {
    val source = ShortArray(512 * 4) { ((it + 1) * 2).toShort() }
    val expected = ShortArray(source.size) { position ->
      when {
        position < 256 -> 0
        position < 512 * 2 -> (source[position - 256] / 2).toShort()
        else -> source[position - 256]
      }
    }
    for (failure in listOf(Failure.EXCEPTION, Failure.DEBT)) for (aliased in listOf(false, true)) {
      val identity = FaultingIdentity(2, failure)
      val engine = object : StreamingDenoiser {
        override fun run(input: FloatArray) = identity.run(input).also { samples ->
          for (i in samples.indices) samples[i] *= 0.5f
        }
        override fun close() = identity.close()
      }
      val reducer = StreamingNoiseReducer(engine, clock = { identity.now })
      val input = ShortArray(512)
      val output = if (aliased) input else ShortArray(512)
      val actual = ShortArray(source.size)
      repeat(4) { frame ->
        source.copyInto(input, 0, frame * 512, (frame + 1) * 512)
        reducer.process(input, output)
        output.copyInto(actual, frame * 512)
      }
      assertArrayEquals("$failure aliased=$aliased", expected, actual)
      assertEquals(3, identity.calls)
      assertEquals(failure.reason, reducer.fallbackReason)
      reducer.close()
    }
  }

  @Test fun newInstancesResetAlignmentAndState() {
    repeat(2) {
      val engine = TimedIdentity(longArrayOf(60_000_000L))
      val reducer = StreamingNoiseReducer(engine, clock = { engine.now })
      val initial = reducer.diagnostics
      assertEquals(0L, initial.processingDebtNanos)
      assertEquals(0L, initial.maxProcessingDebtNanos)
      assertEquals(64_000_000L, initial.processingDebtLimitNanos)
      val output = ShortArray(512)
      reducer.process(ShortArray(512) { 9876 }, output)
      assertArrayEquals(ShortArray(256), output.copyOfRange(0, 256))
      assertArrayEquals(ShortArray(256) { 9876 }, output.copyOfRange(256, 512))
      assertEquals(28_000_000L, reducer.diagnostics.processingDebtNanos)
      assertEquals(28_000_000L, reducer.diagnostics.maxProcessingDebtNanos)
      assertEquals(0L, initial.processingDebtNanos)
      reducer.close()
      assertEquals(28_000_000L, reducer.diagnostics.processingDebtNanos)
      assertEquals(28_000_000L, reducer.diagnostics.maxProcessingDebtNanos)
    }
    assertEquals(0L, NoiseReductionDiagnostics.off().processingDebtNanos)
    assertEquals(0L, NoiseReductionDiagnostics.off().maxProcessingDebtNanos)
    assertEquals(0L, NoiseReductionDiagnostics.off().processingDebtLimitNanos)
  }

  @Test(expected = IllegalArgumentException::class)
  fun rejectsPartialFramesRatherThanQueueingThem() {
    StreamingNoiseReducer(null).process(ShortArray(256), ShortArray(512))
  }

  @Test fun releaseFailureIsReportedAndNeverRetried() {
    var releases = 0
    val engine = object : StreamingDenoiser {
      override fun run(input: FloatArray) = FloatArray(256)
      override fun close() { releases++; throw IllegalStateException("injected release failure") }
    }
    val reducer = StreamingNoiseReducer(engine)
    reducer.close()
    reducer.close()
    assertEquals(1, releases)
    assertEquals("off", reducer.diagnostics.activeMode)
    assertEquals("release_error:IllegalStateException", reducer.fallbackReason)
  }

  @Test fun closeDiscardsThePendingTailWithoutReplayingOrChangingCallerOutput() {
    for (failureAt in listOf(-1, 1)) for (releaseFailure in 0..2) {
      val identity = FaultingIdentity(failureAt, Failure.EXCEPTION)
      val engine = object : StreamingDenoiser {
        override fun run(input: FloatArray) = identity.run(input)
        override fun close() {
          identity.close()
          if (releaseFailure == 1) throw IllegalStateException("injected release failure")
          if (releaseFailure == 2) throw UnsatisfiedLinkError("injected release failure")
        }
      }
      val reducer = StreamingNoiseReducer(engine, clock = { identity.now })
      val output = ShortArray(512)
      repeat(2) { frame -> reducer.process(ShortArray(512) { (frame * 512 + it + 1).toShort() }, output) }
      // Samples 769..1024 are still pending; close must never emit or replay them.
      val lastOutput = ShortArray(512) { (it + 257).toShort() }
      assertArrayEquals(lastOutput, output)
      assertEquals(256, reducer.diagnostics.algorithmicDelaySamples)
      reducer.close()
      reducer.close()
      assertEquals(1, identity.closes)
      assertEquals(2, identity.calls)
      assertArrayEquals(lastOutput, output)
      assertEquals("off", reducer.diagnostics.activeMode)
      assertEquals(0, reducer.diagnostics.algorithmicDelaySamples)
      assertEquals(256, reducer.diagnostics.startupPaddingSamples)
      assertEquals(when {
        failureAt == 1 -> Failure.EXCEPTION.reason
        releaseFailure == 1 -> "release_error:IllegalStateException"
        releaseFailure == 2 -> "release_error:UnsatisfiedLinkError"
        else -> null
      }, reducer.fallbackReason)
      assertThrows(IllegalStateException::class.java) { reducer.process(ShortArray(512) { 12345 }, output) }
      assertArrayEquals(lastOutput, output)
      assertEquals(2, identity.calls)
    }
  }

  @Test(expected = IllegalStateException::class)
  fun rejectsUseAfterCloseWithoutCallingJni() {
    val reducer = StreamingNoiseReducer(DelayedIdentity())
    reducer.close()
    reducer.process(ShortArray(512), ShortArray(512))
  }
}

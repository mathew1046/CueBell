package expo.modules.queuelistener

/**
 * Single-owner, stateful 16 kHz mono PCM16 processor. Each call consumes exactly 512 samples
 * and writes exactly 512 samples into caller-owned output. No frame is gated or dropped.
 * Construct before starting capture; process and close on the owning capture/benchmark thread.
 */
interface PcmNoiseReducer : AutoCloseable {
  fun process(input: ShortArray, output: ShortArray)
  override fun close()
}

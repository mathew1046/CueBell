package expo.modules.queuelistener

import android.content.res.AssetManager
import com.k2fsa.sherpa.onnx.OfflineSpeechDenoiserGtcrnModelConfig
import com.k2fsa.sherpa.onnx.OfflineSpeechDenoiserModelConfig
import com.k2fsa.sherpa.onnx.OnlineSpeechDenoiser
import com.k2fsa.sherpa.onnx.OnlineSpeechDenoiserConfig
import java.io.File
import java.security.MessageDigest

/**
 * Standalone, single-owner 16 kHz mono PCM16 processor, including persistent model
 * state. No Context is required for a filesystem model. Initialization and one
 * zero-frame warm-up happen in the constructor, before microphone capture.
 * A missing/mismatched model, unavailable ABI or recoverable engine error yields
 * permanent raw passthrough with diagnostics, retaining an already-introduced
 * sample delay rather than skipping input. Close discards the pending alignment tail.
 */
class GtcrnNoiseReducer private constructor(modelSource: () -> ModelSource) : PcmNoiseReducer {
  constructor(modelPath: String, assetManager: AssetManager? = null) :
    this({ ModelSource(modelPath, assetManager) })

  private data class ModelSource(val path: String, val assets: AssetManager?)
  private val processor: StreamingNoiseReducer

  init {
    val start = System.nanoTime()
    var native: OnlineSpeechDenoiser? = null
    var engine: StreamingDenoiser? = null
    var failure: String? = null
    try {
      val source = modelSource()
      val digest = MessageDigest.getInstance("SHA-256")
      (source.assets?.open(source.path) ?: File(source.path).inputStream()).use { input ->
        val buffer = ByteArray(8192)
        while (true) {
          val count = input.read(buffer)
          if (count < 0) break
          digest.update(buffer, 0, count)
        }
      }
      check(digest.digest().joinToString("") { "%02x".format(it) } == MODEL_SHA256) { "GTCRN model checksum mismatch" }
      val denoiser = OnlineSpeechDenoiser(source.assets, OnlineSpeechDenoiserConfig(
        model = OfflineSpeechDenoiserModelConfig(
          gtcrn = OfflineSpeechDenoiserGtcrnModelConfig(model = source.path),
          numThreads = 1, debug = false, provider = "cpu")))
      native = denoiser
      check(denoiser.sampleRate == 16000 && denoiser.frameShiftInSamples == 256) { "Unexpected GTCRN model framing" }
      val warmup = denoiser.run(FloatArray(512), 16000)
      check(warmup.sampleRate == 16000 && warmup.samples.size == 256 && warmup.samples.all { it.isFinite() }) {
        "Unexpected GTCRN startup framing"
      }
      denoiser.reset()
      engine = object : StreamingDenoiser {
        override fun run(input: FloatArray): FloatArray {
          val result = denoiser.run(input, 16000)
          check(result.sampleRate == 16000) { "Unexpected GTCRN output sample rate" }
          return result.samples
        }
        override fun close() = denoiser.release()
      }
    } catch (error: Exception) {
      failure = "initialization_error:${error.javaClass.simpleName}"
    } catch (error: LinkageError) {
      failure = "native_unavailable:${error.javaClass.simpleName}"
    }
    if (engine == null) {
      try { native?.release() } catch (_: Exception) { } catch (_: LinkageError) { }
    }
    processor = StreamingNoiseReducer(engine, System.nanoTime() - start, failure)
  }

  val diagnostics: NoiseReductionDiagnostics get() = processor.diagnostics
  /** Allocation-free transition check for the capture loop; snapshot only on a change. */
  val fallbackReason: String? get() = processor.fallbackReason
  override fun process(input: ShortArray, output: ShortArray) = processor.process(input, output)
  override fun close() = processor.close()

  companion object {
    const val MODEL_ASSET = "noise-reduction/gtcrn_simple.onnx"
    const val MODEL_SHA256 = "e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534"

    /** Use the upstream exception-guarded file constructor in production. Only
     * model bytes are persisted, never microphone audio. The caller serializes preload. */
    fun fromAssets(assets: AssetManager, directory: File): GtcrnNoiseReducer = GtcrnNoiseReducer {
      check(directory.isDirectory || directory.mkdirs()) { "Cannot create model directory" }
      val model = File(directory, "gtcrn_simple.onnx")
      if (!model.isFile) {
        val partial = File(directory, "gtcrn_simple.onnx.partial")
        try {
          assets.open(MODEL_ASSET).use { input -> partial.outputStream().use { input.copyTo(it) } }
          check(partial.renameTo(model)) { "Cannot prepare GTCRN model" }
        } finally { partial.delete() }
      }
      // The constructor hashes this file before passing its path to JNI.
      ModelSource(model.absolutePath, null)
    }
  }
}

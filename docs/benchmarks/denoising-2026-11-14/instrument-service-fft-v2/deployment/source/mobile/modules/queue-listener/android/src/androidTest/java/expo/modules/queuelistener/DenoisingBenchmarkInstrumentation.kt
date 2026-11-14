package expo.modules.queuelistener

import android.app.Activity
import android.app.Instrumentation
import android.content.Context
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.os.Process
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.concurrent.locks.LockSupport
import kotlin.math.ceil

/**
 * Dependency-free platform instrumentation runner. Set testInstrumentationRunner to
 * this class in the module's Gradle configuration; AndroidX/JUnit are not needed.
 * Uses the SAME production GtcrnNoiseReducer as capture, including its fail-open
 * policy. A fail-open frame is logged, never silently scored as denoising work.
 *
 * Required arguments: inputDir, outputDir, modelPath. Optional: durationSeconds
 * (30 per mode), warmupSeconds (5), stress (true), replay (false), stressInput,
 * ids (comma-separated device-input IDs), modes (engine,bypass), label. The installed
 * instrumentation entry uses hostMode (activity-and-service or service-only),
 * wakeLock (true), lifecycleTimeoutSeconds (130). It requires Android API 35+.
 */
class DenoisingBenchmarkInstrumentation : Instrumentation() {
  private var options: Map<String, String> = emptyMap()

  override fun onCreate(arguments: Bundle?) {
    super.onCreate(arguments)
    options = arguments?.keySet()?.associateWith { arguments.getString(it).orEmpty() } ?: emptyMap()
    start()
  }

  override fun onStart() {
    val result = Bundle()
    try {
      val path = DenoisingBenchmarkHost(this, options).run()
      result.putString("stream", "Denoising benchmark written to ${path.absolutePath}\n")
      finish(Activity.RESULT_OK, result)
    } catch (error: Throwable) {
      result.putString("stream", "Denoising benchmark failed: ${error.stackTraceToString()}\n")
      finish(Activity.RESULT_CANCELED, result)
    }
  }
}

/**
 * Optional app_process entry point in the test APK's DEX. It needs the real
 * production native libraries on the linker path and the same pinned model.
 * No device job, APK install, or library extraction is performed by this source.
 * Arguments are key=value, identical to the instrumentation -e arguments.
 */
object DenoisingBenchmarkMain {
  @JvmStatic
  fun main(args: Array<String>) {
    val options = args.associate {
      val parts = it.split('=', limit = 2)
      require(parts.size == 2) { "Expected key=value argument, got $it" }
      parts[0] to parts[1]
    }
    println(DenoisingBenchmark(options, null).run().absolutePath)
  }
}

internal class DenoisingBenchmark(
  private val options: Map<String, String>,
  private val context: Context?,
  private val hostSnapshot: (() -> JSONObject)? = null,
) {
  private val inputDir = File(required("inputDir")).canonicalFile
  private val outputDir = File(required("outputDir")).canonicalFile
  private val model = File(required("modelPath")).canonicalFile
  private val durationSeconds = number("durationSeconds", 30, 1..3600)
  private val warmupSeconds = number("warmupSeconds", 5, 0..60)
  private val modes = (options["modes"] ?: "engine,bypass").split(',').also {
    require(it.isNotEmpty() && it.distinct().size == it.size && it.all { mode -> mode in setOf("engine", "bypass") })
  }
  private val report = JSONObject()
  private val stages = JSONArray()
  private val replays = JSONArray()

  private data class Input(
    val id: String, val caseId: String, val variant: String, val file: File,
    val sha256: String, val sampleCount: Int,
  )

  fun run(): File {
    require(!outputDir.exists()) { "Refusing to overwrite output directory: $outputDir" }
    require(outputDir.mkdirs()) { "Cannot create output directory: $outputDir" }
    val result = File(outputDir, "results.json")
    report.put("schema_version", 1).put("status", "running")
      .put("label", options["label"] ?: "unlabelled")
      .put("engine_class", GtcrnNoiseReducer::class.java.name)
      .put("sample_rate", SAMPLE_RATE).put("frame_samples", FRAME_SAMPLES)
      .put("clock_policy", "absolute System.nanoTime deadlines; no rebasing or dropped frames")
      .put("stages", stages).put("replays", replays)
      .put("options", JSONObject(options))
    fun checkpoint(phase: String) {
      report.put("phase", phase)
      result.writeText(report.toString(2))
    }
    checkpoint("validating-inputs")
    try {
      require(flag("stress", true) || flag("replay", false)) { "Select stress and/or replay" }
      val manifestFile = File(inputDir, "device-inputs.json")
      val manifest = JSONObject(manifestFile.readText())
      require(manifest.getInt("schema_version") == 1)
      require(manifest.getInt("sample_rate") == SAMPLE_RATE)
      require(manifest.getInt("frame_samples") == FRAME_SAMPLES)
      val priority = JSONObject().put("requested", Process.THREAD_PRIORITY_AUDIO)
      try {
        Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO)
      } catch (error: SecurityException) {
        priority.put("error", error.javaClass.simpleName)
      }
      priority.put("actual", Process.getThreadPriority(Process.myTid()))
      report.put("thread_priority", priority)
      report.put("input_manifest_sha256", hash(manifestFile))
      report.put("model", JSONObject().put("path", model.absolutePath).put("sha256", hash(model)))
      report.put("environment", environment())
      val selectedIds = options["ids"]?.split(',')?.toSet()
      val inputs = mutableListOf<Input>()
      val entries = manifest.getJSONArray("inputs")
      for (i in 0 until entries.length()) {
        val entry = entries.getJSONObject(i)
        val id = entry.getString("id")
        if (selectedIds != null && id !in selectedIds) continue
        require(id.matches(Regex("[a-zA-Z0-9_-]+"))) { "Unsafe input ID: $id" }
        val file = File(inputDir, entry.getString("relative_path")).canonicalFile
        require(file.path.startsWith(inputDir.path + File.separator)) { "Input path escaped root" }
        require(hash(file) == entry.getString("sha256")) { "Input SHA256 mismatch: $file" }
        require(entry.getInt("sample_zero_offset") == 0) { "Shifted input not supported" }
        inputs += Input(id, entry.getString("case_id"), entry.getString("variant"), file,
          entry.getString("sha256"), entry.getInt("sample_count"))
      }
      require(inputs.isNotEmpty()) { "No selected inputs" }
      require(inputs.map { it.id }.distinct().size == inputs.size) { "Duplicate input IDs" }
      if (selectedIds != null) require(inputs.map { it.id }.toSet() == selectedIds) { "Unknown input ID" }
      val stressInput = options["stressInput"]?.let { id -> inputs.single { it.id == id } }
        ?: inputs.firstOrNull { it.variant != "clean" } ?: inputs.first()
      // Fresh construction/close is the production session reset boundary. Check it
      // explicitly; do not warm a replay with speech or reuse state between cases.
      if ("engine" in modes) {
        checkpoint("reset-check")
        report.put("reset_check", resetCheck(stressInput))
      }
      if (flag("stress", true)) {
        for (mode in modes) {
          checkpoint("stress-$mode")
          runStage("stress-$mode", stressInput, mode,
            ceil(warmupSeconds / FRAME_SECONDS).toInt(),
            ceil(durationSeconds / FRAME_SECONDS).toInt(), replay = false)
          result.writeText(report.toString(2))
        }
      }
      if (flag("replay", false)) {
        for (input in inputs) {
          for (mode in modes) {
            checkpoint("replay-${input.id}-$mode")
            runStage("replay-${input.id}-$mode", input, mode, 0,
              input.sampleCount / FRAME_SAMPLES, replay = true)
            result.writeText(report.toString(2))
          }
        }
      }
      report.put("status", "completed")
      report.put("phase", "completed")
    } catch (error: Throwable) {
      report.put("status", "failed").put("error", error.stackTraceToString())
      throw error
    } finally {
      hostSnapshot?.let { report.put("foreground_host_at_finish", it()) }
      result.writeText(report.toString(2))
    }
    return result
  }

  private fun runStage(
    name: String, source: Input, mode: String, warmupFrames: Int, sustainedFrames: Int, replay: Boolean,
  ) {
    val samples = readWav(source.file)
    require(samples.size == source.sampleCount && samples.size % FRAME_SAMPLES == 0)
    val frames = warmupFrames + sustainedFrames
    require(frames > 0)
    val input = ShortArray(FRAME_SAMPLES)
    val output = ShortArray(FRAME_SAMPLES)
    val recorded = if (replay) ShortArray(samples.size) else null
    val processNs = LongArray(frames)
    val threadCpuNs = LongArray(frames)
    val startLatenessNs = LongArray(frames)
    val completionLatenessNs = LongArray(frames)
    val engineActive = BooleanArray(frames)
    val engineInvoked = BooleanArray(frames)
    val resourceSamples = JSONArray()
    val beforeInit = resources()
    val initializationStart = System.nanoTime()
    val reducer = if (mode == "engine") GtcrnNoiseReducer(model.absolutePath) else null
    val initializationNanos = System.nanoTime() - initializationStart
    var failure: String? = null
    var firstFallbackFrame: Int? = null
    var stageDiagnostics = JSONObject()
    val afterInit = resources()
    try {
      require(reducer?.fallbackReason == null) { "Engine initialization failed: ${reducer?.fallbackReason}" }
      // Each frame's start is anchored to the same clock, rather than sleep(process + 32ms).
      val anchor = System.nanoTime() + FRAME_NS
      val cpuStartMs = Process.getElapsedCpuTime()
      var sustainedStart: JSONObject? = null
      var sampleOffset = 0
      for (frame in 0 until frames) {
        if (frame == warmupFrames) sustainedStart = resources()
        val target = anchor + frame * FRAME_NS
        waitUntil(target)
        samples.copyInto(input, 0, sampleOffset, sampleOffset + FRAME_SAMPLES)
        sampleOffset += FRAME_SAMPLES
        if (sampleOffset == samples.size) sampleOffset = 0
        engineInvoked[frame] = reducer != null && reducer.fallbackReason == null
        val cpuBefore = Debug.threadCpuTimeNanos()
        val started = System.nanoTime()
        if (reducer == null) input.copyInto(output) else reducer.process(input, output)
        val ended = System.nanoTime()
        threadCpuNs[frame] = Debug.threadCpuTimeNanos() - cpuBefore
        processNs[frame] = ended - started
        startLatenessNs[frame] = started - target
        completionLatenessNs[frame] = ended - (target + FRAME_NS)
        engineActive[frame] = engineInvoked[frame] && reducer?.fallbackReason == null
        if (reducer?.fallbackReason != null && firstFallbackFrame == null) {
          firstFallbackFrame = frame
          failure = reducer.fallbackReason
        }
        recorded?.let { output.copyInto(it, frame * FRAME_SAMPLES) }
        // Outside the process timer, but its scheduler impact remains in lateness logs.
        if (frame % 156 == 0 || frame == frames - 1) {
          resourceSamples.put(resources().put("frame", frame)
            .put("phase", if (frame < warmupFrames) "warmup" else "sustained"))
        }
      }
      val finished = System.nanoTime()
      val cpuEndMs = Process.getElapsedCpuTime()
      val after = resources()
      stageDiagnostics = diagnostics(reducer)
      val csv = File(outputDir, "$name.frames.csv")
      csv.bufferedWriter().use { writer ->
        writer.appendLine("frame,phase,process_ns,thread_cpu_ns,start_lateness_ns,completion_lateness_ns,engine_active,engine_invoked")
        for (frame in 0 until frames) {
          writer.appendLine("$frame,${if (frame < warmupFrames) "warmup" else "sustained"},${processNs[frame]},${threadCpuNs[frame]},${startLatenessNs[frame]},${completionLatenessNs[frame]},${if (engineActive[frame]) 1 else 0},${if (engineInvoked[frame]) 1 else 0}")
        }
      }
      val elapsedMs = (finished - anchor) / 1e6
      val cpuMs = cpuEndMs - cpuStartMs
      val stage = JSONObject().put("id", name).put("mode", mode)
        .put("kind", if (replay) "replay" else "stress")
        .put("input_id", source.id).put("input_sha256", source.sha256)
        .put("frame_count", frames).put("warmup_frames", warmupFrames)
        .put("sustained_frames", sustainedFrames).put("audio_duration_s", frames * FRAME_SECONDS)
        .put("elapsed_ms", elapsedMs).put("process_cpu_ms", cpuMs)
        .put("process_cpu_percent_one_core", 100 * cpuMs / elapsedMs)
        .put("frames_file", csv.name).put("frames_sha256", hash(csv))
        .put("initialization_wall_ms", initializationNanos / 1e6)
        .put("resources_before_initialization", beforeInit)
        .put("resources_after_initialization", afterInit)
        .put("resources_sustained_start", sustainedStart ?: JSONObject.NULL)
        .put("resources_sustained_end", after).put("resource_samples", resourceSamples)
        .put("diagnostics", stageDiagnostics)
        .put("first_fallback_frame", firstFallbackFrame ?: JSONObject.NULL)
        .put("fallback_reason", failure ?: JSONObject.NULL)
        .put("state_policy", if (replay) "fresh-engine-per-case" else "fresh-engine; retained state across warmup and repeated input loops")
        .put("input_loop_count", frames * FRAME_SAMPLES.toLong() / samples.size)
        .put("dropped_frames", 0).put("schedule_rebases", 0)
      stages.put(stage)
      if (recorded != null) {
        val wav = File(outputDir, "$name.wav")
        writeWav(wav, recorded)
        replays.put(JSONObject().put("input_id", source.id).put("case_id", source.caseId)
          .put("variant", source.variant).put("mode", mode).put("input_sha256", source.sha256)
          .put("output_file", wav.name).put("output_sha256", hash(wav))
          .put("sample_count", recorded.size).put("sample_zero_offset", 0)
          .put("causal_unshifted", true).put("state_policy", "fresh-engine-per-case")
          .put("all_engine_frames_active", mode == "engine" && engineActive.all { it })
          .put("diagnostics", stageDiagnostics).put("stage_id", name))
      }
    } finally {
      val started = System.nanoTime()
      reducer?.close()
      // The JSON instance is shared with its stage, so the close cost is retained.
      stageDiagnostics.put("close_wall_ms", (System.nanoTime() - started) / 1e6)
      stageDiagnostics.put("resources_after_close", resources())
    }
  }

  private fun resetCheck(source: Input): JSONObject {
    val samples = readWav(source.file)
    val count = minOf(32, samples.size / FRAME_SAMPLES)
    val passes = JSONArray()
    val hashes = mutableListOf<String>()
    var allFramesActive = true
    repeat(2) {
      val reducer = GtcrnNoiseReducer(model.absolutePath)
      val digest = MessageDigest.getInstance("SHA-256")
      val input = ShortArray(FRAME_SAMPLES)
      val output = ShortArray(FRAME_SAMPLES)
      try {
        require(reducer.fallbackReason == null) { "Reset-check initialization failed: ${reducer.fallbackReason}" }
        val anchor = System.nanoTime() + FRAME_NS
        for (frame in 0 until count) {
          waitUntil(anchor + frame * FRAME_NS)
          samples.copyInto(input, 0, frame * FRAME_SAMPLES, (frame + 1) * FRAME_SAMPLES)
          reducer.process(input, output)
          if (reducer.fallbackReason != null) allFramesActive = false
          digest.update(pcmBytes(output))
        }
        hashes += hex(digest.digest())
        passes.put(diagnostics(reducer))
      } finally {
        reducer.close()
      }
    }
    return JSONObject().put("frames_per_pass", count).put("input_id", source.id)
      .put("output_pcm_sha256", JSONArray(hashes)).put("identical_after_recreation", hashes[0] == hashes[1])
      .put("all_engine_frames_active", allFramesActive)
      .put("policy", "two fresh production engines, same PCM, absolute-clock replay")
      .put("passes", passes)
  }

  private fun diagnostics(reducer: GtcrnNoiseReducer?): JSONObject {
    if (reducer == null) return JSONObject().put("active_mode", "bypass")
    val d = reducer.diagnostics
    return JSONObject().put("active_mode", d.activeMode).put("requested_mode", d.requestedMode)
      .put("algorithmic_delay_samples", d.algorithmicDelaySamples)
      .put("startup_padding_samples", d.startupPaddingSamples)
      .put("initialization_ns", d.initializationNanos).put("processed_frames", d.processedFrames)
      .put("max_process_ns", d.maxProcessNanos).put("overload_count", d.overloadCount)
      .put("fallback_reason", d.fallbackReason ?: JSONObject.NULL)
  }

  private fun environment(): JSONObject {
    val env = JSONObject().put("manufacturer", Build.MANUFACTURER).put("model", Build.MODEL)
      .put("device", Build.DEVICE).put("fingerprint", Build.FINGERPRINT)
      .put("sdk_int", Build.VERSION.SDK_INT).put("abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
      .put("is_64_bit", Process.is64Bit()).put("logical_processors", Runtime.getRuntime().availableProcessors())
      .put("pid", Process.myPid()).put("entry_point", if (context == null) "app_process" else "instrumentation")
      .put("uid", Process.myUid()).put("tid", Process.myTid())
      .put("process_cgroup", readProc("/proc/self/cgroup"))
      .put("thread_cgroup", readProc("/proc/self/task/${Process.myTid()}/cgroup"))
      .put("thread_cpuset", readProc("/proc/self/task/${Process.myTid()}/cpuset"))
      .put("thread", Thread.currentThread().name).put("initial_resources", resources())
    hostSnapshot?.let { env.put("foreground_host", it()) }
    if (context != null) {
      val apk = File(context.applicationInfo.sourceDir)
      env.put("test_apk_path", apk.absolutePath).put("test_apk_sha256", hash(apk))
    }
    val classpath = JSONArray()
    for (path in System.getProperty("java.class.path").orEmpty().split(File.pathSeparator)) {
      val file = File(path)
      if (file.isFile) classpath.put(JSONObject().put("path", file.absolutePath).put("sha256", hash(file)))
    }
    env.put("classpath_artifacts", classpath)
    options["apkSha256"]?.let { env.put("caller_supplied_apk_sha256", it) }
    return env
  }

  private fun readProc(path: String): Any =
    runCatching { File(path).readText().trim() }.getOrNull() ?: JSONObject.NULL

  private fun resources(): JSONObject {
    val status = runCatching { File("/proc/self/status").readLines() }.getOrDefault(emptyList())
    fun kb(name: String): Any = status.firstOrNull { it.startsWith("$name:") }
      ?.substringAfter(':')?.trim()?.substringBefore(' ')?.toLongOrNull() ?: JSONObject.NULL
    val runtime = Runtime.getRuntime()
    val result = JSONObject().put("monotonic_ns", System.nanoTime())
      .put("process_cpu_ms", Process.getElapsedCpuTime()).put("thread_cpu_ns", Debug.threadCpuTimeNanos())
      .put("rss_kb", kb("VmRSS")).put("rss_high_water_kb", kb("VmHWM"))
      .put("native_heap_allocated_bytes", Debug.getNativeHeapAllocatedSize())
      .put("java_heap_used_bytes", runtime.totalMemory() - runtime.freeMemory())
    // Sample outside process timers, not once per audio frame. These counters can
    // reveal GC activity across a phase; they do not timestamp an individual pause.
    val runtimeStats = runCatching { Debug.getRuntimeStats() }.getOrDefault(emptyMap())
    val gc = JSONObject()
    for (key in listOf("art.gc.gc-count", "art.gc.gc-time", "art.gc.blocking-gc-count", "art.gc.blocking-gc-time")) {
      runtimeStats[key]?.let { gc.put(key, it) }
    }
    result.put("runtime_gc_counters", gc)
    if (context != null && Build.VERSION.SDK_INT >= 29) {
      val power = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
      power?.let { result.put("thermal_status", it.currentThermalStatus) }
    }
    return result
  }

  private fun required(name: String): String = options[name]?.takeIf { it.isNotBlank() }
    ?: error("Missing $name argument")

  private fun number(name: String, default: Int, range: IntRange): Int =
    (options[name]?.toInt() ?: default).also { require(it in range) { "$name must be in $range" } }

  private fun flag(name: String, default: Boolean): Boolean = options[name]?.toBooleanStrict() ?: default

  companion object {
    private const val SAMPLE_RATE = 16000
    private const val FRAME_SAMPLES = 512
    private const val FRAME_NS = 32_000_000L
    private const val FRAME_SECONDS = 0.032

    private fun waitUntil(target: Long) {
      while (true) {
        check(!Thread.interrupted()) { "Benchmark thread interrupted" }
        val remaining = target - System.nanoTime()
        if (remaining <= 0) return
        LockSupport.parkNanos(remaining)
      }
    }

    private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it.toInt() and 255) }

    private fun hash(file: File): String {
      val digest = MessageDigest.getInstance("SHA-256")
      file.inputStream().use { stream ->
        val buffer = ByteArray(65536)
        while (true) {
          val count = stream.read(buffer)
          if (count < 0) break
          digest.update(buffer, 0, count)
        }
      }
      return hex(digest.digest())
    }

    private fun readWav(file: File): ShortArray {
      val bytes = file.readBytes()
      require(bytes.size >= 44) { "Truncated WAV: $file" }
      val data = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
      fun tag(offset: Int) = String(bytes, offset, 4, Charsets.US_ASCII)
      require(tag(0) == "RIFF" && tag(8) == "WAVE") { "Not a RIFF/WAVE file: $file" }
      require(data.getInt(4).toLong() + 8 == bytes.size.toLong()) { "RIFF size mismatch" }
      var offset = 12
      var validFormat = false
      var pcm: ShortArray? = null
      while (offset + 8 <= bytes.size) {
        val size = data.getInt(offset + 4)
        require(size >= 0 && offset.toLong() + 8 + size <= bytes.size) { "Invalid WAV chunk" }
        when (tag(offset)) {
          "fmt " -> {
            require(size >= 16)
            require(data.getShort(offset + 8).toInt() == 1 && data.getShort(offset + 10).toInt() == 1)
            require(data.getInt(offset + 12) == SAMPLE_RATE && data.getInt(offset + 16) == SAMPLE_RATE * 2)
            require(data.getShort(offset + 20).toInt() == 2 && data.getShort(offset + 22).toInt() == 16)
            validFormat = true
          }
          "data" -> {
            require(pcm == null && size > 0 && size % (FRAME_SAMPLES * 2) == 0) { "PCM must contain complete 512-sample frames" }
            pcm = ShortArray(size / 2) { data.getShort(offset + 8 + it * 2) }
          }
        }
        offset += 8 + size + (size and 1)
      }
      require(validFormat && pcm != null) { "Expected mono PCM16 at 16 kHz: $file" }
      return pcm
    }

    private fun pcmBytes(samples: ShortArray): ByteArray {
      val data = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN)
      for (sample in samples) data.putShort(sample)
      return data.array()
    }

    private fun writeWav(file: File, samples: ShortArray) {
      val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
      header.put("RIFF".toByteArray(Charsets.US_ASCII)).putInt(36 + samples.size * 2)
        .put("WAVEfmt ".toByteArray(Charsets.US_ASCII)).putInt(16).putShort(1).putShort(1)
        .putInt(SAMPLE_RATE).putInt(SAMPLE_RATE * 2).putShort(2).putShort(16)
        .put("data".toByteArray(Charsets.US_ASCII)).putInt(samples.size * 2)
      file.outputStream().use { stream ->
        stream.write(header.array())
        stream.write(pcmBytes(samples))
      }
    }
  }
}

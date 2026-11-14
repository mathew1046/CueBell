package expo.modules.queuelistener

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.ResultReceiver
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

internal object BenchmarkHostContract {
  const val OPTIONS = "benchmark_options"
  const val RECEIVER = "benchmark_receiver"
  const val HARNESS_FINISHED = "benchmark_harness_finished"
  const val EVENT = 1
  const val PREPARE = "expo.modules.queuelistener.benchmark.PREPARE"
  const val RUN = "expo.modules.queuelistener.benchmark.RUN"
  const val CANCEL = "expo.modules.queuelistener.benchmark.CANCEL"

  fun receiver(intent: Intent): ResultReceiver =
    requireNotNull(intent.getParcelableExtra(RECEIVER, ResultReceiver::class.java))

  fun event(receiver: ResultReceiver?, name: String, details: JSONObject = JSONObject()) {
    receiver?.send(EVENT, Bundle().apply {
      putString("event", name)
      putString("details", details.toString())
    })
  }
}

/** Coordinates normal Activity/Service APIs; the service owns the DSP worker. */
internal class DenoisingBenchmarkHost(
  private val instrumentation: Instrumentation,
  private val options: Map<String, String>,
) {
  private val context = instrumentation.context
  private val mode = options["hostMode"] ?: "activity-and-service"
  private val timeoutMs = (options["lifecycleTimeoutSeconds"]?.toLong() ?: 130L) * 1000
  private val deadline = SystemClock.elapsedRealtime() + timeoutMs
  private val root = File(requireNotNull(options["outputDir"])).canonicalFile.parentFile!!
  private val evidence = File(root, "foreground-host.json")
  private val ready = CountDownLatch(1)
  private val stopped = CountDownLatch(1)
  private val destroyed = CountDownLatch(1)
  private val finished = CountDownLatch(1)
  private val completion = AtomicReference<Pair<Int, Bundle>?>(null)
  private val events = JSONArray()
  private val report = JSONObject().put("schema_version", 1).put("status", "starting")
    .put("options", JSONObject(options)).put("host_mode", mode)
    .put("deadline_elapsed_realtime_ms", deadline).put("timeout_ms", timeoutMs)
    .put("service_type", "mediaProcessing").put("microphone_used", false)
    .put("screen_kept_on", false).put("events", events)
  private var activity: Activity? = null
  private val receiver = object : ResultReceiver(null) {
    override fun onReceiveResult(code: Int, data: Bundle?) {
      val bundle = data ?: Bundle()
      if (code == BenchmarkHostContract.EVENT) {
        val name = bundle.getString("event").orEmpty()
        record(name, JSONObject(bundle.getString("details") ?: "{}"))
        when (name) {
          "service_ready" -> ready.countDown()
          "activity_stopped" -> stopped.countDown()
          "service_destroyed" -> destroyed.countDown()
        }
      } else if (completion.compareAndSet(null, code to bundle)) {
        finished.countDown()
      }
    }
  }

  @Synchronized
  private fun record(name: String, details: JSONObject = JSONObject()) {
    when (name) {
      "service_ready" -> report.put("status", "ready")
      "starting_processing" -> report.put("status", "running")
      "host_failed" -> report.put("status", "failed")
    }
    events.put(JSONObject().put("event", name).put("elapsed_realtime_ms", SystemClock.elapsedRealtime())
      .put("details", details))
    val temporary = File(evidence.path + ".tmp")
    FileOutputStream(temporary).use { stream ->
      stream.write(report.toString(2).toByteArray(Charsets.UTF_8))
      stream.fd.sync()
    }
    check(temporary.renameTo(evidence)) { "Cannot publish foreground lifecycle evidence" }
  }

  private fun await(latch: CountDownLatch, seconds: Long, description: String) {
    val until = minOf(deadline, SystemClock.elapsedRealtime() + seconds * 1000)
    while (latch.count > 0) {
      completion.get()?.let { error(it.second.getString("stream") ?: "Host ended before $description") }
      val remaining = until - SystemClock.elapsedRealtime()
      check(remaining > 0) { "Timed out waiting for $description" }
      latch.await(minOf(remaining, 200), TimeUnit.MILLISECONDS)
    }
  }

  fun run(): File {
    require(Build.VERSION.SDK_INT >= 35) { "mediaProcessing benchmark host requires Android API 35+" }
    require(mode in setOf("activity-and-service", "service-only")) { "Invalid hostMode" }
    require(timeoutMs in 15_000L..18_000_000L) { "Invalid lifecycleTimeoutSeconds" }
    require(root.path.startsWith(context.filesDir.canonicalPath + File.separator)) { "Host root must be private files storage" }
    require(!evidence.exists()) { "Refusing to reuse foreground host evidence" }
    var success = false
    try {
      record("starting_activity")
      val bundle = Bundle().apply { options.forEach { (key, value) -> putString(key, value) } }
      val intent = Intent(context, DenoisingBenchmarkActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        .putExtra(BenchmarkHostContract.OPTIONS, bundle)
        .putExtra(BenchmarkHostContract.RECEIVER, receiver)
      activity = instrumentation.startActivitySync(intent)
      await(ready, 30, "visible Activity and foreground service (unlock the device normally)")
      if (mode == "service-only") {
        var backgrounded = false
        instrumentation.runOnMainSync {
          backgrounded = activity!!.moveTaskToBack(true)
        }
        check(backgrounded) { "Could not background the benchmark Activity" }
        await(stopped, 10, "Activity to stop before service-only work")
      }
      record("starting_processing")
      context.startService(Intent(context, DenoisingBenchmarkService::class.java)
        .setAction(BenchmarkHostContract.RUN))
      val remaining = deadline - SystemClock.elapsedRealtime()
      check(remaining > 0 && finished.await(remaining, TimeUnit.MILLISECONDS)) { "Foreground benchmark deadline exceeded" }
      val result = requireNotNull(completion.get())
      check(result.first == Activity.RESULT_OK) { result.second.getString("stream") ?: "Service processing failed" }
      success = true
      return File(requireNotNull(result.second.getString("resultPath")))
    } catch (error: Throwable) {
      record("host_failed", JSONObject().put("error", error.stackTraceToString()))
      throw error
    } finally {
      instrumentation.runOnMainSync {
        context.stopService(Intent(context, DenoisingBenchmarkService::class.java))
        activity?.intent?.putExtra(BenchmarkHostContract.HARNESS_FINISHED, true)
        activity?.finish()
      }
      val serviceDestroyed = ready.count != 0L || destroyed.await(5, TimeUnit.SECONDS)
      synchronized(this) {
        report.put("status", if (success && serviceDestroyed) "completed" else "failed")
          .put("service_destroyed", destroyed.count == 0L)
          .put("activity_finish_requested", activity != null)
        record("cleanup_finished")
      }
      check(serviceDestroyed) { "Foreground service destruction was not confirmed" }
    }
  }
}

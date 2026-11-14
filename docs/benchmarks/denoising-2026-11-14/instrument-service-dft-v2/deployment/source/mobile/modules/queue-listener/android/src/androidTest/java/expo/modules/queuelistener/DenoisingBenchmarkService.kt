package expo.modules.queuelistener

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.drawable.Icon
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.ResultReceiver
import android.os.SystemClock
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicReference

/** Test-only fixture media processing. No AudioRecord, UI wake flags, or privileged settings. */
class DenoisingBenchmarkService : Service() {
  private val main = Handler(Looper.getMainLooper())
  private var receiver: ResultReceiver? = null
  private var options: Map<String, String> = emptyMap()
  private var wakeLock: PowerManager.WakeLock? = null
  private var worker: Thread? = null
  private var timeoutMs = 0L
  private var startedAt = 0L
  private var foreground = false
  private var notificationsEnabled = false
  @Volatile private var workerFinished = false
  private val cancellation = AtomicReference<String?>(null)
  private val watchdog = Runnable { cancel("lifecycle-deadline") }

  override fun onBind(intent: Intent?): IBinder? = null

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    try {
      when (intent?.action) {
        BenchmarkHostContract.CANCEL -> cancel("user-cancelled")
        BenchmarkHostContract.RUN -> {
          check(foreground && worker == null) { "Service must be prepared exactly once before work" }
          worker = Thread({ processFixtures() }, "cuebell-denoising-benchmark").also { it.start() }
        }
        BenchmarkHostContract.PREPARE -> {
          check(!foreground) { "Benchmark service already active" }
          prepare(intent)
        }
        else -> stopSelf()
      }
    } catch (error: Throwable) {
      receiver?.send(Activity.RESULT_CANCELED, Bundle().apply { putString("stream", error.stackTraceToString()) })
      releaseResources()
      stopSelf()
    }
    return START_NOT_STICKY
  }

  private fun prepare(intent: Intent) {
    receiver = BenchmarkHostContract.receiver(intent)
    val bundle = requireNotNull(intent.getBundleExtra(BenchmarkHostContract.OPTIONS))
    options = bundle.keySet().associateWith { bundle.getString(it).orEmpty() }
    timeoutMs = (options["lifecycleTimeoutSeconds"]?.toLong() ?: 130L) * 1000
    require(timeoutMs in 15_000L..18_000_000L)
    startedAt = SystemClock.elapsedRealtime()
    val manager = getSystemService(NotificationManager::class.java)
    manager.createNotificationChannel(NotificationChannel(CHANNEL, "CueBell fixture processing", NotificationManager.IMPORTANCE_LOW))
    notificationsEnabled = manager.areNotificationsEnabled() &&
      manager.getNotificationChannel(CHANNEL).importance != NotificationManager.IMPORTANCE_NONE
    val open = PendingIntent.getActivity(this, 1,
      Intent(this, DenoisingBenchmarkActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        .putExtras(intent.extras ?: Bundle()), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    val stop = PendingIntent.getService(this, 2,
      Intent(this, DenoisingBenchmarkService::class.java).setAction(BenchmarkHostContract.CANCEL),
      PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    val notification = Notification.Builder(this, CHANNEL)
      .setSmallIcon(android.R.drawable.ic_media_play).setContentTitle("CueBell denoising benchmark")
      .setContentText("Processing prerecorded audio: ${options["label"]}")
      .setCategory(Notification.CATEGORY_SERVICE).setOngoing(true).setOnlyAlertOnce(true)
      .setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE).setContentIntent(open)
      .addAction(Notification.Action.Builder(Icon.createWithResource(this, android.R.drawable.ic_media_pause), "Stop", stop).build())
      .build()
    startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROCESSING)
    foreground = true
    if (options["wakeLock"]?.toBooleanStrict() ?: true) {
      wakeLock = getSystemService(PowerManager::class.java)
        .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "CueBell:fixture-benchmark").apply {
          setReferenceCounted(false)
          acquire(timeoutMs)
        }
    }
    main.postDelayed(watchdog, timeoutMs)
    BenchmarkHostContract.event(receiver, "service_ready", snapshot())
  }

  private fun snapshot(): JSONObject = JSONObject().put("service_type", "mediaProcessing")
    .put("service_component", javaClass.name).put("host_mode", options["hostMode"] ?: "activity-and-service")
    .put("foreground_requested", foreground).put("notifications_enabled", notificationsEnabled)
    .put("wake_lock_requested", options["wakeLock"]?.toBooleanStrict() ?: true)
    .put("wake_lock_held", wakeLock?.isHeld == true).put("wake_lock_timeout_ms", timeoutMs)
    .put("service_started_elapsed_realtime_ms", startedAt).put("microphone_used", false)
    .put("screen_kept_on", false).put("cancellation", cancellation.get() ?: JSONObject.NULL)

  private fun processFixtures() {
    var code = Activity.RESULT_CANCELED
    val result = Bundle()
    try {
      val path = DenoisingBenchmark(options, this, ::snapshot).run()
      check(cancellation.get() == null) { "Benchmark cancelled: ${cancellation.get()}" }
      check(SystemClock.elapsedRealtime() - startedAt < timeoutMs) { "Benchmark lifecycle deadline exceeded" }
      code = Activity.RESULT_OK
      result.putString("resultPath", path.absolutePath)
      result.putString("stream", "Denoising benchmark written to ${path.absolutePath}\n")
    } catch (error: Throwable) {
      result.putString("stream", error.stackTraceToString())
    } finally {
      workerFinished = true
      main.post {
        releaseResources()
        stopSelf()
        receiver?.send(code, result)
      }
    }
  }

  private fun cancel(reason: String) {
    cancellation.compareAndSet(null, reason)
    worker?.interrupt()
    BenchmarkHostContract.event(receiver, "service_cancelled", JSONObject().put("reason", reason))
    releaseResources()
    stopSelf()
    if (worker == null) receiver?.send(Activity.RESULT_CANCELED, Bundle().apply { putString("stream", reason) })
  }

  private fun releaseResources() {
    main.removeCallbacks(watchdog)
    if (wakeLock?.isHeld == true) wakeLock?.release()
    stopForeground(STOP_FOREGROUND_REMOVE)
    foreground = false
    BenchmarkHostContract.event(receiver, "service_resources_released", snapshot())
  }

  override fun onTimeout(startId: Int, fgsType: Int) {
    cancel("android-mediaProcessing-time-limit")
  }

  override fun onDestroy() {
    if (!workerFinished && worker != null) {
      cancellation.compareAndSet(null, "service-destroyed")
      worker?.interrupt()
    }
    releaseResources()
    BenchmarkHostContract.event(receiver, "service_destroyed", snapshot())
    super.onDestroy()
  }

  companion object {
    private const val CHANNEL = "cuebell-fixture-processing"
    private const val NOTIFICATION_ID = 41042
  }
}

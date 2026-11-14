package expo.modules.queuelistener

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioAttributes
import android.media.AudioRecord
import android.media.MediaRecorder
import android.net.Uri
import android.os.*
import androidx.core.app.NotificationCompat
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/** The microphone, network, health checks and alerts never depend on the JS runtime. */
class ListenerService : Service() {
  private val main = Handler(Looper.getMainLooper())
  private val client = OkHttpClient.Builder().connectTimeout(12, TimeUnit.SECONDS)
    .readTimeout(0, TimeUnit.SECONDS).pingInterval(10, TimeUnit.SECONDS).build()
  private var socket: WebSocket? = null
  private var started = false
  private var recorder: AudioRecord? = null
  private var capture: Thread? = null
  private val recording = AtomicBoolean(false)
  private var captureActive: AtomicBoolean? = null
  private var wake: PowerManager.WakeLock? = null
  private var baseUrl = ""
  private var bearer = ""
  private var mode = "monitor"
  private var noiseReductionMode = "off"
  private class DenoiserPreparation { @Volatile var cancelled = false }
  private var denoiserPreparation: DenoiserPreparation? = null
  private var stopping = false
  private var waitingForTask = false
  @Volatile private var generation = 0
  private var retries = 0
  private var lastMessage = 0L
  private var connectedAt = 0L
  private var gapSince = 0L
  private val notificationManager get() = getSystemService(NotificationManager::class.java)
  private val spokenAlerts by lazy { SpokenAlerts(this) }
  private fun t(source: String, vararg values: Pair<String, String>) = AppLanguage.text(this, source, *values)

  override fun onBind(intent: Intent?) = null

  override fun onCreate() {
    super.onCreate()
    AppLanguage.onChange = {
      spokenAlerts.close()
      updateListeningChannel()
      if (started && !stopping) notificationManager.notify(1, foregroundNotification(ListenerMemory.message))
      // Re-render existing alerts silently without replaying vibration, sound or speech.
      notificationManager.activeNotifications.filter { it.tag?.startsWith("queue-alert:") == true }.forEach { active ->
        val alert = active.notification.extras.getString("cuebell.alert")
        if (alert != null) showAlert(JSONObject(alert), true)
      }
    }
    updateListeningChannel()
  }

  private fun updateListeningChannel() {
    if (Build.VERSION.SDK_INT >= 26) notificationManager.createNotificationChannel(NotificationChannel(
      "listening", t("Listening status"), NotificationManager.IMPORTANCE_LOW).apply {
      description = t("Microphone activity and coverage gaps"); setSound(null, null)
      lockscreenVisibility = Notification.VISIBILITY_PRIVATE
    })
  }

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    if (intent?.action == "PAUSE") {
      stopping = true
      status("STOPPING", "Turning off the microphone…")
      pauseOnServer()
      stopSelf()
      return START_NOT_STICKY
    }
    if (intent == null) return START_NOT_STICKY
    if (started) {
      if (!stopping && mode == "request" && waitingForTask &&
          intent.getStringExtra("mode") == "monitor") {
        waitingForTask = false
        main.removeCallbacks(processingTimeout)
        baseUrl = intent.getStringExtra("url") ?: baseUrl
        bearer = intent.getStringExtra("token") ?: bearer
        mode = "monitor"
        noiseReductionMode = intent.getStringExtra("noiseReductionMode") ?: "off"
        ListenerMemory.mode = mode
        ListenerMemory.noiseReductionMode = noiseReductionMode
        retries = 0
        connect()
      }
      return START_NOT_STICKY
    }
    started = true
    baseUrl = intent.getStringExtra("url") ?: ""
    bearer = intent.getStringExtra("token") ?: ""
    mode = intent.getStringExtra("mode") ?: "monitor"
    noiseReductionMode = intent.getStringExtra("noiseReductionMode") ?: "off"
    ListenerMemory.mode = mode
    ListenerMemory.noiseReductionMode = noiseReductionMode
    ListenerMemory.noiseReduction = NoiseReductionDiagnostics.off()
    ListenerMemory.running = true
    if (!NotificationGate.visible(this)) {
      stopping = true; stopSelf()
      status("ERROR", "Enable Android notifications and the Listening status channel before starting.")
      return START_NOT_STICKY
    }
    val notification = foregroundNotification("Connecting… Microphone starts after speech is ready.")
    try {
      if (Build.VERSION.SDK_INT >= 29) startForeground(1, notification,
        ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
      else startForeground(1, notification)
    } catch (_: SecurityException) {
      stopping = true; stopSelf()
      status("ERROR", "Android blocked the microphone. Check permissions and try again.")
      return START_NOT_STICKY
    } catch (_: IllegalStateException) {
      stopping = true; stopSelf()
      status("ERROR", "Open CueBell before starting the microphone.")
      return START_NOT_STICKY
    }
    wake = (getSystemService(POWER_SERVICE) as PowerManager)
      .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "CueBell:Listening").apply {
        setReferenceCounted(false); acquire(4 * 60 * 60 * 1000L)
      }
    connect()
    main.postDelayed(watchdog, 2000)
    return START_NOT_STICKY // Never restart a microphone without a visible user action.
  }

  private fun openApp(): PendingIntent {
    val launch = packageManager.getLaunchIntentForPackage(packageName)!!.apply {
      addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
    }
    return PendingIntent.getActivity(this, 0, launch,
      PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
  }

  private fun foregroundNotification(text: String): Notification {
    val pause = PendingIntent.getService(this, 1,
      Intent(this, ListenerService::class.java).setAction("PAUSE"),
      PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    return NotificationCompat.Builder(this, "listening")
      .setSmallIcon(android.R.drawable.ic_btn_speak_now)
      .setContentTitle(t(if (mode == "request") "CueBell · your request" else "CueBell · monitoring"))
      .setContentText(AppLanguage.status(this, text)).setStyle(NotificationCompat.BigTextStyle().bigText(AppLanguage.status(this, text)))
      .setContentIntent(openApp()).setOngoing(true).setOnlyAlertOnce(true)
      .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
      .addAction(android.R.drawable.ic_media_pause, t("Stop microphone"), pause).build()
  }

  private fun status(state: String, message: String) {
    ListenerMemory.emit(JSONObject().put("type", "status").put("state", state)
      .put("message", message).put("gap_seconds", if (gapSince == 0L) 0 else
        (SystemClock.elapsedRealtime() - gapSince) / 1000))
    if (!stopping) notificationManager.notify(1, foregroundNotification(message))
  }

  private fun connect() {
    if (stopping) return
    val gen = ++generation
    status(if (gapSince > 0) "RECONNECTING" else "STARTING",
      if (gapSince > 0) "Reconnecting. Calls may have been missed." else "Connecting to speech recognition…")
    connectedAt = SystemClock.elapsedRealtime()
    lastMessage = connectedAt
    val url = baseUrl.replaceFirst("https://", "wss://").trimEnd('/') + "/v1/stream?mode=$mode"
    val request = Request.Builder().url(url).header("Authorization", "Bearer $bearer")
      .header("x-processing-consent", "audio-gnani;text-openai").build()
    socket = client.newWebSocket(request, object : WebSocketListener() {
      override fun onMessage(webSocket: WebSocket, text: String) {
        main.post {
          if (gen != generation || stopping) return@post
          lastMessage = SystemClock.elapsedRealtime()
          try {
            if (text.length > 65536) error("Message too large")
            val event = JSONObject(text)
            when (event.optString("type")) {
              "status" -> when (event.optString("state")) {
                "READY" -> {
                  if (gapSince == 0L) status("STARTING", "Starting microphone…")
                  startCapture(gen, webSocket)
                }
                "LISTENING" -> {
                  notificationManager.cancel(2)
                  val gap = if (gapSince > 0) (SystemClock.elapsedRealtime() - gapSince) / 1000 else 0
                  val message = if (gap > 0) "Listening again after a ${gap}s gap. Check the display."
                    else if (mode == "request") "Speak your request. Short pauses are OK; wait for it to finish."
                    else "Listening · keep your phone near the announcement speaker."
                  val fallback = noiseReductionMode == "gtcrn" && ListenerMemory.noiseReduction.fallbackReason != null
                  status("LISTENING", if (fallback) "$message Noise reduction unavailable; using original audio." else message)
                  gapSince = 0
                }
                "DEGRADED", "DISCONNECTED" -> {
                  stopCapture()
                  // The relay follows a terminal status with a close code that decides whether to retry.
                  status("RECONNECTING", "Listening interrupted. Calls may have been missed.")
                }
                // Keep the reconnecting state until audio reaches the relay again.
                "STARTING" -> Unit
                else -> ListenerMemory.emit(event)
              }
              "alert", "alert.corrected" -> {
                ListenerMemory.emit(event)
                showAlert(event)
              }
              "transcript" -> {
                if (mode == "request") {
                  // Keep the user-started foreground service alive during interpretation.
                  // Capture is OFF, but it can resume for the new task even if Home is backgrounded.
                  generation++
                  waitingForTask = true
                  stopCapture()
                  socket?.close(1000, null); socket = null
                  status("PROCESSING", "Creating your listening task…")
                  main.postDelayed(processingTimeout, 45000)
                }
                ListenerMemory.emit(event)
              }
              "monitor.pause", "monitor.stop" -> {
                if (mode == "monitor") {
                  // A semantic voice-stop decision must work with JS suspended. Invalidate
                  // callbacks before releasing capture so stream closure cannot reconnect it.
                  stopping = true
                  generation++
                  stopCapture()
                  spokenAlerts.close()
                  socket?.close(1000, null); socket = null
                  ListenerMemory.emit(event)
                  status("STOPPING", "Turning off the microphone at your request…")
                  stopSelf()
                } else ListenerMemory.emit(event)
              }
              else -> ListenerMemory.emit(event)
            }
          } catch (_: Exception) { fail(gen, "The listening service returned an invalid response. Please try again.") }
        }
      }
      override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
        webSocket.close(code, null)
        val permanent = RelayFailure.isPermanent(code)
        main.post { fail(gen, if (permanent) "The speech service rejected the connection."
          else "Speech stream closed. Calls may have been missed.", permanent) }
      }
      override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        val permanent = RelayFailure.isPermanent(response?.code ?: 0)
        main.post { fail(gen, if (permanent) "Your listening session is unavailable. Submit your request again."
          else "Cannot reach the listening service. Check your internet connection.", permanent) }
      }
    })
  }

  private fun startCapture(gen: Int, stream: WebSocket) {
    if (recording.get()) return
    if (noiseReductionMode != "gtcrn") {
      // Do not load JNI, initialize a processor or allocate enhancement buffers.
      ListenerMemory.noiseReduction = NoiseReductionDiagnostics.off()
      startPreparedCapture(gen, stream, null)
      return
    }
    val previous = denoiserPreparation
    if (previous != null) {
      if (!previous.cancelled) return // Duplicate READY while preloading.
      // A cancelled native constructor cannot safely be interrupted. Bound work
      // to one initializer; a reconnect can immediately use raw capture instead.
      publishNoiseReduction(NoiseReductionDiagnostics(activeMode = "off",
        fallbackReason = "previous_initialization_still_running"))
      startPreparedCapture(gen, stream, null)
      return
    }
    val preparation = DenoiserPreparation()
    denoiserPreparation = preparation
    Thread({
      val reducer = GtcrnNoiseReducer.fromAssets(assets, java.io.File(noBackupFilesDir, "noise-reduction"))
      if (preparation.cancelled) {
        reducer.close()
        main.post { if (denoiserPreparation === preparation) denoiserPreparation = null }
      } else main.post {
        if (denoiserPreparation === preparation) denoiserPreparation = null
        if (preparation.cancelled || gen != generation || stopping) {
          reducer.close()
        } else {
          publishNoiseReduction(reducer.diagnostics)
          startPreparedCapture(gen, stream, reducer)
        }
      }
    }, "CueBell-DenoiserPreload").start()
  }

  private fun publishNoiseReduction(diagnostics: NoiseReductionDiagnostics) {
    ListenerMemory.noiseReduction = diagnostics
    ListenerMemory.emit(diagnostics.json().put("type", "noise_reduction"))
    if (diagnostics.fallbackReason != null && !stopping) {
      status(ListenerMemory.state, "Noise reduction unavailable. Listening with original microphone audio.")
    }
  }

  @Suppress("MissingPermission")
  private fun startPreparedCapture(gen: Int, stream: WebSocket, reducer: GtcrnNoiseReducer?) {
    try {
      val minimum = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO,
        AudioFormat.ENCODING_PCM_16BIT)
      check(minimum > 0)
      val audio = AudioRecord.Builder().setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
        .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT)
          .setSampleRate(16000).setChannelMask(AudioFormat.CHANNEL_IN_MONO).build())
        .setBufferSizeInBytes(maxOf(minimum * 2, 8192)).build()
      check(audio.state == AudioRecord.STATE_INITIALIZED && audio.sampleRate == 16000) {
        audio.release(); "16 kHz microphone capture unavailable"
      }
      recorder = audio
      audio.startRecording()
      check(audio.recordingState == AudioRecord.RECORDSTATE_RECORDING)
      val level = AudioLevel()
      ListenerMemory.audioLevel = level
      recording.set(true)
      val active = AtomicBoolean(true)
      captureActive = active
      capture = Thread({
        Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO)
        val samples = ShortArray(512)
        val enhanced = if (reducer != null) ShortArray(512) else null
        val frame = ByteArray(1024)
        var reportedFallback = reducer?.fallbackReason
        var filled = 0
        var lastFrameAt = SystemClock.elapsedRealtime()
        try {
          while (active.get() && gen == generation) {
            val read = audio.read(samples, filled, 512 - filled, AudioRecord.READ_BLOCKING)
            check(read > 0) { "Microphone interrupted" }
            filled += read
            if (filled < 512) continue
            val now = SystemClock.elapsedRealtime()
            // Never replay stale capture after an OS stall or network backlog.
            check(now - lastFrameAt < 500 && stream.queueSize() < 8192) { "Audio coverage gap" }
            lastFrameAt = now
            if (enhanced != null) {
              reducer!!.process(samples, enhanced)
              if (reducer.fallbackReason != reportedFallback) {
                reportedFallback = reducer.fallbackReason
                val diagnostics = reducer.diagnostics
                main.post { if (gen == generation && !stopping) publishNoiseReduction(diagnostics) }
              }
            }
            if (!active.get() || gen != generation) break
            // Synchronous inference cannot be interrupted. Recheck frame age
            // before sending so a long native stall cannot emit stale audio.
            check(SystemClock.elapsedRealtime() - now < 500 && stream.queueSize() < 8192) {
              "Audio coverage gap"
            }
            // The off branch passes the original samples directly to the original encoder.
            Pcm16.encode(enhanced ?: samples, frame)
            check(stream.send(frame.toByteString())) { "Audio connection closed" }
            level.update(samples)
            filled = 0
          }
        } catch (_: Exception) {
          if (active.get()) main.post { if (active.get())
            fail(gen, "Microphone or audio transport interrupted. Check the display.") }
        } finally {
          val diagnostics = reducer?.diagnostics
          try { reducer?.close() } finally {
            samples.fill(0); enhanced?.fill(0); frame.fill(0)
          }
          if (diagnostics != null) main.post {
            if (gen == generation) ListenerMemory.noiseReduction = diagnostics
          }
        }
      }, "CueBell-PCM").apply { start() }
    } catch (_: Exception) {
      reducer?.close()
      fail(gen, "Microphone unavailable. Close other recording apps and retry.", true)
    }
  }

  private fun stopCapture() {
    denoiserPreparation?.cancelled = true
    captureActive?.set(false)
    captureActive = null
    ListenerMemory.audioLevel = null
    recording.set(false)
    val audio = recorder
    recorder = null
    try { audio?.stop() } catch (_: Exception) { }
    try { capture?.join(600) } catch (_: InterruptedException) { }
    capture = null
    audio?.release()
  }

  private fun fail(gen: Int, reason: String, permanent: Boolean = false) {
    if (stopping || gen != generation) return
    generation++ // Ignore all callbacks from the failed stream.
    stopCapture()
    socket?.cancel(); socket = null
    if (gapSince == 0L) gapSince = SystemClock.elapsedRealtime()
    if (mode == "request" || permanent || retries >= 5) {
      status("ERROR", "$reason Try again from the app.")
      notificationManager.notify(2, NotificationCompat.Builder(this, "listening")
        .setSmallIcon(android.R.drawable.ic_dialog_alert).setContentTitle(t("CueBell stopped listening"))
        .setContentText(t("A call may have been missed. Open the app and reconnect."))
        .setContentIntent(openApp()).setAutoCancel(true).build())
      stopping = true; stopSelf()
    } else {
      val delay = (1000L shl retries++)
      status("RECONNECTING", "$reason Retrying in ${delay / 1000}s.")
      main.postDelayed({ connect() }, delay)
    }
  }

  private val watchdog = object : Runnable {
    override fun run() {
      if (stopping) return
      val now = SystemClock.elapsedRealtime()
      if (!NotificationGate.visible(this@ListenerService)) {
        fail(generation, "Listening notification is disabled. Enable it in Android settings.", true)
      }
      if (Build.VERSION.SDK_INT >= 29 && recorder?.activeRecordingConfiguration?.isClientSilenced == true) {
        fail(generation, "Android silenced the microphone. Check microphone privacy settings.", true)
      }
      if (socket != null && now - lastMessage > 20000) fail(generation,
        "No listening heartbeat. Calls may have been missed.")
      if (recording.get() && now - connectedAt > 30000) retries = 0
      main.postDelayed(this, 2000)
    }
  }

  private val processingTimeout = Runnable {
    if (!stopping && waitingForTask)
      fail(generation, "Could not create a listening task. Open the app and try again.", true)
  }

  private fun showAlert(event: JSONObject, silent: Boolean = false) {
    val alert = event.getJSONObject("alert")
    val corrected = event.optString("type") == "alert.corrected"
    val preferences = alert.optJSONArray("alert_preferences")?.let { list ->
      (0 until list.length()).map { list.getString(it) }
    } ?: listOf("visual")
    val vibration = "vibration" in preferences
    val sound = "sound" in preferences
    // Version the channel: Android will not update an existing channel's sound.
    val channel = "calls-v3-${if (vibration) 1 else 0}-${if (sound) 1 else 0}"
    val alarmSound = Uri.parse("android.resource://$packageName/raw/cuebell_alarm")
    if (Build.VERSION.SDK_INT >= 26) notificationManager.createNotificationChannel(NotificationChannel(channel,
      "${t("Listening alerts")}${if (vibration) " · ${t("Vibrate")}" else ""}${if (sound) " · ${t("Alarm sound")}" else ""}",
      NotificationManager.IMPORTANCE_HIGH).apply {
      enableVibration(vibration)
      if (vibration) vibrationPattern = longArrayOf(0, 400, 200, 400, 200, 700)
      setSound(if (sound) alarmSound else null, if (sound) AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_ALARM)
        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build() else null)
      lockscreenVisibility = Notification.VISIBILITY_PRIVATE
    })
    val id = alert.getString("id")
    val tag = "queue-alert:$id"
    notificationManager.activeNotifications.filter { it.tag?.startsWith("queue-alert:") == true && it.tag != tag }
      .sortedBy { it.postTime }.dropLast(19).forEach { notificationManager.cancel(it.tag, it.id) }
    val counter = if (alert.isNull("counter")) t("Counter unknown — check the display.")
      else t("Go to counter {counter}.", "counter" to alert.getString("counter"))
    val summary = if (alert.isNull("summary")) "" else alert.optString("summary")
    val title = if (corrected) t("Correction · check the announcement") else if (summary.isNotBlank()) t("Event detected") else t("It's your turn!")
    val text = if (corrected) t("The previous alert was corrected or cancelled. Check the official source.")
      else if (summary.isNotBlank()) summary
      else t("Token {token}. {counter}", "token" to alert.optString("token", ""), "counter" to counter)
    notificationManager.notify(tag, 100, NotificationCompat.Builder(this, channel)
      .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(title).setContentText(text)
      .addExtras(Bundle().apply { putString("cuebell.alert", JSONObject().put("type", event.optString("type"))
        .put("alert", JSONObject().put("id", id).put("token", alert.opt("token"))
          .put("summary", alert.opt("summary"))
          .put("counter", alert.opt("counter")).put("alert_preferences", alert.optJSONArray("alert_preferences"))).toString()) })
      .setOnlyAlertOnce(silent).setSilent(silent)
      .setStyle(NotificationCompat.BigTextStyle().bigText(text)).setContentIntent(openApp())
      .setPriority(NotificationCompat.PRIORITY_HIGH).setCategory(NotificationCompat.CATEGORY_ALARM)
      .setSound(if (sound) alarmSound else null, android.media.AudioManager.STREAM_ALARM)
      .setVibrate(if (vibration) longArrayOf(0, 400, 200, 400, 200, 700) else longArrayOf(0))
      .setVisibility(NotificationCompat.VISIBILITY_PRIVATE).setAutoCancel(true)
      .setPublicVersion(NotificationCompat.Builder(this, channel)
        .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(t("CueBell alert"))
        .setContentText(t("Open the app to check your listening alert.")).build()).build())
    if (sound && !corrected && !silent) {
      val token = alert.optString("token", "").toList().joinToString(" ")
      runCatching { spokenAlerts.speak(id, if (summary.isNotBlank()) summary else t("It's your turn. Token {token}. {counter}", "token" to token, "counter" to counter)) }
    }
  }

  private fun pauseOnServer() {
    if (mode != "monitor" || bearer.isEmpty()) return
    val body = "{\"action\":\"pause\"}".toRequestBody("application/json".toMediaType())
    client.newCall(Request.Builder().url("${baseUrl.trimEnd('/')}/v1/control")
      .header("Authorization", "Bearer $bearer").post(body).build()).enqueue(object : Callback {
      override fun onFailure(call: Call, e: IOException) { }
      override fun onResponse(call: Call, response: Response) { response.close() }
    })
  }

  override fun onDestroy() {
    AppLanguage.onChange = null
    stopping = true; generation++
    main.removeCallbacksAndMessages(null)
    stopCapture()
    spokenAlerts.close()
    socket?.cancel(); socket = null
    if (wake?.isHeld == true) wake?.release()
    wake = null
    bearer = ""
    ListenerMemory.running = false
    if (ListenerMemory.state == "ERROR") status("ERROR", ListenerMemory.message)
    else status("STOPPED", "Microphone is off.")
    stopForeground(STOP_FOREGROUND_REMOVE)
    super.onDestroy()
  }
}

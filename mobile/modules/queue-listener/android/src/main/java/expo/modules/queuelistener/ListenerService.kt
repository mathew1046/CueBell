package expo.modules.queuelistener

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
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
  private var recorder: AudioRecord? = null
  private var capture: Thread? = null
  private val recording = AtomicBoolean(false)
  private var wake: PowerManager.WakeLock? = null
  private var baseUrl = ""
  private var bearer = ""
  private var mode = "monitor"
  private var stopping = false
  private var generation = 0
  private var retries = 0
  private var lastMessage = 0L
  private var connectedAt = 0L
  private var gapSince = 0L
  private val notificationManager get() = getSystemService(NotificationManager::class.java)

  override fun onBind(intent: Intent?) = null

  override fun onCreate() {
    super.onCreate()
    if (Build.VERSION.SDK_INT >= 26) notificationManager.createNotificationChannel(NotificationChannel(
      "listening", "Listening status", NotificationManager.IMPORTANCE_LOW).apply {
      description = "Microphone activity and coverage gaps"; setSound(null, null)
      lockscreenVisibility = Notification.VISIBILITY_PRIVATE
    })
  }

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    if (intent?.action == "PAUSE") {
      pauseOnServer()
      stopSelf()
      return START_NOT_STICKY
    }
    if (ListenerMemory.running || intent == null) return START_NOT_STICKY
    baseUrl = intent.getStringExtra("url") ?: ""
    bearer = intent.getStringExtra("token") ?: ""
    mode = intent.getStringExtra("mode") ?: "monitor"
    ListenerMemory.mode = mode
    ListenerMemory.running = true
    if (!NotificationGate.visible(this)) {
      status("DISCONNECTED", "Enable Android notifications and the Listening status channel before starting.")
      stopping = true; stopSelf()
      return START_NOT_STICKY
    }
    val notification = foregroundNotification("Connecting… Microphone starts after speech is ready.")
    if (Build.VERSION.SDK_INT >= 29) startForeground(1, notification,
      ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
    else startForeground(1, notification)
    wake = (getSystemService(POWER_SERVICE) as PowerManager)
      .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "QueueSaathi:Listening").apply {
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
      .setContentTitle(if (mode == "request") "QueueSaathi · your request" else "QueueSaathi · monitoring")
      .setContentText(text).setStyle(NotificationCompat.BigTextStyle().bigText(text))
      .setContentIntent(openApp()).setOngoing(true).setOnlyAlertOnce(true)
      .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
      .addAction(android.R.drawable.ic_media_pause, "Stop microphone", pause).build()
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
    status(if (gapSince > 0) "DEGRADED" else "STARTING",
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
                  status("STARTING", "Starting microphone…")
                  startCapture(gen, webSocket)
                }
                "LISTENING" -> {
                  val gap = if (gapSince > 0) (SystemClock.elapsedRealtime() - gapSince) / 1000 else 0
                  status("LISTENING", if (gap > 0) "Listening again after a ${gap}s gap. Check the display."
                    else if (mode == "request") "Speak your request, then pause."
                    else "Listening · keep your phone near the announcement speaker.")
                  gapSince = 0
                }
                "DEGRADED", "DISCONNECTED" -> fail(gen, "Listening interrupted. Calls may be missed.")
                else -> ListenerMemory.emit(event)
              }
              "alert", "alert.corrected" -> {
                ListenerMemory.emit(event)
                showAlert(event)
              }
              "transcript" -> {
                ListenerMemory.emit(event)
                if (mode == "request") {
                  stopping = true
                  stopSelf()
                }
              }
              else -> ListenerMemory.emit(event)
            }
          } catch (_: Exception) { fail(gen, "The listening service returned an invalid response. Please try again.") }
        }
      }
      override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
        webSocket.close(code, null)
        main.post { fail(gen, "Speech stream closed. Calls may have been missed.", RelayFailure.isPermanent(code)) }
      }
      override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        val permanent = RelayFailure.isPermanent(response?.code ?: 0)
        main.post { fail(gen, if (permanent) "Your listening session is unavailable. Submit your request again."
          else "Cannot reach the listening service. Check your internet connection.", permanent) }
      }
    })
  }

  @Suppress("MissingPermission")
  private fun startCapture(gen: Int, stream: WebSocket) {
    if (recording.get()) return
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
      recording.set(true)
      capture = Thread({
        Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO)
        val samples = ShortArray(512)
        val frame = ByteArray(1024)
        var filled = 0
        var lastFrameAt = SystemClock.elapsedRealtime()
        try {
          while (recording.get() && gen == generation) {
            val read = audio.read(samples, filled, 512 - filled, AudioRecord.READ_BLOCKING)
            check(read > 0) { "Microphone interrupted" }
            filled += read
            if (filled < 512) continue
            val now = SystemClock.elapsedRealtime()
            // Never replay stale capture after an OS stall or network backlog.
            check(now - lastFrameAt < 500 && stream.queueSize() < 8192) { "Audio coverage gap" }
            lastFrameAt = now
            Pcm16.encode(samples, frame)
            check(stream.send(frame.toByteString())) { "Audio connection closed" }
            filled = 0
          }
        } catch (_: Exception) {
          main.post { fail(gen, "Microphone or audio transport interrupted. Check the display.") }
        } finally { samples.fill(0); frame.fill(0) }
      }, "QueueSaathi-PCM").apply { start() }
    } catch (_: Exception) { fail(gen, "Microphone unavailable. Close other recording apps and retry.", true) }
  }

  private fun stopCapture() {
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
      status("DISCONNECTED", "$reason Open the app to try again.")
      notificationManager.notify(2, NotificationCompat.Builder(this, "listening")
        .setSmallIcon(android.R.drawable.ic_dialog_alert).setContentTitle("QueueSaathi stopped listening")
        .setContentText("A call may have been missed. Open the app and reconnect.")
        .setContentIntent(openApp()).setAutoCancel(true).build())
      stopping = true; stopSelf()
    } else {
      val delay = (1000L shl retries++)
      status("DEGRADED", "$reason Retrying in ${delay / 1000}s.")
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

  private fun showAlert(event: JSONObject) {
    val alert = event.getJSONObject("alert")
    val corrected = event.optString("type") == "alert.corrected"
    val preferences = alert.optJSONArray("alert_preferences")?.let { list ->
      (0 until list.length()).map { list.getString(it) }
    } ?: listOf("visual")
    val vibration = "vibration" in preferences
    val sound = "sound" in preferences
    val channel = "calls-${if (vibration) 1 else 0}-${if (sound) 1 else 0}"
    if (Build.VERSION.SDK_INT >= 26) notificationManager.createNotificationChannel(NotificationChannel(channel,
      "Token calls${if (vibration) " · vibration" else ""}${if (sound) " · sound" else ""}",
      NotificationManager.IMPORTANCE_HIGH).apply {
      enableVibration(vibration)
      if (vibration) vibrationPattern = longArrayOf(0, 400, 200, 400, 200, 700)
      if (!sound) setSound(null, null)
      lockscreenVisibility = Notification.VISIBILITY_PRIVATE
    })
    val id = alert.getString("id")
    val tag = "queue-alert:$id"
    notificationManager.activeNotifications.filter { it.tag?.startsWith("queue-alert:") == true && it.tag != tag }
      .sortedBy { it.postTime }.dropLast(19).forEach { notificationManager.cancel(it.tag, it.id) }
    val counter = if (alert.isNull("counter")) "Counter unknown — check the display."
      else "Go to counter ${alert.getString("counter")}."
    val title = if (corrected) "Correction · check the announcement" else "Token ${alert.getString("token")} called"
    val text = if (corrected) "The previous call was changed or cancelled. Check the app and official display." else counter
    notificationManager.notify(tag, 100, NotificationCompat.Builder(this, channel)
      .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(title).setContentText(text)
      .setStyle(NotificationCompat.BigTextStyle().bigText(text)).setContentIntent(openApp())
      .setPriority(NotificationCompat.PRIORITY_HIGH).setCategory(NotificationCompat.CATEGORY_EVENT)
      .setDefaults(if (sound) Notification.DEFAULT_SOUND else 0)
      .setVibrate(if (vibration) longArrayOf(0, 400, 200, 400, 200, 700) else longArrayOf(0))
      .setVisibility(NotificationCompat.VISIBILITY_PRIVATE).setAutoCancel(true)
      .setPublicVersion(NotificationCompat.Builder(this, channel)
        .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("QueueSaathi alert")
        .setContentText("Open the app to check your queue announcement.").build()).build())
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
    stopping = true; generation++
    main.removeCallbacksAndMessages(null)
    stopCapture()
    socket?.close(1000, "Microphone stopped"); socket = null
    if (wake?.isHeld == true) wake?.release()
    wake = null
    bearer = ""
    ListenerMemory.running = false
    if (ListenerMemory.state != "DISCONNECTED") status("STOPPED", "Microphone is off.")
    stopForeground(STOP_FOREGROUND_REMOVE)
    super.onDestroy()
  }
}

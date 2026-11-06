package expo.modules.queuelistener

import android.Manifest
import android.content.Intent
import android.content.Context
import android.app.NotificationManager
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.core.app.NotificationManagerCompat
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import org.json.JSONObject
import java.util.concurrent.CopyOnWriteArraySet

object NotificationGate {
  fun visible(context: Context): Boolean = NotificationManagerCompat.from(context).areNotificationsEnabled() &&
    (Build.VERSION.SDK_INT < 26 || context.getSystemService(NotificationManager::class.java)
      .getNotificationChannel("listening")?.importance != NotificationManager.IMPORTANCE_NONE)
}

/** Memory only. No transcript, token, credential or audio files are written. */
object ListenerMemory {
  private val history = ArrayDeque<String>()
  val observers = CopyOnWriteArraySet<(String) -> Unit>()
  @Volatile var running = false
  @Volatile var state = "STOPPED"
  @Volatile var message = "Microphone is off."
  @Volatile var mode = "monitor"
  @Synchronized fun emit(event: JSONObject) {
    if (event.optString("type") == "status") {
      state = event.optString("state")
      message = event.optString("message")
    }
    val raw = event.toString()
    if (event.optString("type") !in listOf("heartbeat", "pong")) {
      if (history.size >= 100) history.removeFirst()
      history.addLast(raw)
    }
    observers.forEach { it(raw) }
  }
  @Synchronized fun snapshot(): String = JSONObject().put("running", running)
    .put("state", state).put("message", message).put("mode", mode)
    .put("events", org.json.JSONArray(history.toList().map { JSONObject(it) })).toString()
  @Synchronized fun clear() { history.clear() }
}

class QueueListenerModule : Module() {
  private val observer: (String) -> Unit = { raw -> sendEvent("onEvent", mapOf("json" to raw)) }
  override fun definition() = ModuleDefinition {
    Name("QueueListener")
    Events("onEvent")
    OnStartObserving("onEvent") { ListenerMemory.observers.add(observer) }
    OnStopObserving("onEvent") { ListenerMemory.observers.remove(observer) }
    OnDestroy { ListenerMemory.observers.remove(observer) }
    Function("snapshot") { ListenerMemory.snapshot() }
    Function("clear") {
      ListenerMemory.clear()
      val manager = appContext.reactContext?.getSystemService(android.app.NotificationManager::class.java)
      manager?.activeNotifications?.filter { it.id != 1 }?.forEach { manager.cancel(it.tag, it.id) }
    }
    Function("dismissAlert") { id: String ->
      appContext.reactContext?.getSystemService(NotificationManager::class.java)?.cancel("queue-alert:$id", 100)
    }
    AsyncFunction("start") { baseUrl: String, token: String, mode: String ->
      val context = appContext.reactContext ?: error("App unavailable.")
      val activity = appContext.activityProvider?.currentActivity
        ?: error("Open the app before starting the microphone.")
      check(activity.hasWindowFocus()) { "Keep the app visible while starting the microphone." }
      check(baseUrl.startsWith("https://") && mode in listOf("request", "monitor")) {
        "A secure HTTPS backend URL is required."
      }
      check(ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
        PackageManager.PERMISSION_GRANTED) { "Microphone permission is required." }
      if (Build.VERSION.SDK_INT >= 33) {
        check(ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
          PackageManager.PERMISSION_GRANTED) { "Allow notifications before background listening." }
      }
      check(!ListenerMemory.running) { "Stop the current microphone session first." }
      check(NotificationGate.visible(context)) { "Enable Android notifications and the Listening status channel before starting." }
      val intent = Intent(context, ListenerService::class.java)
        .putExtra("url", baseUrl).putExtra("token", token).putExtra("mode", mode)
      ContextCompat.startForegroundService(context, intent)
    }
    AsyncFunction("stop") {
      val context = appContext.reactContext ?: return@AsyncFunction false
      context.stopService(Intent(context, ListenerService::class.java))
    }
  }
}

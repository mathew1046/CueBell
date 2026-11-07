package expo.modules.queuelistener

import android.content.Context
import android.media.AudioAttributes
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.view.accessibility.AccessibilityManager
import java.util.Locale

internal class SpokenAlerts(private val context: Context) {
  private val main = Handler(Looper.getMainLooper())
  private var engine: TextToSpeech? = null
  private var ready = false
  private val pending = PendingSpeech()

  fun speak(id: String, text: String) {
    if (!allowed()) return
    val tts = engine
    if (ready && tts != null) {
      tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, id)
      return
    }
    pending.add(id, text)
    if (tts != null) return
    engine = TextToSpeech(context) { status ->
      main.post {
        val initialized = engine ?: return@post
        val locale = Locale.forLanguageTag(AppLanguage.language(context))
        val voice = if (status == TextToSpeech.SUCCESS) runCatching {
          initialized.voices?.firstOrNull {
            it.locale.language == locale.language && !it.isNetworkConnectionRequired &&
              it.features?.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED) != true
          }
        }.getOrNull() else null
        // Only use an installed offline voice for private token details.
        if (voice == null || voice.isNetworkConnectionRequired ||
          voice.features?.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED) == true) {
          close()
          return@post
        }
        val attributes = AudioAttributes.Builder()
          .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
          .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
        ready = runCatching { initialized.setVoice(voice) == TextToSpeech.SUCCESS &&
          initialized.setAudioAttributes(attributes) == TextToSpeech.SUCCESS }.getOrDefault(false)
        val alerts = pending.drain()
        if (ready) for ((id, text) in alerts) {
          if (!allowed()) break
          // QUEUE_FLUSH here would discard every earlier initialization-time alert.
          runCatching { initialized.speak(text, TextToSpeech.QUEUE_ADD, null, id) }
        }
      }
    }
  }

  private fun allowed() = enabled(context) &&
    !context.getSystemService(AccessibilityManager::class.java).isTouchExplorationEnabled

  fun close() {
    pending.clear()
    ready = false
    engine?.shutdown()
    engine = null
  }

  companion object {
    fun enabled(context: Context): Boolean =
      context.getSharedPreferences("cuebell.accessibility", Context.MODE_PRIVATE).getBoolean("spoken_alerts", false)

    fun setEnabled(context: Context, enabled: Boolean) {
      context.getSharedPreferences("cuebell.accessibility", Context.MODE_PRIVATE)
        .edit().putBoolean("spoken_alerts", enabled).apply()
    }
  }
}

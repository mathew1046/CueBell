package expo.modules.queuelistener

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.json.JSONObject

/** Only public UI strings and the language choice are persisted, never queue details. */
internal object AppLanguage {
  var onChange: (() -> Unit)? = null
  fun language(context: Context): String = preferences(context).getString("language", "en") ?: "en"
  private fun preferences(context: Context) = context.getSharedPreferences("cuebell.language", Context.MODE_PRIVATE)

  fun set(context: Context, language: String, catalog: String) {
    JSONObject(catalog) // Validate before replacing the stored catalog.
    preferences(context).edit().putString("language", language).putString("catalog", catalog).apply()
    Handler(Looper.getMainLooper()).post { onChange?.invoke() }
  }

  fun text(context: Context, source: String, vararg values: Pair<String, String>): String {
    val catalog = runCatching { JSONObject(preferences(context).getString("catalog", "{}") ?: "{}") }.getOrDefault(JSONObject())
    var result = catalog.optString(source, source)
    val rtl = language(context) in listOf("ur", "ks", "sd")
    for ((key, value) in values) result = result.replace("{$key}", if (rtl) "\u2068$value\u2069" else value)
    return result
  }

  fun status(context: Context, source: String): String {
    Regex("^Listening again after a (\\d+)s gap\\. Check the display\\.$").matchEntire(source)?.let {
      return text(context, "Listening again after a {seconds}s gap. Check the display.", "seconds" to it.groupValues[1])
    }
    Regex("^(.*) Retrying in (\\d+)s\\.$").matchEntire(source)?.let {
      return status(context, it.groupValues[1]) + " " + text(context, "Retrying in {seconds}s.", "seconds" to it.groupValues[2])
    }
    val suffix = " Try again from the app."
    if (source.endsWith(suffix)) return status(context, source.removeSuffix(suffix)) + " " + text(context, "Try again from the app.")
    return text(context, source)
  }
}

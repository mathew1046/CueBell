package expo.modules.queuelistener

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.os.ResultReceiver
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject

/** Visible test host; never turns on, unlocks, or keeps on the screen. */
class DenoisingBenchmarkActivity : Activity() {
  private var receiver: ResultReceiver? = null
  private var serviceRequested = false
  private var cancelRequested = false

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    receiver = BenchmarkHostContract.receiver(intent)
    val options = requireNotNull(intent.getBundleExtra(BenchmarkHostContract.OPTIONS))
    val padding = (24 * resources.displayMetrics.density).toInt()
    val layout = LinearLayout(this).apply {
      orientation = LinearLayout.VERTICAL
      setPadding(padding, padding, padding, padding)
    }
    layout.addView(TextView(this).apply {
      textSize = 20f
      text = "CueBell denoising benchmark\n\n${options.getString("label")}\n" +
        "Host: ${options.getString("hostMode", "activity-and-service")}\n\n" +
        "Processing prerecorded audio fixtures. No microphone or provider calls.\n" +
        "The screen follows its normal timeout."
    })
    layout.addView(Button(this).apply {
      text = "Stop benchmark"
      setOnClickListener { cancel(); finish() }
    })
    setContentView(layout)
    BenchmarkHostContract.event(receiver, "activity_created")
  }

  override fun onWindowFocusChanged(hasFocus: Boolean) {
    super.onWindowFocusChanged(hasFocus)
    BenchmarkHostContract.event(receiver, "activity_window_focus", JSONObject().put("has_focus", hasFocus))
    if (hasFocus && !serviceRequested && !isFinishing) {
      serviceRequested = true
      try {
        startForegroundService(Intent(this, DenoisingBenchmarkService::class.java)
          .setAction(BenchmarkHostContract.PREPARE)
          .putExtra(BenchmarkHostContract.OPTIONS, intent.getBundleExtra(BenchmarkHostContract.OPTIONS))
          .putExtra(BenchmarkHostContract.RECEIVER, receiver))
      } catch (error: Throwable) {
        receiver?.send(RESULT_CANCELED, Bundle().apply { putString("stream", error.stackTraceToString()) })
      }
    }
  }

  override fun onResume() {
    super.onResume()
    BenchmarkHostContract.event(receiver, "activity_resumed")
  }

  override fun onPause() {
    BenchmarkHostContract.event(receiver, "activity_paused")
    super.onPause()
  }

  override fun onStop() {
    BenchmarkHostContract.event(receiver, "activity_stopped")
    super.onStop()
  }

  private fun cancel() {
    if (cancelRequested) return
    cancelRequested = true
    if (serviceRequested) {
      startService(Intent(this, DenoisingBenchmarkService::class.java).setAction(BenchmarkHostContract.CANCEL))
    } else {
      receiver?.send(RESULT_CANCELED, Bundle().apply { putString("stream", "Activity closed before service start") })
    }
  }

  override fun onDestroy() {
    if (isFinishing && !intent.getBooleanExtra(BenchmarkHostContract.HARNESS_FINISHED, false)) cancel()
    BenchmarkHostContract.event(receiver, "activity_destroyed")
    super.onDestroy()
  }
}

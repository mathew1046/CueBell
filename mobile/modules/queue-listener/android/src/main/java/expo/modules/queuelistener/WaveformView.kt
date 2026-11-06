package expo.modules.queuelistener

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.os.SystemClock
import expo.modules.kotlin.AppContext
import expo.modules.kotlin.views.ExpoView

/** Draws about one second of microphone level history on the display's frame clock. */
class WaveformView(context: Context, appContext: AppContext) : ExpoView(context, appContext) {
  private val barCount = 37
  private val history = FloatArray(barCount + 1)
  private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
  private var newest = 0
  private var sampledAt = 0L

  var animate = false
    set(value) {
      field = value
      invalidate()
    }

  init {
    setWillNotDraw(false)
    importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
  }

  fun setBarColor(color: Int) {
    paint.color = color
    invalidate()
  }

  override fun onWindowVisibilityChanged(visibility: Int) {
    super.onWindowVisibilityChanged(visibility)
    if (visibility == VISIBLE) invalidate() else sampledAt = 0
  }

  override fun onDraw(canvas: Canvas) {
    super.onDraw(canvas)
    val level = ListenerMemory.audioLevel
    val active = animate && level != null && isShown && windowVisibility == VISIBLE
    val now = SystemClock.uptimeMillis()
    if (!active || now - sampledAt > 100) {
      history.fill(0f)
      sampledAt = now
    }
    if (active && now - sampledAt >= 32) {
      newest = (newest + 1) % history.size
      history[newest] = level.value
      sampledAt += 32
    }
    val blend = ((now - sampledAt) / 32f).coerceAtMost(1f)
    val step = width.toFloat() / barCount
    val radius = minOf(step * 0.21f, resources.displayMetrics.density * 1.75f)
    val center = height / 2f
    for (bar in 0 until barCount) {
      val index = (newest + bar + 2) % history.size
      val previous = (index + history.size - 1) % history.size
      val amplitude = history[previous] + (history[index] - history[previous]) * blend
      val half = radius + amplitude * center * 0.9f
      val x = (bar + 0.5f) * step
      canvas.drawRoundRect(x - radius, center - half, x + radius, center + half, radius, radius, paint)
    }
    if (active) postInvalidateOnAnimation()
  }
}

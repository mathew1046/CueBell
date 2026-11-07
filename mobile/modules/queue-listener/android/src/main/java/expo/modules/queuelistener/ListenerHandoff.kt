package expo.modules.queuelistener

/** Only continue an already user-started foreground request; never start fresh in the background. */
object ListenerHandoff {
  fun allowed(running: Boolean, currentMode: String, state: String, nextMode: String): Boolean =
    running && currentMode == "request" && state == "PROCESSING" && nextMode == "monitor"
}

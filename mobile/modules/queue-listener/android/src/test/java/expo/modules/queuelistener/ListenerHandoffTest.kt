package expo.modules.queuelistener

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ListenerHandoffTest {
  @Test fun continuesOnlyTheCompletedForegroundRequest() {
    assertTrue(ListenerHandoff.allowed(true, "request", "PROCESSING", "monitor"))
    for (state in listOf("STARTING", "READY", "LISTENING", "STOPPING", "STOPPED", "ERROR")) {
      assertFalse(ListenerHandoff.allowed(true, "request", state, "monitor"))
    }
  }

  @Test fun neverRestartsStoppedOrUnrelatedMicrophones() {
    assertFalse(ListenerHandoff.allowed(false, "request", "PROCESSING", "monitor"))
    assertFalse(ListenerHandoff.allowed(true, "monitor", "PROCESSING", "monitor"))
    assertFalse(ListenerHandoff.allowed(true, "request", "PROCESSING", "request"))
  }
}

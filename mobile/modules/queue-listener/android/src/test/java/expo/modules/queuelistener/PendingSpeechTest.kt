package expo.modules.queuelistener

import org.junit.Assert.*
import org.junit.Test

class PendingSpeechTest {
  @Test fun distinctInitializationAlertsDrainInOrderExactlyOnce() {
    val pending = PendingSpeech()
    pending.add("a", "Token A")
    pending.add("b", "Token B")
    pending.add("c", "Token C")
    assertEquals(listOf("a" to "Token A", "b" to "Token B", "c" to "Token C"), pending.drain())
    assertTrue(pending.drain().isEmpty())
  }

  @Test fun duplicateIdsReplaceTextWithoutDuplicatingOrReorderingSpeech() {
    val pending = PendingSpeech()
    pending.add("a", "Token A")
    pending.add("b", "Token B")
    pending.add("a", "Updated token A")
    assertEquals(listOf("a" to "Updated token A", "b" to "Token B"), pending.drain())
  }

  @Test fun backlogIsBoundedAndCloseDiscardsPrivateSpeech() {
    val pending = PendingSpeech(2)
    pending.add("a", "Token A")
    pending.add("b", "Token B")
    pending.add("c", "Token C")
    assertEquals(listOf("b" to "Token B", "c" to "Token C"), pending.drain())
    pending.add("d", "Token D")
    pending.clear()
    assertTrue(pending.drain().isEmpty())
  }
}

package expo.modules.queuelistener

/** Bounded initialization backlog; repeat delivery replaces text without duplicating an ID. */
internal class PendingSpeech(private val capacity: Int = 20) {
  private val items = linkedMapOf<String, String>()

  fun add(id: String, text: String) {
    items[id] = text
    if (items.size > capacity) items.remove(items.keys.first())
  }

  fun drain(): List<Pair<String, String>> {
    val result = items.map { it.key to it.value }
    clear()
    return result
  }

  fun clear() { items.clear() }
}

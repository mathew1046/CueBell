package expo.modules.queuelistener

/** A rejected upgrade is HTTP, whereas an already accepted stream uses application close codes. */
internal object RelayFailure {
  fun isPermanent(code: Int): Boolean = code == 401 || code == 403 || code == 4401 || code == 4403
}

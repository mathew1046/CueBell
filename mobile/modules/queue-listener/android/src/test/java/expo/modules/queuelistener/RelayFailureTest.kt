package expo.modules.queuelistener

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.junit.Assert.*
import org.junit.Test
import java.net.InetAddress
import java.net.ServerSocket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

class RelayFailureTest {
  @Test fun authenticationFailuresArePermanentBeforeAndAfterUpgrade() {
    for (code in listOf(401, 403, 4401, 4403)) assertTrue("code=$code", RelayFailure.isPermanent(code))
  }

  @Test fun temporaryFailuresStillAllowReconnect() {
    for (code in listOf(0, 1000, 1001, 1006, 1011, 409, 429, 500, 502, 503, 504)) {
      assertFalse("code=$code", RelayFailure.isPermanent(code))
    }
  }

  @Test fun rejectedUpgradeReachesFailureCallbackAsHttpNotWebSocketClose() {
    val server = ServerSocket(0, 1, InetAddress.getByName("127.0.0.1")).apply { soTimeout = 5000 }
    val responseCode = AtomicInteger(0)
    val closeCode = AtomicInteger(0)
    val completed = CountDownLatch(1)
    val responder = Thread {
      server.accept().use { peer ->
        peer.soTimeout = 5000
        val input = peer.getInputStream().bufferedReader()
        while (true) {
          val line = input.readLine() ?: break
          if (line.isEmpty()) break
        }
        peer.getOutputStream().write("HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
      }
    }.apply { start() }
    val client = OkHttpClient()
    val socket = client.newWebSocket(Request.Builder().url("http://127.0.0.1:${server.localPort}/v1/stream").build(),
      object : WebSocketListener() {
        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
          responseCode.set(response?.code ?: 0)
          response?.close()
          completed.countDown()
        }
        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
          closeCode.set(code)
          completed.countDown()
        }
      })
    try {
      assertTrue("Expected rejected WebSocket upgrade", completed.await(5, TimeUnit.SECONDS))
      assertEquals(403, responseCode.get())
      assertEquals(0, closeCode.get())
      assertTrue(RelayFailure.isPermanent(responseCode.get()))
    } finally {
      socket.cancel()
      server.close()
      responder.join(1000)
      client.dispatcher.executorService.shutdownNow()
      client.connectionPool.evictAll()
    }
  }
}

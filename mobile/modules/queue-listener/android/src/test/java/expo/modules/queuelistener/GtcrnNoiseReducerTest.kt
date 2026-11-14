package expo.modules.queuelistener

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class GtcrnNoiseReducerTest {
  @get:Rule val folder = TemporaryFolder()

  @Test fun missingFileFailsOpenBeforeAnyJniLibraryIsLoaded() {
    val reducer = GtcrnNoiseReducer(File(folder.root, "missing.onnx").path)
    val input = ShortArray(512) { (it * 197 - 32768).toShort() }
    val output = ShortArray(512)
    reducer.process(input, output)
    assertArrayEquals(input, output)
    assertEquals("initialization_error:FileNotFoundException", reducer.fallbackReason)
    assertEquals("off", reducer.diagnostics.activeMode)
    assertEquals(0, reducer.diagnostics.algorithmicDelaySamples)
    assertEquals(0, reducer.diagnostics.startupPaddingSamples)
    assertTrue(reducer.diagnostics.initializationNanos > 0)
    reducer.close()
    reducer.close()
  }

  @Test fun untrustedOrTruncatedModelNeverReachesNativeConstructor() {
    val model = folder.newFile("invalid.onnx")
    model.writeBytes(byteArrayOf(1, 2, 3))
    val reducer = GtcrnNoiseReducer(model.path)
    val input = ShortArray(512) { Short.MAX_VALUE }
    val output = ShortArray(512)
    reducer.process(input, output)
    assertArrayEquals(input, output)
    assertEquals("initialization_error:IllegalStateException", reducer.fallbackReason)
    assertEquals(0L, reducer.diagnostics.processedFrames)
    reducer.close()
  }
}

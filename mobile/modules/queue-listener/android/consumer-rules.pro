# JNI resolves these class/field names; the upstream AAR has no keep rules.
-keep class com.k2fsa.sherpa.onnx.OnlineSpeechDenoiser { *; }
-keep class com.k2fsa.sherpa.onnx.OnlineSpeechDenoiserConfig { *; }
-keep class com.k2fsa.sherpa.onnx.OfflineSpeechDenoiser*Config { *; }
-keep class com.k2fsa.sherpa.onnx.DenoisedAudio { *; }

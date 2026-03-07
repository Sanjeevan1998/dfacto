package com.dfacto.dfacto_app

import android.os.Handler
import android.os.Looper
import com.google.mlkit.genai.common.DownloadStatus
import com.google.mlkit.genai.common.FeatureStatus
import com.google.mlkit.genai.common.audio.AudioSource
import com.google.mlkit.genai.speechrecognition.SpeechRecognition
import com.google.mlkit.genai.speechrecognition.SpeechRecognizerOptions
import com.google.mlkit.genai.speechrecognition.SpeechRecognizerResponse
import com.google.mlkit.genai.speechrecognition.speechRecognizerOptions
import com.google.mlkit.genai.speechrecognition.speechRecognizerRequest
import io.flutter.plugin.common.EventChannel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * Flutter EventChannel StreamHandler wrapping ML Kit GenAI Speech Recognition.
 *
 * Channel : "com.dfacto/speech_recognition"
 * Emits   : String (transcript text chunks — partial or final)
 * Errors  : UNAVAILABLE | DOWNLOAD_FAILED | RECOGNITION_ERROR
 */
class SpeechRecognitionPlugin(
    private val context: android.content.Context
) : EventChannel.StreamHandler {

    private var recognizer: com.google.mlkit.genai.speechrecognition.SpeechRecognizer? = null
    private var recognitionJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val mainHandler = Handler(Looper.getMainLooper())

    // ── EventChannel.StreamHandler ───────────────────────────────────────────

    override fun onListen(arguments: Any?, events: EventChannel.EventSink) {
        val options: SpeechRecognizerOptions = speechRecognizerOptions {
            locale = Locale.US
            preferredMode = SpeechRecognizerOptions.Mode.MODE_ADVANCED
        }
        recognizer = SpeechRecognition.getClient(options)

        scope.launch {
            try {
                val status: Int = recognizer!!.checkStatus()
                when (status) {
                    FeatureStatus.AVAILABLE -> {
                        startRecognition(events)
                    }
                    FeatureStatus.DOWNLOADABLE -> {
                        recognizer!!.download().collect { downloadStatus ->
                            when (downloadStatus) {
                                is DownloadStatus.DownloadCompleted -> {
                                    startRecognition(events)
                                }
                                is DownloadStatus.DownloadFailed -> {
                                    mainHandler.post {
                                        events.error(
                                            "DOWNLOAD_FAILED",
                                            "ML Kit model download failed",
                                            null
                                        )
                                    }
                                }
                                is DownloadStatus.DownloadProgress -> { /* ignored */ }
                                else -> {}
                            }
                        }
                    }
                    else -> {
                        mainHandler.post {
                            events.error(
                                "UNAVAILABLE",
                                "GenAI STT requires Android AICore / Gemini Nano (API 31+)",
                                null
                            )
                        }
                    }
                }
            } catch (e: Exception) {
                mainHandler.post {
                    events.error("RECOGNITION_ERROR", e.message, null)
                }
            }
        }
    }

    override fun onCancel(arguments: Any?) {
        recognitionJob?.cancel()
        recognitionJob = null
        scope.launch {
            try {
                recognizer?.stopRecognition()
                recognizer?.close()
            } catch (_: Exception) {}
            recognizer = null
        }
    }

    // ── Internal ─────────────────────────────────────────────────────────────

    private fun startRecognition(events: EventChannel.EventSink) {
        recognitionJob = scope.launch {
            try {
                val request = speechRecognizerRequest {
                    audioSource = AudioSource.fromMic()
                }

                recognizer!!.startRecognition(request).collect { response ->
                    val text: String? = when (response) {
                        is SpeechRecognizerResponse.PartialTextResponse -> response.text
                        is SpeechRecognizerResponse.FinalTextResponse   -> response.text
                        is SpeechRecognizerResponse.CompletedResponse   -> null
                        is SpeechRecognizerResponse.ErrorResponse       -> null
                        else -> null
                    }
                    if (!text.isNullOrBlank()) {
                        mainHandler.post { events.success(text) }
                    }
                }
            } catch (e: Exception) {
                mainHandler.post {
                    events.error("RECOGNITION_ERROR", e.message, null)
                }
            }
        }
    }
}

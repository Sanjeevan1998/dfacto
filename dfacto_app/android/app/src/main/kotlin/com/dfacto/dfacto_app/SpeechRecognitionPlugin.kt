package com.dfacto.dfacto_app

import android.content.Context
import android.os.Handler
import android.os.Looper
import com.google.mlkit.genai.speech.recognition.AudioSource
import com.google.mlkit.genai.speech.recognition.DownloadStatus
import com.google.mlkit.genai.speech.recognition.FeatureStatus
import com.google.mlkit.genai.speech.recognition.SpeechRecognition
import com.google.mlkit.genai.speech.recognition.SpeechRecognitionResult
import com.google.mlkit.genai.speech.recognition.SpeechRecognizer
import com.google.mlkit.genai.speech.recognition.SpeechRecognizerOptions
import com.google.mlkit.genai.speech.recognition.speechRecognizerOptions
import com.google.mlkit.genai.speech.recognition.speechRecognizerRequest
import io.flutter.plugin.common.EventChannel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * Flutter EventChannel StreamHandler that wraps ML Kit GenAI Speech Recognition.
 *
 * Channel name : "com.dfacto/speech_recognition"
 * Flutter side receives: String (transcript text, partial or final)
 * Flutter side errors  : "UNAVAILABLE" | "DOWNLOAD_FAILED" | "RECOGNITION_ERROR"
 */
class SpeechRecognitionPlugin(private val context: Context) : EventChannel.StreamHandler {

    private var recognizer: SpeechRecognizer? = null
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
                        // Model is on-device and ready — start immediately.
                        startRecognition(events)
                    }
                    FeatureStatus.DOWNLOADABLE -> {
                        // Trigger model download, then start when complete.
                        recognizer!!.download.collect { downloadStatus ->
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
                                is DownloadStatus.DownloadProgress -> {
                                    // Could forward progress if needed — ignored for now.
                                }
                                else -> {}
                            }
                        }
                    }
                    else -> {
                        // FeatureStatus.UNAVAILABLE or unknown
                        mainHandler.post {
                            events.error(
                                "UNAVAILABLE",
                                "GenAI Speech Recognition is not available on this device " +
                                    "(requires Android AICore / Gemini Nano, API 31+)",
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
                        is SpeechRecognitionResult.Partial -> response.text
                        is SpeechRecognitionResult.Final   -> response.text
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

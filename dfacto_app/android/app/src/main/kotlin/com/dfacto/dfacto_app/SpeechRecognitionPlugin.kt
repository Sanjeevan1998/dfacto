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
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * Flutter EventChannel StreamHandler wrapping ML Kit GenAI Speech Recognition.
 *
 * Channel : "com.dfacto/speech_recognition"
 *
 * Emits Map payloads:
 *   Transcript → {"text": String, "isFinal": Boolean}
 *   Status     → {"status": String}
 *                "downloading" — Gemini Nano model downloading
 *                "available"   — ready to capture
 *                "basic_mode"  — fell back to MODE_BASIC (AICore not ready)
 *
 * Errors: UNAVAILABLE | DOWNLOAD_FAILED | RECOGNITION_ERROR
 *
 * Strategy:
 *   1. Try MODE_ADVANCED (Gemini Nano on-device via AICore)
 *   2. If UNAVAILABLE or exception → automatically fall back to MODE_BASIC
 *      (uses Android platform STT — still continuous via the same EventChannel)
 */
class SpeechRecognitionPlugin(
    private val context: android.content.Context
) : EventChannel.StreamHandler {

    private var recognizer: com.google.mlkit.genai.speechrecognition.SpeechRecognizer? = null
    private var recognitionJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val mainHandler = Handler(Looper.getMainLooper())

    // ── Emit helpers ──────────────────────────────────────────────────────────

    private fun emitStatus(events: EventChannel.EventSink, status: String) {
        mainHandler.post { events.success(mapOf("status" to status)) }
    }

    private fun emitTranscript(events: EventChannel.EventSink, text: String, isFinal: Boolean) {
        if (text.isBlank()) return
        mainHandler.post { events.success(mapOf("text" to text, "isFinal" to isFinal)) }
    }

    // ── EventChannel.StreamHandler ────────────────────────────────────────────

    override fun onListen(arguments: Any?, events: EventChannel.EventSink) {
        scope.launch {
            tryStartWithMode(SpeechRecognizerOptions.Mode.MODE_ADVANCED, events)
        }
    }

    override fun onCancel(arguments: Any?) {
        recognitionJob?.cancel()
        recognitionJob = null
        scope.launch {
            try { recognizer?.stopRecognition(); recognizer?.close() }
            catch (_: Exception) {}
            recognizer = null
        }
    }

    // ── Mode selection with automatic fallback ────────────────────────────────

    private suspend fun tryStartWithMode(
        mode: Int,
        events: EventChannel.EventSink
    ) {
        val opts: SpeechRecognizerOptions = speechRecognizerOptions {
            locale = Locale.US
            preferredMode = mode
        }

        val rec = try {
            SpeechRecognition.getClient(opts)
        } catch (e: Exception) {
            fallbackToBasic(mode, events, e)
            return
        }
        recognizer = rec

        try {
            val status: Int = rec.checkStatus()
            when (status) {
                FeatureStatus.AVAILABLE -> {
                    val statusLabel = if (mode == SpeechRecognizerOptions.Mode.MODE_ADVANCED)
                        "available" else "basic_mode"
                    emitStatus(events, statusLabel)
                    startRecognition(events)
                }

                FeatureStatus.DOWNLOADABLE -> {
                    // Gemini Nano needs to be downloaded — show spinner in Flutter.
                    emitStatus(events, "downloading")
                    rec.download().collect { dl ->
                        when (dl) {
                            is DownloadStatus.DownloadCompleted -> {
                                emitStatus(events, "available")
                                startRecognition(events)
                            }
                            is DownloadStatus.DownloadFailed -> {
                                // download failed — fall back to BASIC
                                fallbackToBasic(mode, events, null)
                            }
                            is DownloadStatus.DownloadProgress -> { /* no-op */ }
                            else -> {}
                        }
                    }
                }

                FeatureStatus.DOWNLOADING -> {
                    // AICore is already downloading model — wait for it then retry.
                    emitStatus(events, "downloading")
                    var retries = 0
                    while (retries < 20) {   // poll up to 20 × 3s = 60s
                        delay(3_000)
                        val retryStatus = try { rec.checkStatus() } catch (_: Exception) { -1 }
                        if (retryStatus == FeatureStatus.AVAILABLE) {
                            emitStatus(events, "available")
                            startRecognition(events)
                            return
                        }
                        if (retryStatus != FeatureStatus.DOWNLOADING) break
                        retries++
                    }
                    // Timed out or status changed to something unexpected — fall back.
                    fallbackToBasic(mode, events, null)
                }

                else -> {
                    // FeatureStatus.UNAVAILABLE or unknown — fall back to BASIC.
                    fallbackToBasic(mode, events, null)
                }
            }
        } catch (e: Exception) {
            fallbackToBasic(mode, events, e)
        }
    }

    private fun fallbackToBasic(
        priorMode: Int,
        events: EventChannel.EventSink,
        cause: Exception?
    ) {
        if (priorMode == SpeechRecognizerOptions.Mode.MODE_BASIC) {
            // Already tried BASIC — truly unavailable.
            mainHandler.post {
                events.error(
                    "UNAVAILABLE",
                    "GenAI Speech Recognition unavailable on this device (API 31+, AICore required). ${cause?.message ?: ""}",
                    null
                )
            }
            return
        }
        // First call was ADVANCED → fall back to BASIC silently.
        scope.launch {
            emitStatus(events, "basic_mode")
            tryStartWithMode(SpeechRecognizerOptions.Mode.MODE_BASIC, events)
        }
    }

    // ── Recognition loop ──────────────────────────────────────────────────────

    private fun startRecognition(events: EventChannel.EventSink) {
        recognitionJob = scope.launch {
            try {
                val request = speechRecognizerRequest {
                    audioSource = AudioSource.fromMic()
                }
                recognizer!!.startRecognition(request).collect { response ->
                    when (response) {
                        is SpeechRecognizerResponse.PartialTextResponse ->
                            emitTranscript(events, response.text, isFinal = false)
                        is SpeechRecognizerResponse.FinalTextResponse ->
                            emitTranscript(events, response.text, isFinal = true)
                        is SpeechRecognizerResponse.CompletedResponse -> { /* session ended */ }
                        is SpeechRecognizerResponse.ErrorResponse     -> { /* ignored */ }
                        else -> {}
                    }
                }
            } catch (e: Exception) {
                mainHandler.post { events.error("RECOGNITION_ERROR", e.message, null) }
            }
        }
    }
}

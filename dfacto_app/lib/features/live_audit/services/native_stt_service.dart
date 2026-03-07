import 'dart:async';
import 'package:flutter/services.dart';

/// Bridges the Kotlin ML Kit GenAI Speech Recognition EventChannel to Dart.
///
/// Channel: "com.dfacto/speech_recognition"
///
/// Kotlin sends Map payloads:
///   Transcript → {"text": String, "isFinal": bool}
///   Status     → {"status": String}  "downloading" | "available"
class NativeSTTService {
  NativeSTTService._();
  static final NativeSTTService instance = NativeSTTService._();

  static const _channel = EventChannel('com.dfacto/speech_recognition');

  StreamSubscription<dynamic>? _subscription;

  bool get isRunning => _subscription != null;

  /// Start continuous transcription.
  ///
  /// [onTranscript] — called for every text chunk; [isFinal] = true when the
  ///                  utterance is complete (commit to buffer), false for partials.
  /// [onStatus]    — "downloading" | "available" from Kotlin side.
  /// [onError]     — PlatformException code + message.
  void start({
    required void Function(String text, bool isFinal) onTranscript,
    required void Function(String status) onStatus,
    required void Function(String code, String message) onError,
  }) {
    if (_subscription != null) return;

    _subscription = _channel.receiveBroadcastStream().listen(
      (event) {
        final map = Map<String, dynamic>.from(event as Map? ?? {});

        if (map.containsKey('status')) {
          // Status payload: {"status": "downloading"} or {"status": "available"}
          final status = map['status'] as String? ?? '';
          if (status.isNotEmpty) onStatus(status);
        } else if (map.containsKey('text')) {
          // Transcript payload: {"text": "...", "isFinal": true|false}
          final text = map['text'] as String? ?? '';
          final isFinal = map['isFinal'] as bool? ?? true;
          if (text.isNotEmpty) onTranscript(text, isFinal);
        }
      },
      onError: (error) {
        if (error is PlatformException) {
          onError(error.code, error.message ?? 'Unknown STT error');
        } else {
          onError('UNKNOWN', error.toString());
        }
      },
      cancelOnError: false,
    );
  }

  /// Stop transcription and tear down the stream.
  void stop() {
    _subscription?.cancel();
    _subscription = null;
  }
}

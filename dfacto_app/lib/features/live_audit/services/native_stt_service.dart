import 'dart:async';
import 'package:flutter/services.dart';

/// Bridges the Kotlin ML Kit GenAI Speech Recognition EventChannel to Dart.
///
/// Channel: "com.dfacto/speech_recognition"
/// Events : String (transcript text — partial or final)
/// Errors : PlatformException with codes UNAVAILABLE | DOWNLOAD_FAILED | RECOGNITION_ERROR
class NativeSTTService {
  NativeSTTService._();
  static final NativeSTTService instance = NativeSTTService._();

  static const _channel = EventChannel('com.dfacto/speech_recognition');

  StreamSubscription<dynamic>? _subscription;

  bool get isRunning => _subscription != null;

  /// Start continuous transcription.
  ///
  /// [onTranscript] is called for every text chunk (partial or final).
  /// [onError]      is called on PlatformException from the Kotlin side.
  void start({
    required void Function(String text) onTranscript,
    required void Function(String code, String message) onError,
  }) {
    if (_subscription != null) return;

    _subscription = _channel.receiveBroadcastStream().listen(
      (event) {
        final text = event as String? ?? '';
        if (text.isNotEmpty) onTranscript(text);
      },
      onError: (error) {
        if (error is PlatformException) {
          onError(error.code, error.message ?? 'Unknown error');
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

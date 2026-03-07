import 'dart:async';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text/speech_recognition_result.dart';

/// Dead-simple continuous speech service.
///
/// Architecture: ONE Timer that polls stt.isListening every 500ms.
/// If we should be running but we're not listening → start a new session.
/// No race conditions, no restart-inside-callback issues.
class SpeechService {
  SpeechService._();
  static final SpeechService instance = SpeechService._();

  final _stt = SpeechToText();
  bool _available = false;
  bool _shouldRun = false;
  Timer? _watchdog;

  void Function(String partial)? _onPartial;
  void Function(String finalWords)? _onFinal;

  bool get isRunning => _shouldRun;

  Future<bool> _ensureInit() async {
    if (_available) return true;
    _available = await _stt.initialize(
      onError: (_) {},    // errors handled by watchdog
      onStatus: (_) {},   // status handled by watchdog
    );
    return _available;
  }

  /// Start continuous listening. Calls [onPartial] with partial words as you
  /// speak (~100ms cadence). Calls [onFinal] with the completed phrase when
  /// a natural pause is detected.
  Future<void> start({
    required void Function(String partial) onPartial,
    required void Function(String finalWords) onFinal,
  }) async {
    if (_shouldRun) return;
    final ok = await _ensureInit();
    if (!ok) return;

    _onPartial = onPartial;
    _onFinal = onFinal;
    _shouldRun = true;

    // Start first session
    _beginSession();

    // Watchdog: every 500ms, if we should be running but aren't → restart
    _watchdog = Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (_shouldRun && !_stt.isListening) {
        _beginSession();
      }
    });
  }

  void _beginSession() {
    if (!_shouldRun || !_available) return;
    // Don't start if already listening (avoid double-starts)
    if (_stt.isListening) return;

    _stt.listen(
      onResult: _onResult,
      listenFor: const Duration(seconds: 60),
      pauseFor: const Duration(seconds: 2),
      localeId: 'en_US',
      listenOptions: SpeechListenOptions(
        partialResults: true,
        listenMode: ListenMode.dictation,
        cancelOnError: false,
      ),
    );
  }

  void _onResult(SpeechRecognitionResult result) {
    final words = result.recognizedWords.trim();
    if (words.isEmpty) return;

    if (result.finalResult) {
      _onFinal?.call(words);
      // Session will end naturally → watchdog picks up and restarts
    } else {
      _onPartial?.call(words);
    }
  }

  Future<void> stop() async {
    _shouldRun = false;
    _watchdog?.cancel();
    _watchdog = null;
    _onPartial = null;
    _onFinal = null;
    if (_stt.isListening) await _stt.stop();
  }

  Future<void> cancel() async {
    _shouldRun = false;
    _watchdog?.cancel();
    _watchdog = null;
    _onPartial = null;
    _onFinal = null;
    if (_stt.isListening) await _stt.cancel();
  }
}

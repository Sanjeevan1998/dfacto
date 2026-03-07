import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/fact_check_result.dart';

/// A streaming transcript token from Gemini Live.
/// [text] is the raw token (may be a word, partial phrase, or punctuation).
/// [isPartial] is always true during a live session; false would indicate final.
class TranscriptEvent {
  const TranscriptEvent({
    required this.text,
    required this.isPartial,
  });
  final String text;
  final bool isPartial;
}

class WebSocketService {
  WebSocketService._();
  static final WebSocketService instance = WebSocketService._();

  WebSocketChannel? _channel;
  StreamController<FactCheckResult>? _resultController;
  StreamController<TranscriptEvent>? _transcriptController;
  StreamController<void>? _doneController;
  bool _isConnected = false;

  bool get isConnected => _isConnected;

  Stream<FactCheckResult>? get resultStream => _resultController?.stream;
  Stream<TranscriptEvent>? get transcriptStream => _transcriptController?.stream;

  /// Emits once when the backend sends {"type":"done"} after Stop + flush.
  Stream<void>? get doneStream => _doneController?.stream;

  /// Connect to the FastAPI WebSocket endpoint.
  void connect({String host = '192.168.1.158', int port = 8000}) {
    final uri = Uri.parse('ws://$host:$port/ws/live-audit');
    _resultController = StreamController<FactCheckResult>.broadcast();
    _transcriptController = StreamController<TranscriptEvent>.broadcast();
    _doneController = StreamController<void>.broadcast();
    _channel = WebSocketChannel.connect(uri);
    _isConnected = true;

    _channel!.stream.listen(
      (message) {
        try {
          final json = jsonDecode(message as String) as Map<String, dynamic>;
          final type = json['type'] as String? ?? 'result';

          switch (type) {
            case 'transcript':
              _transcriptController?.add(TranscriptEvent(
                text: json['text'] as String? ?? '',
                isPartial: json['isPartial'] as bool? ?? true,
              ));

            case 'result':
              final result = FactCheckResult.fromJson(json);
              _resultController?.add(result);

            case 'done':
              _doneController?.add(null);

            case 'error':
              final msg = json['message'] as String? ?? 'Unknown error';
              _resultController?.addError(Exception(msg));
              _transcriptController?.addError(Exception(msg));
          }
        } catch (e) {
          // ignore: avoid_print
          print('[WebSocketService] Parse error: $e');
        }
      },
      onError: (e) {
        _isConnected = false;
        _resultController?.addError(e);
        _transcriptController?.addError(e);
      },
      onDone: () {
        _isConnected = false;
        _resultController?.close();
        _transcriptController?.close();
        _doneController?.close();
      },
    );
  }

  /// Send a raw PCM audio chunk to the backend.
  void sendAudioChunk(Uint8List chunk) {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(chunk);
    }
  }

  /// Send the stop control message — backend will flush buffer and send "done".
  void sendStop() {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(jsonEncode({'type': 'stop'}));
    }
  }

  /// Disconnect cleanly.
  Future<void> disconnect() async {
    _isConnected = false;
    await _channel?.sink.close();
    await _resultController?.close();
    await _transcriptController?.close();
    await _doneController?.close();
    _channel = null;
    _resultController = null;
    _transcriptController = null;
    _doneController = null;
  }
}

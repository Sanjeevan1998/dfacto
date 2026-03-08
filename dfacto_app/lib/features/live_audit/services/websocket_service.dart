import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/fact_check_result.dart';

class WebSocketService {
  WebSocketService._();
  static final WebSocketService instance = WebSocketService._();

  WebSocketChannel? _channel;
  StreamController<FactCheckResult>? _resultController;
  StreamController<void>? _doneController;
  StreamController<Map<String, dynamic>>? _transcriptController;
  bool _isConnected = false;

  bool get isConnected => _isConnected;

  Stream<FactCheckResult>? get resultStream => _resultController?.stream;

  /// Emits once when the backend sends {"type":"done"} after Stop + flush.
  Stream<void>? get doneStream => _doneController?.stream;

  /// Emits transcript events from backend: {"text":"...","is_final":true}
  Stream<Map<String, dynamic>>? get transcriptStream =>
      _transcriptController?.stream;

  /// Connect to the FastAPI WebSocket endpoint.
  void connect({String host = '192.168.1.158', int port = 8000}) {
    final uri = Uri.parse('ws://$host:$port/ws/live-audit');
    _resultController = StreamController<FactCheckResult>.broadcast();
    _doneController = StreamController<void>.broadcast();
    _transcriptController = StreamController<Map<String, dynamic>>.broadcast();
    _channel = WebSocketChannel.connect(uri);
    _isConnected = true;

    _channel!.stream.listen(
      (message) {
        try {
          final json = jsonDecode(message as String) as Map<String, dynamic>;
          final type = json['type'] as String? ?? '';

          switch (type) {
            case 'result':
              final result = FactCheckResult.fromJson(json);
              _resultController?.add(result);

            case 'transcript':
              _transcriptController?.add(json);

            case 'done':
              _doneController?.add(null);

            case 'error':
              final msg = json['message'] as String? ?? 'Unknown error';
              _resultController?.addError(Exception(msg));
          }
        } catch (e) {
          // ignore: avoid_print
          print('[WebSocketService] Parse error: $e');
        }
      },
      onError: (e) {
        _isConnected = false;
        _resultController?.addError(e);
      },
      onDone: () {
        _isConnected = false;
        _resultController?.close();
        _doneController?.close();
        _transcriptController?.close();
      },
    );
  }

  /// Send raw PCM audio bytes as a binary WebSocket frame.
  void sendAudioBytes(Uint8List bytes) {
    if (_isConnected && _channel != null && bytes.isNotEmpty) {
      _channel!.sink.add(bytes);
    }
  }

  /// Send a transcript text chunk to the backend for claim detection.
  /// [isFinal] = true when the utterance is complete (natural pause detected).
  void sendTranscriptText(String text, {bool isFinal = false}) {
    if (_isConnected && _channel != null && text.trim().isNotEmpty) {
      _channel!.sink.add(jsonEncode({
        'type': 'transcript_text',
        'text': text,
        'isFinal': isFinal,
      }));
    }
  }

  /// Send the stop control message.
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
    await _doneController?.close();
    await _transcriptController?.close();
    _channel = null;
    _resultController = null;
    _doneController = null;
    _transcriptController = null;
  }
}

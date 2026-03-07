import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/fact_check_result.dart';

/// An intermediate transcript event from the backend.
/// Arrives before the final FactCheckResult for the same chunk.
class TranscriptEvent {
  const TranscriptEvent({required this.text, required this.claim});
  final String text;
  final String claim;
}

class WebSocketService {
  WebSocketService._();
  static final WebSocketService instance = WebSocketService._();

  WebSocketChannel? _channel;
  StreamController<FactCheckResult>? _resultController;
  StreamController<TranscriptEvent>? _transcriptController;
  bool _isConnected = false;

  bool get isConnected => _isConnected;

  Stream<FactCheckResult>? get resultStream => _resultController?.stream;
  Stream<TranscriptEvent>? get transcriptStream => _transcriptController?.stream;

  /// Connect to the FastAPI WebSocket endpoint.
  void connect({String host = '192.168.1.158', int port = 8000}) {
    final uri = Uri.parse('ws://$host:$port/ws/live-audit');
    _resultController = StreamController<FactCheckResult>.broadcast();
    _transcriptController = StreamController<TranscriptEvent>.broadcast();
    _channel = WebSocketChannel.connect(uri);
    _isConnected = true;

    _channel!.stream.listen(
      (message) {
        try {
          final json = jsonDecode(message as String) as Map<String, dynamic>;
          final type = json['type'] as String? ?? 'result';

          if (type == 'transcript') {
            final event = TranscriptEvent(
              text: json['text'] as String? ?? '',
              claim: json['claim'] as String? ?? '',
            );
            _transcriptController?.add(event);
          } else {
            // type == 'result' or legacy payload without type field
            final result = FactCheckResult.fromJson(json);
            _resultController?.add(result);
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
      },
    );
  }

  /// Send a raw audio chunk to the backend.
  void sendAudioChunk(Uint8List chunk) {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(chunk);
    }
  }

  /// Disconnect cleanly.
  Future<void> disconnect() async {
    _isConnected = false;
    await _channel?.sink.close();
    await _resultController?.close();
    await _transcriptController?.close();
    _channel = null;
    _resultController = null;
    _transcriptController = null;
  }
}

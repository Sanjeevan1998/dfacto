import 'dart:async';
import 'dart:typed_data';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

class AudioService {
  AudioService._();
  static final AudioService instance = AudioService._();

  final AudioRecorder _recorder = AudioRecorder();
  StreamController<Uint8List>? _streamController;
  bool _isRecording = false;

  bool get isRecording => _isRecording;

  /// Request microphone permission. Returns true if granted.
  Future<bool> requestPermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  /// Start recording and return a stream of raw PCM audio chunks.
  Future<Stream<Uint8List>?> startRecording() async {
    final granted = await requestPermission();
    if (!granted) return null;
    if (_isRecording) return _streamController?.stream;

    _streamController = StreamController<Uint8List>.broadcast();
    _isRecording = true;

    // record v6: startStream() — no recorderId parameter
    final stream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        bitRate: 256000,
      ),
    );

    stream.listen(
      (chunk) => _streamController?.add(chunk),
      onError: (e) => _streamController?.addError(e),
      onDone: () => _streamController?.close(),
    );

    return _streamController!.stream;
  }

  /// Stop recording and clean up.
  Future<void> stopRecording() async {
    if (!_isRecording) return;
    _isRecording = false;
    await _recorder.stop();
    await _streamController?.close();
    _streamController = null;
  }

  void dispose() {
    _recorder.dispose();
    _streamController?.close();
  }
}

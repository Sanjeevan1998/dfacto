import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import '../../navigation/app_shell.dart';
import 'models/fact_check_result.dart';
import 'services/audio_service.dart';
import 'services/websocket_service.dart';
import 'widgets/listen_button.dart';
import 'widgets/waveform_visualizer.dart';
import 'widgets/live_transcript_panel.dart';
import 'widgets/fact_check_feed.dart';

class LiveAuditScreen extends StatefulWidget {
  const LiveAuditScreen({super.key});

  @override
  State<LiveAuditScreen> createState() => _LiveAuditScreenState();
}

class _LiveAuditScreenState extends State<LiveAuditScreen> {
  bool _isListening = false;
  bool _isStopping = false;

  // Granola-style transcript: all finalised words in one growing string.
  String _committedText = '';
  String _partialText = '';

  final List<FactCheckResult> _results = [];

  final _audio = AudioService.instance;
  final _ws = WebSocketService.instance;

  StreamSubscription<dynamic>? _resultSub;
  StreamSubscription<dynamic>? _doneSub;
  StreamSubscription<Map<String, dynamic>>? _transcriptSub;
  StreamSubscription<Uint8List>? _audioSub;

  // ── Session control ────────────────────────────────────────────────────────

  Future<void> _startListening() async {
    // Connect WebSocket first — fact-check results & transcripts come back here.
    _ws.connect();

    _resultSub = _ws.resultStream?.listen((result) {
      if (!mounted) return;
      setState(() => _results.insert(0, result));
    });

    _doneSub = _ws.doneStream?.listen((_) {
      if (!mounted) return;
      _finalizeSession();
    });

    // Subscribe to transcript events from backend (Gemini Live API ASR).
    _transcriptSub = _ws.transcriptStream?.listen((event) {
      if (!mounted) return;
      final text = event['text'] as String? ?? '';
      final isFinal = event['is_final'] as bool? ?? true;
      if (text.isEmpty) return;

      setState(() {
        if (isFinal) {
          _committedText = _committedText.isEmpty
              ? text
              : '$_committedText $text';
          _partialText = '';
        } else {
          _partialText = text;
        }
      });
    });

    // Start raw audio capture and pipe bytes to backend via WebSocket.
    final audioStream = await _audio.startRecording();
    if (audioStream == null) {
      // Permission denied or recorder failed
      _ws.disconnect();
      return;
    }

    _audioSub = audioStream.listen((Uint8List bytes) {
      _ws.sendAudioBytes(bytes);
    });

    setState(() {
      _isListening = true;
      _isStopping = false;
    });
  }

  Future<void> _stopListening() async {
    setState(() {
      _isListening = false;
      _isStopping = true;
    });

    // Stop audio capture first.
    _audioSub?.cancel();
    _audioSub = null;
    await _audio.stopRecording();

    // Tell backend to flush its buffer and send "done".
    _ws.sendStop();

    // Safety timeout: finalize if backend doesn't respond in 30s.
    Future.delayed(const Duration(seconds: 30), () {
      if (mounted && _isStopping) _finalizeSession();
    });
  }

  void _finalizeSession() {
    if (!mounted) return;

    _resultSub?.cancel();
    _doneSub?.cancel();
    _transcriptSub?.cancel();
    _audioSub?.cancel();
    _resultSub = null;
    _doneSub = null;
    _transcriptSub = null;
    _audioSub = null;

    setState(() => _isStopping = false);
    _ws.disconnect();
  }

  Future<void> _toggleListening() async {
    if (_isListening) {
      await _stopListening();
    } else {
      await _startListening();
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  @override
  void dispose() {
    _audioSub?.cancel();
    _audio.stopRecording();
    _resultSub?.cancel();
    _doneSub?.cancel();
    _transcriptSub?.cancel();
    _ws.disconnect();
    super.dispose();
  }

  // ── Build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final hasTranscript = _committedText.isNotEmpty || _partialText.isNotEmpty;

    return Scaffold(
      backgroundColor: context.bg,
      body: SafeArea(
        child: Column(
          children: [
            // ── Header ───────────────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
              child: Row(
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Live Audit',
                          style: DfactoTextStyles.displayLarge(context.textPrimary)),
                      const SizedBox(height: 2),
                      Text('Studio broadcast monitor',
                          style: DfactoTextStyles.bodyMedium(context.textSecondary)),
                    ],
                  ),
                  const Spacer(),
                  _StatusChip(isListening: _isListening, isStopping: _isStopping),
                  const SizedBox(width: 10),
                  const ThemeToggleButton(),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // ── Waveform + Mic button ─────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Container(
                height: 90,
                decoration: BoxDecoration(
                  color: context.surfaceHigh,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: context.border, width: 1),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: WaveformVisualizer(isActive: _isListening),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(right: 16),
                      child: _isStopping
                          ? const SizedBox(
                              width: 44,
                              height: 44,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : ListenButton(
                              isListening: _isListening,
                              onTap: _toggleListening,
                            ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),

            // ── Live Transcript ───────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Text('Live Transcript',
                      style: DfactoTextStyles.headlineMedium(context.textPrimary)),
                  const Spacer(),
                  if (hasTranscript || _results.isNotEmpty)
                    GestureDetector(
                      onTap: () => setState(() {
                        _committedText = '';
                        _results.clear();
                        _partialText = '';
                      }),
                      child: Text('Clear all',
                          style: DfactoTextStyles.bodySmall(context.textMuted)),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 6),

            Expanded(
              flex: 3,
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 20),
                decoration: BoxDecoration(
                  color: context.surfaceHigh,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: context.border, width: 1),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: LiveTranscriptPanel(
                    committedText: _committedText,
                    partialText: _partialText,
                    isListening: _isListening,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 10),

            // ── Fact-Check Cards ──────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Text('Fact-Check Results',
                      style: DfactoTextStyles.headlineMedium(context.textPrimary)),
                  const Spacer(),
                  Text(
                    _isListening
                        ? 'Live'
                        : _isStopping
                            ? 'Processing…'
                            : 'Paused',
                    style: _isListening
                        ? DfactoTextStyles.bodySmall(DfactoColors.verdictTrue)
                        : DfactoTextStyles.bodySmall(context.textMuted),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 6),

            Expanded(
              flex: 2,
              child: FactCheckFeed(results: _results.isEmpty ? null : _results),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Status chip ───────────────────────────────────────────────────────────────

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.isListening, required this.isStopping});
  final bool isListening;
  final bool isStopping;

  @override
  Widget build(BuildContext context) {
    final label = isListening ? 'HOT MIC' : isStopping ? 'PROCESSING' : 'IDLE';
    final active = isListening || isStopping;
    final color = isListening
        ? DfactoColors.verdictTrue
        : isStopping
            ? DfactoColors.verdictMixed
            : context.textMuted;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: active
            ? color.withValues(alpha: 0.12)
            : context.surfaceHigh,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: active ? color.withValues(alpha: 0.35) : context.border,
          width: 1,
        ),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 400),
          width: 6,
          height: 6,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: active ? color : context.textMuted,
          ),
        ),
        const SizedBox(width: 5),
        Text(label, style: DfactoTextStyles.labelBold(active ? color : context.textMuted)),
      ]),
    );
  }
}

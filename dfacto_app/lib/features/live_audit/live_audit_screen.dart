import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import '../../navigation/app_shell.dart';
import 'models/fact_check_result.dart';
import 'models/transcript_segment.dart';
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
  bool _isStopping = false; // true while awaiting backend "done" after Stop

  final List<TranscriptSegment> _segments = [];
  final List<FactCheckResult> _results = [];

  // Live partial text: accumulates Gemini transcript tokens word-by-word.
  // Cleared and committed to _segments when a fact-check result arrives,
  // or when the session ends.
  String _partialText = '';

  final _audio = AudioService.instance;
  final _ws = WebSocketService.instance;

  StreamSubscription<dynamic>? _audioSub;
  StreamSubscription<dynamic>? _transcriptSub;
  StreamSubscription<dynamic>? _resultSub;
  StreamSubscription<dynamic>? _doneSub;

  // ── Session control ────────────────────────────────────────────────────────

  Future<void> _startListening() async {
    // 1. Start raw PCM recording
    final audioStream = await _audio.startRecording();
    if (audioStream == null) {
      // Permission denied or hardware error
      return;
    }

    // 2. Connect WebSocket to backend
    _ws.connect();

    // 3. Subscribe to transcript tokens → append word-by-word to partial text
    _transcriptSub = _ws.transcriptStream?.listen((event) {
      if (!mounted) return;
      setState(() => _partialText += event.text);
    });

    // 4. Subscribe to fact-check results
    //    When a result arrives, commit the accumulated partial text as a
    //    completed segment and clear the partial for the next window.
    _resultSub = _ws.resultStream?.listen((result) {
      if (!mounted) return;
      setState(() {
        // Snapshot the partial text that produced this claim
        final segText = _partialText.trim();
        _partialText = '';

        if (segText.isNotEmpty) {
          _segments.add(TranscriptSegment(
            id: DateTime.now().toIso8601String(),
            text: segText,
            claim: result.claimText,
            result: result,
          ));
        }
        _results.insert(0, result);
      });
    });

    // 5. Subscribe to "done" — backend finished flushing after Stop
    _doneSub = _ws.doneStream?.listen((_) {
      if (!mounted) return;
      _finalizeSession();
    });

    // 6. Stream PCM chunks to backend via WebSocket
    _audioSub = audioStream.listen((chunk) {
      _ws.sendAudioChunk(chunk);
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

    // Stop recording first so no more audio chunks are produced
    await _audio.stopRecording();
    _audioSub?.cancel();
    _audioSub = null;

    // Send stop signal to backend — it will flush the buffer and send "done"
    _ws.sendStop();

    // _doneSub will call _finalizeSession() when backend responds with "done".
    // Safety timeout: if backend doesn't respond in 10s, finalize anyway.
    Future.delayed(const Duration(seconds: 10), () {
      if (mounted && _isStopping) _finalizeSession();
    });
  }

  void _finalizeSession() {
    if (!mounted) return;

    // Cancel all subscriptions
    _transcriptSub?.cancel();
    _resultSub?.cancel();
    _doneSub?.cancel();
    _transcriptSub = null;
    _resultSub = null;
    _doneSub = null;

    // Commit any remaining partial text as a segment (no result yet)
    final remaining = _partialText.trim();
    setState(() {
      if (remaining.isNotEmpty) {
        _segments.add(TranscriptSegment(
          id: DateTime.now().toIso8601String(),
          text: remaining,
          claim: '',
        ));
      }
      _partialText = '';
      _isStopping = false;
    });

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
    _audio.stopRecording();
    _audioSub?.cancel();
    _transcriptSub?.cancel();
    _resultSub?.cancel();
    _doneSub?.cancel();
    _ws.disconnect();
    super.dispose();
  }

  // ── Build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    // Show completed segments + a live partial segment at the bottom
    final displaySegments = [
      ..._segments,
      if (_partialText.isNotEmpty)
        TranscriptSegment(
          id: '__partial__',
          text: _partialText,
          claim: '',
        ),
    ];

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
                  if (displaySegments.isNotEmpty)
                    GestureDetector(
                      onTap: () => setState(() {
                        _segments.clear();
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
                    segments: displaySegments,
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

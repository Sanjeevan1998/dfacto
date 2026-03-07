import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import '../../navigation/app_shell.dart';
import 'models/fact_check_result.dart';
import 'services/native_stt_service.dart';
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

  // ML Kit model download in progress — show spinner instead of mic.
  bool _isModelDownloading = false;

  // Granola-style transcript:
  //   _committedText = all final segments joined
  //   _partialText   = current in-progress partial (shown in muted style)
  String _committedText = '';
  String _partialText = '';

  final List<FactCheckResult> _results = [];

  final _stt = NativeSTTService.instance;
  final _ws = WebSocketService.instance;

  StreamSubscription<dynamic>? _resultSub;
  StreamSubscription<dynamic>? _doneSub;

  // ── Session control ────────────────────────────────────────────────────────

  Future<void> _startListening() async {
    _ws.connect();

    _resultSub = _ws.resultStream?.listen((result) {
      if (!mounted) return;
      setState(() => _results.insert(0, result));
    });

    _doneSub = _ws.doneStream?.listen((_) {
      if (!mounted) return;
      _finalizeSession();
    });

    _stt.start(
      onTranscript: (String text, bool isFinal) {
        if (!mounted) return;
        setState(() {
          if (isFinal) {
            // Commit to the permanent buffer.
            _committedText = _committedText.isEmpty
                ? text
                : '$_committedText $text';
            _partialText = '';
          } else {
            // Show as in-progress partial (replaced on next partial).
            _partialText = text;
          }
        });
        // Send to backend — isFinal distinguishes utterance boundary.
        _ws.sendTranscriptText(text, isFinal: isFinal);
      },
      onStatus: (String status) {
        if (!mounted) return;
        setState(() {
          _isModelDownloading = status == 'downloading';
        });
        if (status == 'available') {
          // Model is ready — already triggered startRecognition() in Kotlin.
          // No action needed here.
        }
      },
      onError: (String code, String message) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              code == 'UNAVAILABLE'
                  ? 'On-device GenAI STT not available on this device.'
                  : 'Speech error ($code): $message',
            ),
            backgroundColor: DfactoColors.verdictFalse,
          ),
        );
        setState(() {
          _isListening = false;
          _isStopping = false;
          _isModelDownloading = false;
        });
      },
    );

    setState(() {
      _isListening = true;
      _isStopping = false;
    });
  }

  Future<void> _stopListening() async {
    setState(() {
      _isListening = false;
      _isStopping = true;
      _isModelDownloading = false;
    });

    _stt.stop();

    // Flush any in-progress partial as final before stopping.
    if (_partialText.isNotEmpty) {
      _ws.sendTranscriptText(_partialText, isFinal: true);
      setState(() {
        _committedText = _committedText.isEmpty
            ? _partialText
            : '$_committedText $_partialText';
        _partialText = '';
      });
    }

    _ws.sendStop();

    // Safety timeout.
    Future.delayed(const Duration(seconds: 30), () {
      if (mounted && _isStopping) _finalizeSession();
    });
  }

  void _finalizeSession() {
    if (!mounted) return;
    _resultSub?.cancel();
    _doneSub?.cancel();
    _resultSub = null;
    _doneSub = null;
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
    _stt.stop();
    _resultSub?.cancel();
    _doneSub?.cancel();
    _ws.disconnect();
    super.dispose();
  }

  // ── Build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final hasContent = _committedText.isNotEmpty ||
        _partialText.isNotEmpty ||
        _results.isNotEmpty;

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
                  _StatusChip(
                    isListening: _isListening,
                    isStopping: _isStopping,
                    isDownloading: _isModelDownloading,
                  ),
                  const SizedBox(width: 10),
                  const ThemeToggleButton(),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // ── Waveform + Mic / Download indicator ───────────────────────────
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
                        child: _isModelDownloading
                            ? Row(
                                children: [
                                  const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  ),
                                  const SizedBox(width: 10),
                                  Text(
                                    'Downloading AI model…',
                                    style: DfactoTextStyles.bodySmall(context.textMuted),
                                  ),
                                ],
                              )
                            : WaveformVisualizer(isActive: _isListening),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(right: 16),
                      child: _isModelDownloading || _isStopping
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
                  if (hasContent)
                    GestureDetector(
                      onTap: () => setState(() {
                        _committedText = '';
                        _partialText = '';
                        _results.clear();
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
  const _StatusChip({
    required this.isListening,
    required this.isStopping,
    required this.isDownloading,
  });

  final bool isListening;
  final bool isStopping;
  final bool isDownloading;

  @override
  Widget build(BuildContext context) {
    final String label;
    final Color color;

    if (isDownloading) {
      label = 'MODEL DL';
      color = DfactoColors.verdictMixed;
    } else if (isListening) {
      label = 'HOT MIC';
      color = DfactoColors.verdictTrue;
    } else if (isStopping) {
      label = 'PROCESSING';
      color = DfactoColors.verdictMixed;
    } else {
      label = 'IDLE';
      color = context.textMuted;
    }

    final active = isListening || isStopping || isDownloading;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: active ? color.withValues(alpha: 0.12) : context.surfaceHigh,
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
        Text(label,
            style: DfactoTextStyles.labelBold(active ? color : context.textMuted)),
      ]),
    );
  }
}

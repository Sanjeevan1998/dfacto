import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import '../../navigation/app_shell.dart';
import 'models/fact_check_result.dart';
import 'models/transcript_segment.dart';
import 'services/speech_service.dart';
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
  bool _isChecking = false;

  final List<TranscriptSegment> _segments = [];
  final List<FactCheckResult> _results = [];
  String _partialText = '';

  final _speech = SpeechService.instance;
  final _textController = TextEditingController();

  // ── Toggle mic ────────────────────────────────────────────────────────────

  Future<void> _toggleListening() async {
    if (_isListening) {
      await _speech.stop();
      setState(() {
        _isListening = false;
        _partialText = '';
      });
    } else {
      await _speech.start(
        onPartial: (partial) {
          if (mounted) setState(() => _partialText = partial);
        },
        onFinal: (phrase) {
          if (!mounted || phrase.trim().isEmpty) return;
          setState(() {
            _partialText = '';
            _segments.add(TranscriptSegment(
              id: DateTime.now().toIso8601String(),
              text: phrase,
              claim: '',
            ));
          });
        },
      );
      setState(() => _isListening = true);
    }
  }


  // ── Fact-check via /debug/check ───────────────────────────────────────────

  Future<void> _factCheck(TranscriptSegment seg) async {
    try {
      final uri = Uri.parse('http://192.168.1.158:8000/debug/check');
      final client = HttpClient()
        ..connectionTimeout = const Duration(seconds: 10)
        ..idleTimeout = const Duration(seconds: 50);

      final result = await Future.any([
        _doFactCheck(client, uri, seg),
        Future.delayed(const Duration(seconds: 50), () => 'timeout'),
      ]);

      if (result == 'timeout' && mounted) {
        setState(() => seg.error = 'Timed out');
      }
    } catch (e) {
      if (mounted) setState(() => seg.error = 'Error: $e');
    }
  }

  Future<Object?> _doFactCheck(
      HttpClient client, Uri uri, TranscriptSegment seg) async {
    try {
      final request = await client.postUrl(uri);
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode({'claim': seg.claim}));
      final response = await request.close();
      final body = await response.transform(utf8.decoder).join();
      client.close();

      if (response.statusCode == 200 && mounted) {
        final json = jsonDecode(body) as Map<String, dynamic>;
        if (json.containsKey('claimText')) {
          final result = FactCheckResult.fromJson(json);
          setState(() {
            seg.result = result;
            _results.insert(0, result);
          });
        }
      } else if (mounted) {
        setState(() => seg.error = 'HTTP ${response.statusCode}');
      }
    } catch (e) {
      if (mounted) setState(() => seg.error = e.toString());
    }
    return null;
  }

  // ── Text debug input ──────────────────────────────────────────────────────

  Future<void> _submitTextClaim() async {
    final claim = _textController.text.trim();
    if (claim.isEmpty) return;
    setState(() => _isChecking = true);
    _textController.clear();

    final seg = TranscriptSegment(
      id: DateTime.now().toIso8601String(),
      text: claim,
      claim: claim,
    );
    setState(() => _segments.add(seg));
    await _factCheck(seg);
    if (mounted) setState(() => _isChecking = false);
  }

  @override
  void dispose() {
    _speech.cancel();
    _textController.dispose();
    super.dispose();
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    // Produce display segments: completed ones + a live partial segment at end
    final displaySegments = [
      ..._segments,
      if (_partialText.isNotEmpty)
        TranscriptSegment(
          id: '__partial__',
          text: _partialText,
          claim: '',     // no claim yet — partial results never trigger fact-check
        ),
    ];

    return Scaffold(
      backgroundColor: context.bg,
      body: SafeArea(
        child: Column(
          children: [
            // ── Header ─────────────────────────────────────────────────────
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
                  _StatusChip(isListening: _isListening),
                  const SizedBox(width: 10),
                  const ThemeToggleButton(),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // ── Waveform + Mic button ───────────────────────────────────────
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
                      child: ListenButton(
                        isListening: _isListening,
                        onTap: _toggleListening,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),

            // ── Text debug input ────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Container(
                decoration: BoxDecoration(
                  color: context.surfaceHigh,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: context.border, width: 1),
                ),
                child: Row(
                  children: [
                    const SizedBox(width: 14),
                    Expanded(
                      child: TextField(
                        controller: _textController,
                        style: DfactoTextStyles.bodyMedium(context.textPrimary),
                        decoration: InputDecoration(
                          hintText: 'Or type a claim to fact-check…',
                          hintStyle: DfactoTextStyles.bodyMedium(context.textMuted),
                          border: InputBorder.none,
                          isDense: true,
                          contentPadding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _submitTextClaim(),
                      ),
                    ),
                    _isChecking
                        ? Padding(
                            padding: const EdgeInsets.all(12),
                            child: SizedBox(
                              width: 18, height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2, color: context.accent),
                            ),
                          )
                        : IconButton(
                            onPressed: _submitTextClaim,
                            icon: Icon(Icons.send_rounded,
                                color: context.accent, size: 20),
                            padding: const EdgeInsets.all(10),
                          ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),

            // ── Live Transcript ─────────────────────────────────────────────
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

            // ── Fact-Check Cards ────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Text('Fact-Check Results',
                      style: DfactoTextStyles.headlineMedium(context.textPrimary)),
                  const Spacer(),
                  Text(
                    _isListening ? 'Live' : 'Paused',
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
  const _StatusChip({required this.isListening});
  final bool isListening;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: isListening
            ? DfactoColors.verdictTrue.withValues(alpha: 0.12)
            : context.surfaceHigh,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isListening
              ? DfactoColors.verdictTrue.withValues(alpha: 0.35)
              : context.border,
          width: 1,
        ),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 400),
          width: 6, height: 6,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isListening ? DfactoColors.verdictTrue : context.textMuted,
          ),
        ),
        const SizedBox(width: 5),
        Text(
          isListening ? 'HOT MIC' : 'IDLE',
          style: DfactoTextStyles.labelBold(
              isListening ? DfactoColors.verdictTrue : context.textMuted),
        ),
      ]),
    );
  }
}

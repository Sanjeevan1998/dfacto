import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import '../../../core/theme/app_theme.dart';
import '../models/fact_check_result.dart';

/// Full-screen bottom sheet shown when tapping a fact-check card.
Future<void> showFactCheckDetail(
  BuildContext context,
  FactCheckResult result, {
  String host = '192.168.1.158',
  int port = 8000,
}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _FactCheckDetailSheet(
      result: result,
      host: host,
      port: port,
    ),
  );
}

// ── Chat message model ────────────────────────────────────────────────────────

class _ChatMessage {
  _ChatMessage({required this.text, required this.isUser, this.isLoading = false});
  final String text;
  final bool isUser;
  final bool isLoading;
}

class _FactCheckDetailSheet extends StatefulWidget {
  const _FactCheckDetailSheet({
    required this.result,
    required this.host,
    required this.port,
  });

  final FactCheckResult result;
  final String host;
  final int port;

  @override
  State<_FactCheckDetailSheet> createState() => _FactCheckDetailSheetState();
}

class _FactCheckDetailSheetState extends State<_FactCheckDetailSheet> {
  final _questionController = TextEditingController();
  final _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];
  bool _isLoading = false;

  @override
  void dispose() {
    _questionController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _askFollowup() async {
    final question = _questionController.text.trim();
    if (question.isEmpty || _isLoading) return;

    _questionController.clear();

    setState(() {
      _messages.add(_ChatMessage(text: question, isUser: true));
      _messages.add(_ChatMessage(text: '', isUser: false, isLoading: true));
      _isLoading = true;
    });
    _scrollToBottom();

    String answer;
    try {
      final uri = Uri.parse('http://${widget.host}:${widget.port}/debug/followup');
      final response = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'claim': widget.result.claimText,
          'question': question,
          'context': widget.result.summaryAndExplanation,
        }),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        answer = (data['answer'] as String? ?? '').trim();
        if (answer.isEmpty) answer = 'No answer found.';
      } else {
        answer = 'Error ${response.statusCode}: could not get an answer.';
      }
    } catch (e) {
      answer = 'Request failed: $e';
    }

    setState(() {
      _messages.removeLast(); // remove loading bubble
      _messages.add(_ChatMessage(text: answer, isUser: false));
      _isLoading = false;
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // ── Verdict helpers ───────────────────────────────────────────────────────

  Color _vc(BuildContext ctx) {
    switch (widget.result.claimVeracity) {
      case ClaimVeracity.trueVerdict:  return DfactoColors.verdictTrue;
      case ClaimVeracity.mostlyTrue:   return const Color(0xFF8BC34A);
      case ClaimVeracity.halfTrue:     return DfactoColors.verdictMixed;
      case ClaimVeracity.mostlyFalse:  return const Color(0xFFFF5722);
      case ClaimVeracity.falseVerdict: return DfactoColors.verdictFalse;
      case ClaimVeracity.unknown:      return DfactoColors.verdictUnknown;
    }
  }

  String get _verdictLabel {
    switch (widget.result.claimVeracity) {
      case ClaimVeracity.trueVerdict:  return 'TRUE';
      case ClaimVeracity.mostlyTrue:   return 'MOSTLY TRUE';
      case ClaimVeracity.halfTrue:     return 'HALF TRUE';
      case ClaimVeracity.mostlyFalse:  return 'MOSTLY FALSE';
      case ClaimVeracity.falseVerdict: return 'FALSE';
      case ClaimVeracity.unknown:      return 'UNVERIFIABLE';
    }
  }

  IconData get _verdictIcon {
    switch (widget.result.claimVeracity) {
      case ClaimVeracity.trueVerdict:  return Icons.check_circle_rounded;
      case ClaimVeracity.mostlyTrue:   return Icons.check_circle_outline_rounded;
      case ClaimVeracity.halfTrue:     return Icons.info_rounded;
      case ClaimVeracity.mostlyFalse:  return Icons.warning_amber_rounded;
      case ClaimVeracity.falseVerdict: return Icons.cancel_rounded;
      case ClaimVeracity.unknown:      return Icons.help_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final vc = _vc(context);
    final sources = widget.result.keySources.isNotEmpty
        ? widget.result.keySources
        : (widget.result.keySource != null ? [widget.result.keySource!] : <String>[]);

    return DraggableScrollableSheet(
      initialChildSize: 0.88,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (ctx, sheetScroll) {
        return Container(
          decoration: BoxDecoration(
            color: context.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            children: [
              // ── Drag handle ───────────────────────────────────────────────
              Center(
                child: Container(
                  margin: const EdgeInsets.only(top: 10, bottom: 6),
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: context.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),

              // ── Verdict badge ─────────────────────────────────────────────
              Container(
                margin: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: vc.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: vc.withValues(alpha: 0.25)),
                ),
                child: Row(children: [
                  Icon(_verdictIcon, color: vc, size: 18),
                  const SizedBox(width: 8),
                  Text(_verdictLabel,
                      style: DfactoTextStyles.headlineMedium(vc)
                          .copyWith(fontSize: 15, letterSpacing: 1.1)),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
                    decoration: BoxDecoration(
                      color: vc.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '${(widget.result.confidenceScore * 100).round()}%',
                      style: DfactoTextStyles.bodySmall(vc)
                          .copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
                ]),
              ),

              // ── Scrollable body ───────────────────────────────────────────
              Expanded(
                child: ListView(
                  controller: _scrollController,
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
                  children: [
                    // Claim
                    _SectionLabel('Claim'),
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: context.surfaceHigh,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '"${widget.result.claimText}"',
                        style: DfactoTextStyles.bodyMedium(context.textPrimary)
                            .copyWith(fontStyle: FontStyle.italic),
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Analysis
                    if (widget.result.summaryAndExplanation.isNotEmpty) ...[
                      _SectionLabel('Analysis'),
                      const SizedBox(height: 6),
                      Text(
                        widget.result.summaryAndExplanation,
                        style: DfactoTextStyles.bodyMedium(context.textPrimary)
                            .copyWith(height: 1.65),
                      ),
                      const SizedBox(height: 16),
                    ],

                    // Sources
                    if (sources.isNotEmpty) ...[
                      _SectionLabel('Sources'),
                      const SizedBox(height: 6),
                      Container(
                        decoration: BoxDecoration(
                          color: context.surfaceHigh,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: context.border),
                        ),
                        child: Column(
                          children: [
                            for (int i = 0; i < sources.length; i++)
                              _DetailSourceRow(
                                url: sources[i],
                                isFirst: i == 0,
                                isLast: i == sources.length - 1,
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                    ],

                    // Chat header (only when messages exist)
                    if (_messages.isNotEmpty) ...[
                      _SectionLabel('Follow-up'),
                      const SizedBox(height: 10),
                    ],

                    // Chat messages
                    for (final msg in _messages) _ChatBubble(message: msg),

                    const SizedBox(height: 12),
                  ],
                ),
              ),

              // ── Follow-up input bar ───────────────────────────────────────
              Container(
                padding: EdgeInsets.fromLTRB(
                    12, 8, 12, MediaQuery.of(context).viewInsets.bottom + 10),
                decoration: BoxDecoration(
                  color: context.surface,
                  border: Border(top: BorderSide(color: context.border, width: 1)),
                ),
                child: Row(children: [
                  Expanded(
                    child: TextField(
                      controller: _questionController,
                      style: DfactoTextStyles.bodyMedium(context.textPrimary),
                      decoration: InputDecoration(
                        hintText: 'Ask a follow-up question…',
                        hintStyle: DfactoTextStyles.bodyMedium(context.textMuted),
                        filled: true,
                        fillColor: context.surfaceHigh,
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 10),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: BorderSide.none,
                        ),
                      ),
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _askFollowup(),
                      maxLines: 1,
                    ),
                  ),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: _isLoading ? null : _askFollowup,
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: _isLoading
                            ? context.border
                            : context.accent,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: _isLoading
                          ? Padding(
                              padding: const EdgeInsets.all(10),
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: context.textMuted,
                              ),
                            )
                          : Icon(
                              Icons.send_rounded,
                              color: context.isDark ? Colors.black : Colors.white,
                              size: 18,
                            ),
                    ),
                  ),
                ]),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ── Section label ─────────────────────────────────────────────────────────────

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Text(
        text.toUpperCase(),
        style: DfactoTextStyles.bodySmall(context.textMuted)
            .copyWith(fontWeight: FontWeight.w600, letterSpacing: 0.9),
      );
}

// ── Chat bubble ───────────────────────────────────────────────────────────────

class _ChatBubble extends StatelessWidget {
  const _ChatBubble({required this.message});
  final _ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;

    return Padding(
      padding: EdgeInsets.only(
        top: 6,
        left: isUser ? 40 : 0,
        right: isUser ? 0 : 40,
      ),
      child: Align(
        alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: isUser
                ? context.accent.withValues(alpha: 0.10)
                : context.surfaceHigh,
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(14),
              topRight: const Radius.circular(14),
              bottomLeft: Radius.circular(isUser ? 14 : 4),
              bottomRight: Radius.circular(isUser ? 4 : 14),
            ),
            border: Border.all(color: context.border, width: 0.8),
          ),
          child: message.isLoading
              ? SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    color: context.textMuted,
                  ),
                )
              : Text(
                  message.text,
                  style: DfactoTextStyles.bodyMedium(
                    isUser ? context.textPrimary : context.textPrimary,
                  ).copyWith(height: 1.55),
                ),
        ),
      ),
    );
  }
}

// ── Source row ────────────────────────────────────────────────────────────────

class _DetailSourceRow extends StatelessWidget {
  const _DetailSourceRow({
    required this.url,
    required this.isFirst,
    required this.isLast,
  });

  final String url;
  final bool isFirst;
  final bool isLast;

  Future<void> _launch() async {
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  String get _domain {
    try {
      return Uri.parse(url).host.replaceFirst('www.', '');
    } catch (_) {
      return url;
    }
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: _launch,
      borderRadius: BorderRadius.only(
        topLeft: Radius.circular(isFirst ? 10 : 0),
        topRight: Radius.circular(isFirst ? 10 : 0),
        bottomLeft: Radius.circular(isLast ? 10 : 0),
        bottomRight: Radius.circular(isLast ? 10 : 0),
      ),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          border: isLast
              ? null
              : Border(bottom: BorderSide(color: context.border, width: 0.5)),
        ),
        child: Row(children: [
          Icon(Icons.link_rounded, color: context.textMuted, size: 14),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _domain,
                  style: DfactoTextStyles.bodySmall(context.textPrimary)
                      .copyWith(fontWeight: FontWeight.w600),
                ),
                Text(
                  url,
                  style: DfactoTextStyles.bodySmall(context.textMuted),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 1,
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          Icon(Icons.open_in_new_rounded, color: context.textMuted, size: 13),
        ]),
      ),
    );
  }
}

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import '../../../core/theme/app_theme.dart';
import '../models/fact_check_result.dart';

/// Full-screen bottom sheet shown when tapping a fact-check card.
/// Shows complete verdict, explanation, all sources, and a follow-up Q&A input.
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

  bool _isLoading = false;
  String? _answer;

  @override
  void dispose() {
    _questionController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // ── Follow-up API call ────────────────────────────────────────────────────

  Future<void> _askFollowup() async {
    final question = _questionController.text.trim();
    if (question.isEmpty) return;

    setState(() {
      _isLoading = true;
      _answer = null;
    });

    try {
      final uri = Uri.parse(
          'http://${widget.host}:${widget.port}/debug/followup');
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
        setState(() => _answer = data['answer'] as String? ?? '');
      } else {
        setState(() => _answer = 'Error: could not get an answer.');
      }
    } catch (e) {
      setState(() => _answer = 'Error: $e');
    } finally {
      setState(() => _isLoading = false);
      // Scroll to show the answer
      await Future.delayed(const Duration(milliseconds: 100));
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    }
  }

  // ── Verdict helpers ───────────────────────────────────────────────────────

  Color _verdictColor(BuildContext context) {
    switch (widget.result.claimVeracity) {
      case ClaimVeracity.trueVerdict:    return DfactoColors.verdictTrue;
      case ClaimVeracity.mostlyTrue:     return const Color(0xFF8BC34A);
      case ClaimVeracity.halfTrue:       return DfactoColors.verdictMixed;
      case ClaimVeracity.mostlyFalse:    return const Color(0xFFFF5722);
      case ClaimVeracity.falseVerdict:   return DfactoColors.verdictFalse;
      case ClaimVeracity.unknown:        return DfactoColors.verdictUnknown;
    }
  }

  String get _verdictLabel {
    switch (widget.result.claimVeracity) {
      case ClaimVeracity.trueVerdict:    return 'TRUE';
      case ClaimVeracity.mostlyTrue:     return 'MOSTLY TRUE';
      case ClaimVeracity.halfTrue:       return 'HALF TRUE';
      case ClaimVeracity.mostlyFalse:    return 'MOSTLY FALSE';
      case ClaimVeracity.falseVerdict:   return 'FALSE';
      case ClaimVeracity.unknown:        return 'UNVERIFIABLE';
    }
  }

  IconData get _verdictIcon {
    switch (widget.result.claimVeracity) {
      case ClaimVeracity.trueVerdict:    return Icons.check_circle_rounded;
      case ClaimVeracity.mostlyTrue:     return Icons.check_circle_outline_rounded;
      case ClaimVeracity.halfTrue:       return Icons.info_rounded;
      case ClaimVeracity.mostlyFalse:    return Icons.warning_amber_rounded;
      case ClaimVeracity.falseVerdict:   return Icons.cancel_rounded;
      case ClaimVeracity.unknown:        return Icons.help_rounded;
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final vc = _verdictColor(context);
    final sources = widget.result.keySources.isNotEmpty
        ? widget.result.keySources
        : (widget.result.keySource != null
            ? [widget.result.keySource!]
            : <String>[]);

    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (ctx, sheetScroll) {
        return Container(
          decoration: BoxDecoration(
            color: context.surface,
            borderRadius:
                const BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            children: [
              // ── Drag handle ───────────────────────────────────────────────
              Center(
                child: Container(
                  margin: const EdgeInsets.only(top: 10, bottom: 4),
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: context.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),

              // ── Verdict header ────────────────────────────────────────────
              Container(
                margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: vc.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: vc.withValues(alpha: 0.25),
                    width: 1,
                  ),
                ),
                child: Row(
                  children: [
                    Icon(_verdictIcon, color: vc, size: 20),
                    const SizedBox(width: 10),
                    Text(
                      _verdictLabel,
                      style: DfactoTextStyles.headlineMedium(vc)
                          .copyWith(letterSpacing: 1.2, fontSize: 16),
                    ),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: vc.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '${(widget.result.confidenceScore * 100).round()}% confidence',
                        style: DfactoTextStyles.bodySmall(vc)
                            .copyWith(fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
              ),

              // ── Scrollable content ────────────────────────────────────────
              Expanded(
                child: ListView(
                  controller: sheetScroll,
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                  children: [
                    // Claim
                    Text(
                      'Claim',
                      style: DfactoTextStyles.labelBold(context.textMuted)
                          .copyWith(letterSpacing: 0.8),
                    ),
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
                    const SizedBox(height: 18),

                    // Full explanation
                    if (widget.result.summaryAndExplanation.isNotEmpty) ...[
                      Text(
                        'Analysis',
                        style: DfactoTextStyles.labelBold(context.textMuted)
                            .copyWith(letterSpacing: 0.8),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        widget.result.summaryAndExplanation,
                        style: DfactoTextStyles.bodyMedium(context.textPrimary)
                            .copyWith(height: 1.65),
                      ),
                      const SizedBox(height: 18),
                    ],

                    // Sources
                    if (sources.isNotEmpty) ...[
                      Text(
                        'Sources',
                        style: DfactoTextStyles.labelBold(context.textMuted)
                            .copyWith(letterSpacing: 0.8),
                      ),
                      const SizedBox(height: 8),
                      Container(
                        decoration: BoxDecoration(
                          color: context.surfaceHigh,
                          borderRadius: BorderRadius.circular(10),
                          border:
                              Border.all(color: context.border, width: 1),
                        ),
                        child: Column(
                          children: [
                            for (int i = 0; i < sources.length; i++)
                              _DetailSourceRow(
                                url: sources[i],
                                isLast: i == sources.length - 1,
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],

                    // Follow-up answer
                    if (_answer != null) ...[
                      Text(
                        'Answer',
                        style: DfactoTextStyles.labelBold(context.textMuted)
                            .copyWith(letterSpacing: 0.8),
                      ),
                      const SizedBox(height: 6),
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: context.accentSoft,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                              color: context.border, width: 1),
                        ),
                        child: Text(
                          _answer!,
                          style: DfactoTextStyles.bodyMedium(
                              context.textPrimary).copyWith(height: 1.65),
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],

                    const SizedBox(height: 80), // Space for input bar
                  ],
                ),
              ),

              // ── Follow-up input ───────────────────────────────────────────
              Container(
                padding: EdgeInsets.fromLTRB(
                  16, 10, 16,
                  MediaQuery.of(context).viewInsets.bottom + 12,
                ),
                decoration: BoxDecoration(
                  color: context.surface,
                  border: Border(top: BorderSide(color: context.border, width: 1)),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _questionController,
                        style: DfactoTextStyles.bodyMedium(context.textPrimary),
                        decoration: InputDecoration(
                          hintText: 'Ask a follow-up question…',
                          hintStyle:
                              DfactoTextStyles.bodyMedium(context.textMuted),
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
                    _isLoading
                        ? const SizedBox(
                            width: 38,
                            height: 38,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : GestureDetector(
                            onTap: _askFollowup,
                            child: Container(
                              width: 38,
                              height: 38,
                              decoration: BoxDecoration(
                                color: context.accent,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Icon(
                                Icons.send_rounded,
                                color: context.isDark
                                    ? Colors.black
                                    : Colors.white,
                                size: 18,
                              ),
                            ),
                          ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ── Source row in detail sheet ────────────────────────────────────────────────

class _DetailSourceRow extends StatelessWidget {
  const _DetailSourceRow({required this.url, required this.isLast});

  final String url;
  final bool isLast;

  Future<void> _launch() async {
    final uri = Uri.tryParse(url);
    if (uri != null && await canLaunchUrl(uri)) {
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
      borderRadius: isLast
          ? const BorderRadius.vertical(bottom: Radius.circular(10))
          : BorderRadius.zero,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          border: isLast
              ? null
              : Border(
                  bottom: BorderSide(color: context.border, width: 0.5)),
        ),
        child: Row(
          children: [
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
                    style: DfactoTextStyles.bodySmall(context.textMuted)
                        .copyWith(decoration: TextDecoration.underline),
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                  ),
                ],
              ),
            ),
            Icon(Icons.open_in_new_rounded,
                color: context.textMuted, size: 13),
          ],
        ),
      ),
    );
  }
}

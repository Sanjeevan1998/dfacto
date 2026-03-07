import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../models/fact_check_result.dart';
import '../models/transcript_segment.dart';

/// Live scrolling transcript panel.
/// Renders spoken text as it arrives, with inline verdict highlights
/// and a pulsing indicator for claims currently being fact-checked.
class LiveTranscriptPanel extends StatefulWidget {
  const LiveTranscriptPanel({
    super.key,
    required this.segments,
    required this.isListening,
  });

  final List<TranscriptSegment> segments;
  final bool isListening;

  @override
  State<LiveTranscriptPanel> createState() => _LiveTranscriptPanelState();
}

class _LiveTranscriptPanelState extends State<LiveTranscriptPanel>
    with SingleTickerProviderStateMixin {
  final _scroll = ScrollController();
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
  }

  @override
  void didUpdateWidget(LiveTranscriptPanel old) {
    super.didUpdateWidget(old);
    // Auto-scroll to bottom whenever segments change
    if (widget.segments.length != old.segments.length ||
        widget.segments.lastOrNull?.result != old.segments.lastOrNull?.result) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    }
  }

  void _scrollToBottom() {
    if (_scroll.hasClients) {
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  @override
  void dispose() {
    _scroll.dispose();
    _pulse.dispose();
    super.dispose();
  }

  Color _verdictColor(ClaimVeracity v) {
    switch (v) {
      case ClaimVeracity.trueVerdict:
        return DfactoColors.verdictTrue;
      case ClaimVeracity.mostlyTrue:
        return const Color(0xFF8BC34A);
      case ClaimVeracity.halfTrue:
        return DfactoColors.verdictMixed;
      case ClaimVeracity.mostlyFalse:
        return const Color(0xFFFF5722);
      case ClaimVeracity.falseVerdict:
        return DfactoColors.verdictFalse;
      case ClaimVeracity.unknown:
        return DfactoColors.verdictUnknown;
    }
  }

  String _verdictEmoji(ClaimVeracity v) {
    switch (v) {
      case ClaimVeracity.trueVerdict:
        return '✓';
      case ClaimVeracity.mostlyTrue:
        return '✓~';
      case ClaimVeracity.halfTrue:
        return '~';
      case ClaimVeracity.mostlyFalse:
        return '✗~';
      case ClaimVeracity.falseVerdict:
        return '✗';
      case ClaimVeracity.unknown:
        return '?';
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.segments.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.mic_none_rounded,
              size: 32,
              color: context.textMuted,
            ),
            const SizedBox(height: 8),
            Text(
              widget.isListening
                  ? 'Listening… speak a claim'
                  : 'Tap the mic to start',
              style: DfactoTextStyles.bodyMedium(context.textMuted),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      itemCount: widget.segments.length,
      itemBuilder: (context, i) {
        final seg = widget.segments[i];
        return _SegmentTile(
          segment: seg,
          pulse: _pulse,
          verdictColor: seg.isChecked ? _verdictColor(seg.result!.claimVeracity) : null,
          verdictEmoji: seg.isChecked ? _verdictEmoji(seg.result!.claimVeracity) : null,
        );
      },
    );
  }
}

// ── Individual transcript segment tile ───────────────────────────────────────

class _SegmentTile extends StatelessWidget {
  const _SegmentTile({
    required this.segment,
    required this.pulse,
    this.verdictColor,
    this.verdictEmoji,
  });

  final TranscriptSegment segment;
  final AnimationController pulse;
  final Color? verdictColor;
  final String? verdictEmoji;

  @override
  Widget build(BuildContext context) {
    final hasClaim = segment.hasClaim;
    final isPending = segment.isPending;
    final isChecked = segment.isChecked;
    final isError = segment.isError;
    final vc = verdictColor;

    Color? bgColor;
    Color borderColor = Colors.transparent;
    if (isChecked && vc != null) {
      bgColor = vc.withValues(alpha: 0.08);
      borderColor = vc.withValues(alpha: 0.3);
    } else if (isPending || isError) {
      bgColor = context.surfaceHigh;
      borderColor = context.border;
    }

    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      curve: Curves.easeInOut,
      margin: const EdgeInsets.only(bottom: 8),
      padding: hasClaim
          ? const EdgeInsets.fromLTRB(12, 8, 12, 8)
          : const EdgeInsets.symmetric(vertical: 2),
      decoration: hasClaim
          ? BoxDecoration(
              color: bgColor,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: borderColor, width: 1),
            )
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildText(context, vc),
          if (hasClaim) ...[
            const SizedBox(height: 6),
            if (isChecked && vc != null)
              _VerdictChip(
                label: segment.result!.claimVeracity.name
                    .replaceAll('Verdict', '')
                    .toUpperCase(),
                emoji: verdictEmoji!,
                color: vc,
                confidence: segment.result!.confidenceScore,
              )
            else if (isError)
              _ErrorBadge(message: segment.error!)
            else if (isPending)
              _PendingIndicator(pulse: pulse),
          ],
        ],
      ),
    );
  }

  Widget _buildText(BuildContext context, Color? verdictColor) {
    final fullText = segment.text;
    final claim = segment.claim;

    if (!segment.hasClaim || claim.isEmpty) {
      // Plain text — no claim found
      return Text(
        fullText,
        style: DfactoTextStyles.bodyMedium(context.textSecondary),
      );
    }

    // Try to locate the claim within the transcript for inline highlighting
    final idx = fullText.toLowerCase().indexOf(claim.toLowerCase());
    if (idx == -1) {
      // Claim not found verbatim — show all text highlighted
      return RichText(
        text: TextSpan(
          text: fullText,
          style: DfactoTextStyles.bodyMedium(
            verdictColor ?? context.textPrimary,
          ).copyWith(fontWeight: FontWeight.w600),
        ),
      );
    }

    final before = fullText.substring(0, idx);
    final match = fullText.substring(idx, idx + claim.length);
    final after = fullText.substring(idx + claim.length);
    final vc = verdictColor ?? context.accent;

    return RichText(
      text: TextSpan(
        style: DfactoTextStyles.bodyMedium(context.textSecondary),
        children: [
          if (before.isNotEmpty) TextSpan(text: before),
          WidgetSpan(
            alignment: PlaceholderAlignment.middle,
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 1),
              padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
              decoration: BoxDecoration(
                color: vc.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: vc.withValues(alpha: 0.4), width: 0.5),
              ),
              child: Text(
                match,
                style: DfactoTextStyles.bodyMedium(vc).copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
          if (after.isNotEmpty) TextSpan(text: after),
        ],
      ),
    );
  }
}

// ── Verdict chip ──────────────────────────────────────────────────────────────

class _VerdictChip extends StatelessWidget {
  const _VerdictChip({
    required this.label,
    required this.emoji,
    required this.color,
    required this.confidence,
  });

  final String label;
  final String emoji;
  final Color color;
  final double confidence;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: color.withValues(alpha: 0.35), width: 1),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(emoji, style: TextStyle(color: color, fontSize: 11)),
              const SizedBox(width: 4),
              Text(
                label,
                style: DfactoTextStyles.labelBold(color)
                    .copyWith(fontSize: 10, letterSpacing: 0.8),
              ),
            ],
          ),
        ),
        const SizedBox(width: 6),
        Text(
          '${(confidence * 100).round()}% confidence',
          style: DfactoTextStyles.bodySmall(context.textMuted)
              .copyWith(fontSize: 10),
        ),
      ],
    );
  }
}

// ── Pending pulsing dots ──────────────────────────────────────────────────────

class _PendingIndicator extends StatelessWidget {
  const _PendingIndicator({required this.pulse});
  final AnimationController pulse;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedBuilder(
          animation: pulse,
          builder: (_, __) => Opacity(
            opacity: 0.4 + 0.6 * pulse.value,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(
                3,
                (i) => Container(
                  margin: EdgeInsets.only(right: i < 2 ? 3 : 0),
                  width: 4,
                  height: 4,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: context.accent,
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          'Fact-checking…',
          style: DfactoTextStyles.bodySmall(context.textMuted)
              .copyWith(fontSize: 10),
        ),
      ],
    );
  }
}

// ── Error badge ───────────────────────────────────────────────────────────────

class _ErrorBadge extends StatelessWidget {
  const _ErrorBadge({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.error_outline_rounded,
            size: 12, color: context.textMuted),
        const SizedBox(width: 4),
        Flexible(
          child: Text(
            message.contains('Connection refused') || message.contains('timeout')
                ? 'Backend unreachable — is the server running?'
                : 'Check failed: $message',
            style: DfactoTextStyles.bodySmall(context.textMuted)
                .copyWith(fontSize: 10),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}

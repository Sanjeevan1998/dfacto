import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../models/fact_check_result.dart';
import 'package:url_launcher/url_launcher.dart';

class FactCheckCard extends StatelessWidget {
  const FactCheckCard({super.key, required this.result});

  final FactCheckResult result;

  Color get _verdictColor {
    switch (result.claimVeracity) {
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

  String get _verdictLabel {
    switch (result.claimVeracity) {
      case ClaimVeracity.trueVerdict:
        return 'TRUE';
      case ClaimVeracity.mostlyTrue:
        return 'MOSTLY TRUE';
      case ClaimVeracity.halfTrue:
        return 'HALF TRUE';
      case ClaimVeracity.mostlyFalse:
        return 'MOSTLY FALSE';
      case ClaimVeracity.falseVerdict:
        return 'FALSE';
      case ClaimVeracity.unknown:
        return 'UNVERIFIABLE';
    }
  }

  IconData get _verdictIcon {
    switch (result.claimVeracity) {
      case ClaimVeracity.trueVerdict:
        return Icons.check_circle_rounded;
      case ClaimVeracity.mostlyTrue:
        return Icons.check_circle_outline_rounded;
      case ClaimVeracity.halfTrue:
        return Icons.info_rounded;
      case ClaimVeracity.mostlyFalse:
        return Icons.warning_amber_rounded;
      case ClaimVeracity.falseVerdict:
        return Icons.cancel_rounded;
      case ClaimVeracity.unknown:
        return Icons.help_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    // ── Pending / loading state ─────────────────────────────────────────────
    if (result.isPending) {
      return _PendingCard(claimText: result.claimText);
    }

    final vc = _verdictColor;
    final sources = result.keySources.isNotEmpty
        ? result.keySources
        : (result.keySource != null ? [result.keySource!] : <String>[]);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      decoration: BoxDecoration(
        color: context.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: context.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Verdict Badge Bar ─────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: vc.withValues(alpha: 0.07),
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(15)),
              border: Border(
                bottom: BorderSide(color: context.border, width: 1),
              ),
            ),
            child: Row(
              children: [
                Icon(_verdictIcon, color: vc, size: 15),
                const SizedBox(width: 6),
                Text(
                  _verdictLabel,
                  style: DfactoTextStyles.labelBold(vc)
                      .copyWith(letterSpacing: 1.2),
                ),
                const Spacer(),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: vc.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '${(result.confidenceScore * 100).round()}%',
                    style: DfactoTextStyles.labelBold(vc)
                        .copyWith(fontSize: 10),
                  ),
                ),
              ],
            ),
          ),

          // ── Claim Text ───────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 4),
            child: Text(
              '"${result.claimText}"',
              style: DfactoTextStyles.bodyMedium(context.textSecondary)
                  .copyWith(fontStyle: FontStyle.italic, fontSize: 12),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // ── Summary ──────────────────────────────────────────────────────
          if (result.summaryAndExplanation.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
              child: Text(
                result.summaryAndExplanation,
                style: DfactoTextStyles.bodyMedium(context.textSecondary),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ),

          // ── Sources (clickable links) ─────────────────────────────────────
          if (sources.isNotEmpty)
            Container(
              decoration: BoxDecoration(
                color: context.surfaceHigh,
                borderRadius: const BorderRadius.vertical(
                  bottom: Radius.circular(15),
                ),
              ),
              child: Column(
                children: [
                  for (int i = 0; i < sources.length && i < 3; i++)
                    _SourceRow(
                      url: sources[i],
                      isLast: i == sources.length - 1 || i == 2,
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ── Clickable source row ──────────────────────────────────────────────────────

class _SourceRow extends StatelessWidget {
  const _SourceRow({required this.url, required this.isLast});

  final String url;
  final bool isLast;

  Future<void> _launch() async {
    final uri = Uri.tryParse(url);
    if (uri != null && await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  String get _displayUrl {
    try {
      final uri = Uri.parse(url);
      return uri.host.replaceFirst('www.', '');
    } catch (_) {
      return url;
    }
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: _launch,
      borderRadius: isLast
          ? const BorderRadius.vertical(bottom: Radius.circular(15))
          : BorderRadius.zero,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          border: isLast
              ? null
              : Border(bottom: BorderSide(color: context.border, width: 0.5)),
        ),
        child: Row(
          children: [
            Icon(Icons.open_in_new_rounded, color: context.textMuted, size: 11),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                _displayUrl,
                style: DfactoTextStyles.bodySmall(context.textMuted)
                    .copyWith(decoration: TextDecoration.underline),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Pending / loading card ────────────────────────────────────────────────────

class _PendingCard extends StatelessWidget {
  const _PendingCard({required this.claimText});

  final String claimText;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      decoration: BoxDecoration(
        color: context.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: context.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Checking header ───────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: DfactoColors.verdictMixed.withValues(alpha: 0.07),
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(15)),
              border: Border(
                bottom: BorderSide(color: context.border, width: 1),
              ),
            ),
            child: Row(
              children: [
                SizedBox(
                  width: 13,
                  height: 13,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    color: DfactoColors.verdictMixed,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  'CHECKING…',
                  style: DfactoTextStyles.labelBold(DfactoColors.verdictMixed)
                      .copyWith(letterSpacing: 1.2),
                ),
              ],
            ),
          ),

          // ── Claim text ───────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
            child: Text(
              '"$claimText"',
              style: DfactoTextStyles.bodyMedium(context.textSecondary)
                  .copyWith(fontStyle: FontStyle.italic, fontSize: 12),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}

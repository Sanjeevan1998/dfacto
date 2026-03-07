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
      case ClaimVeracity.falseVerdict:
        return DfactoColors.verdictFalse;
      case ClaimVeracity.mixed:
        return DfactoColors.verdictMixed;
      case ClaimVeracity.unknown:
        return DfactoColors.verdictUnknown;
    }
  }

  String get _verdictLabel {
    switch (result.claimVeracity) {
      case ClaimVeracity.trueVerdict:
        return 'TRUE';
      case ClaimVeracity.falseVerdict:
        return 'FALSE';
      case ClaimVeracity.mixed:
        return 'MIXED';
      case ClaimVeracity.unknown:
        return 'UNKNOWN';
    }
  }

  IconData get _verdictIcon {
    switch (result.claimVeracity) {
      case ClaimVeracity.trueVerdict:
        return Icons.check_circle_rounded;
      case ClaimVeracity.falseVerdict:
        return Icons.cancel_rounded;
      case ClaimVeracity.mixed:
        return Icons.info_rounded;
      case ClaimVeracity.unknown:
        return Icons.help_rounded;
    }
  }

  Future<void> _launchSource() async {
    if (result.keySource != null) {
      final uri = Uri.tryParse(result.keySource!);
      if (uri != null && await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final vc = _verdictColor;

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
                // Confidence badge
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
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
            child: Text(
              result.summaryAndExplanation,
              style: DfactoTextStyles.bodyMedium(context.textSecondary),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // ── Source Link ──────────────────────────────────────────────────
          if (result.keySource != null)
            InkWell(
              onTap: _launchSource,
              borderRadius: const BorderRadius.vertical(
                bottom: Radius.circular(15),
              ),
              child: Container(
                width: double.infinity,
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                decoration: BoxDecoration(
                  color: context.surfaceHigh,
                  borderRadius: const BorderRadius.vertical(
                    bottom: Radius.circular(15),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.open_in_new_rounded,
                      color: context.textMuted,
                      size: 12,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        result.keySource!,
                        style: DfactoTextStyles.bodySmall(context.textMuted),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

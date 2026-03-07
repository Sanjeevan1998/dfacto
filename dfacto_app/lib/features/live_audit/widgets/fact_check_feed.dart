import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../models/fact_check_result.dart';
import 'fact_check_card.dart';

class FactCheckFeed extends StatelessWidget {
  const FactCheckFeed({super.key, this.results});

  final List<FactCheckResult>? results;

  @override
  Widget build(BuildContext context) {
    final items = results ?? _mockResults;

    if (items.isEmpty) {
      return _EmptyFeedPlaceholder();
    }

    return ListView.builder(
      padding: const EdgeInsets.only(bottom: 16),
      itemCount: items.length,
      itemBuilder: (context, index) {
        return TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.0, end: 1.0),
          duration: Duration(milliseconds: 300 + (index * 60)),
          curve: Curves.easeOutCubic,
          builder: (context, value, child) {
            return Transform.translate(
              offset: Offset(30 * (1 - value), 0),
              child: Opacity(opacity: value, child: child),
            );
          },
          child: FactCheckCard(result: items[index]),
        );
      },
    );
  }
}

class _EmptyFeedPlaceholder extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.receipt_long_outlined,
            color: context.border,
            size: 44,
          ),
          const SizedBox(height: 12),
          Text(
            'Fact-checks will appear here',
            style: DfactoTextStyles.bodyMedium(context.textSecondary),
          ),
          const SizedBox(height: 4),
          Text(
            'Start listening to begin monitoring',
            style: DfactoTextStyles.bodySmall(context.textMuted),
          ),
        ],
      ),
    );
  }
}

// ─── Mock data for development & testing ─────────────────────────────────────
final List<FactCheckResult> _mockResults = [
  FactCheckResult(
    id: '1',
    claimText: 'The economy grew by 4.2% last quarter.',
    claimVeracity: ClaimVeracity.mixed,
    confidenceScore: 0.61,
    summaryAndExplanation:
        'GDP grew by 2.1%, not 4.2%. The higher figure refers to a single sector, not the overall economy.',
    keySource: 'https://www.bea.gov',
  ),
  FactCheckResult(
    id: '2',
    claimText: 'Vaccines contain microchips for surveillance.',
    claimVeracity: ClaimVeracity.falseVerdict,
    confidenceScore: 0.98,
    summaryAndExplanation:
        'No credible scientific evidence supports this claim. Multiple global health authorities have refuted it.',
    keySource: 'https://www.who.int',
  ),
  FactCheckResult(
    id: '3',
    claimText: 'Renewable energy now accounts for over 30% of global electricity.',
    claimVeracity: ClaimVeracity.trueVerdict,
    confidenceScore: 0.87,
    summaryAndExplanation:
        'IEA data confirms renewables exceeded 30% of global electricity generation in 2023.',
    keySource: 'https://www.iea.org',
  ),
];

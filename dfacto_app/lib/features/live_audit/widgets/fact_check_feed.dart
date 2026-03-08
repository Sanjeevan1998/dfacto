import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../models/fact_check_result.dart';
import 'fact_check_card.dart';
import 'fact_check_detail_sheet.dart';

class FactCheckFeed extends StatelessWidget {
  const FactCheckFeed({
    super.key,
    this.results,
    this.host = '192.168.1.158',
    this.port = 8000,
  });

  final List<FactCheckResult>? results;
  final String host;
  final int port;

  @override
  Widget build(BuildContext context) {
    final items = results ?? [];

    if (items.isEmpty) {
      return _EmptyFeedPlaceholder();
    }

    return ListView.builder(
      padding: const EdgeInsets.only(bottom: 16),
      itemCount: items.length,
      itemBuilder: (context, index) {
        final item = items[index];
        return TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.0, end: 1.0),
          duration: Duration(milliseconds: 300 + (index * 50).clamp(0, 400)),
          curve: Curves.easeOutCubic,
          builder: (context, value, child) {
            return Transform.translate(
              offset: Offset(30 * (1 - value), 0),
              child: Opacity(opacity: value, child: child),
            );
          },
          child: item.isPending
              // Pending cards are not tappable yet
              ? FactCheckCard(result: item)
              // Completed cards open the detail sheet on tap
              : GestureDetector(
                  onTap: () => showFactCheckDetail(
                    context,
                    item,
                    host: host,
                    port: port,
                  ),
                  child: FactCheckCard(result: item),
                ),
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

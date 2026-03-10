import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../models/headline.dart';
import '../../../core/theme/app_theme.dart';

class HeadlineCard extends StatelessWidget {
  const HeadlineCard({
    super.key,
    required this.headline,
    required this.onTap,
  });

  final Headline headline;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final verdictColor = headline.verdictColor(context);
    final verdictBg = headline.verdictBgColor();

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: context.surface,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: context.border, width: 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Meta row: source + date
            Row(
              children: [
                if (headline.source.isNotEmpty)
                  Text(
                    headline.source.toUpperCase(),
                    style: GoogleFonts.outfit(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: context.textMuted,
                      letterSpacing: 0.5,
                    ),
                  ),
                const Spacer(),
                if (headline.timestamp.isNotEmpty)
                  Text(
                    _formatDate(headline.timestamp),
                    style: GoogleFonts.inter(
                      fontSize: 10,
                      color: context.textMuted,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            // Headline title
            Text(
              headline.title,
              style: GoogleFonts.outfit(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: context.textPrimary,
                height: 1.3,
                letterSpacing: -0.2,
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            if (headline.snippet.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                headline.snippet,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  color: context.textSecondary,
                  height: 1.45,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            const SizedBox(height: 10),
            // Bottom row: keyword pill + verdict chip
            Row(
              children: [
                if (headline.keyword.isNotEmpty)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: context.surfaceHigh,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      headline.keyword,
                      style: GoogleFonts.outfit(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: context.textSecondary,
                      ),
                    ),
                  ),
                const Spacer(),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: verdictBg,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    headline.verdict,
                    style: GoogleFonts.outfit(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: verdictColor,
                      letterSpacing: 0.3,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _formatDate(String timestamp) {
    try {
      final dt = DateTime.parse(timestamp);
      final diff = DateTime.now().difference(dt);
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      return '${diff.inDays}d ago';
    } catch (_) {
      return timestamp;
    }
  }
}

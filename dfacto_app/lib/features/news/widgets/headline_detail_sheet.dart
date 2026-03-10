import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/headline.dart';
import '../../../core/theme/app_theme.dart';

class HeadlineDetailSheet extends StatelessWidget {
  const HeadlineDetailSheet({super.key, required this.headline});

  final Headline headline;

  @override
  Widget build(BuildContext context) {
    final verdictColor = headline.verdictColor(context);
    final verdictBg = headline.verdictBgColor();

    return DraggableScrollableSheet(
      initialChildSize: 0.6,
      minChildSize: 0.3,
      maxChildSize: 0.92,
      snap: true,
      snapSizes: const [0.3, 0.6, 0.92],
      builder: (context, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: context.surface,
            borderRadius:
                const BorderRadius.vertical(top: Radius.circular(28)),
            border: Border(top: BorderSide(color: context.border, width: 1)),
          ),
          child: Column(
            children: [
              // Drag handle
              Center(
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 12),
                  width: 44,
                  height: 4,
                  decoration: BoxDecoration(
                    color: context.borderStrong,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              Expanded(
                child: ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 48),
                  children: [
                    // Verdict + confidence row
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: verdictBg,
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            headline.verdict,
                            style: GoogleFonts.outfit(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: verdictColor,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: context.surfaceHigh,
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            '${(headline.confidenceScore * 100).round()}% confidence',
                            style: GoogleFonts.outfit(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: context.textSecondary,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    // Headline title
                    Text(
                      headline.title,
                      style: GoogleFonts.outfit(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: context.textPrimary,
                        height: 1.25,
                        letterSpacing: -0.3,
                      ),
                    ),
                    const SizedBox(height: 4),
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
                    if (headline.snippet.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      Text(
                        headline.snippet,
                        style: GoogleFonts.inter(
                          fontSize: 14,
                          color: context.textSecondary,
                          height: 1.55,
                        ),
                      ),
                    ],
                    if (headline.explanation.isNotEmpty) ...[
                      const SizedBox(height: 24),
                      Text(
                        'WHY THIS VERDICT',
                        style: GoogleFonts.outfit(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: context.textMuted,
                          letterSpacing: 1.0,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: context.surfaceHigh,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: context.border),
                        ),
                        child: Text(
                          headline.explanation,
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            color: context.textSecondary,
                            height: 1.55,
                          ),
                        ),
                      ),
                    ],
                    if (headline.url.isNotEmpty) ...[
                      const SizedBox(height: 24),
                      Text(
                        'SOURCE',
                        style: GoogleFonts.outfit(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: context.textMuted,
                          letterSpacing: 1.0,
                        ),
                      ),
                      const SizedBox(height: 8),
                      GestureDetector(
                        onTap: () async {
                          final uri = Uri.parse(headline.url);
                          if (await canLaunchUrl(uri)) {
                            launchUrl(uri,
                                mode: LaunchMode.externalApplication);
                          }
                        },
                        child: Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: context.surfaceHigh,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: context.border),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.link_rounded,
                                  size: 16, color: context.textSecondary),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  headline.url,
                                  style: GoogleFonts.inter(
                                    fontSize: 12,
                                    color: context.textSecondary,
                                    decoration: TextDecoration.underline,
                                    decorationColor: context.textMuted,
                                  ),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
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

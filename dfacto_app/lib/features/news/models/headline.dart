import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

class Headline {
  final int id;
  final String title;
  final String source;
  final String url;
  final String snippet;
  final String keyword;
  final String verdict;
  final double confidenceScore;
  final String explanation;
  final String timestamp;

  const Headline({
    required this.id,
    required this.title,
    required this.source,
    required this.url,
    required this.snippet,
    required this.keyword,
    required this.verdict,
    required this.confidenceScore,
    required this.explanation,
    required this.timestamp,
  });

  factory Headline.fromJson(Map<String, dynamic> json) {
    return Headline(
      id: json['id'] as int? ?? 0,
      title: json['title'] as String? ?? '',
      source: json['source'] as String? ?? '',
      url: json['url'] as String? ?? '',
      snippet: json['snippet'] as String? ?? '',
      keyword: json['associated_keyword'] as String? ?? '',
      verdict: json['verdict'] as String? ?? 'N/A',
      confidenceScore: (json['confidence_score'] as num?)?.toDouble() ?? 0.0,
      explanation: json['explanation'] as String? ?? '',
      timestamp: json['timestamp'] as String? ?? '',
    );
  }

  Color verdictColor(BuildContext context) {
    switch (verdict) {
      case 'TRUE':
        return const Color(0xFF48D67B);
      case 'FALSE':
        return const Color(0xFFFF5353);
      case 'MIXED':
        return const Color(0xFFFFCC52);
      default:
        return DfactoColors.verdictUnknown;
    }
  }

  Color verdictBgColor() {
    switch (verdict) {
      case 'TRUE':
        return const Color(0x3D48D67B);
      case 'FALSE':
        return const Color(0x3DFF5353);
      case 'MIXED':
        return const Color(0x3DFFCC52);
      default:
        return const Color(0x3D9E9E9E);
    }
  }
}

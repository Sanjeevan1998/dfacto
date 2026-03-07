enum ClaimVeracity { trueVerdict, falseVerdict, mixed, unknown }

class FactCheckResult {
  const FactCheckResult({
    required this.id,
    required this.claimText,
    required this.claimVeracity,
    required this.confidenceScore,
    required this.summaryAndExplanation,
    this.keySource,
  });

  final String id;
  final String claimText;
  final ClaimVeracity claimVeracity;
  final double confidenceScore; // 0.0 – 1.0
  final String summaryAndExplanation;
  final String? keySource;

  factory FactCheckResult.fromJson(Map<String, dynamic> json) {
    return FactCheckResult(
      id: json['id'] as String? ?? DateTime.now().toIso8601String(),
      // Support both camelCase (backend) and snake_case (legacy)
      claimText: json['claimText'] as String? ?? json['claim_text'] as String? ?? '',
      claimVeracity: _parseVeracity(
        json['claimVeracity'] as String? ?? json['claim_veracity'] as String?,
      ),
      confidenceScore: (json['confidenceScore'] as num?)?.toDouble() ??
          (json['confidence_score'] as num?)?.toDouble() ?? 0.0,
      summaryAndExplanation: json['summaryAndExplanation'] as String? ??
          json['summary_and_explanation'] as String? ?? '',
      keySource: json['keySource'] as String? ??
          json['key_source'] as String? ??
          (json['key_sources'] is List
              ? (json['key_sources'] as List).isNotEmpty
                  ? (json['key_sources'] as List).first as String?
                  : null
              : json['key_sources'] as String?),
    );
  }

  static ClaimVeracity _parseVeracity(String? value) {
    switch (value?.toLowerCase()) {
      case 'trueverdict':
      case 'true':
        return ClaimVeracity.trueVerdict;
      case 'falseverdict':
      case 'false':
        return ClaimVeracity.falseVerdict;
      case 'mixed':
        return ClaimVeracity.mixed;
      default:
        return ClaimVeracity.unknown;
    }
  }
}

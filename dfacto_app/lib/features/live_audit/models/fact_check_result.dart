enum ClaimVeracity {
  trueVerdict,
  mostlyTrue,
  halfTrue,
  mostlyFalse,
  falseVerdict,
  unknown,
}

class FactCheckResult {
  const FactCheckResult({
    required this.id,
    required this.claimText,
    required this.claimVeracity,
    required this.confidenceScore,
    required this.summaryAndExplanation,
    this.keySource,
    this.keySources = const [],
    this.isPending = false,
  });

  final String id;
  final String claimText;
  final ClaimVeracity claimVeracity;
  final double confidenceScore; // 0.0 – 1.0
  final String summaryAndExplanation;
  final String? keySource;
  final List<String> keySources;

  /// True while the backend is still running the pipeline for this claim.
  final bool isPending;

  /// Creates a placeholder shown immediately when the backend starts checking.
  factory FactCheckResult.pending(String claimText) {
    return FactCheckResult(
      id: 'pending__$claimText',
      claimText: claimText,
      claimVeracity: ClaimVeracity.unknown,
      confidenceScore: 0.0,
      summaryAndExplanation: '',
      isPending: true,
    );
  }

  factory FactCheckResult.fromJson(Map<String, dynamic> json) {
    // Collect all source URLs (key_sources array + keySource single)
    final sources = <String>[];
    final raw = json['key_sources'];
    if (raw is List) sources.addAll(raw.whereType<String>());
    final single = json['keySource'] as String? ?? json['key_source'] as String?;
    if (single != null && !sources.contains(single)) sources.insert(0, single);

    return FactCheckResult(
      id: json['id'] as String? ?? DateTime.now().toIso8601String(),
      claimText: json['claimText'] as String? ?? json['claim_text'] as String? ?? '',
      claimVeracity: _parseVeracity(
        json['claimVeracity'] as String? ?? json['claim_veracity'] as String?,
      ),
      confidenceScore: (json['confidenceScore'] as num?)?.toDouble() ??
          (json['confidence_score'] as num?)?.toDouble() ?? 0.0,
      summaryAndExplanation: json['summaryAndExplanation'] as String? ??
          json['summary_and_explanation'] as String? ?? '',
      keySource: sources.isNotEmpty ? sources.first : null,
      keySources: sources,
    );
  }

  static ClaimVeracity _parseVeracity(String? value) {
    switch (value?.toLowerCase()) {
      case 'trueverdict':
      case 'true':
        return ClaimVeracity.trueVerdict;
      case 'mostlytrue':
      case 'mostly true':
        return ClaimVeracity.mostlyTrue;
      case 'halftrue':
      case 'half true':
      case 'mixed':
        return ClaimVeracity.halfTrue;
      case 'mostlyfalse':
      case 'mostly false':
        return ClaimVeracity.mostlyFalse;
      case 'falseverdict':
      case 'false':
        return ClaimVeracity.falseVerdict;
      default:
        return ClaimVeracity.unknown;
    }
  }
}

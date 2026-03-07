import '../models/fact_check_result.dart';

/// A segment of the live transcript.
/// [text] — the spoken words for this chunk.
/// [claim] — the extracted claim (may be empty if no claim found).
/// [result] — null until fact-check completes; then populated with verdict.
class TranscriptSegment {
  TranscriptSegment({
    required this.id,
    required this.text,
    required this.claim,
    this.result,
    this.error,
  });

  final String id;
  final String text;
  String claim;            // mutable: classify upgrades '' → extracted claim
  FactCheckResult? result;
  String? error;

  bool get hasClaim => claim.isNotEmpty;
  bool get isChecked => result != null;
  bool get isError => error != null;
  bool get isPending => hasClaim && !isChecked && !isError;
}

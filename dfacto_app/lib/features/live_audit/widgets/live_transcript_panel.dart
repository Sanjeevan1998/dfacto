import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

/// Live scrolling transcript panel — Granola-style continuous text.
///
/// Shows all committed (finalised) words in normal colour followed
/// immediately by the in-progress partial words in a dimmed style.
/// Auto-scrolls to bottom on every update so the latest word is
/// always visible.
class LiveTranscriptPanel extends StatefulWidget {
  const LiveTranscriptPanel({
    super.key,
    required this.committedText,
    required this.partialText,
    required this.isListening,
  });

  /// All finalised words for the session (never shrinks).
  final String committedText;

  /// Current in-progress partial from the active STT session.
  final String partialText;

  final bool isListening;

  @override
  State<LiveTranscriptPanel> createState() => _LiveTranscriptPanelState();
}

class _LiveTranscriptPanelState extends State<LiveTranscriptPanel> {
  final _scroll = ScrollController();

  @override
  void didUpdateWidget(LiveTranscriptPanel old) {
    super.didUpdateWidget(old);
    // Auto-scroll to bottom on any text change (committed or partial)
    if (widget.committedText != old.committedText ||
        widget.partialText != old.partialText) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    }
  }

  void _scrollToBottom() {
    if (_scroll.hasClients) {
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    }
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final hasAnyText =
        widget.committedText.isNotEmpty || widget.partialText.isNotEmpty;

    if (!hasAnyText) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.mic_none_rounded, size: 32, color: context.textMuted),
            const SizedBox(height: 8),
            Text(
              widget.isListening ? 'Listening… speak a claim' : 'Tap the mic to start',
              style: DfactoTextStyles.bodyMedium(context.textMuted),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      controller: _scroll,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      child: RichText(
        text: TextSpan(
          style: DfactoTextStyles.bodyMedium(context.textSecondary)
              .copyWith(height: 1.6),
          children: [
            // All committed (finalised) words — normal colour
            if (widget.committedText.isNotEmpty)
              TextSpan(text: widget.committedText),

            // Space between committed and partial
            if (widget.committedText.isNotEmpty && widget.partialText.isNotEmpty)
              const TextSpan(text: ' '),

            // In-progress partial words — dimmed to show they're tentative
            if (widget.partialText.isNotEmpty)
              TextSpan(
                text: widget.partialText,
                style: TextStyle(
                  color: context.textSecondary.withValues(alpha: 0.45),
                  fontStyle: FontStyle.italic,
                ),
              ),

            // Blinking cursor while listening
            if (widget.isListening)
              WidgetSpan(
                alignment: PlaceholderAlignment.middle,
                child: _Cursor(),
              ),
          ],
        ),
      ),
    );
  }
}

// ── Blinking cursor ───────────────────────────────────────────────────────────

class _Cursor extends StatefulWidget {
  @override
  State<_Cursor> createState() => _CursorState();
}

class _CursorState extends State<_Cursor> with SingleTickerProviderStateMixin {
  late final AnimationController _blink;

  @override
  void initState() {
    super.initState();
    _blink = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 530),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _blink.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _blink,
      builder: (_, __) => Opacity(
        opacity: _blink.value > 0.5 ? 1.0 : 0.0,
        child: Container(
          margin: const EdgeInsets.only(left: 2),
          width: 2,
          height: 14,
          decoration: BoxDecoration(
            color: context.accent,
            borderRadius: BorderRadius.circular(1),
          ),
        ),
      ),
    );
  }
}

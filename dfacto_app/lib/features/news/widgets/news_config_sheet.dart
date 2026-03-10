import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../core/theme/app_theme.dart';
import '../services/news_api_service.dart';

class NewsConfigSheet extends StatefulWidget {
  const NewsConfigSheet({
    super.key,
    required this.initialKeywords,
    required this.initialInterval,
    required this.onSaved,
  });

  final String initialKeywords;
  final int initialInterval;
  final VoidCallback onSaved;

  @override
  State<NewsConfigSheet> createState() => _NewsConfigSheetState();
}

class _NewsConfigSheetState extends State<NewsConfigSheet> {
  late final TextEditingController _keywordsCtrl;
  late final TextEditingController _intervalCtrl;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _keywordsCtrl = TextEditingController(text: widget.initialKeywords);
    _intervalCtrl =
        TextEditingController(text: widget.initialInterval.toString());
  }

  @override
  void dispose() {
    _keywordsCtrl.dispose();
    _intervalCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final keywords = _keywordsCtrl.text.trim();
    final interval = int.tryParse(_intervalCtrl.text.trim()) ?? 30;
    if (keywords.isEmpty) {
      setState(() => _error = 'Keywords cannot be empty.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await NewsApiService().updateConfig(keywords, interval);
      if (mounted) {
        widget.onSaved();
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = 'Failed to save. Is the news backend running?';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 40,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Handle
          Center(
            child: Container(
              width: 44,
              height: 4,
              decoration: BoxDecoration(
                color: context.borderStrong,
                borderRadius: BorderRadius.circular(999),
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Crawler Config',
            style: GoogleFonts.outfit(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: context.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Enter keywords (comma-separated) and how often to crawl.',
            style: GoogleFonts.inter(
                fontSize: 13, color: context.textSecondary),
          ),
          const SizedBox(height: 20),
          Text(
            'KEYWORDS',
            style: GoogleFonts.outfit(
              fontSize: 10,
              fontWeight: FontWeight.w700,
              color: context.textMuted,
              letterSpacing: 1.0,
            ),
          ),
          const SizedBox(height: 6),
          TextField(
            controller: _keywordsCtrl,
            style:
                GoogleFonts.inter(fontSize: 14, color: context.textPrimary),
            decoration: InputDecoration(
              hintText: 'e.g. climate change, AI, economy',
              hintStyle: GoogleFonts.inter(
                  fontSize: 14, color: context.textMuted),
              filled: true,
              fillColor: context.surfaceHigh,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'INTERVAL (MINUTES)',
            style: GoogleFonts.outfit(
              fontSize: 10,
              fontWeight: FontWeight.w700,
              color: context.textMuted,
              letterSpacing: 1.0,
            ),
          ),
          const SizedBox(height: 6),
          TextField(
            controller: _intervalCtrl,
            keyboardType: TextInputType.number,
            style:
                GoogleFonts.inter(fontSize: 14, color: context.textPrimary),
            decoration: InputDecoration(
              hintText: '30',
              hintStyle: GoogleFonts.inter(
                  fontSize: 14, color: context.textMuted),
              filled: true,
              fillColor: context.surfaceHigh,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(
              _error!,
              style: GoogleFonts.inter(
                  fontSize: 12, color: DfactoColors.verdictFalse),
            ),
          ],
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _saving ? null : _save,
              style: ElevatedButton.styleFrom(
                backgroundColor: context.accent,
                foregroundColor:
                    context.isDark ? Colors.black : Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
                elevation: 0,
              ),
              child: _saving
                  ? SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: context.isDark ? Colors.black : Colors.white,
                      ),
                    )
                  : Text(
                      'Save Configuration',
                      style: GoogleFonts.outfit(
                          fontSize: 14, fontWeight: FontWeight.w700),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme/app_theme.dart';
import 'models/headline.dart';
import 'services/news_api_service.dart';
import 'widgets/headline_card.dart';
import 'widgets/headline_detail_sheet.dart';
import 'widgets/news_config_sheet.dart';

class NewsScreen extends StatefulWidget {
  const NewsScreen({super.key});

  @override
  State<NewsScreen> createState() => _NewsScreenState();
}

class _NewsScreenState extends State<NewsScreen> {
  final _api = NewsApiService();
  List<Headline> _headlines = [];
  String _keywords = '';
  int _interval = 60;
  bool _loading = true;
  bool _triggering = false;
  String? _error;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadAll();
    // Auto-refresh every 30 seconds
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) _loadHeadlines();
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadAll() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    await Future.wait([_loadConfig(), _loadHeadlines()]);
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _loadConfig() async {
    try {
      final config = await _api.getConfig();
      if (mounted) {
        setState(() {
          _keywords = config['keywords'] as String? ?? '';
          _interval = config['timer_interval'] as int? ?? 60;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadHeadlines() async {
    try {
      final headlines = await _api.getHeadlines();
      if (mounted) setState(() => _headlines = headlines);
    } catch (e) {
      if (mounted) setState(() => _error = 'Cannot reach news backend. Start it on port 8001.');
    }
  }

  Future<void> _trigger() async {
    setState(() => _triggering = true);
    try {
      await _api.triggerCrawler();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Crawler triggered! Refresh in ~30 seconds.',
              style: GoogleFonts.inter(fontSize: 13),
            ),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12)),
            margin: const EdgeInsets.all(16),
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to trigger. Is the backend running?',
                style: GoogleFonts.inter(fontSize: 13)),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12)),
            margin: const EdgeInsets.all(16),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _triggering = false);
    }
  }

  void _openConfig() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.surface,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
      builder: (_) => NewsConfigSheet(
        initialKeywords: _keywords,
        initialInterval: _interval,
        onSaved: _loadAll,
      ),
    );
  }

  void _openDetail(Headline h) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => HeadlineDetailSheet(headline: h),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.bg,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'News.',
                  style: GoogleFonts.outfit(
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                    color: context.textPrimary,
                    letterSpacing: -0.5,
                    height: 1.0,
                  ),
                ),
                if (_keywords.isNotEmpty)
                  Text(
                    _keywords,
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      color: context.textMuted,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          // Refresh button
          _IconPill(
            icon: Icons.refresh_rounded,
            onTap: _loading ? null : _loadHeadlines,
          ),
          const SizedBox(width: 8),
          // Trigger button
          _IconPill(
            icon: _triggering
                ? Icons.hourglass_top_rounded
                : Icons.play_arrow_rounded,
            onTap: _triggering ? null : _trigger,
          ),
          const SizedBox(width: 8),
          // Config button
          _IconPill(
            icon: Icons.tune_rounded,
            onTap: _openConfig,
          ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) return _buildSkeletons();
    if (_error != null) return _buildError();
    if (_headlines.isEmpty) return _buildEmpty();
    return RefreshIndicator(
      onRefresh: _loadHeadlines,
      color: context.accent,
      child: ListView.builder(
        padding: const EdgeInsets.only(top: 16, bottom: 120),
        itemCount: _headlines.length,
        itemBuilder: (_, i) => HeadlineCard(
          headline: _headlines[i],
          onTap: () => _openDetail(_headlines[i]),
        ),
      ),
    );
  }

  Widget _buildSkeletons() {
    return ListView.builder(
      padding: const EdgeInsets.only(top: 16),
      itemCount: 5,
      itemBuilder: (_, __) => _SkeletonCard(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off_rounded,
                size: 48, color: context.textMuted),
            const SizedBox(height: 16),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                  fontSize: 13, color: context.textSecondary),
            ),
            const SizedBox(height: 24),
            GestureDetector(
              onTap: _loadAll,
              child: Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: context.surfaceHigh,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: context.border),
                ),
                child: Text(
                  'Retry',
                  style: GoogleFonts.outfit(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: context.textPrimary,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.article_outlined, size: 48, color: context.textMuted),
            const SizedBox(height: 16),
            Text(
              'No headlines yet.',
              style: GoogleFonts.outfit(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: context.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Configure keywords and tap ▶ to crawl.',
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                  fontSize: 13, color: context.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Icon pill button ─────────────────────────────────────────────────────────
class _IconPill extends StatelessWidget {
  const _IconPill({required this.icon, this.onTap});
  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: context.surfaceHigh,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: context.border),
        ),
        child: Icon(icon, size: 18, color: context.textSecondary),
      ),
    );
  }
}

// ─── Skeleton loading card ────────────────────────────────────────────────────
class _SkeletonCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: context.surface,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: context.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Bone(width: 80, height: 10),
          const SizedBox(height: 10),
          _Bone(width: double.infinity, height: 14),
          const SizedBox(height: 6),
          _Bone(width: double.infinity, height: 12),
          const SizedBox(height: 4),
          _Bone(width: 200, height: 12),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _Bone(width: 60, height: 20),
              _Bone(width: 50, height: 20),
            ],
          ),
        ],
      ),
    );
  }
}

class _Bone extends StatelessWidget {
  const _Bone({required this.width, required this.height});
  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: context.surfaceHigh,
        borderRadius: BorderRadius.circular(6),
      ),
    );
  }
}

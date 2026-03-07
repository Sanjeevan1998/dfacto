import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';

class InteractiveStubScreen extends StatelessWidget {
  const InteractiveStubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return _StubScreen(
      icon: Icons.chat_bubble_rounded,
      label: 'Interactive',
      subtitle: 'Voice-first conversational\nfact-checking companion.',
    );
  }
}

class ScannerStubScreen extends StatelessWidget {
  const ScannerStubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return _StubScreen(
      icon: Icons.document_scanner_rounded,
      label: 'Scanner',
      subtitle: 'Deep-research tool for\nmedia, links, and documents.',
    );
  }
}

class RadarStubScreen extends StatelessWidget {
  const RadarStubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return _StubScreen(
      icon: Icons.radar_rounded,
      label: 'Radar',
      subtitle: 'Personalized proactive\nintelligence feed.',
    );
  }
}

// ─── Shared Stub Widget ───────────────────────────────────────────────────────
class _StubScreen extends StatelessWidget {
  const _StubScreen({
    required this.icon,
    required this.label,
    required this.subtitle,
  });

  final IconData icon;
  final String label;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.bg,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: context.surfaceHigh,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: context.border),
              ),
              child: Icon(icon, color: context.accent, size: 30),
            ),
            const SizedBox(height: 24),
            Text(
              label,
              style: DfactoTextStyles.headlineMedium(context.textPrimary),
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: DfactoTextStyles.bodyMedium(context.textSecondary),
            ),
            const SizedBox(height: 32),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              decoration: BoxDecoration(
                color: context.accentSoft,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: context.borderStrong,
                ),
              ),
              child: Text(
                'COMING SOON',
                style: DfactoTextStyles.labelBold(context.accent).copyWith(
                  letterSpacing: 1.5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

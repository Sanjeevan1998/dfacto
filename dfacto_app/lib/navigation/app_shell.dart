import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme/app_theme.dart';
import '../core/theme/theme_notifier.dart';
import '../features/live_audit/live_audit_screen.dart';
import '../features/interactive/interactive_stub_screen.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _selectedIndex = 0;

  static const List<Widget> _screens = [
    LiveAuditScreen(),
    InteractiveStubScreen(),
    ScannerStubScreen(),
    RadarStubScreen(),
  ];

  void _onDestinationSelected(int index) {
    setState(() => _selectedIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 250),
        switchInCurve: Curves.easeOutCubic,
        switchOutCurve: Curves.easeInCubic,
        child: KeyedSubtree(
          key: ValueKey<int>(_selectedIndex),
          child: _screens[_selectedIndex],
        ),
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(color: context.border, width: 0.5),
          ),
        ),
        child: NavigationBar(
          selectedIndex: _selectedIndex,
          onDestinationSelected: _onDestinationSelected,
          backgroundColor: context.surface,
          height: 64,
          animationDuration: const Duration(milliseconds: 300),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.radio_button_unchecked_rounded),
              selectedIcon: Icon(Icons.radio_button_checked_rounded),
              label: 'Live Audit',
            ),
            NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline_rounded),
              selectedIcon: Icon(Icons.chat_bubble_rounded),
              label: 'Interactive',
            ),
            NavigationDestination(
              icon: Icon(Icons.document_scanner_outlined),
              selectedIcon: Icon(Icons.document_scanner_rounded),
              label: 'Scanner',
            ),
            NavigationDestination(
              icon: Icon(Icons.radar_outlined),
              selectedIcon: Icon(Icons.radar_rounded),
              label: 'Radar',
            ),
          ],
        ),
      ),
    );
  }
}

/// Minimal theme toggle button exposed as a reusable widget
/// so each screen can place it in its own header row.
class ThemeToggleButton extends ConsumerWidget {
  const ThemeToggleButton({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isDark = context.isDark;

    return GestureDetector(
      onTap: () => ref.read(themeModeProvider.notifier).toggle(),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOutCubic,
        width: 52,
        height: 28,
        padding: const EdgeInsets.all(3),
        decoration: BoxDecoration(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: context.borderStrong,
            width: 1,
          ),
        ),
        child: Stack(
          children: [
            // Knob
            AnimatedAlign(
              duration: const Duration(milliseconds: 350),
              curve: Curves.easeOutCubic,
              alignment: isDark ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  color: context.accent,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  isDark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
                  size: 12,
                  color: isDark ? Colors.black : Colors.white,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

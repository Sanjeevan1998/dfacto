import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

class ListenButton extends StatelessWidget {
  const ListenButton({
    super.key,
    required this.isListening,
    required this.onTap,
  });

  final bool isListening;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final stopColor = DfactoColors.verdictFalse;
    final activeColor = context.accent;
    final borderColor = isListening
        ? stopColor.withValues(alpha: 0.5)
        : activeColor.withValues(alpha: 0.4);
    final bgColor = isListening
        ? stopColor.withValues(alpha: 0.08)
        : context.accentSoft;
    final icon = isListening ? Icons.stop_rounded : Icons.mic_rounded;
    final labelColor = isListening ? stopColor : activeColor;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOutCubic,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(32),
          border: Border.all(color: borderColor, width: 1),
          boxShadow: [
            BoxShadow(
              color: isListening
                  ? stopColor.withValues(alpha: 0.15)
                  : context.accent.withValues(alpha: 0.10),
              blurRadius: 16,
              spreadRadius: 0,
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 200),
              child: Icon(
                icon,
                key: ValueKey(isListening),
                color: labelColor,
                size: 18,
              ),
            ),
            const SizedBox(width: 10),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 200),
              child: Text(
                isListening ? 'Stop Listening' : 'Start Listening',
                key: ValueKey(isListening),
                style: DfactoTextStyles.labelBold(labelColor).copyWith(
                  letterSpacing: 0.6,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

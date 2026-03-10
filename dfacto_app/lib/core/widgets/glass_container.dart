import 'dart:ui';
import 'package:flutter/material.dart';

/// A glass-morphism container using BackdropFilter blur.
/// Matches the design from the UI/UX prototype (rgba(255,255,255,0.22) + blur(16px)).
class GlassContainer extends StatelessWidget {
  const GlassContainer({
    super.key,
    required this.child,
    this.borderRadius = 22.0,
    this.opacity = 0.22,
    this.blurSigma = 16.0,
    this.showBorder = true,
    this.padding,
  });

  final Widget child;
  final double borderRadius;
  final double opacity;
  final double blurSigma;
  final bool showBorder;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blurSigma, sigmaY: blurSigma),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: opacity),
            borderRadius: BorderRadius.circular(borderRadius),
            border: showBorder
                ? Border.all(
                    color: Colors.white.withValues(alpha: 0.08),
                    width: 1,
                  )
                : null,
          ),
          child: child,
        ),
      ),
    );
  }
}

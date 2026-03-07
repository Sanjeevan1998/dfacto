import 'dart:math';
import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

class WaveformVisualizer extends StatefulWidget {
  const WaveformVisualizer({super.key, required this.isActive});

  final bool isActive;

  @override
  State<WaveformVisualizer> createState() => _WaveformVisualizerState();
}

class _WaveformVisualizerState extends State<WaveformVisualizer>
    with TickerProviderStateMixin {
  static const int _barCount = 24;
  final List<AnimationController> _controllers = [];
  final List<Animation<double>> _animations = [];
  final Random _random = Random();

  @override
  void initState() {
    super.initState();
    _initAnimations();
  }

  void _initAnimations() {
    for (int i = 0; i < _barCount; i++) {
      final duration = Duration(milliseconds: 380 + _random.nextInt(480));
      final controller = AnimationController(vsync: this, duration: duration)
        ..repeat(reverse: true);

      final animation = Tween<double>(
        begin: 0.05 + _random.nextDouble() * 0.08,
        end: 0.25 + _random.nextDouble() * 0.70,
      ).animate(CurvedAnimation(parent: controller, curve: Curves.easeInOut));

      _controllers.add(controller);
      _animations.add(animation);

      Future.delayed(Duration(milliseconds: i * 28), () {
        if (mounted && widget.isActive) {
          _controllers[i].repeat(reverse: true);
        }
      });
    }
  }

  @override
  void didUpdateWidget(WaveformVisualizer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isActive != oldWidget.isActive) {
      if (widget.isActive) {
        for (final c in _controllers) {
          c.repeat(reverse: true);
        }
      } else {
        for (final c in _controllers) {
          c.animateTo(0.05, duration: const Duration(milliseconds: 600));
        }
      }
    }
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final idleColor = context.border;
    final activeColor = context.accent;

    return SizedBox(
      height: 52,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: List.generate(_barCount, (i) {
          return AnimatedBuilder(
            animation: _animations[i],
            builder: (context, _) {
              final heightFactor =
                  widget.isActive ? _animations[i].value : 0.07;
              return Container(
                width: 3,
                height: 52 * heightFactor,
                margin: const EdgeInsets.symmetric(horizontal: 2),
                decoration: BoxDecoration(
                  color: widget.isActive
                      ? activeColor.withValues(
                          alpha: 0.35 + (_animations[i].value * 0.65),
                        )
                      : idleColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              );
            },
          );
        }),
      ),
    );
  }
}

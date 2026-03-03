import 'package:flutter/material.dart';

/// Wraps a list of children with staggered fade+slide-in animations.
class StaggerList extends StatefulWidget {
  final List<Widget> children;
  final Duration staggerDelay;
  final Duration itemDuration;

  const StaggerList({
    super.key,
    required this.children,
    this.staggerDelay = const Duration(milliseconds: 50),
    this.itemDuration = const Duration(milliseconds: 300),
  });

  @override
  State<StaggerList> createState() => _StaggerListState();
}

class _StaggerListState extends State<StaggerList>
    with TickerProviderStateMixin {
  final _controllers = <AnimationController>[];
  final _animations = <Animation<double>>[];

  @override
  void initState() {
    super.initState();
    _buildAnimations();
    _startStagger();
  }

  @override
  void didUpdateWidget(covariant StaggerList oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.children.length != oldWidget.children.length) {
      _disposeControllers();
      _buildAnimations();
      _startStagger();
    }
  }

  void _buildAnimations() {
    for (var i = 0; i < widget.children.length; i++) {
      final ctrl = AnimationController(
        vsync: this,
        duration: widget.itemDuration,
      );
      _controllers.add(ctrl);
      _animations.add(
        CurvedAnimation(parent: ctrl, curve: Curves.easeOutCubic),
      );
    }
  }

  void _startStagger() {
    for (var i = 0; i < _controllers.length; i++) {
      Future.delayed(widget.staggerDelay * i, () {
        if (mounted && i < _controllers.length) {
          _controllers[i].forward();
        }
      });
    }
  }

  void _disposeControllers() {
    for (final c in _controllers) {
      c.dispose();
    }
    _controllers.clear();
    _animations.clear();
  }

  @override
  void dispose() {
    _disposeControllers();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: List.generate(widget.children.length, (i) {
        return FadeTransition(
          opacity: _animations[i],
          child: SlideTransition(
            position: Tween<Offset>(
              begin: const Offset(0, 0.1),
              end: Offset.zero,
            ).animate(_animations[i]),
            child: widget.children[i],
          ),
        );
      }),
    );
  }
}

import 'package:flutter_test/flutter_test.dart';
import 'package:pyclaw/core/providers/chat_provider.dart';
import 'package:pyclaw/core/providers/session_provider.dart';
import 'package:pyclaw/core/providers/config_provider.dart';
import 'package:pyclaw/core/providers/plan_provider.dart';
import 'package:pyclaw/core/providers/cron_provider.dart';
import 'package:pyclaw/core/providers/system_provider.dart';

void main() {
  group('ChatState', () {
    test('default values', () {
      const state = ChatState();
      expect(state.messages, isEmpty);
      expect(state.isGenerating, isFalse);
      expect(state.error, isNull);
    });

    test('copyWith preserves unchanged fields', () {
      const state = ChatState(isGenerating: true);
      final updated = state.copyWith(error: 'oops');
      expect(updated.isGenerating, isTrue);
      expect(updated.error, 'oops');
    });
  });

  group('SessionState', () {
    test('default values', () {
      const state = SessionState();
      expect(state.sessions, isEmpty);
      expect(state.isLoading, isFalse);
    });

    test('copyWith updates sessions', () {
      const state = SessionState();
      final updated = state.copyWith(isLoading: true);
      expect(updated.isLoading, isTrue);
      expect(updated.sessions, isEmpty);
    });
  });

  group('ConfigState', () {
    test('default values', () {
      const state = ConfigState();
      expect(state.config, isEmpty);
      expect(state.models, isEmpty);
      expect(state.providers, isEmpty);
    });

    test('copyWith merges config', () {
      const state = ConfigState(config: {'key': 'val'});
      final updated = state.copyWith(providers: ['openai']);
      expect(updated.config, {'key': 'val'});
      expect(updated.providers, ['openai']);
    });
  });

  group('PlanState', () {
    test('default values', () {
      const state = PlanState();
      expect(state.plans, isEmpty);
      expect(state.isLoading, isFalse);
    });
  });

  group('CronState', () {
    test('default values', () {
      const state = CronState();
      expect(state.jobs, isEmpty);
      expect(state.history, isEmpty);
      expect(state.isLoading, isFalse);
    });

    test('copyWith updates independently', () {
      const state = CronState();
      final updated = state.copyWith(isLoading: true, error: 'timeout');
      expect(updated.isLoading, isTrue);
      expect(updated.error, 'timeout');
      expect(updated.jobs, isEmpty);
    });
  });

  group('SystemState', () {
    test('default values', () {
      const state = SystemState();
      expect(state.info, isEmpty);
      expect(state.doctorChecks, isEmpty);
    });

    test('copyWith updates info', () {
      const state = SystemState();
      final updated = state.copyWith(info: {'version': '0.1.0'});
      expect(updated.info['version'], '0.1.0');
    });
  });
}

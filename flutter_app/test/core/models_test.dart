import 'package:flutter_test/flutter_test.dart';
import 'package:pyclaw/core/models/message.dart';
import 'package:pyclaw/core/models/session.dart';
import 'package:pyclaw/core/models/plan.dart';
import 'package:pyclaw/core/models/cron_job.dart';
import 'package:pyclaw/core/models/agent.dart';
import 'package:pyclaw/core/models/channel.dart';

void main() {
  group('Message', () {
    test('fromJson parses correctly', () {
      final json = {
        'id': 'msg-1',
        'role': 'user',
        'content': 'Hello',
        'created_at': '2026-03-02T10:00:00Z',
        'tool_calls': [],
      };
      final msg = Message.fromJson(json);
      expect(msg.id, 'msg-1');
      expect(msg.role, MessageRole.user);
      expect(msg.content, 'Hello');
      expect(msg.isStreaming, isFalse);
    });

    test('copyWith preserves unmodified fields', () {
      final msg = Message(
        id: 'a',
        role: MessageRole.assistant,
        content: 'hi',
        createdAt: DateTime.now(),
      );
      final updated = msg.copyWith(content: 'updated');
      expect(updated.id, 'a');
      expect(updated.role, MessageRole.assistant);
      expect(updated.content, 'updated');
    });

    test('fromJson handles missing fields gracefully', () {
      final msg = Message.fromJson({});
      expect(msg.id, '');
      expect(msg.role, MessageRole.assistant);
      expect(msg.content, '');
    });
  });

  group('ToolCall', () {
    test('fromJson and copyWith', () {
      final tc = ToolCall.fromJson({
        'id': 'tc-1',
        'name': 'web_search',
        'arguments': '{"q":"test"}',
        'is_running': true,
      });
      expect(tc.id, 'tc-1');
      expect(tc.name, 'web_search');
      expect(tc.isRunning, isTrue);

      final finished = tc.copyWith(isRunning: false, result: 'done');
      expect(finished.isRunning, isFalse);
      expect(finished.result, 'done');
    });
  });

  group('Session', () {
    test('fromJson parses session_id and id', () {
      final s1 = Session.fromJson({'session_id': 'sess-1', 'title': 'Test'});
      expect(s1.id, 'sess-1');

      final s2 = Session.fromJson({'id': 'sess-2'});
      expect(s2.id, 'sess-2');
    });
  });

  group('Plan', () {
    test('progress calculation', () {
      final plan = Plan(
        id: 'p1',
        goal: 'Deploy',
        steps: [
          const PlanStep(index: 0, description: 'Build', status: StepStatus.done),
          const PlanStep(index: 1, description: 'Test', status: StepStatus.done),
          const PlanStep(index: 2, description: 'Deploy', status: StepStatus.pending),
        ],
        createdAt: DateTime.now(),
      );
      expect(plan.completedCount, 2);
      expect(plan.totalCount, 3);
      expect(plan.progress, closeTo(0.667, 0.01));
    });

    test('empty plan has zero progress', () {
      final plan = Plan(id: 'p', goal: 'g', createdAt: DateTime.now());
      expect(plan.progress, 0);
    });
  });

  group('CronJob', () {
    test('fromJson parses schedule types', () {
      final j = CronJob.fromJson({
        'id': 'c1',
        'name': 'Daily check',
        'schedule_type': 'every',
        'schedule': '1h',
        'prompt': 'check status',
      });
      expect(j.scheduleType, ScheduleType.every);
      expect(j.enabled, isTrue);
    });
  });

  group('Agent', () {
    test('fromJson parses tools list', () {
      final a = Agent.fromJson({
        'name': 'coder',
        'tools': ['web_search', 'code_exec'],
        'is_default': true,
      });
      expect(a.name, 'coder');
      expect(a.tools, hasLength(2));
      expect(a.isDefault, isTrue);
    });
  });

  group('Channel', () {
    test('fromJson parses state', () {
      final c = Channel.fromJson({
        'id': 'ch-1',
        'type': 'telegram',
        'state': 'online',
        'message_count': 42,
      });
      expect(c.state, ChannelState.online);
      expect(c.messageCount, 42);
    });

    test('handles unknown state', () {
      final c = Channel.fromJson({'id': 'x', 'type': 't', 'state': 'bogus'});
      expect(c.state, ChannelState.offline);
    });
  });
}

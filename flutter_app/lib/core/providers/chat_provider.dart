import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/models/message.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';

const _uuid = Uuid();

/// Chat state for the current session.
class ChatState {
  final List<Message> messages;
  final bool isGenerating;
  final String? error;

  const ChatState({
    this.messages = const [],
    this.isGenerating = false,
    this.error,
  });

  ChatState copyWith({
    List<Message>? messages,
    bool? isGenerating,
    String? error,
  }) =>
      ChatState(
        messages: messages ?? this.messages,
        isGenerating: isGenerating ?? this.isGenerating,
        error: error,
      );
}

class ChatNotifier extends StateNotifier<ChatState> {
  final GatewayClient _client;
  String? _currentSessionId;
  String _currentAgentId = 'main';

  ChatNotifier(this._client) : super(const ChatState()) {
    _client.on('chat.message_update', _onMessageUpdate);
    _client.on('chat.tool_start', _onToolStart);
    _client.on('chat.tool_end', _onToolEnd);
    _client.on('chat.error', _onError);
    _client.on('chat.agent_end', _onDone);
  }

  String? get currentSessionId => _currentSessionId;

  /// Load messages for a session.
  Future<void> loadSession(String sessionId, {String agentId = 'main'}) async {
    _currentSessionId = sessionId;
    _currentAgentId = agentId;
    try {
      final result = await _client.call('chat.history', {
        'sessionId': sessionId,
        'agentId': agentId,
      });
      final msgs = (result['messages'] as List?)
              ?.map((m) => Message.fromJson(m as Map<String, dynamic>))
              .toList() ??
          [];
      state = ChatState(messages: msgs);
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  /// Start a new session.
  void newSession() {
    _currentSessionId = null;
    state = const ChatState();
  }

  /// Send a message and begin streaming.
  Future<void> send(String text,
      {String? agentId, String? provider, String? model}) async {
    final userMsg = Message(
      id: _uuid.v4().substring(0, 12),
      role: MessageRole.user,
      content: text,
      createdAt: DateTime.now(),
    );
    final assistantMsg = Message(
      id: _uuid.v4().substring(0, 12),
      role: MessageRole.assistant,
      content: '',
      createdAt: DateTime.now(),
      isStreaming: true,
    );

    state = state.copyWith(
      messages: [...state.messages, userMsg, assistantMsg],
      isGenerating: true,
      error: null,
    );

    try {
      final effectiveAgentId = agentId ?? _currentAgentId;
      final params = <String, dynamic>{
        'message': text,
        'agentId': effectiveAgentId,
      };
      if (_currentSessionId != null) params['sessionId'] = _currentSessionId;
      if (provider != null) params['provider'] = provider;
      if (model != null) params['model'] = model;

      final result =
          await _client.call('chat.send', params, const Duration(seconds: 120));
      _currentSessionId ??=
          result['sessionId'] as String? ?? result['session_id'] as String?;
      _currentAgentId = effectiveAgentId;
    } catch (e) {
      state = state.copyWith(isGenerating: false, error: e.toString());
    }
  }

  /// Abort current generation.
  Future<void> abort() async {
    if (!state.isGenerating || _currentSessionId == null) return;
    try {
      await _client.call('chat.abort', {
        'sessionId': _currentSessionId,
        'agentId': _currentAgentId,
      });
    } catch (_) {}
    state = state.copyWith(isGenerating: false);
    _finishStreaming();
  }

  /// Edit a message and regenerate from that point.
  Future<void> editMessage(String messageId, String newContent) async {
    try {
      await _client.call('chat.edit', {
        // Kept for forward compatibility with servers that support targeted edit.
        'messageId': messageId,
        'message': newContent,
        if (_currentSessionId != null) 'sessionId': _currentSessionId,
        'agentId': _currentAgentId,
      });
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  /// Resend the last user message to regenerate the reply.
  Future<void> resend() async {
    try {
      await _client.call('chat.resend', {
        if (_currentSessionId != null) 'sessionId': _currentSessionId,
        'agentId': _currentAgentId,
      });
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  void _onMessageUpdate(dynamic payload) {
    if (payload is! Map) return;
    final delta = payload['delta'] as String? ?? '';
    if (delta.isEmpty) return;

    final msgs = [...state.messages];
    if (msgs.isNotEmpty && msgs.last.role == MessageRole.assistant) {
      msgs[msgs.length - 1] = msgs.last.copyWith(
        content: msgs.last.content + delta,
      );
    }
    state = state.copyWith(messages: msgs);
  }

  void _onToolStart(dynamic payload) {
    if (payload is! Map) return;
    final toolCall = ToolCall(
      id: payload['toolCallId'] as String? ??
          payload['call_id'] as String? ??
          '',
      name: payload['name'] as String? ?? payload['tool'] as String? ?? '',
      arguments: payload['arguments'] as String? ?? '',
      isRunning: true,
      startedAt: DateTime.now(),
    );

    final msgs = [...state.messages];
    if (msgs.isNotEmpty && msgs.last.role == MessageRole.assistant) {
      final updated = msgs.last.copyWith(
        toolCalls: [...msgs.last.toolCalls, toolCall],
      );
      msgs[msgs.length - 1] = updated;
    }
    state = state.copyWith(messages: msgs);
  }

  void _onToolEnd(dynamic payload) {
    if (payload is! Map) return;
    final callId =
        payload['toolCallId'] as String? ?? payload['call_id'] as String?;
    if (callId == null) return;

    final msgs = [...state.messages];
    if (msgs.isNotEmpty && msgs.last.role == MessageRole.assistant) {
      final updatedCalls = msgs.last.toolCalls.map((tc) {
        if (tc.id == callId) {
          return tc.copyWith(
            result: payload['result'] as String?,
            error: payload['error'] as String?,
            isRunning: false,
            finishedAt: DateTime.now(),
          );
        }
        return tc;
      }).toList();
      msgs[msgs.length - 1] = msgs.last.copyWith(toolCalls: updatedCalls);
    }
    state = state.copyWith(messages: msgs);
  }

  void _onError(dynamic payload) {
    final errorMsg = payload is Map
        ? (payload['message'] as String? ?? 'Unknown error')
        : payload.toString();
    state = state.copyWith(isGenerating: false, error: errorMsg);
    _finishStreaming();
  }

  void _onDone(dynamic _) {
    state = state.copyWith(isGenerating: false);
    _finishStreaming();
  }

  void _finishStreaming() {
    final msgs = [...state.messages];
    if (msgs.isNotEmpty && msgs.last.isStreaming) {
      msgs[msgs.length - 1] = msgs.last.copyWith(isStreaming: false);
      state = state.copyWith(messages: msgs);
    }
  }

  @override
  void dispose() {
    _client.off('chat.message_update', _onMessageUpdate);
    _client.off('chat.tool_start', _onToolStart);
    _client.off('chat.tool_end', _onToolEnd);
    _client.off('chat.error', _onError);
    _client.off('chat.agent_end', _onDone);
    super.dispose();
  }
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref.watch(gatewayClientProvider));
});

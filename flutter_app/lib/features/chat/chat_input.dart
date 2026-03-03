import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';

/// Chat input bar with send/abort, file attachment, multi-line support, and keyboard shortcuts.
class ChatInput extends StatefulWidget {
  final bool isGenerating;
  final ValueChanged<String> onSend;
  final VoidCallback onAbort;
  final ValueChanged<List<PlatformFile>>? onFilesAttached;

  const ChatInput({
    super.key,
    required this.isGenerating,
    required this.onSend,
    required this.onAbort,
    this.onFilesAttached,
  });

  @override
  State<ChatInput> createState() => _ChatInputState();
}

class _ChatInputState extends State<ChatInput> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();
  bool _hasText = false;
  final _attachments = <PlatformFile>[];

  @override
  void initState() {
    super.initState();
    _controller.addListener(() {
      final has = _controller.text.trim().isNotEmpty;
      if (has != _hasText) setState(() => _hasText = has);
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _submit() {
    final text = _controller.text.trim();
    if (text.isEmpty && _attachments.isEmpty) return;
    if (_attachments.isNotEmpty) {
      widget.onFilesAttached?.call(List.of(_attachments));
    }
    if (text.isNotEmpty) widget.onSend(text);
    _controller.clear();
    setState(() => _attachments.clear());
    _focusNode.requestFocus();
  }

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.any,
    );
    if (result != null && result.files.isNotEmpty) {
      setState(() => _attachments.addAll(result.files));
      widget.onFilesAttached?.call(result.files);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
      decoration: BoxDecoration(
        color: scheme.surface,
        border: Border(top: BorderSide(color: scheme.outlineVariant, width: 0.5)),
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (_attachments.isNotEmpty)
              SizedBox(
                height: 40,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.only(bottom: 6),
                  itemCount: _attachments.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 6),
                  itemBuilder: (context, i) {
                    final f = _attachments[i];
                    return Chip(
                      avatar: Icon(_fileIcon(f.extension ?? ''), size: 16),
                      label: Text(
                        f.name.length > 20 ? '${f.name.substring(0, 18)}...' : f.name,
                        style: const TextStyle(fontSize: 12),
                      ),
                      deleteIcon: const Icon(Icons.close, size: 14),
                      onDeleted: () => setState(() => _attachments.removeAt(i)),
                      visualDensity: VisualDensity.compact,
                    );
                  },
                ),
              ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                IconButton(
                  icon: const Icon(Icons.attach_file),
                  tooltip: 'Attach file',
                  onPressed: _pickFiles,
                  style: IconButton.styleFrom(foregroundColor: scheme.onSurfaceVariant),
                ),
                Expanded(
                  child: KeyboardListener(
                    focusNode: FocusNode(),
                    onKeyEvent: (event) {
                      if (event is KeyDownEvent &&
                          event.logicalKey == LogicalKeyboardKey.enter &&
                          !HardwareKeyboard.instance.isShiftPressed) {
                        _submit();
                      }
                    },
                    child: TextField(
                      controller: _controller,
                      focusNode: _focusNode,
                      maxLines: 5,
                      minLines: 1,
                      textInputAction: TextInputAction.newline,
                      decoration: InputDecoration(
                        hintText: 'Type a message...',
                        hintStyle: TextStyle(color: scheme.onSurfaceVariant.withAlpha(150)),
                        border: InputBorder.none,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 4),
                _SendButton(
                  isGenerating: widget.isGenerating,
                  hasContent: _hasText || _attachments.isNotEmpty,
                  onSend: _submit,
                  onAbort: widget.onAbort,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  IconData _fileIcon(String ext) => switch (ext.toLowerCase()) {
        'pdf' => Icons.picture_as_pdf,
        'png' || 'jpg' || 'jpeg' || 'gif' || 'webp' => Icons.image,
        'mp3' || 'wav' || 'ogg' || 'aac' => Icons.audiotrack,
        'mp4' || 'webm' || 'mov' => Icons.videocam,
        'doc' || 'docx' => Icons.description,
        'xls' || 'xlsx' => Icons.table_chart,
        'ppt' || 'pptx' => Icons.slideshow,
        'zip' || 'tar' || 'gz' || '7z' => Icons.folder_zip,
        _ => Icons.insert_drive_file,
      };
}

/// Animated send/stop button with spring effect.
class _SendButton extends StatefulWidget {
  final bool isGenerating;
  final bool hasContent;
  final VoidCallback onSend;
  final VoidCallback onAbort;

  const _SendButton({
    required this.isGenerating,
    required this.hasContent,
    required this.onSend,
    required this.onAbort,
  });

  @override
  State<_SendButton> createState() => _SendButtonState();
}

class _SendButtonState extends State<_SendButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 150),
      lowerBound: 0.0,
      upperBound: 1.0,
    );
    _scale = Tween<double>(begin: 1.0, end: 0.85).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _onTapDown(TapDownDetails _) => _ctrl.forward();
  void _onTapUp(TapUpDetails _) => _ctrl.reverse();
  void _onTapCancel() => _ctrl.reverse();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return GestureDetector(
      onTapDown: _onTapDown,
      onTapUp: _onTapUp,
      onTapCancel: _onTapCancel,
      child: ScaleTransition(
        scale: _scale,
        child: widget.isGenerating
            ? IconButton.filled(
                icon: const Icon(Icons.stop, size: 20),
                tooltip: 'Stop generating',
                style: IconButton.styleFrom(
                  backgroundColor: scheme.error,
                  foregroundColor: scheme.onError,
                ),
                onPressed: widget.onAbort,
              )
            : IconButton.filled(
                icon: const Icon(Icons.send, size: 20),
                tooltip: 'Send (Enter)',
                onPressed: widget.hasContent ? widget.onSend : null,
              ),
      ),
    );
  }
}

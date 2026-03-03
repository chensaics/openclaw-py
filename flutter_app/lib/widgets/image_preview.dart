import 'package:flutter/material.dart';
import 'package:photo_view/photo_view.dart';

/// Full-screen image viewer with pinch-to-zoom and Hero animation.
class ImagePreview extends StatelessWidget {
  final String imageUrl;
  final String heroTag;

  const ImagePreview({
    super.key,
    required this.imageUrl,
    required this.heroTag,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: Center(
        child: Hero(
          tag: heroTag,
          child: PhotoView(
            imageProvider: NetworkImage(imageUrl),
            minScale: PhotoViewComputedScale.contained,
            maxScale: PhotoViewComputedScale.covered * 3,
            backgroundDecoration: const BoxDecoration(color: Colors.black),
            loadingBuilder: (context, event) => Center(
              child: CircularProgressIndicator(
                value: event == null
                    ? null
                    : event.cumulativeBytesLoaded / (event.expectedTotalBytes ?? 1),
                color: scheme.primary,
              ),
            ),
            errorBuilder: (context, error, stackTrace) => Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.broken_image, color: Colors.white54, size: 48),
                const SizedBox(height: 8),
                Text(
                  'Failed to load image',
                  style: TextStyle(color: Colors.white.withAlpha(180)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Inline image thumbnail that opens [ImagePreview] on tap.
class ImageThumbnail extends StatelessWidget {
  final String imageUrl;
  final double maxHeight;

  const ImageThumbnail({
    super.key,
    required this.imageUrl,
    this.maxHeight = 200,
  });

  @override
  Widget build(BuildContext context) {
    final tag = 'img-${imageUrl.hashCode}';

    return GestureDetector(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ImagePreview(imageUrl: imageUrl, heroTag: tag),
          ),
        );
      },
      child: Hero(
        tag: tag,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: ConstrainedBox(
            constraints: BoxConstraints(maxHeight: maxHeight),
            child: Image.network(
              imageUrl,
              fit: BoxFit.cover,
              loadingBuilder: (context, child, progress) {
                if (progress == null) return child;
                return SizedBox(
                  height: 100,
                  child: Center(
                    child: CircularProgressIndicator(
                      value: progress.cumulativeBytesLoaded /
                          (progress.expectedTotalBytes ?? 1),
                      strokeWidth: 2,
                    ),
                  ),
                );
              },
              errorBuilder: (_, __, ___) => Container(
                height: 100,
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                child: const Center(child: Icon(Icons.broken_image, size: 32)),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

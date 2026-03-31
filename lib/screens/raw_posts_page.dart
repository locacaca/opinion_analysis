import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../l10n/app_strings.dart';
import '../models/sentiment_models.dart';
import '../providers/app_language_provider.dart';

class RawPostsPage extends StatelessWidget {
  const RawPostsPage({
    super.key,
    required this.posts,
    required this.language,
  });

  final List<SourcePost> posts;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(AppStrings.rawPostsPageTitle(language)),
        actions: [
          IconButton(
            tooltip: AppStrings.copyAll(language),
            onPressed: posts.isEmpty
                ? null
                : () => _copyText(
                      context,
                      posts.map(_formatPost).join('\n\n'),
                      language: language,
                    ),
            icon: const Icon(Icons.content_copy_rounded),
          ),
        ],
      ),
      body: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        itemBuilder: (context, index) {
          final post = posts[index];
          return Card(
            child: ListTile(
              contentPadding: const EdgeInsets.all(18),
              title: Text(
                post.title,
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      color: Colors.white,
                      height: 1.45,
                    ),
              ),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      post.originalLink,
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            color: Colors.white60,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      post.source.toUpperCase(),
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            color: Colors.cyanAccent,
                          ),
                    ),
                  ],
                ),
              ),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    tooltip: AppStrings.copy(language),
                    onPressed: () => _copyText(
                      context,
                      _formatPost(post),
                      language: language,
                    ),
                    icon: const Icon(
                      Icons.content_copy_rounded,
                      color: Colors.white70,
                    ),
                  ),
                  IconButton(
                    tooltip: AppStrings.openSourcePost(language),
                    onPressed: () => _launchExternal(post.originalLink),
                    icon: const Icon(
                      Icons.open_in_new_rounded,
                      color: Colors.cyanAccent,
                    ),
                  ),
                ],
              ),
              onTap: () => _launchExternal(post.originalLink),
            ),
          );
        },
        separatorBuilder: (_, _) => const SizedBox(height: 10),
        itemCount: posts.length,
      ),
    );
  }
}

Future<void> _launchExternal(String url) async {
  final uri = Uri.tryParse(url);
  if (uri == null) {
    return;
  }
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

Future<void> _copyText(
  BuildContext context,
  String text, {
  required AppLanguage language,
}) async {
  final normalized = text.trim();
  if (normalized.isEmpty) {
    return;
  }
  await Clipboard.setData(ClipboardData(text: normalized));
  if (!context.mounted) {
    return;
  }
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(AppStrings.copied(language))),
  );
}

String _formatPost(SourcePost post) {
  final buffer = StringBuffer(post.title.trim());
  if (post.content.trim().isNotEmpty) {
    buffer.write('\n');
    buffer.write(post.content.trim());
  }
  if (post.originalLink.trim().isNotEmpty) {
    buffer.write('\n');
    buffer.write(post.originalLink.trim());
  }
  return buffer.toString();
}

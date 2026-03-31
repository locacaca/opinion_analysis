import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../l10n/app_strings.dart';
import '../models/sentiment_models.dart';
import '../providers/app_language_provider.dart';
import '../providers/sentiment_provider.dart';
import 'raw_posts_page.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  late final TextEditingController _keywordController;

  @override
  void initState() {
    super.initState();
    final initialKeyword = context.read<SentimentProvider>().currentKeyword;
    _keywordController = TextEditingController(text: initialKeyword);
  }

  @override
  void dispose() {
    _keywordController.dispose();
    super.dispose();
  }

  Future<void> _submitKeyword() async {
    await context.read<SentimentProvider>().fetchDashboard(
          keyword: _keywordController.text,
        );
  }

  @override
  Widget build(BuildContext context) {
    return Consumer2<SentimentProvider, AppLanguageProvider>(
      builder: (context, sentimentProvider, languageProvider, _) {
        final dashboard = sentimentProvider.dashboard;
        final language = languageProvider.language;

        return Scaffold(
          body: DecoratedBox(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFF081120),
                  Color(0xFF0A1830),
                  Color(0xFF06101B),
                ],
              ),
            ),
            child: SafeArea(
              child: RefreshIndicator(
                onRefresh: () => sentimentProvider.fetchDashboard(),
                color: Theme.of(context).colorScheme.primary,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
                  children: [
                    _DashboardHeader(
                      isLoading: sentimentProvider.isLoading,
                      onRefresh: () => sentimentProvider.fetchDashboard(),
                      language: language,
                    ),
                    const SizedBox(height: 20),
                    _KeywordSearchBar(
                      controller: _keywordController,
                      isLoading: sentimentProvider.isLoading,
                      language: language,
                      selectedSources: sentimentProvider.selectedSources,
                      onSubmit: _submitKeyword,
                    ),
                    const SizedBox(height: 16),
                    _CurrentKeywordBanner(
                      keyword: dashboard.keyword,
                      language: language,
                    ),
                    const SizedBox(height: 20),
                    _SummaryBanner(
                      summary: dashboard.summary,
                      language: language,
                    ),
                    const SizedBox(height: 20),
                    _MetricsRow(
                      dashboard: dashboard,
                      language: language,
                    ),
                    const SizedBox(height: 20),
                    _SentimentGauge(
                      score: dashboard.sentimentScore,
                      language: language,
                    ),
                    if (sentimentProvider.errorMessage case final message?) ...[
                      const SizedBox(height: 16),
                      _ErrorBanner(message: message),
                    ],
                    const SizedBox(height: 24),
                    Text(
                      AppStrings.coreControversies(language),
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                    ),
                    const SizedBox(height: 14),
                    if (dashboard.controversyPoints.isEmpty)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 14),
                        child: Text(
                          AppStrings.noControversies(language),
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                color: Colors.white54,
                              ),
                        ),
                      )
                    else
                      ...dashboard.controversyPoints.take(3).map(
                        (point) => Padding(
                          padding: const EdgeInsets.only(bottom: 14),
                          child: _ControversyCard(
                            point: point,
                            language: language,
                          ),
                        ),
                      ),
                    const SizedBox(height: 12),
                    _PostsSection(
                      posts: dashboard.posts,
                      language: language,
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader({
    required this.isLoading,
    required this.onRefresh,
    required this.language,
  });

  final bool isLoading;
  final Future<void> Function() onRefresh;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                AppStrings.dashboardTitle(language),
                style: Theme.of(context).appBarTheme.titleTextStyle,
              ),
              const SizedBox(height: 8),
              Text(
                AppStrings.dashboardSubtitle(language),
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.white70,
                      letterSpacing: 0.2,
                    ),
              ),
            ],
          ),
        ),
        OutlinedButton(
          onPressed: context.read<AppLanguageProvider>().toggleLanguage,
          child: Text(AppStrings.languageToggle(language)),
        ),
        const SizedBox(width: 12),
        FilledButton.tonalIcon(
          onPressed: isLoading ? null : onRefresh,
          icon: isLoading
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.sync_rounded),
          label: Text(
            isLoading
                ? AppStrings.syncing(language)
                : AppStrings.refresh(language),
          ),
        ),
      ],
    );
  }
}

class _KeywordSearchBar extends StatelessWidget {
  const _KeywordSearchBar({
    required this.controller,
    required this.isLoading,
    required this.language,
    required this.selectedSources,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final bool isLoading;
  final AppLanguage language;
  final Set<SourcePlatform> selectedSources;
  final Future<void> Function() onSubmit;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: controller,
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => onSubmit(),
                    decoration: InputDecoration(
                      hintText: AppStrings.searchHint(language),
                      prefixIcon: const Icon(Icons.search_rounded),
                      filled: true,
                      fillColor: Colors.white.withValues(alpha: 0.04),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(18),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    AppStrings.sourceSelector(language),
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    AppStrings.sourceHint(language),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.white60,
                        ),
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: SourcePlatform.values.map((source) {
                      final selected = selectedSources.contains(source);
                      return FilterChip(
                        selected: selected,
                        label: Text(source.displayName),
                        onSelected: (_) {
                          context.read<SentimentProvider>().toggleSource(source);
                        },
                        showCheckmark: true,
                        selectedColor: Colors.cyanAccent.withValues(alpha: 0.18),
                        checkmarkColor: Colors.cyanAccent,
                        labelStyle: Theme.of(context).textTheme.labelLarge?.copyWith(
                              color: selected ? Colors.cyanAccent : Colors.white70,
                              fontWeight: FontWeight.w700,
                            ),
                        backgroundColor: Colors.white.withValues(alpha: 0.04),
                        side: BorderSide(
                          color: selected
                              ? Colors.cyanAccent.withValues(alpha: 0.4)
                              : Colors.white.withValues(alpha: 0.08),
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            FilledButton.icon(
              onPressed: isLoading ? null : onSubmit,
              icon: const Icon(Icons.auto_awesome_rounded),
              label: Text(AppStrings.analyze(language)),
            ),
          ],
        ),
      ),
    );
  }
}

class _CurrentKeywordBanner extends StatelessWidget {
  const _CurrentKeywordBanner({
    required this.keyword,
    required this.language,
  });

  final String keyword;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        _InfoChip(
          label: AppStrings.currentKeyword(language),
          value: keyword,
        ),
        _InfoChip(
          label: AppStrings.retainedCount(language, context.watch<SentimentProvider>().dashboard.retainedCommentCount),
          value: '',
        ),
      ],
    );
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Text(
        value.isEmpty ? label : '$label: $value',
        style: Theme.of(context).textTheme.labelLarge?.copyWith(
              color: Colors.white70,
            ),
      ),
    );
  }
}

class _SummaryBanner extends StatelessWidget {
  const _SummaryBanner({
    required this.summary,
    required this.language,
  });

  final String summary;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        gradient: LinearGradient(
          colors: [
            Colors.cyanAccent.withValues(alpha: 0.15),
            Colors.tealAccent.withValues(alpha: 0.08),
            Colors.transparent,
          ],
        ),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.08),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  AppStrings.executiveSummary(language),
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: Colors.cyanAccent,
                        letterSpacing: 1.1,
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ),
              IconButton(
                tooltip: AppStrings.copy(language),
                onPressed: summary.trim().isEmpty
                    ? null
                    : () => _copyText(
                          context,
                          summary,
                          language: language,
                        ),
                icon: const Icon(
                  Icons.content_copy_rounded,
                  color: Colors.cyanAccent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            summary,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Colors.white,
                  height: 1.5,
                ),
          ),
        ],
      ),
    );
  }
}

class _MetricsRow extends StatelessWidget {
  const _MetricsRow({
    required this.dashboard,
    required this.language,
  });

  final DashboardResponse dashboard;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _MetricCard(
            title: AppStrings.heatIndex(language),
            value: '${dashboard.heatScore}/100',
            accent: const Color(0xFFFF9F43),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: _MetricCard(
            title: AppStrings.sourceCoverage(language),
            value:
                '${dashboard.sourceBreakdown.values.where((count) => count > 0).length}',
            accent: const Color(0xFF2AE6A1),
            footer: dashboard.sourceBreakdown.entries
                .where((entry) => entry.value > 0)
                .map(
                  (entry) => AppStrings.sourceLabel(
                    language,
                    entry.key.toUpperCase(),
                    entry.value,
                  ),
                )
                .join('  '),
          ),
        ),
      ],
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.title,
    required this.value,
    required this.accent,
    this.footer,
  });

  final String title;
  final String value;
  final Color accent;
  final String? footer;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Colors.white70,
                  ),
            ),
            const SizedBox(height: 10),
            Text(
              value,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                  ),
            ),
            if (footer case final text? when text.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                text,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: accent,
                    ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SentimentGauge extends StatelessWidget {
  const _SentimentGauge({
    required this.score,
    required this.language,
  });

  final int score;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    final normalized = score / 100;
    final sentimentLabel = AppStrings.sentimentLabel(language, score);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    AppStrings.sentimentIndex(language),
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                Text(
                  '$score/100',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              sentimentLabel,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white70,
                  ),
            ),
            const SizedBox(height: 20),
            SizedBox(
              height: 180,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  CustomPaint(
                    size: const Size.square(180),
                    painter: _GaugePainter(progress: normalized),
                  ),
                  Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '$score',
                        style:
                            Theme.of(context).textTheme.displaySmall?.copyWith(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w800,
                                ),
                      ),
                      Text(
                        AppStrings.signalStrength(language),
                        style: Theme.of(context).textTheme.labelMedium?.copyWith(
                              color: Colors.white54,
                              letterSpacing: 0.9,
                            ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            _GradientSentimentBar(progress: normalized),
          ],
        ),
      ),
    );
  }
}

class _GradientSentimentBar extends StatelessWidget {
  const _GradientSentimentBar({required this.progress});

  final double progress;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final knobOffset = math.max(0.0, constraints.maxWidth * progress - 10);
        return Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              height: 14,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(999),
                gradient: const LinearGradient(
                  colors: [
                    Color(0xFFFF4D5A),
                    Color(0xFFF5C04A),
                    Color(0xFF2AE6A1),
                  ],
                ),
              ),
            ),
            Positioned(
              left: knobOffset,
              top: -2,
              child: Container(
                width: 18,
                height: 18,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.white,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.white.withValues(alpha: 0.35),
                      blurRadius: 16,
                      spreadRadius: 2,
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _GaugePainter extends CustomPainter {
  const _GaugePainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final strokeWidth = 18.0;
    final rect = Offset.zero & size;
    const startAngle = math.pi;
    const sweepAngle = math.pi;

    final backgroundPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.08)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = strokeWidth;

    final foregroundPaint = Paint()
      ..shader = const LinearGradient(
        colors: [
          Color(0xFFFF4D5A),
          Color(0xFFF5C04A),
          Color(0xFF2AE6A1),
        ],
      ).createShader(rect)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = strokeWidth;

    canvas.drawArc(
      rect.deflate(strokeWidth),
      startAngle,
      sweepAngle,
      false,
      backgroundPaint,
    );
    canvas.drawArc(
      rect.deflate(strokeWidth),
      startAngle,
      sweepAngle * progress,
      false,
      foregroundPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFF6B6B).withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: const Color(0xFFFF6B6B).withValues(alpha: 0.32),
        ),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Color(0xFFFF9B9B)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ControversyCard extends StatelessWidget {
  const _ControversyCard({
    required this.point,
    required this.language,
  });

  final ControversyPoint point;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(28),
      onTap: point.link == null ? null : () => _launchExternal(point.link!),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: Colors.cyanAccent.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.auto_graph_rounded,
                  color: Colors.cyanAccent,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      point.title,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      point.summary,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Colors.white70,
                            height: 1.45,
                          ),
                    ),
                    if (point.link case final link?)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Text(
                          link,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style:
                              Theme.of(context).textTheme.labelMedium?.copyWith(
                                    color: Colors.cyanAccent,
                                  ),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    tooltip: AppStrings.copy(language),
                    onPressed: () => _copyText(
                      context,
                      _formatControversyPoint(point),
                      language: language,
                    ),
                    icon: const Icon(
                      Icons.content_copy_rounded,
                      color: Colors.white54,
                    ),
                  ),
                  Icon(
                    Icons.open_in_new_rounded,
                    color: point.link == null ? Colors.white24 : Colors.white54,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PostsSection extends StatelessWidget {
  const _PostsSection({
    required this.posts,
    required this.language,
  });

  final List<SourcePost> posts;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              AppStrings.rawPosts(language),
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
            ),
            Text(
              AppStrings.postsCount(language, posts.length),
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Colors.white54,
                  ),
            ),
            const SizedBox(width: 12),
            TextButton(
              onPressed: posts.isEmpty
                  ? null
                  : () => _copyText(
                        context,
                        _formatPosts(posts),
                        language: language,
                      ),
              child: Text(AppStrings.copyAll(language)),
            ),
            const SizedBox(width: 8),
            TextButton(
              onPressed: posts.isEmpty
                  ? null
                  : () {
                      Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => RawPostsPage(
                            posts: posts,
                            language: language,
                          ),
                        ),
                      );
                    },
              child: Text(AppStrings.viewAll(language, posts.length)),
            ),
          ],
        ),
        const SizedBox(height: 14),
        if (posts.isEmpty)
          Text(
            AppStrings.noPosts(language),
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white54,
                ),
          )
        else
          ...posts.take(3).map(
            (post) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _PostTile(
                post: post,
                language: language,
              ),
            ),
          ),
      ],
    );
  }
}

class _PostTile extends StatelessWidget {
  const _PostTile({
    required this.post,
    required this.language,
  });

  final SourcePost post;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        title: Text(
          post.title,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Colors.white,
                height: 1.4,
              ),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  _MetaChip(label: post.source.toUpperCase()),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      post.originalLink,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            color: Colors.white60,
                          ),
                    ),
                  ),
                ],
              ),
              if (post.content.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  post.content,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white54,
                        height: 1.4,
                      ),
                ),
              ],
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
                Icons.north_east_rounded,
                color: Colors.cyanAccent,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: Colors.cyanAccent,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.9,
            ),
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

String _formatControversyPoint(ControversyPoint point) {
  final buffer = StringBuffer(point.title.trim());
  if (point.summary.trim().isNotEmpty) {
    buffer.write('\n');
    buffer.write(point.summary.trim());
  }
  if ((point.link ?? '').trim().isNotEmpty) {
    buffer.write('\n');
    buffer.write(point.link!.trim());
  }
  return buffer.toString();
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

String _formatPosts(List<SourcePost> posts) {
  return posts.map(_formatPost).join('\n\n');
}

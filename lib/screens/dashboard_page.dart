import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../l10n/app_strings.dart';
import '../models/sentiment_models.dart';
import '../providers/app_language_provider.dart';
import '../providers/sentiment_provider.dart';
import '../services/local_insight_translator.dart';
import '../widgets/mermaid_mindmap_card.dart';
import 'raw_posts_page.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  late final TextEditingController _keywordController;
  bool _isShowingMonitoringAlert = false;

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
        if (sentimentProvider.hasPendingSentimentAlert &&
            !_isShowingMonitoringAlert) {
          WidgetsBinding.instance.addPostFrameCallback((_) async {
            if (!mounted) {
              return;
            }
            _isShowingMonitoringAlert = true;
            final score = (sentimentProvider.pendingSentimentAlertScore ?? 0).toInt();
            await showDialog<void>(
              context: context,
              builder: (dialogContext) {
                return AlertDialog(
                  title: Text(AppStrings.monitoringAlertTitle(language)),
                  content: Text(
                    AppStrings.monitoringAlertBody(
                      language,
                      sentimentProvider.currentKeyword,
                      score,
                    ),
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.of(dialogContext).pop(),
                      child: const Text('OK'),
                    ),
                  ],
                );
              },
            );
            if (!mounted) {
              return;
            }
            context.read<SentimentProvider>().clearPendingSentimentAlert();
            _isShowingMonitoringAlert = false;
          });
        }

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
                      onToggleLanguage: () async {
                        context.read<AppLanguageProvider>().toggleLanguage();
                      },
                      language: language,
                    ),
                    const SizedBox(height: 20),
                    _KeywordSearchBar(
                      controller: _keywordController,
                      isLoading: sentimentProvider.isLoading,
                      configurationLocked:
                          sentimentProvider.configurationLocked,
                      language: language,
                      selectedSources: sentimentProvider.selectedSources,
                      totalFetchLimit: sentimentProvider.totalFetchLimit,
                      sourceWeights: sentimentProvider.sourceWeights,
                      youtubeMode: sentimentProvider.youtubeMode,
                      outputLanguage: sentimentProvider.outputLanguage,
                      monitoringEnabled: sentimentProvider.monitoringEnabled,
                      monitoringInterval: sentimentProvider.monitoringInterval,
                      monitoringStartedAt:
                          sentimentProvider.monitoringStartedAt,
                      monitoringRemaining:
                          sentimentProvider.monitoringRemaining,
                      monitoringTriggerCount:
                          sentimentProvider.monitoringTriggerCount,
                      onSubmit: _submitKeyword,
                    ),
                    if (sentimentProvider.showLoadingProgress) ...[
                      const SizedBox(height: 16),
                      _LoadingProgressCard(
                        steps: sentimentProvider.loadingSteps,
                        currentStepIndex: sentimentProvider.loadingStepIndex,
                        stages: sentimentProvider.loadingMonitorStages,
                        language: language,
                      ),
                    ],
                    if (sentimentProvider.errorMessage case final message?) ...[
                      const SizedBox(height: 16),
                      _ErrorBanner(
                        message: LocalInsightTranslator.translate(
                          message,
                          language,
                        ),
                      ),
                    ],
                    if (dashboard == null) ...[
                      const SizedBox(height: 18),
                      _InitialStateCard(
                        isLoading: sentimentProvider.isLoading,
                        language: language,
                      ),
                    ] else ...[
                      const SizedBox(height: 16),
                      _CurrentKeywordBanner(
                        keyword: dashboard.keyword,
                        retainedCount: dashboard.retainedCommentCount,
                        language: language,
                      ),
                      const SizedBox(height: 20),
                      _SourceCollectionStatsCard(
                        dashboard: dashboard,
                        language: language,
                      ),
                      const SizedBox(height: 20),
                      _SummaryBanner(
                        summary: dashboard.summary,
                        language: language,
                      ),
                      const SizedBox(height: 20),
                      MermaidMindmapCard(
                        dashboard: dashboard,
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

class _InitialStateCard extends StatelessWidget {
  const _InitialStateCard({
    required this.isLoading,
    required this.language,
  });

  final bool isLoading;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (isLoading)
              const Padding(
                padding: EdgeInsets.only(bottom: 16),
                child: SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2.4),
                ),
              ),
            Text(
              isLoading
                  ? AppStrings.syncing(language)
                  : AppStrings.inputPromptTitle(language),
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 10),
            Text(
              isLoading
                  ? AppStrings.loadingBody(language)
                  : AppStrings.inputPromptBody(language),
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white70,
                    height: 1.5,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader({
    required this.isLoading,
    required this.onRefresh,
    required this.onToggleLanguage,
    required this.language,
  });

  final bool isLoading;
  final Future<void> Function() onRefresh;
  final Future<void> Function() onToggleLanguage;
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
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              AppStrings.interfaceLanguage(language),
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Colors.white60,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 6),
            OutlinedButton(
              onPressed: isLoading ? null : onToggleLanguage,
              child: Text(AppStrings.languageToggle(language)),
            ),
          ],
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
    required this.configurationLocked,
    required this.language,
    required this.selectedSources,
    required this.totalFetchLimit,
    required this.sourceWeights,
    required this.youtubeMode,
    required this.outputLanguage,
    required this.monitoringEnabled,
    required this.monitoringInterval,
    required this.monitoringStartedAt,
    required this.monitoringRemaining,
    required this.monitoringTriggerCount,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final bool isLoading;
  final bool configurationLocked;
  final AppLanguage language;
  final Set<SourcePlatform> selectedSources;
  final int totalFetchLimit;
  final Map<SourcePlatform, SourceWeightTier> sourceWeights;
  final YouTubeCollectionMode youtubeMode;
  final AppLanguage outputLanguage;
  final bool monitoringEnabled;
  final Duration monitoringInterval;
  final DateTime? monitoringStartedAt;
  final Duration? monitoringRemaining;
  final int monitoringTriggerCount;
  final Future<void> Function() onSubmit;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: controller,
              textInputAction: TextInputAction.search,
              enabled: !configurationLocked,
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
                final isDisabled = source == SourcePlatform.x;
                return FilterChip(
                  selected: selected,
                  label: Text(
                    isDisabled
                        ? '${source.displayName} - ${AppStrings.sourceUnavailable(language)}'
                        : source.displayName,
                  ),
                  onSelected: (configurationLocked || isDisabled)
                      ? null
                      : (_) {
                          context.read<SentimentProvider>().toggleSource(source);
                        },
                  showCheckmark: true,
                  selectedColor: Colors.cyanAccent.withValues(alpha: 0.18),
                  checkmarkColor: Colors.cyanAccent,
                  labelStyle: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: isDisabled
                            ? Colors.white38
                            : selected
                                ? Colors.cyanAccent
                                : Colors.white70,
                        fontWeight: FontWeight.w700,
                      ),
                  backgroundColor: isDisabled
                      ? Colors.white.withValues(alpha: 0.02)
                      : Colors.white.withValues(alpha: 0.04),
                  side: BorderSide(
                    color: isDisabled
                        ? Colors.white.withValues(alpha: 0.05)
                        : selected
                            ? Colors.cyanAccent.withValues(alpha: 0.4)
                            : Colors.white.withValues(alpha: 0.08),
                  ),
                );
              }).toList(),
            ),
            if (selectedSources.contains(SourcePlatform.youtube)) ...[
              const SizedBox(height: 18),
              Text(
                AppStrings.youtubeMode(language),
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                AppStrings.youtubeModeHint(language),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.white60,
                    ),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  ChoiceChip(
                    selected: youtubeMode == YouTubeCollectionMode.officialApi,
                    label: Text(AppStrings.youtubeModeOfficial(language)),
                    onSelected: configurationLocked
                        ? null
                        : (_) {
                            context.read<SentimentProvider>().setYouTubeMode(
                                  YouTubeCollectionMode.officialApi,
                                );
                          },
                  ),
                  ChoiceChip(
                    selected: youtubeMode == YouTubeCollectionMode.headlessBrowser,
                    label: Text(AppStrings.youtubeModeBrowser(language)),
                    onSelected: configurationLocked
                        ? null
                        : (_) {
                            context.read<SentimentProvider>().setYouTubeMode(
                                  YouTubeCollectionMode.headlessBrowser,
                                );
                          },
                  ),
                ],
              ),
            ],
            const SizedBox(height: 18),
            Text(
              '${AppStrings.totalFetchLimit(language)}: $totalFetchLimit',
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              AppStrings.totalFetchLimitHint(language),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white60,
                  ),
            ),
            Slider(
              value: totalFetchLimit.toDouble(),
              min: selectedSources.length.toDouble(),
              max: 50,
              divisions: 50 - selectedSources.length,
              label: '$totalFetchLimit',
              onChanged: configurationLocked
                  ? null
                  : (value) {
                      context.read<SentimentProvider>().setTotalFetchLimit(
                            value.round(),
                          );
                    },
            ),
            const SizedBox(height: 8),
            Text(
              AppStrings.sourceWeight(language),
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 10),
            ...selectedSources.map(
              (source) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _SourceWeightRow(
                  source: source,
                  selectedTier: sourceWeights[source] ?? SourceWeightTier.medium,
                  language: language,
                  isLocked: configurationLocked,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              AppStrings.outputLanguage(language),
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              AppStrings.outputLanguageHint(language),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white60,
                  ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ChoiceChip(
                  selected: outputLanguage == AppLanguage.english,
                  label: Text(AppStrings.languageEnglish(language)),
                  onSelected: configurationLocked
                      ? null
                      : (_) {
                          context.read<SentimentProvider>().setOutputLanguage(
                                AppLanguage.english,
                              );
                        },
                ),
                ChoiceChip(
                  selected: outputLanguage == AppLanguage.chinese,
                  label: Text(AppStrings.languageChinese(language)),
                  onSelected: configurationLocked
                      ? null
                      : (_) {
                          context.read<SentimentProvider>().setOutputLanguage(
                                AppLanguage.chinese,
                              );
                        },
                ),
              ],
            ),
            const SizedBox(height: 18),
            Text(
              AppStrings.monitoring(language),
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              monitoringEnabled
                  ? AppStrings.monitoringLocked(language)
                  : AppStrings.monitoringHint(language),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white60,
                  ),
            ),
            const SizedBox(height: 12),
            if (monitoringEnabled) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  _InfoChip(
                    label: _monitoringLabelStartedAt(language),
                    value: _formatDateTimeForMonitoring(
                      monitoringStartedAt,
                      language,
                    ),
                  ),
                  _InfoChip(
                    label: _monitoringLabelCountdown(language),
                    value: _formatMonitoringCountdown(
                      monitoringRemaining,
                      language,
                    ),
                  ),
                  _InfoChip(
                    label: _monitoringLabelTriggerCount(language),
                    value: monitoringTriggerCount.toString(),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<Duration>(
                    value: monitoringInterval,
                    decoration: InputDecoration(
                      labelText: AppStrings.monitoringInterval(language),
                    ),
                    items: SentimentProvider.monitoringIntervals.map((duration) {
                      return DropdownMenuItem<Duration>(
                        value: duration,
                        child: Text(
                          _formatMonitoringInterval(duration, language),
                        ),
                      );
                    }).toList(),
                    onChanged: configurationLocked
                        ? null
                        : (value) {
                            if (value == null) {
                              return;
                            }
                            context.read<SentimentProvider>().setMonitoringInterval(
                                  value,
                                );
                          },
                  ),
                ),
                const SizedBox(width: 12),
                FilledButton.tonalIcon(
                  onPressed: isLoading
                      ? null
                      : () {
                          context.read<SentimentProvider>().toggleMonitoring(
                                keyword: controller.text,
                              );
                        },
                  icon: Icon(
                    monitoringEnabled
                        ? Icons.pause_circle_outline_rounded
                        : Icons.notifications_active_outlined,
                  ),
                  label: Text(
                    monitoringEnabled
                        ? AppStrings.monitoringStop(language)
                        : AppStrings.monitoringStart(language),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: isLoading ? null : onSubmit,
                icon: const Icon(Icons.auto_awesome_rounded),
                label: Text(AppStrings.analyze(language)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/*
/*
String _formatMonitoringInterval(Duration duration, AppLanguage language) {
  if (duration.inDays >= 1) {
    final days = duration.inDays;
    return language == AppLanguage.chinese ? '$days 天' : '$days day${days > 1 ? 's' : ''}';
  }
  if (duration.inHours >= 1) {
    final hours = duration.inHours;
    return language == AppLanguage.chinese ? '$hours 小时' : '$hours hour${hours > 1 ? 's' : ''}';
  }
  final minutes = duration.inMinutes;
  return language == AppLanguage.chinese ? '$minutes 分钟' : '$minutes minutes';
}
*/

String _formatMonitoringInterval(Duration duration, AppLanguage language) {
  if (duration.inDays >= 1) {
    final days = duration.inDays;
    return language == AppLanguage.chinese
        ? '$days 天'
        : '$days day${days > 1 ? 's' : ''}';
  }
  if (duration.inHours >= 1) {
    final hours = duration.inHours;
    return language == AppLanguage.chinese
        ? '$hours 小时'
        : '$hours hour${hours > 1 ? 's' : ''}';
  }
  final minutes = duration.inMinutes;
  return language == AppLanguage.chinese ? '$minutes 分钟' : '$minutes minutes';
}
*/

String _formatMonitoringInterval(Duration duration, AppLanguage language) {
  if (duration.inDays >= 1) {
    final days = duration.inDays;
    return language == AppLanguage.chinese
        ? '$days day'
        : '$days day${days > 1 ? 's' : ''}';
  }
  if (duration.inHours >= 1) {
    final hours = duration.inHours;
    return language == AppLanguage.chinese
        ? '$hours hour'
        : '$hours hour${hours > 1 ? 's' : ''}';
  }
  final minutes = duration.inMinutes;
  return '$minutes minutes';
}

class _LoadingProgressCard extends StatelessWidget {
  const _LoadingProgressCard({
    required this.steps,
    required this.currentStepIndex,
    required this.stages,
    required this.language,
  });

  final List<String> steps;
  final int currentStepIndex;
  final List<MonitorStage> stages;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2.2),
                ),
                const SizedBox(width: 12),
                Text(
                  AppStrings.liveProgress(language),
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              AppStrings.liveProgressHint(language),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white60,
                    height: 1.4,
                  ),
            ),
            const SizedBox(height: 14),
            ...steps.asMap().entries.map((entry) {
              final index = entry.key;
              final step = entry.value;
              final isActive = index == currentStepIndex;
              final isDone = index < currentStepIndex;
              final icon = isDone
                  ? Icons.check_circle_rounded
                  : isActive
                      ? Icons.radio_button_checked_rounded
                      : Icons.radio_button_off_rounded;
              final color = isDone
                  ? Colors.greenAccent
                  : isActive
                      ? Colors.cyanAccent
                      : Colors.white30;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(icon, size: 18, color: color),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        LocalInsightTranslator.translate(step, language),
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: isActive ? Colors.white : Colors.white70,
                              fontWeight: isActive ? FontWeight.w700 : FontWeight.w400,
                            ),
                      ),
                    ),
                  ],
                ),
              );
            }),
            if (stages.isNotEmpty && currentStepIndex == 0) ...[
              const SizedBox(height: 6),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.04),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.08),
                  ),
                ),
                child: Text(
                  LocalInsightTranslator.translate(
                    _monitorStageDetail(stages.last),
                    language,
                  ),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white70,
                        height: 1.4,
                      ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _BackendTimelineCard extends StatelessWidget {
  const _BackendTimelineCard({
    required this.stages,
    required this.language,
  });

  final List<MonitorStage> stages;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    if (stages.isEmpty) {
      return const SizedBox.shrink();
    }

    final visibleStages = stages.length > 8 ? stages.sublist(stages.length - 8) : stages;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              AppStrings.backendTimeline(language),
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              AppStrings.backendTimelineHint(language),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white60,
                    height: 1.4,
                  ),
            ),
            const SizedBox(height: 14),
            ...visibleStages.map(
              (stage) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.bolt_rounded,
                      size: 18,
                      color: Colors.cyanAccent,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            LocalInsightTranslator.translate(
                              _monitorStageLabel(stage),
                              language,
                            ),
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            LocalInsightTranslator.translate(
                              _monitorStageDetail(stage),
                              language,
                            ),
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Colors.white60,
                                ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _monitorStageLabel(MonitorStage stage) {
  switch (stage.stage) {
    case 'request_received':
      return 'Request received';
    case 'storage_initialized':
      return 'Database initialized';
    case 'run_created':
      return 'Collection run created';
    case 'sources_selected':
      return 'Sources selected';
    case 'source_limits_resolved':
      return 'Fetch limits resolved';
    case 'collector_plan_ready':
      return 'Collector plan ready';
    case 'source_collection_started':
      return 'Source collection started';
    case 'record_persisted':
      return 'Record saved to database';
    case 'source_collection_finished':
      return 'Source collection finished';
    case 'collection_completed':
      return 'Collection completed';
    case 'database_loading_started':
      return 'Reading records from database';
    case 'records_stored':
      return 'Records loaded';
    case 'llm_analysis_started':
      return 'Model analysis started';
    case 'llm_analysis_completed':
      return 'Model analysis completed';
    case 'score_computation_started':
      return 'Metric computation started';
    case 'score_computation_completed':
      return 'Metric computation completed';
    case 'run_finalization_started':
      return 'Finalizing run';
    case 'response_ready':
      return 'Dashboard ready';
    case 'failed':
      return 'Pipeline failed';
    default:
      return stage.stage.replaceAll('_', ' ');
  }
}

String _monitorStageDetail(MonitorStage stage) {
  final source = '${stage.details['source'] ?? ''}'.trim();
  final rawCount = '${stage.details['raw_record_count'] ?? ''}'.trim();
  final storedCount = '${stage.details['stored_record_count'] ?? ''}'.trim();
  final runId = '${stage.details['run_id'] ?? ''}'.trim();
  switch (stage.stage) {
    case 'run_created':
      return runId.isEmpty ? 'A new backend run was created.' : 'Run ID: $runId';
    case 'source_collection_started':
      return source.isEmpty ? 'Backend started collecting one source.' : 'Source: $source';
    case 'source_collection_finished':
      if (source.isNotEmpty && rawCount.isNotEmpty) {
        return 'Source: $source, raw records: $rawCount';
      }
      return 'Backend finished one source.';
    case 'record_persisted':
      if (source.isNotEmpty && storedCount.isNotEmpty) {
        return 'Source: $source, stored count: $storedCount';
      }
      return 'One cleaned record was persisted.';
    case 'records_stored':
      return storedCount.isEmpty
          ? 'Current run records were loaded from database.'
          : 'Stored records: $storedCount';
    case 'llm_analysis_completed':
      final sentiment = '${stage.details['sentiment_score'] ?? ''}'.trim();
      return sentiment.isEmpty ? 'The model returned structured analysis.' : 'Sentiment score: $sentiment';
    case 'llm_analysis_started':
      final model = '${stage.details['llm_model'] ?? ''}'.trim();
      return model.isEmpty ? 'Collected records were sent to the model.' : 'Model: $model';
    case 'score_computation_completed':
      final heat = '${stage.details['heat_score'] ?? ''}'.trim();
      return heat.isEmpty ? 'Heat and source metrics were computed.' : 'Heat score: $heat';
    case 'failed':
      final error = '${stage.details['error'] ?? ''}'.trim();
      return error.isEmpty ? 'The backend run failed.' : error;
    default:
      return 'Completed.';
  }
}

class _SourceWeightRow extends StatelessWidget {
  const _SourceWeightRow({
    required this.source,
    required this.selectedTier,
    required this.language,
    required this.isLocked,
  });

  final SourcePlatform source;
  final SourceWeightTier selectedTier;
  final AppLanguage language;
  final bool isLocked;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          source.displayName,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: Colors.white70,
                fontWeight: FontWeight.w700,
              ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: SourceWeightTier.values.map((tier) {
            final label = switch (tier) {
              SourceWeightTier.low => AppStrings.weightLow(language),
              SourceWeightTier.medium => AppStrings.weightMedium(language),
              SourceWeightTier.high => AppStrings.weightHigh(language),
            };
            final selected = tier == selectedTier;
            return ChoiceChip(
              selected: selected,
              label: Text(label),
              onSelected: isLocked
                  ? null
                  : (_) {
                      context.read<SentimentProvider>().setSourceWeight(
                            source,
                            tier,
                          );
                    },
              selectedColor: Colors.tealAccent.withValues(alpha: 0.18),
              labelStyle: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: selected ? Colors.tealAccent : Colors.white70,
                    fontWeight: FontWeight.w700,
                  ),
              backgroundColor: Colors.white.withValues(alpha: 0.04),
              side: BorderSide(
                color: selected
                    ? Colors.tealAccent.withValues(alpha: 0.38)
                    : Colors.white.withValues(alpha: 0.08),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }
}

/*
/*
String _monitoringLabelStartedAt(AppLanguage language) {
  return language == AppLanguage.chinese ? '开启时间' : 'Started At';
}

String _monitoringLabelCountdown(AppLanguage language) {
  return language == AppLanguage.chinese ? '触发倒计时' : 'Countdown';
}

String _monitoringLabelTriggerCount(AppLanguage language) {
  return language == AppLanguage.chinese ? '累计触发次数' : 'Trigger Count';
}

String _formatDateTimeForMonitoring(DateTime? value, AppLanguage language) {
  if (value == null) {
    return language == AppLanguage.chinese ? '未开始' : 'Not started';
  }
  final local = value.toLocal();
  final month = local.month.toString().padLeft(2, '0');
  final day = local.day.toString().padLeft(2, '0');
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  final second = local.second.toString().padLeft(2, '0');
  return '${local.year}-$month-$day $hour:$minute:$second';
}

String _formatMonitoringCountdown(Duration? duration, AppLanguage language) {
  if (duration == null) {
    return language == AppLanguage.chinese ? '等待中' : 'Waiting';
  }
  final totalSeconds = duration.inSeconds.clamp(0, 359999);
  final hours = (totalSeconds ~/ 3600).toString().padLeft(2, '0');
  final minutes = ((totalSeconds % 3600) ~/ 60).toString().padLeft(2, '0');
  final seconds = (totalSeconds % 60).toString().padLeft(2, '0');
  return '$hours:$minutes:$seconds';
}
*/

String _monitoringLabelStartedAt(AppLanguage language) {
  return language == AppLanguage.chinese ? '开启时间' : 'Started At';
}

String _monitoringLabelCountdown(AppLanguage language) {
  return language == AppLanguage.chinese ? '触发倒计时' : 'Countdown';
}

String _monitoringLabelTriggerCount(AppLanguage language) {
  return language == AppLanguage.chinese ? '累计触发次数' : 'Trigger Count';
}

String _formatDateTimeForMonitoring(DateTime? value, AppLanguage language) {
  if (value == null) {
    return language == AppLanguage.chinese ? '未开始' : 'Not started';
  }
  final local = value.toLocal();
  final month = local.month.toString().padLeft(2, '0');
  final day = local.day.toString().padLeft(2, '0');
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  final second = local.second.toString().padLeft(2, '0');
  return '${local.year}-$month-$day $hour:$minute:$second';
}

String _formatMonitoringCountdown(Duration? duration, AppLanguage language) {
  if (duration == null) {
    return language == AppLanguage.chinese ? '等待中' : 'Waiting';
  }
  final totalSeconds = duration.inSeconds.clamp(0, 359999) as int;
  final hours = (totalSeconds ~/ 3600).toString().padLeft(2, '0');
  final minutes = ((totalSeconds % 3600) ~/ 60).toString().padLeft(2, '0');
  final seconds = (totalSeconds % 60).toString().padLeft(2, '0');
  return '$hours:$minutes:$seconds';
}
*/

String _monitoringLabelStartedAt(AppLanguage language) {
  return language == AppLanguage.chinese ? 'Started At' : 'Started At';
}

String _monitoringLabelCountdown(AppLanguage language) {
  return language == AppLanguage.chinese ? 'Countdown' : 'Countdown';
}

String _monitoringLabelTriggerCount(AppLanguage language) {
  return language == AppLanguage.chinese ? 'Trigger Count' : 'Trigger Count';
}

String _formatDateTimeForMonitoring(DateTime? value, AppLanguage language) {
  if (value == null) {
    return language == AppLanguage.chinese ? 'Not started' : 'Not started';
  }
  final local = value.toLocal();
  final month = local.month.toString().padLeft(2, '0');
  final day = local.day.toString().padLeft(2, '0');
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  final second = local.second.toString().padLeft(2, '0');
  return '${local.year}-$month-$day $hour:$minute:$second';
}

String _formatMonitoringCountdown(Duration? duration, AppLanguage language) {
  if (duration == null) {
    return 'Waiting';
  }
  final totalSeconds = duration.inSeconds.clamp(0, 359999) as int;
  final hours = (totalSeconds ~/ 3600).toString().padLeft(2, '0');
  final minutes = ((totalSeconds % 3600) ~/ 60).toString().padLeft(2, '0');
  final seconds = (totalSeconds % 60).toString().padLeft(2, '0');
  return '$hours:$minutes:$seconds';
}

class _CurrentKeywordBanner extends StatelessWidget {
  const _CurrentKeywordBanner({
    required this.keyword,
    required this.retainedCount,
    required this.language,
  });

  final String keyword;
  final int retainedCount;
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
          label: AppStrings.retainedCount(language, retainedCount),
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

class _SourceCollectionStatsCard extends StatelessWidget {
  const _SourceCollectionStatsCard({
    required this.dashboard,
    required this.language,
  });

  final DashboardResponse dashboard;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    final sources = <String>{
      ...dashboard.sourceLimits.keys,
      ...dashboard.rawCountBySource.keys,
      ...dashboard.retainedCountBySource.keys,
      ...dashboard.discardedCountBySource.keys,
      ...dashboard.sourceBreakdown.keys,
    }.toList()
      ..sort();

    if (sources.isEmpty) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              language == AppLanguage.chinese
                  ? '平台抓取统计'
                  : 'Source Collection Stats',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              language == AppLanguage.chinese
                  ? '显示每个平台分配数量、实际抓取数量、清理掉的数量、最终保留数量。'
                  : 'Allocated, fetched, discarded, and retained counts for each source.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white70,
                  ),
            ),
            const SizedBox(height: 18),
            ...sources.map(
              (source) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _SourceCollectionStatRow(
                  source: source,
                  allocated: dashboard.sourceLimits[source] ?? 0,
                  fetched: dashboard.rawCountBySource[source] ?? 0,
                  discarded: dashboard.discardedCountBySource[source] ?? 0,
                  retained: dashboard.retainedCountBySource[source] ??
                      dashboard.sourceBreakdown[source] ??
                      0,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SourceCollectionStatRow extends StatelessWidget {
  const _SourceCollectionStatRow({
    required this.source,
    required this.allocated,
    required this.fetched,
    required this.discarded,
    required this.retained,
  });

  final String source;
  final int allocated;
  final int fetched;
  final int discarded;
  final int retained;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            source.toUpperCase(),
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.8,
                ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              _InfoChip(label: 'Allocated', value: allocated.toString()),
              _InfoChip(label: 'Fetched', value: fetched.toString()),
              _InfoChip(label: 'Discarded', value: discarded.toString()),
              _InfoChip(label: 'Retained', value: retained.toString()),
            ],
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
    return Card(
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
                ],
              ),
            ),
            const SizedBox(width: 12),
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
          ],
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
